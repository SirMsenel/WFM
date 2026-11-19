"""Ajanda, statü geçmişi, izin kapsamı ve üçüncü faz planlama kuralları."""
import copy,unittest
from datetime import timedelta
from unittest.mock import patch
import pandas as pd
from test_phase7 import Base
from test_planning import demand,row,emp,DAY,rules
from ortak.calisma_alani_deposu import save_keys,connect,dumps,loads
from ortak.statuler import meal_plan,defaults
from ortak.mola_servisi import init as init_breaks,records
from ortak.statu_degisimleri import submit,decide,requests

FUTURE=(pd.Timestamp.now(tz='Europe/Istanbul').tz_localize(None)+pd.Timedelta(days=2)).normalize().date()

class StatusRulesTests(Base):
 def plan(self,group='fulltime'):
  self.s['status_rules']=dict(defaults(),enabled=True,automatic=True,shrinkage_included=True,coaching_by_leader=True);coverage=demand(slots=range(1,49));coverage['İhtiyaç']=2;coverage['Atanan']=3;coverage['Eksik']=0;coverage['Fazla']=1
  return meal_plan(self.s,[row(start='08:00',end='17:00')],coverage,[emp(group=group)])
 def test_automatic_breaks_skip_first_and_last_hour(self):
  items,_,__=self.plan();rest=[x for x in items if x['kind']=='Mola'];self.assertTrue(rest)
  for r in rest:self.assertGreaterEqual(pd.Timestamp(r['start']).hour,9);self.assertLessEqual(pd.Timestamp(r['end']),pd.Timestamp(DAY)+pd.Timedelta(hours=16))
 def test_leader_mode_does_not_auto_assign_coaching(self):
  items,_,__=self.plan();self.assertFalse(any(x['kind']=='Koçluk' for x in items))
 def test_meal_none_skips_minimum_rule_and_meal(self):
  self.plan();self.s['status_rules']['groups']['fulltime'].update(meal_disabled=True,min_shift_hours=0,meal_minutes=0);coverage=demand(slots=range(1,49));coverage['İhtiyaç']=0;coverage['Atanan']=3;coverage['Eksik']=0;coverage['Fazla']=3;items,_,__=meal_plan(self.s,[row()],coverage,[emp()]);self.assertFalse(any(x['kind']=='Yemek' for x in items))
 def test_meal_weekday_override_changes_duration(self):
  self.plan();self.s['status_rules']['groups']['fulltime']['meal_day_overrides']=[{'weekdays':[DAY.weekday()],'minutes':60}];coverage=demand(slots=range(1,49));coverage['İhtiyaç']=0;coverage['Atanan']=3;coverage['Eksik']=0;coverage['Fazla']=3;items,_,__=meal_plan(self.s,[row()],coverage,[emp()]);meal=next(x for x in items if x['kind']=='Yemek');self.assertEqual((pd.Timestamp(meal['end'])-pd.Timestamp(meal['start'])).total_seconds(),3600)
 def test_friday_male_rule_enforced_by_engine(self):
  from modules.vardiya_plani.vardiya_motoru import generate_plan
  friday=DAY+timedelta(days=(4-DAY.weekday())%7);r=rules();r['friday']={'block_men_midday':True};person=dict(emp(),gender='Erkek');fixed=dict(row(day=friday),start='08:00',end='17:00');df=demand().assign(Tarih=friday);out=generate_plan([person],df,r,list(r['work_type']),friday,friday,fixed=[fixed],auto_fill=False);self.assertTrue(any('Cuma' in x['Sorun'] for x in out['issues']))

