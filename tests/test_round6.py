"""Altıncı güncelleme: kalıcılık, gece kontenjanı ve Planlama onaylı değişimler."""
import copy,os,sqlite3,tempfile,unittest
from pathlib import Path
from datetime import date,timedelta
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from streamlit.testing.v1 import AppTest
from test_round5 import make_state
from test_planning import DAY,row,emp,rules,demand
from ortak.calisma_alani_deposu import connect,save_keys,hydrate,loads
from ortak.vardiya_degisimleri import validate_changes,apply_changes,check_conservation
from ortak.degisim_onaylari import submit_change,decide_change,change_requests
from ortak.talep_servisi import create_request,act,refresh
from ortak.kesin_kayit_deposu import fixed_calendar_rows,night_capacity_check

class Base(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name);self.s=make_state(self.folder/'w.db',self.folder/'auth.db')
  self.old=[row('1',DAY,'OFF',None,None),row('2',DAY,'WORK','08:00','17:00'),row('1',DAY+timedelta(days=1),'WORK','08:00','17:00'),row('2',DAY+timedelta(days=1),'OFF',None,None)]
  self.s['published_shift_plan']=copy.deepcopy(self.old);save_keys(self.s)
 def tearDown(self):self.temp.cleanup()
 def planner(self):self.s['profile']={'position':'wfm','username':'planner','full_name':'Planlama'}
 def agent(self,eid='1'):self.s['profile']={'position':'agent','username':'u'+eid,'employee_id':eid,'full_name':'Person '+eid,'team_lead':'Lead'}
 def lead(self):self.s['profile']={'position':'tl','username':'lead','full_name':'Lead','manager':'Manager'}
 def balanced(self):return [dict(r,shift_code='WORK' if r['shift_code']=='OFF' else 'OFF',start='08:00' if r['shift_code']=='OFF' else None,end='17:00' if r['shift_code']=='OFF' else None) for r in self.old]

