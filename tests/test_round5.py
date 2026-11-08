import copy,os,sqlite3,tempfile,unittest
from pathlib import Path
from datetime import timedelta,datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch,Mock
import pandas as pd
import numpy as np
from streamlit.testing.v1 import AppTest
from test_planning import DAY,demand,emp,row,rules
from test_round4 import profile_frame
from core.workspace_store import init_db,connect,save_keys,loads
from core.personel_deposu import ensure_identity,list_people
from core.personel_is_akisi import submit,decide,proposals
from core.roller_ve_yetkiler import init_governance,save_permissions,permissions
from core.vardiya_degisimleri import apply_changes,validate_changes,check_conservation
from core.request_assignments import resolve_swap


def make_state(path,auth):
 init_db(path)
 with sqlite3.connect(auth) as db:
  db.executescript('CREATE TABLE employees(employee_id INTEGER PRIMARY KEY,full_name TEXT,team_lead TEXT,manager TEXT,location TEXT,work_type TEXT,position TEXT,language TEXT);CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,password_hash TEXT,employee_id INTEGER,is_active INTEGER);')
  db.executemany('INSERT INTO employees VALUES(?,?,?,?,?,?,?,?)',[(1,'Person A','Lead','Manager','Ankara','fulltime','agent','tr'),(2,'Person B','Lead','Manager','Ankara','fulltime','agent','tr'),(3,'Person C','Other','Manager','Ankara','fulltime','agent','tr')])
  db.executemany('INSERT INTO users(username,password_hash,employee_id,is_active) VALUES(?,?,?,?)',[(f'u{i}','!none',i,1) for i in [1,2,3]])
 ensure_identity(auth)
 with sqlite3.connect(auth) as db:db.execute("UPDATE employees SET sicil_no='SC001' WHERE employee_id=1")
 state={'workspace_db_path':str(path),'auth_db_path':str(auth),'profile':{'position':'tl','username':'lead','full_name':'Lead','manager':'Manager'},'shift_rules':rules(),'plan_ctx':{'start':DAY,'end':DAY+timedelta(days=1)},'plan_ctx_confirmed':True,'sp_staffing_result_df':demand(days=2),'planning_languages':{'tr':True,'en':True,'ar':True}}
 state['employees_cache']=[p for p in list_people(state) if p['position']=='agent'];return state


class WorkflowTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name);self.s=make_state(self.path/'w.db',self.path/'auth.db')
 def tearDown(self):self.temp.cleanup()
 def addition(self):return submit(self.s,'Ekleme',{'full_name':'New Agent','username':'new.user','sicil_no':'NEW900','work_type':'akademi','language':'en','location':'Ankara','effective_date':'2026-11-09'},'Yeni işe alım')
 def manager(self):self.s['profile']={'position':'manager','username':'manager','full_name':'Manager'}
 def planner(self):self.s['profile']={'position':'wfm','username':'planner','full_name':'Planning'}
 def test_three_stage_addition_and_password_never_in_audit(self):
  item=self.addition();self.assertEqual(item['stage'],'Yönetici onayı')
  self.manager();item=decide(self.s,item,True,'Uygun');self.assertEqual(item['stage'],'Planlama onayı')
  with self.assertRaises(ValueError):decide(self.s,item,True)
  self.planner();item=decide(self.s,item,True,'Tamam','DemoPass#900')
  self.assertEqual(item['stage'],'Tamamlandı');person=next(p for p in list_people(self.s) if p['username']=='new.user');self.assertEqual(person['sicil_no'],'NEW900')
  with sqlite3.connect(self.s['auth_db_path']) as db:hashed=db.execute("SELECT password_hash FROM users WHERE username='new.user'").fetchone()[0]
  from passlib.context import CryptContext
  self.assertTrue(CryptContext(schemes=['pbkdf2_sha256']).verify('DemoPass#900',hashed))
  with connect(self.s['workspace_db_path']) as db:
   text=' '.join(r[0] for r in db.execute('SELECT payload FROM audit_events'))
  self.assertNotIn('DemoPass#900',text)
 def test_wrong_manager_and_stale_version_are_rejected(self):
  item=self.addition();self.s['profile']={'position':'manager','username':'wrong','full_name':'Wrong'}
  with self.assertRaises(ValueError):decide(self.s,item,True)
  self.manager();decide(self.s,item,True)
  with self.assertRaises(ValueError):decide(self.s,item,True)
 def test_short_password_rolls_back_both_databases(self):
  item=self.addition();self.manager();item=decide(self.s,item,True);self.planner()
  with self.assertRaises(ValueError):decide(self.s,item,True,password='short')
  self.assertFalse(any(p['username']=='new.user' for p in list_people(self.s)))
  self.assertEqual(proposals(self.s)[0]['stage'],'Planlama onayı')
 def test_departure_preserves_history_and_disables_account(self):
  self.s['published_shift_plan']=[row()];save_keys(self.s)
  date=datetime.now(ZoneInfo('Europe/Istanbul')).date().isoformat()
  item=submit(self.s,'Ayrılma',{'employee_id':'1','effective_date':date},'İstifa')
  self.manager();item=decide(self.s,item,True);self.planner();decide(self.s,item,True)
  self.assertFalse(any(str(p['employee_id'])=='1' for p in list_people(self.s)))
  self.assertTrue(any(str(p['employee_id'])=='1' for p in list_people(self.s,True)))
  self.assertEqual(self.s['published_shift_plan'],[row()])
 def test_team_leader_cannot_remove_other_team(self):
  with self.assertRaises(ValueError):submit(self.s,'Ayrılma',{'employee_id':'3','effective_date':'2026-12-01'},'Test')
 def test_only_planning_can_manage_permissions_and_report_stays_lead_only(self):
  self.manager()
  with self.assertRaises(ValueError):save_permissions(self.s,'tl',['rapor_gir'],'Test')
  self.planner()
  with self.assertRaises(ValueError):save_permissions(self.s,'manager',['rapor_gir'],'Test')
  save_permissions(self.s,'tl',['rapor_gir'],'Sadece rapor')
  self.s['profile']={'position':'tl'};self.assertEqual(permissions(self.s),{'rapor_gir'})


