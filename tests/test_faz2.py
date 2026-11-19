"""İkinci faz: shrinkage, statü hakları, yayın kilitleri ve izleme doğruluğu."""
import copy,unittest,math
from datetime import timedelta
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from test_phase7 import Base
from test_planning import DAY,demand,row,emp
from test_round4 import draft
from ortak.calisma_alani_deposu import connect,save_keys,dumps,loads
from ortak.yayin_onaylari import submit,vote,proposals
from ortak.statuler import defaults,meal_plan
from ortak.izleme_analitigi import assess,call_history,daily_insights
from ortak.veri_secimi import select_columns

class AnalyticsTests(unittest.TestCase):
 def test_selected_columns_copy_without_losing_original(self):
  original=pd.DataFrame({'tarih':pd.date_range(DAY,periods=2),'cagri_sayisi':[1,2],'aht':[3,4]});chosen=select_columns(original,['tarih','cagri_sayisi']);self.assertNotIn('aht',chosen);self.assertIn('aht',original)
  for cols in [[],['aht'],['tarih'],['absent']]:
   with self.assertRaises(ValueError):select_columns(original,cols)
 def test_tolerance_boundary_missing_and_excluded(self):
  values=pd.Series([-10,10,10.001,None,500]);status=assess(values,10,pd.Series([True,True,True,True,False]));self.assertEqual(status.tolist(),['Uygun','Uygun','Sınır dışında','Veri yok','Ölçüm dışı'])
  with self.assertRaises(ValueError):assess(values,float('nan'))
 def test_interval_slots_are_real_timestamps(self):
  frame=pd.DataFrame({'tarih':[str(DAY),str(DAY)],'slot':[17,18],'cagri_sayisi':[10,20]});out=call_history(frame,'tarih','cagri_sayisi');self.assertEqual(out.Zaman.dt.strftime('%H:%M').tolist(),['08:00','08:30'])
 def test_same_weekday_reference_is_past_only(self):
  frame=pd.DataFrame({'Zaman':pd.date_range(DAY,periods=35),'Çağrı':[100]*35});out=daily_insights(frame);self.assertTrue(pd.isna(out['Aynı gün ort.'].iloc[0]));self.assertEqual(out['Aynı gün ort.'].iloc[14],100);frame.loc[28,'Çağrı']=1000;out=daily_insights(frame);self.assertEqual(out['Aynı gün ort.'].iloc[28],100)

class PublicationFlowTests(Base):
 def test_no_second_pending_plan_even_same_fingerprint(self):
  ident=self.queue()
  with self.assertRaisesRegex(ValueError,'onay bekleyen'):self.queue()
  self.assertEqual(len(proposals(self.s)),1)
 def test_changed_draft_rejected_without_writing_global_state(self):
  self.queue()
  with connect(self.s['workspace_db_path']) as db:before=db.execute("SELECT payload FROM work_state WHERE key='draft_shift_plan'").fetchone()[0]
  self.s['draft_shift_plan']=[row(code='OFF',start=None,end=None)];result=draft(self.s)
  with self.assertRaisesRegex(ValueError,'onay bekleyen'):submit(self.s,result)
  with connect(self.s['workspace_db_path']) as db:self.assertEqual(db.execute("SELECT payload FROM work_state WHERE key='draft_shift_plan'").fetchone()[0],before)
 def test_concurrent_submissions_reserve_only_one_pending_plan(self):
  result=draft(self.s);save_keys(self.s)
  def attempt(_):
   try:return submit(copy.deepcopy(self.s),result)
   except ValueError:return None
  with ThreadPoolExecutor(2) as pool:results=list(pool.map(attempt,range(2)))
  self.assertEqual(sum(x is not None for x in results),1);self.assertEqual(len(proposals(self.s)),1)
 def test_competing_different_sources_cannot_overwrite_winner(self):
  states=[copy.deepcopy(self.s),copy.deepcopy(self.s)];states[1]['shift_rules']['capacity']={'max_overstaff':2};results=[draft(x) for x in states]
  def attempt(i):
   try:return submit(states[i],results[i])
   except ValueError:return None
  with ThreadPoolExecutor(2) as pool:ids=list(pool.map(attempt,range(2)))
  winner=next(i for i,value in enumerate(ids) if value is not None)
  with connect(self.s['workspace_db_path']) as db:stored=loads(db.execute("SELECT payload FROM work_state WHERE key='shift_rules'").fetchone()[0])
  self.assertEqual(stored,states[winner]['shift_rules'])
 def test_votes_are_visible_from_another_account(self):
  ident=self.queue();self.s['profile']['full_name']='Birinci Planlamacı';vote(self.s,ident);other=dict(self.s,profile={'position':'wfm','username':'p2'});item=proposals(other)[0];self.assertEqual(item['votes'][0]['name'],'Birinci Planlamacı');self.assertEqual(item['votes'][0]['as'],'planner1')
 def test_past_publication_cannot_withdraw_or_reopen(self):
  from ortak.yayin_servisi import publish_plan,withdraw,publications
  self.s['shift_rules']['publication_approvals']['enabled']=False;result=draft(self.s);publish_plan(self.s,result);batch=publications(self.s)[0];before=copy.deepcopy(self.s['published_shift_plan'])
  with patch('ortak.yayin_servisi.publication_today',return_value=DAY+timedelta(days=1)):
   for reopen in [True,False]:
    with self.assertRaisesRegex(ValueError,'Geçmiş'):withdraw(self.s,batch,reopen)
  self.assertEqual(before,self.s['published_shift_plan'])
 def test_pending_requests_can_be_bypassed_by_planning(self):
  from ortak.talep_servisi import create_request
  from ortak.donem_kilitleri import planning_problem,assert_can_plan
  self.s['profile']={'position':'agent','username':'u1','employee_id':'1','team_lead':'Lead'};create_request(self.s,{'type':'Yıllık İzin Talebi','start_date':str(DAY)});self.planner('p1');self.assertEqual(planning_problem(self.s)['kind'],'requests');self.s['planning_bypass']={str(DAY)+'|'+str(DAY):{'actor':'p1','reason':'Sonra değerlendirilecek'}};save_keys(self.s);assert_can_plan(self.s)