class HistoryTests(Base):
 def test_shrinkage_unions_overlapping_status_intervals(self):
  from ortak.statu_gecmisi import ingest,suggested_shrinkage
  self.s['published_shift_plan']=[row(day=FUTURE,start='08:00',end='09:00')];save_keys(self.s);ingest(self.s,[{'id':'a','employee_id':'1','start':str(FUTURE)+' 08:15','end':str(FUTURE)+' 08:45','kind':'Mola'},{'id':'b','employee_id':'1','start':str(FUTURE)+' 08:30','end':str(FUTURE)+' 09:00','kind':'Yemek'}]);table,total,synthetic=suggested_shrinkage(self.s,FUTURE,FUTURE);self.assertAlmostEqual(total,75);self.assertFalse(synthetic)
 def test_history_ingest_requires_planning(self):
  from ortak.statu_gecmisi import ingest
  self.s['profile']={'position':'agent','username':'u1'}
  with self.assertRaises(ValueError):ingest(self.s,[])

class SwapTests(Base):
 def setUp(self):
  super().setUp();self.s['published_shift_plan']=[row('1',day=FUTURE),row('2',day=FUTURE)];save_keys(self.s);init_breaks(self.s['workspace_db_path'])
  with connect(self.s['workspace_db_path']) as db:
   for i,start in [('1','12:00'),('2','13:00')]:
    a=pd.Timestamp(str(FUTURE)+' '+start);p={'employee_id':i,'date':str(FUTURE),'kind':'Yemek','start':str(a),'end':str(a+pd.Timedelta(minutes=30)),'status':'Planlı'};db.execute('INSERT INTO planned_breaks VALUES(?,?,?)',('status'+i,'pub',dumps(p)))
  self.s['profile']={'position':'agent','username':'u1','employee_id':'1','team_lead':'Lead'}
 def test_peer_then_leader_approval_atomically_swaps_times(self):
  ident=submit(self.s,'status1','status2','Karşılıklı değişim');item=requests(self.s)[0]
  with self.assertRaises(ValueError):decide(self.s,item,True)
  self.s['profile']={'position':'agent','username':'u2','employee_id':'2','team_lead':'Lead'};decide(self.s,requests(self.s)[0],True);self.s['profile']={'position':'tl','username':'lead','full_name':'Lead'};self.assertEqual(decide(self.s,requests(self.s)[0],True),'Uygulandı');new={r['id']:r for r in records(self.s)};self.assertIn('13:00',new['status1']['start']);self.assertIn('12:00',new['status2']['start'])
 def test_different_groups_cannot_swap(self):
  from ortak.statu_degisimleri import validate
  people={'1':dict(emp('1'),team_lead='Lead'),'2':dict(emp('2',group='akademi'),team_lead='Lead')};a,b=records(self.s)
  with self.assertRaisesRegex(ValueError,'grup'):validate(self.s,a,b,people,[a,b])
 def test_stale_request_cannot_overwrite_updated_status(self):
  submit(self.s,'status1','status2','Talep');self.s['profile']={'position':'agent','username':'u2','employee_id':'2'};decide(self.s,requests(self.s)[0],True)
  with connect(self.s['workspace_db_path']) as db:p=loads(db.execute("SELECT payload FROM planned_breaks WHERE id='status1'").fetchone()[0]);p['start']=str(FUTURE)+' 11:00:00';db.execute("UPDATE planned_breaks SET payload=? WHERE id='status1'",(dumps(p),))
  self.s['profile']={'position':'tl','username':'lead','full_name':'Lead'}
  with self.assertRaisesRegex(ValueError,'değişmiş'):decide(self.s,requests(self.s)[0],True)