class ChangeRulesTests(Base):
 def test_tl_proposal_waits_and_only_planning_can_apply(self):
  proposal=submit_change(self.s,self.balanced(),'Vardiya değişimi','Karşılıklı OFF')
  self.assertEqual(self.s['published_shift_plan'],self.old)
  with self.assertRaises(ValueError):decide_change(self.s,proposal,True)
  self.s['profile']={'position':'manager','username':'manager'}
  with self.assertRaises(ValueError):decide_change(self.s,proposal,True)
  self.planner();decide_change(self.s,proposal,True)
  self.assertEqual(change_requests(self.s)[0]['status'],'Uygulandı');check_conservation(self.old,self.s['published_shift_plan'])
  with self.assertRaises(ValueError):decide_change(self.s,proposal,True)
 def test_reject_preserves_roster_and_has_reason(self):
  proposal=submit_change(self.s,self.balanced(),'Vardiya değişimi','Karşılıklı');self.planner()
  with self.assertRaises(ValueError):decide_change(self.s,proposal,False)
  decide_change(self.s,proposal,False,'Uygun değil');self.assertEqual(self.s['published_shift_plan'],self.old)
 def test_stale_roster_proposal_does_not_overwrite_new_hours(self):
  proposal=submit_change(self.s,[dict(self.old[1],end='16:00')],'Erken çıkış','Talep')
  self.planner();apply_changes(self.s,[dict(self.old[1],end='15:00')],'Erken çıkış','Başka işlem')
  with self.assertRaises(ValueError):decide_change(self.s,proposal,True)
  self.assertEqual(change_requests(self.s)[0]['status'],'Planlama onayı')
  self.assertEqual(next(r for r in self.s['published_shift_plan'] if r['employee_id']=='2' and r['date']==str(DAY))['end'],'15:00')
 def test_tampering_proposal_rejected_atomically(self):
  proposal=submit_change(self.s,self.balanced(),'Vardiya değişimi','Talep');proposal['reason']='Changed';self.planner()
  with self.assertRaises(ValueError):decide_change(self.s,proposal,True)
  with connect(self.s['workspace_db_path']) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM shift_change_batches').fetchone()[0],0)
 def test_cross_week_off_balance_not_hidden_by_period_total(self):
  sunday=DAY+timedelta(days=6);monday=sunday+timedelta(days=1)
  old=[row('1',sunday,'OFF',None,None),row('2',sunday),row('1',monday),row('2',monday,'OFF',None,None)]
  new=[dict(old[0],shift_code='WORK',start='08:00',end='17:00'),dict(old[1],shift_code='OFF',start=None,end=None),dict(old[2],shift_code='OFF',start=None,end=None),dict(old[3],shift_code='WORK',start='08:00',end='17:00')]
  with self.assertRaisesRegex(ValueError,'haftalık OFF'):check_conservation(old,new)
 def test_different_groups_or_languages_cannot_swap(self):
  for field,value in [('work_type','akademi'),('language','en')]:
   s=copy.deepcopy(self.s);s['employees_cache'][1][field]=value
   with self.assertRaisesRegex(ValueError,'grupları|diller|dil'):validate_changes(s,self.balanced(),'Vardiya değişimi','Talep')
 def test_different_shift_durations_rejected_even_if_week_totals_equal(self):
  old=[row('1',DAY,start='08:00',end='15:00'),row('2',DAY,start='10:00',end='15:00'),row('1',DAY+timedelta(days=1),start='10:00',end='15:00'),row('2',DAY+timedelta(days=1),start='08:00',end='15:00')]
  new=[dict(old[0],start='10:00'),dict(old[1],start='08:00'),dict(old[2],start='08:00'),dict(old[3],start='10:00')]
  with self.assertRaisesRegex(ValueError,'süreleri aynı'):check_conservation(old,new)
 def test_free_timing_edits_cannot_masquerade_as_swap(self):
  old=[row('1',DAY),row('2',DAY,start='09:00',end='18:00')]
  new=[dict(old[0],start='10:00',end='19:00'),dict(old[1],start='11:00',end='20:00')]
  with self.assertRaisesRegex(ValueError,'mevcut saatlerinden'):check_conservation(old,new)
 def test_seventh_consecutive_day_rejected_across_week_boundary(self):
  r=self.s['shift_rules']['work_type']['fulltime'];r.update(allow_6th_day=True,max_days_per_week_default=6,min_off_days=1,max_consecutive_days=6)
  records=[row('1',DAY+timedelta(days=i)) for i in [0,1,2,3,4,5,7,8]]+[row('1',DAY+timedelta(days=6),'OFF',None,None),row('2',DAY+timedelta(days=1),'OFF',None,None),row('2',DAY+timedelta(days=6))]
  self.s['published_shift_plan']=records
  changes=[]
  for record in records:
   if record['date'] not in {str(DAY+timedelta(days=1)),str(DAY+timedelta(days=6))}:continue
   changes.append(dict(record,shift_code='WORK' if record['shift_code']=='OFF' else 'OFF',start='08:00' if record['shift_code']=='OFF' else None,end='17:00' if record['shift_code']=='OFF' else None))
  with self.assertRaisesRegex(ValueError,'Üst üste'):validate_changes(self.s,changes,'Vardiya değişimi','Talep')
 def test_swap_rechecks_eleven_hours_rest(self):
  for p in self.s['employees_cache']:p['work_type']='akademi'
  self.s['shift_rules']['work_type']['akademi']['shift_total_hours_max']=9
  old=[row('1',DAY),row('2',DAY,start='17:00',end='02:00'),row('1',DAY+timedelta(days=1))]
  self.s['published_shift_plan']=old
  changes=[dict(old[0],start='17:00',end='02:00'),dict(old[1],start='08:00',end='17:00')]
  with self.assertRaisesRegex(ValueError,'dinlenme'):validate_changes(self.s,changes,'Vardiya değişimi','Talep')
 def test_agent_cannot_edit_another_person_attendance(self):
  self.agent();changed=dict(self.old[1],end='16:00')
  with self.assertRaisesRegex(ValueError,'kendi vardiyan'):validate_changes(self.s,[changed],'Erken çıkış','Talep',submitting=True)
 def test_report_requires_tl_origin_then_planning_approval(self):
  changed=dict(self.old[1],shift_code='RAPOR',start=None,end=None);self.planner()
  with self.assertRaises(ValueError):submit_change(self.s,[changed],'Rapor','Talep')
  self.lead();proposal=submit_change(self.s,[changed],'Rapor','Sağlık raporu');self.planner();decide_change(self.s,proposal,True)
  self.assertEqual(next(r for r in self.s['published_shift_plan'] if r['employee_id']=='2' and r['date']==str(DAY))['shift_code'],'RAPOR')
 def test_agent_early_and_late_requests_approved_to_roster(self):
  for typ,start,end in [('Erken Çıkış Talebi','08:00','16:00'),('Geç Giriş Talebi','09:00','17:00')]:
   self.s['published_shift_plan']=[row('1',DAY)];save_keys(self.s);self.agent()
   req=create_request(self.s,{'type':typ,'start_date':str(DAY),'end_date':str(DAY),'overtime_start':start,'overtime_end':end,'note':'Ulaşım'})
   self.lead();req=act(self.s,req,'forward');self.planner();done=act(self.s,req,'apply')
   self.assertEqual(done['status'],'Uygulandı');self.assertEqual(self.s['published_shift_plan'][0]['start'],start);self.assertEqual(self.s['published_shift_plan'][0]['end'],end);self.assertTrue(done['resolved_assignments'][0]['attendance_adjusted'])
 def test_monitoring_scope_and_counts(self):
  from modules.izleme import metrics
  from ortak.personel import visible_people
  self.planner();apply_changes(self.s,[dict(self.old[1],end='16:00')],'Erken çıkış','Ulaşım')
  people=visible_people({'position':'agent','employee_id':'1'},self.s['employees_cache']);counts,events=metrics(self.s,people,DAY,DAY+timedelta(days=1));self.assertEqual(counts['Erken çıkış'],0)
  people=visible_people({'position':'tl','full_name':'Lead'},self.s['employees_cache']);counts,events=metrics(self.s,people,DAY,DAY+timedelta(days=1));self.assertEqual(counts['Erken çıkış'],1);self.assertEqual(len(events),1)