class StatusTests(Base):
 def setup_status(self,days=1):
  cfg=dict(defaults(),enabled=True,shrinkage_included=True,automatic=True)
  for rule in cfg['groups'].values():rule.update(meal_minutes=30,break_minutes=15,break_total_minutes=30,break_per_hour_max=15,coaching_monthly_minutes=60,coaching_chunk_minutes=15)
  self.s['status_rules']=cfg;coverage=pd.concat([demand(slots=range(1,49)).assign(Tarih=DAY+timedelta(days=i)) for i in range(days)],ignore_index=True);coverage['İhtiyaç']=5;coverage['Atanan']=5;coverage['Eksik']=0;coverage['Fazla']=0
  rows=[row(day=DAY+timedelta(days=i),start='08:00',end='17:00') for i in range(days)];return rows,coverage
 def test_statuses_inside_shrinkage_do_not_double_count(self):
  rows,coverage=self.setup_status();items,out,issues=meal_plan(self.s,rows,coverage,[emp()]);self.assertTrue(any(x['kind']=='Yemek' for x in items));self.assertTrue(any(x['kind']=='Mola' for x in items));self.assertTrue(any(x['kind']=='Koçluk' for x in items));self.assertEqual(out.Eksik.sum(),0);self.assertGreater(out['Mola kaybı'].sum(),0)
 def test_status_loss_above_budget_is_counted(self):
  rows,coverage=self.setup_status();self.s['staffing_parameters']={'shrinkage':0};self.s['status_rules']['automatic']=False;items,out,issues=meal_plan(self.s,rows,coverage,[emp()]);self.assertGreater(out.Eksik.sum(),0)
 def test_meals_breaks_and_coaching_fit_shift_without_overlap(self):
  rows,coverage=self.setup_status();items,out,issues=meal_plan(self.s,rows,coverage,[emp()]);ordered=sorted(items,key=lambda x:x['start']);a=pd.Timestamp(DAY)+pd.Timedelta(hours=8);b=a+pd.Timedelta(hours=9)
  for p in ordered:self.assertLessEqual(a,pd.Timestamp(p['start']));self.assertLessEqual(pd.Timestamp(p['end']),b)
  for first,second in zip(ordered,ordered[1:]):self.assertLessEqual(pd.Timestamp(first['end']),pd.Timestamp(second['start']))
 def test_monthly_coaching_is_one_hour_in_fragments(self):
  rows,coverage=self.setup_status(days=6);items,_,issues=meal_plan(self.s,rows,coverage,[emp()]);coaching=[p for p in items if p['kind']=='Koçluk'];self.assertEqual(len(coaching),4);self.assertEqual(sum((pd.Timestamp(p['end'])-pd.Timestamp(p['start'])).total_seconds()/60 for p in coaching),60)
 def test_previously_published_coaching_reduces_remaining_target(self):
  rows,coverage=self.setup_status(days=5)
  from ortak.mola_servisi import init
  init(self.s['workspace_db_path'])
  with connect(self.s['workspace_db_path']) as db:db.execute('INSERT INTO planned_breaks VALUES(?,?,?)',('old','pub',dumps({'employee_id':'1','kind':'Koçluk','start':str(pd.Timestamp(DAY)-pd.Timedelta(days=1)+pd.Timedelta(hours=12)),'end':str(pd.Timestamp(DAY)-pd.Timedelta(days=1)+pd.Timedelta(hours=12,minutes=30))})))
  items,_,__=meal_plan(self.s,rows,coverage,[emp()]);self.assertEqual(sum((pd.Timestamp(p['end'])-pd.Timestamp(p['start'])).total_seconds()/60 for p in items if p['kind']=='Koçluk'),30)
 def test_empty_status_cell_has_clear_validation(self):
  from modules.statu_kurallari import validate
  rows,coverage=self.setup_status();cfg=self.s['status_rules'];cfg['groups']['fulltime']['break_rules']=[{'min_hours':None,'max_hours':4,'minutes':15}]
  with self.assertRaisesRegex(ValueError,'boş'):validate(cfg)
 def test_cached_status_plan_is_not_mutable_and_reacts_to_new_shrinkage(self):
  rows,coverage=self.setup_status();first=meal_plan(self.s,rows,coverage,[emp()]);first[1].loc[0,'Atanan']=999;again=meal_plan(self.s,rows,coverage,[emp()]);self.assertNotEqual(again[1].loc[0,'Atanan'],999)
  self.s['staffing_parameters']={'shrinkage':0};changed=meal_plan(self.s,rows,coverage,[emp()]);self.assertGreater(changed[1].Eksik.sum(),again[1].Eksik.sum())
 def test_selected_work_durations_survive_rule_enforcement(self):
  from ortak.varsayilan_kurallar import enforce_current_rules
  self.s['shift_rules']['work_type']['dis_kaynak'].update(duration_custom=True,shift_total_hours=8.5);enforce_current_rules(self.s);self.assertEqual(self.s['shift_rules']['work_type']['dis_kaynak']['shift_total_hours'],8.5)