class AgendaTests(Base):
 def setUp(self):
  super().setUp();self.s['published_shift_plan']=[row('1',day=FUTURE),row('2',day=FUTURE)];self.s['sp_staffing_result_df']=demand(slots=range(1,49),count=0).assign(Tarih=FUTURE);self.s['profile']={'position':'tl','username':'lead','full_name':'Lead','employee_id':'99'};save_keys(self.s)
 def test_meeting_requires_leader_work_and_staff_availability(self):
  from ortak.ajanda_servisi import add_work,add_coaching
  a=pd.Timestamp(FUTURE)+pd.Timedelta(hours=12)
  with self.assertRaisesRegex(ValueError,'ajandana'):add_coaching(self.s,'1',a)
  add_work(self.s,pd.Timestamp(FUTURE)+pd.Timedelta(hours=8),pd.Timestamp(FUTURE)+pd.Timedelta(hours=17));ident=add_coaching(self.s,'1',a);self.assertTrue(any(x['id']==ident for x in records(self.s)))
  with self.assertRaises(ValueError):add_coaching(self.s,'2',a)
 def test_leader_cannot_assign_other_team(self):
  from ortak.ajanda_servisi import add_coaching
  self.s['profile']['full_name']='Other Lead'
  with self.assertRaises(ValueError):add_coaching(self.s,'1',pd.Timestamp(FUTURE)+pd.Timedelta(hours=12))

class ScenarioAndScopeTests(Base):
 def test_scenario_spread_and_target_sl_change_requirements(self):
  from ortak.senaryolar import simulate
  history=pd.DataFrame({'tarih':pd.date_range('2025-11-01',periods=365),'cagri_sayisi':[5000.]*365});a,_=simulate(history,'2026-12-01',3,200,target_sl=.8);b,_=simulate(history,'2026-12-01',3,200,target_sl=.95);self.assertEqual(len(a),9);self.assertGreaterEqual(b['Gerekli personel'].sum(),a['Gerekli personel'].sum());self.assertGreater(a.loc[a.Senaryo=='Kötü','Çağrı tahmini'].sum(),a.loc[a.Senaryo=='İyi','Çağrı tahmini'].sum())
 def test_language_demand_does_not_replace_common_need(self):
  from ortak.plan_ihtiyaci import demand as active
  base=self.s['sp_staffing_result_df'];self.s['language_demands']={'en':base.assign(**{'Planlanan Agent':1})};self.s['planning_demand_language']='en';self.s['planning_languages']={'tr':False,'en':True,'ar':False};self.assertEqual(active(self.s)['Planlanan Agent'].iloc[0],1);self.assertIs(self.s['sp_staffing_result_df'],base)
 def test_published_period_guard_respects_language_scope(self):
  from ortak.donem_uyarisi import existing_range
  self.s['published_shift_plan']=[dict(row(day=FUTURE),language='tr')];self.s['planning_languages']={'tr':False,'en':True};self.assertFalse(existing_range(self.s,FUTURE,FUTURE));self.s['planning_languages']['tr']=True;self.assertTrue(existing_range(self.s,FUTURE,FUTURE))