class RosterChangeTests(WorkflowTests):
 def setUp(self):
  super().setUp()
  self.old=[row('1',DAY,'OFF',None,None),row('2',DAY,'WORK','08:00','17:00'),row('1',DAY+timedelta(days=1),'WORK','08:00','17:00'),row('2',DAY+timedelta(days=1),'OFF',None,None)]
  self.s['published_shift_plan']=copy.deepcopy(self.old);save_keys(self.s)
 def balanced(self):
  return [dict(r,shift_code='WORK' if r['shift_code']=='OFF' else 'OFF',start='08:00' if r['shift_code']=='OFF' else None,end='17:00' if r['shift_code']=='OFF' else None) for r in self.old]
 def test_two_day_off_exchange_is_saved_with_old_new_actor_and_reason(self):
  ident=apply_changes(self.s,self.balanced(),'Vardiya değişimi','OFF dengeli değişim')
  check_conservation(self.old,self.s['published_shift_plan'])
  with connect(self.s['workspace_db_path']) as db:payload=loads(db.execute('SELECT payload FROM shift_change_batches WHERE id=?',(ident,)).fetchone()[0])
  self.assertEqual(payload['actor'],'lead');self.assertEqual(payload['reason'],'OFF dengeli değişim');self.assertEqual(len(payload['before']),4);self.assertEqual(len(payload['after']),4)
 def test_single_day_off_exchange_rejected_without_any_write(self):
  with self.assertRaises(ValueError):apply_changes(self.s,self.balanced()[:2],'Vardiya değişimi','Tek gün')
  self.assertEqual(self.s['published_shift_plan'],self.old)
  with connect(self.s['workspace_db_path']) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM shift_change_batches').fetchone()[0],0)
 def test_missing_reason_and_other_team_rejected(self):
  with self.assertRaises(ValueError):apply_changes(self.s,self.balanced(),'Vardiya değişimi','')
  self.s['employees_cache'][1]['team_lead']='Other'
  with self.assertRaises(ValueError):apply_changes(self.s,self.balanced(),'Vardiya değişimi','Başka ekip')
 def test_report_only_team_leader_and_attendance_is_separate_type(self):
  changed=dict(self.old[1],shift_code='RAPOR',start=None,end=None)
  self.manager()
  with self.assertRaises(ValueError):apply_changes(self.s,[changed],'Rapor','Rapor')
  self.s['profile']={'position':'tl','username':'lead','full_name':'Lead'}
  apply_changes(self.s,[changed],'Rapor','Sağlık raporu')
  self.assertEqual(next(r for r in self.s['published_shift_plan'] if r['employee_id']=='2' and r['date']==str(DAY))['shift_code'],'RAPOR')
 def test_early_departure_is_logged_and_keeps_work_status(self):
  changed=dict(self.old[1],end='16:00')
  apply_changes(self.s,[changed],'Erken çıkış','Onaylı erken çıkış')
  row=next(r for r in self.s['published_shift_plan'] if r['employee_id']=='2' and r['date']==str(DAY))
  self.assertEqual(row['shift_code'],'WORK');self.assertEqual(row['end'],'16:00');self.assertTrue(row['attendance_adjusted'])
 def test_agent_preview_balances_two_off_days_and_rejects_one_day(self):
  request={'id':'preview','employee_id':'1','start_date':str(DAY),'end_date':str(DAY+timedelta(days=1)),'targets':[{'employee_id':'2'}],'swap_dates':[str(DAY),str(DAY+timedelta(days=1))]}
  self.assertEqual(len(resolve_swap(self.s,request)),4)
  request['swap_dates']=[str(DAY)]
  with self.assertRaises(ValueError):resolve_swap(self.s,request)


