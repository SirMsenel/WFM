import copy,tempfile,sqlite3,unittest
from pathlib import Path
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import pandas as pd
from test_round5 import make_state
from test_round4 import draft
from test_planning import DAY,demand,row,emp,rules
from ortak.calisma_alani_deposu import connect,save_keys,loads
from ortak.yayin_onaylari import submit,vote,proposals,ready
from ortak.talep_servisi import create_request,act,refresh

class Base(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();folder=Path(self.temp.name);self.s=make_state(folder/'w.db',folder/'a.db');self.s['profile']={'position':'wfm','username':'planner1'};self.s['plan_ctx']={'start':DAY,'end':DAY};self.s['plan_group_priority']=list(self.s['shift_rules']['work_type']);self.s['shift_rules']['publication_approvals']={'enabled':True};self.s['sp_staffing_result_df']=demand();self.s['published_shift_plan']=[];save_keys(self.s)
 def tearDown(self):self.temp.cleanup()
 def planner(self,name):self.s['profile']={'position':'wfm','username':name}
 def queue(self):
  result=draft(self.s);return submit(self.s,result)

class ApprovalTests(Base):
 def test_two_different_planners_required(self):
  ident=self.queue();self.assertFalse(vote(self.s,ident));self.assertFalse(self.s['published_shift_plan'])
  with self.assertRaises(ValueError):vote(self.s,ident)
  self.planner('planner2');self.assertTrue(vote(self.s,ident));self.assertTrue(self.s['published_shift_plan']);self.assertEqual(proposals(self.s)[0]['status'],'Yayınlandı')
  with self.assertRaises(ValueError):vote(self.s,ident)
 def test_more_than_five_percent_requires_manager_after_two_planners(self):
  self.s['sp_staffing_result_df']=demand(count=100);ident=self.queue();vote(self.s,ident);self.planner('planner2');self.assertFalse(vote(self.s,ident));self.assertFalse(self.s['published_shift_plan'])
  self.s['profile']={'position':'planning_manager','username':'lead_plan'};self.assertTrue(vote(self.s,ident));self.assertTrue(self.s['published_shift_plan'])
 def test_exact_five_percent_no_manager_required(self):
  item={'votes':[{'actor':'a'},{'actor':'b'}],'manager':None,'rate':5};self.assertTrue(ready(item));item['rate']=5.0001;self.assertFalse(ready(item))
 def test_moderator_switches_do_not_supply_independent_votes(self):
  ident=self.queue();self.s['profile']={'position':'wfm','username':'a','_actor_username':'root'};vote(self.s,ident)
  self.s['profile']={'position':'wfm','username':'b','_actor_username':'root'}
  with self.assertRaisesRegex(ValueError,'gerçek kullanıcı'):vote(self.s,ident)
 def test_changed_source_cannot_publish_old_approved_snapshot(self):
  ident=self.queue();vote(self.s,ident);self.s['shift_rules']['general']['weekday_general_start']='09:00';save_keys(self.s);self.planner('planner2')
  with self.assertRaises(ValueError):vote(self.s,ident)
  self.assertFalse(self.s['published_shift_plan'])
 def test_wrong_role_and_reject_without_reason(self):
  ident=self.queue();self.s['profile']={'position':'manager','username':'manager'}
  with self.assertRaises(ValueError):vote(self.s,ident)
  self.planner('p2')
  with self.assertRaises(ValueError):vote(self.s,ident,False)
  vote(self.s,ident,False,'Eksikleri yeniden değerlendir');self.assertEqual(proposals(self.s)[0]['status'],'Reddedildi')
 def test_simulated_leave_only_finalized_when_published(self):
  self.s['profile']={'position':'agent','username':'u1','employee_id':'1','team_lead':'Lead'};req=create_request(self.s,{'type':'Yıllık İzin Talebi','start_date':str(DAY),'end_date':str(DAY),'note':'İzin'});self.planner('planner1')
  req=act(self.s,req,'takeover','Planlama üstleniyor');req=act(self.s,req,'simulate');self.assertEqual(req['status'],'Simülasyonda');ident=self.queue();vote(self.s,ident);self.assertEqual(refresh(self.s)[0]['status'],'Simülasyonda');self.planner('planner2');vote(self.s,ident);self.assertEqual(refresh(self.s)[0]['status'],'Onaylandı')
 def test_cancellation_removes_tentative_leave_and_logs_reason(self):
  self.s['profile']={'position':'agent','username':'u1','employee_id':'1','team_lead':'Lead'};req=create_request(self.s,{'type':'Yıllık İzin Talebi','start_date':str(DAY)});self.planner('planner1');req=act(self.s,req,'simulate')
  with self.assertRaises(ValueError):act(self.s,req,'cancel_planning')
  req=act(self.s,req,'cancel_planning','Kritik ihtiyaç; yeniden görüşülecek');self.assertEqual(req['status'],'İptal Edildi');self.assertEqual(req['events'][-1]['note'],'Kritik ihtiyaç; yeniden görüşülecek')

class AdditionalPhase7Tests(Base):
 def test_legacy_apply_is_staged_when_new_publication_flow_enabled(self):
  self.s['profile']={'position':'agent','username':'u1','employee_id':'1','team_lead':'Lead'};req=create_request(self.s,{'type':'Yıllık İzin Talebi','start_date':str(DAY)});self.planner('planner1');req=act(self.s,req,'takeover','Üstlen');req=act(self.s,req,'apply');self.assertEqual(req['queue'],'SIMULATION');self.assertEqual(req['status'],'Simülasyonda')
 def test_personnel_revision_invalidates_pending_plan(self):
  ident=self.queue();vote(self.s,ident)
  with connect(self.s['workspace_db_path']) as db:db.execute("INSERT INTO metadata VALUES('directory_revision','changed') ON CONFLICT(key) DO UPDATE SET value=excluded.value")
  self.planner('p2')
  with self.assertRaises(ValueError):vote(self.s,ident)
  self.assertFalse(self.s['published_shift_plan'])
 def test_seven_quota_precedes_academy_even_if_it_fills_demand(self):
  from modules.vardiya_plani.vardiya_motoru import generate_plan
  r=rules();r['boosts']={'weekday_0700_fulltime_extra_enabled':True,'weekday_0700_fulltime_extra_count':3};r['capacity']={'max_overstaff':3};people=[emp(str(i)) for i in range(1,5)]+[emp(str(i),group='akademi') for i in range(5,15)]
  df=demand(slots=range(15,39),count=3);df.loc[df.Slot<17,'Planlanan Agent']=0
  result=generate_plan(people,df,r,['akademi','fulltime','dis_kaynak'],DAY,DAY);self.assertEqual(sum(x.get('start')=='07:00' for x in result['plan']),3)
 def test_night_meal_counts_next_day_coverage(self):
  from ortak.statuler import defaults,meal_plan
  cfg=dict(defaults(),enabled=True);cfg['groups']['fulltime'].update(after_start=3,before_start=6)
  a=demand(slots=range(1,49));b=a.copy();b['Tarih']=DAY+timedelta(days=1);coverage=pd.concat([a,b],ignore_index=True);coverage['İhtiyaç']=1;coverage['Atanan']=3;coverage['Eksik']=0;coverage['Fazla']=2
  meals,out,issues=meal_plan({'status_rules':cfg},[row(start='22:00',end='07:00')],coverage,[emp()]);self.assertFalse(issues);self.assertAlmostEqual(out['Mola kaybı'].sum(),1.);self.assertEqual(pd.Timestamp(meals[0]['start']).date(),DAY+timedelta(days=1))

class CapacityTests(Base):
 def test_slot_shrinkage_changes_only_configured_slots(self):
  from modules.mesai_plani.personel_ihtiyaci import calculate_staffing
  from test_round4 import profile_frame
  fc=pd.DataFrame({'tarih':[pd.Timestamp(DAY)],'y_pred':[1000.]});profile=profile_frame().drop(columns='Tarih');a=calculate_staffing(fc,profile);b=calculate_staffing(fc,profile,slot_shrinkage=[{'start_slot':25,'end_slot':28,'rate':.6}])
  self.assertTrue((b.loc[b.Slot.between(25,28),'Planlanan Agent']>a.loc[a.Slot.between(25,28),'Planlanan Agent']).all());self.assertEqual(a.loc[a.Slot==20,'Planlanan Agent'].iloc[0],b.loc[b.Slot==20,'Planlanan Agent'].iloc[0])
 def test_minimum_shift_and_controlled_positive_slots(self):
  from modules.vardiya_plani.vardiya_motoru import generate_plan,bounds
  r=rules();r['work_type']['akademi']['min_shift_hours']=4;r['capacity']={'max_overstaff':1};df=demand(count=0,slots=range(17,35));df.loc[df.Slot.isin([33,34]),'Planlanan Agent']=1
  result=generate_plan([emp(group='akademi')],df,r,list(r['work_type']),DAY,DAY)
  work=[x for x in result['plan'] if bounds(x)];self.assertTrue(work);self.assertGreaterEqual((bounds(work[0])[1]-bounds(work[0])[0]).total_seconds(),4*3600);self.assertGreater(result['coverage'].Fazla.sum(),0)
 def test_seven_oclock_quota_three_not_only_two(self):
  from modules.vardiya_plani.vardiya_motoru import generate_plan
  r=rules();r['boosts']={'weekday_0700_fulltime_extra_enabled':True,'weekday_0700_fulltime_extra_count':3};df=demand(slots=range(15,35),count=4);df.loc[df.Slot<17,'Planlanan Agent']=0
  result=generate_plan([emp(str(i)) for i in range(1,6)],df,r,list(r['work_type']),DAY,DAY)
  self.assertEqual(sum(x.get('start')=='07:00' for x in result['plan']),3)
 def test_inverse_erlang_capacity_respects_sl(self):
  from modules.similasyon import inverse_erlang
  from modules.mesai_plani.personel_ihtiyaci import erlang_c_metrics_for_m
  calls=inverse_erlang(20);self.assertGreater(calls,0);_,sl,occ=erlang_c_metrics_for_m(calls,300,1800,20,20);self.assertGreaterEqual(sl,.8-1e-8);self.assertLessEqual(occ,.85+1e-8)
 def test_meals_fit_night_shift_and_reduce_coverage(self):
  from ortak.statuler import meal_plan,defaults
  s={'status_rules':dict(defaults(),enabled=True)};coverage=demand(slots=range(1,49));coverage['İhtiyaç']=1;coverage['Atanan']=3;coverage['Eksik']=0;coverage['Fazla']=2
  meals,result,issues=meal_plan(s,[row(code='GECE',start='00:00',end='08:00')],coverage,[emp()]);self.assertFalse(issues);self.assertEqual(len(meals),1);self.assertLessEqual(pd.Timestamp(meals[0]['end']),pd.Timestamp(DAY)+pd.Timedelta(hours=8));self.assertAlmostEqual(result['Mola kaybı'].sum(),1.)
 def test_class_default_buffer_and_transport(self):
  from modules.vardiya_plani.planlama_verileri import collect_inputs
  s=self.s;s['employees_cache'][0]['work_type']='akademi';s['acad_schedules']={'u1':{'2026-Güz':{'Saat':['08:00-12:00'],'Pazartesi':['Ders']}}}
  blocks=collect_inputs(s)[3]['1'];self.assertTrue(any(b==pd.Timestamp(DAY)+pd.Timedelta(hours=12,minutes=30) for a,b in blocks))
  s['academic_transport']={'u1':{'class':{'enabled':True,'minutes':60,'available_after':'14:00'}}};blocks=collect_inputs(s)[3]['1'];self.assertTrue(any(b==pd.Timestamp(DAY)+pd.Timedelta(hours=14) for a,b in blocks))
 def test_operations_metrics_ingest_and_real_service_level(self):
  from ortak.tahmin_kayit_servisi import ingest_actuals,capture_forecast,compare
  from test_round4 import profile_frame
  from ortak.canli_metrikler import actual_metrics
  ingest_actuals(pd.DataFrame({'tarih':[str(DAY)],'slot':[17],'cagri_sayisi':[40],'aht_sec':[300.],'answered':[35],'answered_target':[28],'staffed':[10]}),self.s['workspace_db_path']);ident=capture_forecast(self.s,pd.DataFrame({'tarih':[pd.Timestamp(DAY)],'y_pred':[1920.]}),profile_frame());result=actual_metrics(self.s,compare(ident,self.s['workspace_db_path']));self.assertEqual(result.loc[result.slot==17,'Gerçek SL (%)'].iloc[0],70)
  with self.assertRaises(ValueError):ingest_actuals(pd.DataFrame({'tarih':[str(DAY)],'slot':[18],'cagri_sayisi':[2],'answered':[3]}),self.s['workspace_db_path'])

class BreakTests(Base):
 def setUp(self):
  super().setUp();self.day=pd.Timestamp.now(tz='Europe/Istanbul').date()+timedelta(days=1);self.s['published_shift_plan']=[row(str(i),self.day) for i in (1,2,3)];self.s['sp_staffing_result_df']=demand(start=self.day,count=2);self.s['status_rules']={'groups':{'fulltime':{'break_minutes':15}}};save_keys(self.s)
 def test_concurrent_requests_reserve_only_one_available_position(self):
  from ortak.mola_servisi import request
  def send(eid):
   s=copy.deepcopy(self.s);s['profile']={'position':'agent','employee_id':eid,'username':'u'+eid}
   try:return request(s,pd.Timestamp(self.day)+pd.Timedelta(hours=12),15)
   except ValueError:return None
  with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(send,['1','2']))
  self.assertEqual(sum(bool(r) for r in result),1)
 def test_meal_overlap_and_cancellation_scope(self):
  from ortak.mola_servisi import request,cancel,init,availability
  init(self.s['workspace_db_path']);self.s['profile']={'position':'agent','employee_id':'1','username':'u1'};ident=request(self.s,pd.Timestamp(self.day)+pd.Timedelta(hours=12),15)
  with self.assertRaises(ValueError):request(self.s,pd.Timestamp(self.day)+pd.Timedelta(hours=12),15)
  self.s['profile']['employee_id']='2'
  with self.assertRaises(ValueError):cancel(self.s,ident)
  self.s['profile']['employee_id']='1';cancel(self.s,ident);self.assertEqual(availability(self.s,'1',pd.Timestamp(self.day)+pd.Timedelta(hours=12),15),1)
 def test_outside_shift_and_missing_demand_refused(self):
  from ortak.mola_servisi import availability
  with self.assertRaises(ValueError):availability(self.s,'1',pd.Timestamp(self.day)+pd.Timedelta(hours=2),15)
  self.s['sp_staffing_result_df']=pd.DataFrame()
  with self.assertRaises(ValueError):availability(self.s,'1',pd.Timestamp(self.day)+pd.Timedelta(hours=12),15)

class FeedbackTests(Base):
 def test_anonymous_payload_does_not_contain_sender(self):
  from ortak.gorusler import submit,records
  self.s['profile']={'position':'agent','username':'secret-user','full_name':'Gizli Personel'};ident=submit(self.s,'Şikâyet','Takip sorunu',True)
  with connect(self.s['workspace_db_path']) as db:
   raw=db.execute('SELECT * FROM feedback WHERE id=?',(ident,)).fetchone();self.assertNotIn('secret-user',raw['payload']);self.assertNotIn('Gizli Personel',raw['payload'])
  self.s['profile']={'position':'wfm','username':'planner'};self.assertIsNone(records(self.s)[0]['sender'])
 def test_other_agent_cannot_read_private_feedback(self):
  from ortak.gorusler import submit,records
  self.s['profile']={'position':'agent','username':'a'};submit(self.s,'Öneri','Önerim');self.s['profile']={'position':'agent','username':'b'};self.assertFalse(records(self.s))

if __name__=='__main__':unittest.main()