class PublicationAndForecastTests(Base):
 def test_direct_cell_change_replans_statuses_and_notifies_person(self):
  from ortak.vardiya_degisimleri import apply_changes
  from ortak.bildirimler import items
  self.s['published_shift_plan']=[dict(row('1',day=FUTURE),publication_id='pub'),dict(row('2',day=FUTURE),publication_id='pub')];self.s['sp_staffing_result_df']=demand(slots=range(1,49),count=0).assign(Tarih=FUTURE);self.s['status_rules']=dict(defaults(),enabled=True,automatic=True,shrinkage_included=True,coaching_by_leader=True);save_keys(self.s);init_breaks(self.s['workspace_db_path'])
  with connect(self.s['workspace_db_path']) as db:db.execute('INSERT INTO planned_breaks VALUES(?,?,?)',('old','pub',dumps({'employee_id':'1','date':str(FUTURE),'kind':'Yemek','start':str(FUTURE)+' 12:00:00','end':str(FUTURE)+' 12:30:00','status':'Planlı'})))
  change=dict(self.s['published_shift_plan'][0],start='09:00',end='18:00');apply_changes(self.s,[change],'Planlama düzeltmesi','Günlük plan düzeltmesi');updated=[x for x in records(self.s) if x['employee_id']=='1'];self.assertTrue(updated);self.assertFalse(any(x['id']=='old' for x in updated));self.assertTrue(all(pd.Timestamp(x['start'])>=pd.Timestamp(FUTURE)+pd.Timedelta(hours=9) and pd.Timestamp(x['end'])<=pd.Timestamp(FUTURE)+pd.Timedelta(hours=18) for x in updated));self.s['profile']={'username':'u1','employee_id':'1','position':'agent'};self.assertTrue(any(x['Konu']=='Vardiya değişimi' for x in items(self.s)))
 def test_direct_edit_requires_planning_role(self):
  from ortak.vardiya_degisimleri import validate_changes
  self.s['profile']={'position':'tl','username':'lead','full_name':'Lead'}
  with self.assertRaises(ValueError):validate_changes(self.s,[],'Planlama düzeltmesi','Test')
 def test_forecast_sl_uses_forecast_aht_not_realized_aht(self):
  from ortak.tahmin_kayit_servisi import capture_forecast,ingest_actuals,compare
  from ortak.canli_metrikler import actual_metrics
  from test_round4 import profile_frame
  fc=pd.DataFrame({'tarih':[pd.Timestamp(DAY)],'y_pred':[1920.]});self.s['staffing_parameters']={'aht':300,'target_sl':.8,'target_time':20,'occ_target':.85};ident=capture_forecast(self.s,fc,profile_frame());ingest_actuals(pd.DataFrame({'tarih':[str(DAY)],'slot':[17],'cagri_sayisi':[50],'aht_sec':[600],'answered':[45],'answered_target':[35]}),self.s['workspace_db_path']);a=actual_metrics(self.s,compare(ident,self.s['workspace_db_path']))
  ingest_actuals(pd.DataFrame({'tarih':[str(DAY)],'slot':[17],'cagri_sayisi':[50],'aht_sec':[100],'answered':[45],'answered_target':[35]}),self.s['workspace_db_path']);b=actual_metrics(self.s,compare(ident,self.s['workspace_db_path']));self.assertEqual(a.loc[a.slot==17,'Tahmini SL (%)'].iloc[0],b.loc[b.slot==17,'Tahmini SL (%)'].iloc[0])
 def test_forecast_archive_keeps_erlang_parameters(self):
  from ortak.tahmin_kayit_servisi import capture_forecast,runs
  from test_round4 import profile_frame
  import json
  self.s['staffing_parameters']={'aht':280,'target_sl':.9};capture_forecast(self.s,pd.DataFrame({'tarih':[pd.Timestamp(DAY)],'y_pred':[1000]}),profile_frame());self.s['staffing_parameters']['target_sl']=.5;stored=json.loads(runs(self.s['workspace_db_path'])[0]['metadata']);self.assertEqual(stored['staffing_parameters']['target_sl'],.9)
 def test_special_calendar_is_identical_to_forecast_calendar(self):
  from ortak.interval_servisi import calendar_flags,FLAGS
  from modules.cagri_tahmini.tahmin import _apply_date_bank_features
  dates=pd.date_range('2026-01-01',periods=365);frame=pd.DataFrame({'tarih':dates});expected=_apply_date_bank_features(frame.copy(),'tarih',FLAGS,frame).set_index('tarih')[FLAGS].astype(int);pd.testing.assert_frame_equal(calendar_flags(dates),expected)