class NightCapacityTests(Base):
 def setUp(self):
  super().setUp();self.s['published_shift_plan']=[]
  for p in self.s['employees_cache']:p['work_type']='akademi'
  self.s['shift_rules']['night'].update(mode='normal',normal={'tr':1,'en':0,'ar':0})
  self.s['shift_rules']['general'].update(night_window_start='00:00',night_window_end='08:00');save_keys(self.s)
  self.payload={'type':'Gece Vardiyası Talebi','start_date':str(DAY),'end_date':str(DAY),'overtime_start':'00:00','overtime_end':'08:00','note':'Gece'}
 def test_pending_request_reserves_capacity_and_rejection_releases_it(self):
  self.agent();req=create_request(self.s,self.payload);self.agent('2')
  with self.assertRaisesRegex(ValueError,'dolu'):create_request(self.s,self.payload)
  self.lead();act(self.s,req,'reject','Uygun değil');self.agent('2');self.assertTrue(create_request(self.s,self.payload)['id'])
 def test_approved_night_appears_in_source_calendar_and_night_gaps(self):
  self.agent();req=create_request(self.s,self.payload);self.lead();req=act(self.s,req,'forward');self.planner();act(self.s,req,'apply')
  rows=fixed_calendar_rows(self.s,DAY,DAY);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['shift_code'],'GECE');self.assertEqual(rows[0]['end'],'08:00')
  from ortak.gece_kontrolleri import night_gaps
  self.s['plan_ctx']={'start':DAY,'end':DAY};self.assertFalse(night_gaps(self.s))
 def test_no_contingent_or_disallowed_group_cannot_request(self):
  self.agent();self.s['shift_rules']['night']['normal']['tr']=0
  with self.assertRaises(ValueError):create_request(self.s,self.payload)
  self.s['shift_rules']['night']['normal']['tr']=1;self.s['employees_cache'][0]['work_type']='fulltime'
  with self.assertRaises(ValueError):create_request(self.s,self.payload)
 def test_two_sessions_do_not_overbook_one_night_position(self):
  def send(eid):
   state=copy.deepcopy(self.s);state['profile']={'position':'agent','employee_id':eid,'username':'u'+eid,'team_lead':'Lead'}
   try:return create_request(state,self.payload)['id']
   except ValueError:return None
  with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(send,['1','2']))
  self.assertEqual(sum(bool(r) for r in results),1)
  with connect(self.s['workspace_db_path']) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],1)