class PlanningRulesTests(unittest.TestCase):
 def test_forecast_view_uses_same_due_dates_and_november_tenth_is_not_due(self):
  from modules.shift_planner.forecast_view import _compute_son_odeme_flag
  from core.billing_calendar import billing_flag
  dates=pd.Series(pd.date_range('2026-11-01','2026-11-30'))
  pd.testing.assert_series_equal(_compute_son_odeme_flag(dates),billing_flag(dates,'due'))
  self.assertEqual(_compute_son_odeme_flag(pd.Series(pd.to_datetime(['2026-11-09','2026-11-10']))).tolist(),[1,0])
 def test_summer_ignores_classes_and_holiday_ignores_exam(self):
  from test_round4 import state
  from modules.shift_planing.planning_data import collect_inputs
  s=state();s['employees_cache']=[dict(emp(group='akademi'),language='tr')];day=pd.Timestamp('2026-07-06').date();s['plan_ctx']={'start':day,'end':day}
  s['acad_schedules']={'u1':{'2026-Bahar':{'Saat':['08:00-10:00'],'Pazartesi':['Class']}}}
  self.assertFalse(collect_inputs(s)[3])
  s['shift_rules']['school']={'summer_months':[],'holiday_priority':True};self.assertTrue(collect_inputs(s)[3])
  day=pd.Timestamp('2026-03-20').date();s['plan_ctx']={'start':day,'end':day};s['acad_exam_calendar']={'u1':{'2026-Sinav':{'Tarih':[str(day)],'Saat':['10:00'],'Ders':['Exam']}}}
  self.assertFalse(collect_inputs(s)[3]);s['shift_rules']['school']['holiday_priority']=False;self.assertTrue(collect_inputs(s)[3])
 def test_off_distribution_leaves_some_sunday_capacity(self):
  from modules.shift_planing.engine import generate_plan
  r=rules();r['off_rules']={'distribution':'İhtiyaca göre dağıt'};r['work_type']['fulltime'].update(min_off_days=2,max_consecutive_days=5)
  staff=[emp(str(i)) for i in range(1,5)]
  df=demand(days=7,count=4);df.loc[pd.to_datetime(df.Tarih).dt.weekday==5,'Planlanan Agent']=0;df.loc[pd.to_datetime(df.Tarih).dt.weekday==6,'Planlanan Agent']=2
  result=generate_plan(staff,df,r,list(r['work_type']),DAY,DAY+timedelta(days=6))
  sunday=result['coverage'][pd.to_datetime(result['coverage'].Tarih).dt.weekday==6]
  self.assertGreater(sunday.Atanan.sum(),0)
  self.assertFalse(result['issues'])
 def test_shortage_extension_proposal_respects_academy_maximum(self):
  from test_round4 import state
  from core.eksik_aksiyonlari import suggestions
  s=state();s['employees_cache']=[dict(emp(group='akademi'),language='tr')];s['plan_ctx']={'start':DAY,'end':DAY};s['sp_staffing_result_df']=demand(slots=range(17,31));s['draft_shift_plan']=[row(start='08:00',end='12:00',source='auto')]
  options,rejected=suggestions(s,str(DAY),25,30)
  self.assertTrue(options);self.assertEqual(options[0]['row']['end'],'15:00');self.assertEqual(options[0]['gain'],3)
 def test_future_employee_cannot_work_before_start_or_after_end(self):
  from modules.shift_planing.engine import generate_plan
  person=emp();person['employment_start']=str(DAY+timedelta(days=1))
  result=generate_plan([person],demand(),rules(),list(rules()['work_type']),DAY,DAY)
  self.assertEqual(result['plan'][0]['shift_code'],'OFF')


class UIExpansionTests(unittest.TestCase):
 def test_period_accepts_two_weeks_or_three_days(self):
  at=AppTest.from_string('from modules.shift_planing.period import render\nrender()');at.session_state['sp_staffing_result_df']=demand(days=14);at.run();self.assertFalse(at.exception)
  control=at.date_input[0];control.set_value((DAY,DAY+timedelta(days=13))).run();at.button(key='vp_confirm').click().run()
  self.assertEqual(at.session_state['plan_ctx']['end'],DAY+timedelta(days=13))
  at.date_input[0].set_value((DAY,DAY+timedelta(days=2))).run();self.assertEqual(at.session_state['plan_ctx']['end'],DAY+timedelta(days=2));self.assertFalse(at.exception)
 def test_staffing_does_not_truncate_two_week_forecast(self):
  from modules.shift_planner.staffing_forecast import render
  at=AppTest.from_string('from modules.shift_planner.staffing_forecast import render\nrender()',default_timeout=60)
  at.session_state['sp_forecast_df']=pd.DataFrame({'tarih':pd.date_range(DAY,periods=14),'y_pred':[100.]*14});at.session_state['sp_active_ratio_profile_df']=profile_frame(DAY);at.session_state['sp_forecast_meta']={'model_name':'Test'};at.run()
  next(b for b in at.button if 'Personel İhtiyacını Hesapla' in b.label).click().run()
  self.assertFalse(at.exception);self.assertEqual(pd.to_datetime(at.session_state['sp_staffing_result_df'].Tarih).nunique(),14)

if __name__=='__main__':unittest.main()