class NotificationTests(Base):
 def test_agent_only_sees_own_requests_and_read_state_is_private(self):
  from ortak.talep_servisi import create_request
  from ortak.bildirimler import items,mark_read
  self.s['profile']={'position':'agent','username':'u1','employee_id':'1','team_lead':'Lead'};create_request(self.s,{'type':'Yıllık İzin Talebi','start_date':str(DAY)});first=items(self.s);self.assertTrue(first);mark_read(self.s,first[0]['id']);self.assertTrue(items(self.s)[0]['Okundu']);self.s['profile']={'position':'agent','username':'u2','employee_id':'2','team_lead':'Lead'};self.assertFalse(items(self.s))
  with self.assertRaises(ValueError):mark_read(self.s,first[0]['id'])

class NotificationReplyTests(Base):
 def test_anonymous_owner_receives_reply_in_private_inbox(self):
  from ortak.gorusler import submit as send,reply
  from ortak.bildirimler import items
  self.s['profile']={'position':'agent','username':'u1','employee_id':'1'};ident=send(self.s,'Şikâyet','İçerik',True);self.planner('p1');reply(self.s,ident,'İnceleme tamamlandı');self.s['profile']={'position':'agent','username':'u1','employee_id':'1'};self.assertTrue(any(x['İçerik']=='İnceleme tamamlandı' for x in items(self.s)));self.s['profile']={'position':'agent','username':'u2','employee_id':'2'};self.assertFalse(items(self.s))
 def test_published_statuses_are_visible_after_last_required_approval(self):
  from ortak.mola_servisi import records
  result=draft(self.s);result['breaks']=[{'employee_id':'1','date':str(DAY),'kind':'Yemek','start':str(DAY)+' 12:00:00','end':str(DAY)+' 12:30:00','status':'Planlı'}];ident=submit(self.s,result);vote(self.s,ident);self.assertFalse(records(self.s));self.planner('p2');vote(self.s,ident);self.assertEqual(records(self.s)[0]['kind'],'Yemek')