class ForecastAndUITests(Base):
 def test_yearly_daily_forecast_is_saved_before_interval_and_can_be_reused(self):
  from ortak.cagri_tahmin_servisi import activate_forecast
  from ortak.gunluk_tahmin_deposu import saved_daily
  frame=pd.DataFrame({'tarih':pd.date_range('2027-01-01','2027-12-31'),'y_pred':100.})
  activate_forecast(self.s,frame,{'model_name':'Yıllık plan'})
  records=saved_daily(self.s['workspace_db_path']);self.assertEqual(len(records),1);self.assertEqual(len(records[0]['frame']),365)
  state={'workspace_db_path':self.s['workspace_db_path']};activate_forecast(state,records[0]['frame'],records[0]['meta']);self.assertEqual(len(saved_daily(self.s['workspace_db_path'])),1)
  pd.testing.assert_frame_equal(state['sp_forecast_df'],frame)
 def test_saved_forecast_title_does_not_mutate_forecast(self):
  from ortak.gunluk_tahmin_deposu import capture_daily,saved_daily,daily_label
  from ortak.kayit_basliklari import set_title
  self.planner();frame=pd.DataFrame({'tarih':pd.date_range(DAY,periods=2),'y_pred':[100.,200.]});ident=capture_daily(self.s,frame,{'model_name':'Model'})
  set_title(self.s,ident,'Kasım operasyon planı');record=saved_daily(self.s['workspace_db_path'])[0]
  self.assertEqual(daily_label(record,self.s['workspace_db_path']),'Kasım operasyon planı');pd.testing.assert_frame_equal(record['frame'],frame)
 def test_staffing_selected_short_period_preserves_full_daily_forecast(self):
  from test_round4 import profile_frame
  frame=pd.DataFrame({'tarih':pd.date_range(DAY,periods=14),'y_pred':100.})
  at=AppTest.from_string('from modules.mesai_plani.personel_ihtiyaci import render\nrender()',default_timeout=60);at.session_state['workspace_db_path']=self.s['workspace_db_path'];at.session_state['sp_forecast_df']=frame;at.session_state['sp_active_ratio_profile_df']=profile_frame(DAY);at.run()
  at.date_input[0].set_value(DAY+timedelta(days=7));at.date_input[1].set_value(DAY+timedelta(days=9)).run()
  next(b for b in at.button if 'Personel İhtiyacını Hesapla' in b.label).click().run();self.assertFalse(at.exception);self.assertEqual(len(at.session_state['sp_staffing_result_df']),3*48);self.assertEqual(len(at.session_state['sp_forecast_df']),14)
 def test_tenure_boundaries_and_unknown_start(self):
  from ortak.personel_karti import tenure
  today=date(2026,11,8)
  for start,expected in [('2026-08-09','0–3 ay'),('2026-08-08','3–6 ay'),('2026-05-08','6–12 ay'),('2025-11-08','1–2 yıl'),('2024-11-08','2–3 yıl'),('2023-11-08','3+ yıl')]:self.assertEqual(tenure(start,today)[0],expected)
  self.assertIn('bekleniyor',tenure(None,today)[0])
 def test_all_shifts_visible_to_agent_with_dynamic_rize_location(self):
  people=[dict(emp('1',group='akademi'),location='Rize',team_lead='Lead'),dict(emp('2',group='akademi'),location='Bolu',team_lead='Other')]
  at=AppTest.from_string("import streamlit as st\nfrom modules.tum_vardiyalar.ortak import fetch_agents,get_locations_by_work_type\nst.session_state['result']=fetch_agents()\nst.session_state['locations']=get_locations_by_work_type('akademi')")
  at.session_state['profile']={'position':'agent','employee_id':'1'};at.session_state['personnel_cache']=people;at.run();self.assertFalse(at.exception);self.assertEqual(len(at.session_state['result']),2);self.assertIn('Rize',at.session_state['locations'])
 def test_calendars_only_show_names_dates_and_shifts(self):
  from ortak.planlama import calendar_grid
  grid=calendar_grid({'source_rows':self.old,'staff':self.s['employees_cache'],'exam_keys':set()},{'start':DAY,'end':DAY+timedelta(days=1)})
  self.assertNotIn('Sicil no',grid);self.assertNotIn('Kullanıcı adı',grid);self.assertEqual(len(grid.columns),3)
 def test_soft_is_warning_hard_is_blocker(self):
  from modules.vardiya_plani.vardiya_motoru import generate_plan
  from ortak.planlama_gorunumu import blocking_issues
  r=rules();r['work_type']['akademi'].update(max_end_time='21:00',max_end_is_hard=False,override_required_if_violate=True)
  candidate=row(code='MESAI',start='18:00',end='23:00');person=emp(group='akademi')
  soft=generate_plan([person],demand(),r,list(r['work_type']),DAY,DAY,fixed=[candidate],auto_fill=False)
  self.assertTrue(soft['issues']);self.assertFalse(blocking_issues(soft));self.assertEqual(soft['issues'][0]['severity'],'warning')
  r['work_type']['akademi']['max_end_is_hard']=True
  hard=generate_plan([person],demand(),r,list(r['work_type']),DAY,DAY,fixed=[candidate],auto_fill=False);self.assertTrue(blocking_issues(hard))
 def test_role_landings_and_monitor_access(self):
  from ortak.erisim import landing_page,allowed_pages
  self.assertEqual(landing_page({'position':'wfm'}),'🗓️ Vardiya Planı');self.assertEqual(landing_page({'position':'tl'}),'📊 İzleme');self.assertEqual(landing_page({'position':'agent'}),'📌 Takip');self.assertIn('📊 İzleme',allowed_pages({'position':'agent'},[]));self.assertNotIn('⚙️ Ayarlar',allowed_pages({'position':'manager'},['⚙️ Ayarlar']))
 def test_company_survives_personnel_creation_and_identity_migration(self):
  from ortak.personel_is_akisi import submit,decide
  from ortak.personel_deposu import list_people
  item=submit(self.s,'Ekleme',{'full_name':'Company Person','username':'company.user','sicil_no':'C900','work_type':'akademi','language':'tr','location':'Rize','company':'Ulak','effective_date':'2026-11-01'},'Yeni personel')
  self.s['profile']={'position':'manager','full_name':'Manager','username':'manager'};item=decide(self.s,item,True);self.planner();decide(self.s,item,True)
  self.assertEqual(next(p for p in list_people(self.s) if p['username']=='company.user')['company'],'Ulak')