class AdditionalIntegrationTests(Base):
 def test_transport_and_dorm_use_longer_delay_not_sum(self):
  from modules.vardiya_plani.planlama_verileri import collect_inputs
  self.s['employees_cache'][0]['work_type']='akademi';self.s['acad_schedules']={'u1':{'2026-Güz':{'Saat':['08:00-12:00'],'Pazartesi':['Ders']}}};self.s['academic_transport']={'u1':{'travel':True,'travel_hours':1,'dorm':True,'dorm_hours':2}};blocks=collect_inputs(self.s)[3]['1'];self.assertTrue(any(b==pd.Timestamp(DAY)+pd.Timedelta(hours=14) for a,b in blocks));self.assertFalse(any(b==pd.Timestamp(DAY)+pd.Timedelta(hours=15) for a,b in blocks))
 def test_half_hour_dorm_delay_is_not_forced_to_one_hour(self):
  from modules.vardiya_plani.planlama_verileri import collect_inputs
  self.s['employees_cache'][0]['work_type']='akademi';self.s['acad_schedules']={'u1':{'2026-Güz':{'Saat':['08:00-12:00'],'Pazartesi':['Ders']}}};self.s['academic_transport']={'u1':{'travel':False,'dorm':True,'dorm_hours':.5}};blocks=collect_inputs(self.s)[3]['1'];self.assertTrue(any(b==pd.Timestamp(DAY)+pd.Timedelta(hours=12,minutes=30) for a,b in blocks))
 def test_language_plan_approval_keeps_other_language_publication(self):
  from ortak.yayin_onaylari import submit,vote
  from modules.vardiya_plani.planlama_verileri import collect_inputs,fingerprint
  from modules.vardiya_plani.vardiya_motoru import generate_plan
  self.s['employees_cache'][1]['language']='en';self.s['published_shift_plan']=[dict(row('1',day=DAY),language='tr')];common=demand(count=10);specific=demand(count=1);self.s['sp_staffing_result_df']=common;self.s['language_demands']={'en':specific};self.s['planning_languages']={'tr':False,'en':True,'ar':False};self.s['planning_demand_language']='en';save_keys(self.s)
  staff,fixed,history,unavailable,issues=collect_inputs(self.s);result=generate_plan(staff,specific,self.s['shift_rules'],self.s['plan_group_priority'],DAY,DAY,fixed=fixed,history=history,unavailable=unavailable);result.update(staff=staff,period={'start':str(DAY),'end':str(DAY)});self.s['draft_shift_plan']=result['plan'];self.s['planning_result_fingerprint']=fingerprint(self.s);ident=submit(self.s,result);vote(self.s,ident);self.planner('p2');vote(self.s,ident);self.assertEqual({r['language'] for r in self.s['published_shift_plan']},{'tr','en'});self.assertTrue((self.s['sp_staffing_result_df']['Planlanan Agent']==10).all())
 def test_deputy_role_has_management_pages_but_cannot_publish(self):
  from ortak.erisim import allowed_pages
  from ortak.yayin_onaylari import submit
  from test_round4 import draft
  self.assertIn('📆 Ajanda',allowed_pages({'position':'assistant_manager'},['📆 Ajanda','📥 Onay Merkezi']));self.s['profile']={'position':'assistant_manager','username':'deputy'}
  with self.assertRaises(ValueError):submit(self.s,draft(self.s))
 def test_welcome_popup_is_scoped_and_read_receipt_is_persisted(self):
  from streamlit.testing.v1 import AppTest
  from ortak.talep_servisi import create_request
  from ortak.bildirimler import items
  self.s['profile']={'position':'agent','username':'u1','employee_id':'1','team_lead':'Lead'};create_request(self.s,{'type':'Yıllık İzin Talebi','start_date':str(DAY)});at=AppTest.from_string('from ortak.bildirim_popup import render\nimport streamlit as st\nrender(st.session_state)')
  for key,value in self.s.items():at.session_state[key]=value
  at.session_state['_notification_intro_pending']=True;at.run();self.assertFalse(at.exception);at.button(key='welcome_notices_read').click().run();self.assertFalse(at.exception);self.assertTrue(all(x['Okundu'] for x in items(self.s)))

class FingerprintRegressionTests(Base):
 def test_browsing_empty_language_screen_does_not_invalidate_pending_plan(self):
  from modules.vardiya_plani.planlama_verileri import fingerprint
  self.s.pop('language_demands',None);before=fingerprint(self.s);self.s['language_demands']={};self.assertEqual(before,fingerprint(self.s))