class AdditionalSafetyTests(Base):
 def test_forecast_scope_initial_dates_are_populated_and_filter_applies(self):
  frame=pd.DataFrame({'tarih':pd.date_range(DAY,periods=30),'cagri_sayisi':100})
  at=AppTest.from_string('from modules.cagri_tahmini.veri_kaynagi import render\nrender()');at.session_state['cf_all_df']=frame;at.session_state['cf_full_df']=frame;at.session_state['cf_raw_df']=frame;at.session_state['cf_meta']={'rows':30,'cols':2,'columns':list(frame)};at.session_state['cf_scope_enabled']=True;at.run();self.assertFalse(at.exception)
  self.assertEqual(at.date_input(key='cf_scope_start').value,DAY);self.assertEqual(at.date_input(key='cf_scope_end').value,DAY+timedelta(days=29))
  at.date_input(key='cf_scope_end').set_value(DAY+timedelta(days=2)).run();next(b for b in at.button if b.label=='✅ Uygula').click().run();self.assertFalse(at.exception);self.assertEqual(len(at.session_state['cf_full_df']),3)
 def test_login_resets_previous_accounts_subpage_but_preserves_shared_roster(self):
  from ortak.erisim import enter_session
  state={'main_page':'📌 Takip','nav_tracking':'Ders Programı','nav_tracking_control':'Ders Programı','new_request_type':'Rapor Bildirimi','published_shift_plan':self.old}
  enter_session(state,{'position':'agent'})
  self.assertNotIn('nav_tracking',state);self.assertNotIn('new_request_type',state);self.assertEqual(state['main_page'],'📌 Takip');self.assertEqual(state['published_shift_plan'],self.old)
 def test_withdrawn_roster_proposal_fails_cleanly_without_partial_write(self):
  item=submit_change(self.s,self.balanced(),'Vardiya değişimi','Talep');self.s['published_shift_plan']=[];save_keys(self.s);self.planner()
  with self.assertRaisesRegex(ValueError,'Vardiyalar talep sonrası değişmiş'):decide_change(self.s,item,True)
  with connect(self.s['workspace_db_path']) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM shift_change_batches').fetchone()[0],0)
 def test_soft_publication_requires_separate_consent(self):
  from test_round4 import draft
  from ortak.yayin_servisi import publish_plan
  self.planner();self.s['published_shift_plan']=[];self.s['plan_ctx']={'start':DAY,'end':DAY};self.s['employees_cache'][0]['work_type']='akademi'
  self.s['shift_rules']['work_type']['akademi'].update(max_end_time='21:00',max_end_is_hard=False,override_required_if_violate=True)
  self.s['draft_shift_plan']=[row('1',DAY,code='MESAI',start='18:00',end='23:00')];self.s['plan_group_priority']=list(self.s['shift_rules']['work_type']);save_keys(self.s);result=draft(self.s)
  with self.assertRaisesRegex(ValueError,'Esnek kural'):publish_plan(self.s,result)
  self.s['planning_accept_soft']=True;publish_plan(self.s,result);self.assertTrue(self.s['last_publication']['id'])
 def test_tl_report_request_applies_to_published_roster(self):
  request=create_request(self.s,{'type':'Rapor Bildirimi','start_date':str(DAY),'end_date':str(DAY),'report_employee_id':'2','note':'Sağlık raporu'})
  self.assertEqual(request['queue'],'WFM');self.planner();done=act(self.s,request,'apply')
  self.assertEqual(done['status'],'Uygulandı');self.assertEqual(done['resolved_assignments'][0]['shift_code'],'RAPOR')
  from modules.vardiya_plani.planlama_verileri import collect_inputs
  self.assertTrue(any(r['shift_code']=='RAPOR' for r in collect_inputs(self.s)[1]))
 def test_renaming_selected_record_keeps_same_forecast_selected(self):
  from ortak.gunluk_tahmin_deposu import capture_daily,saved_daily
  self.planner()
  for i in range(2):capture_daily(self.s,pd.DataFrame({'tarih':pd.date_range(DAY,periods=2),'y_pred':[100.+i,200.+i]}),{'model_name':'Model '+str(i)})
  at=AppTest.from_string('import streamlit as st\nfrom modules.kayit_merkezi import render_daily\nrender_daily(st.session_state)');at.session_state['workspace_db_path']=self.s['workspace_db_path'];at.session_state['profile']=self.s['profile'];at.run();self.assertFalse(at.exception)
  at.selectbox(key='registry_daily').select(at.selectbox(key='registry_daily').options[1]).run();ident=at.session_state['registry_daily_id'];at.text_input(key='record_title_'+ident).set_value('İkinci özel plan').run();at.button(key='record_title_save_'+ident).click().run()
  self.assertFalse(at.exception);self.assertEqual(at.session_state['registry_daily_id'],ident);self.assertEqual(at.selectbox(key='registry_daily').value,'İkinci özel plan')

if __name__=='__main__':unittest.main()
