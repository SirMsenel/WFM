import tempfile
import unittest
from pathlib import Path
from datetime import timedelta,time
import pandas as pd
from streamlit.testing.v1 import AppTest
from test_planning import DAY,demand,emp,row,rules
from modules.shift_planing.engine import generate_plan,bounds
from modules.shift_planing.planning_data import collect_inputs
from core.planning import preview_plan,calendar_grid
from core.planning_ui import shortage_matrix,blocking_issues
from core.defaults import default_shift_rules
from core.rule_service import apply_rules
from core.workspace_store import init_db,hydrate
from core.work_hours import overlap_hours,save_target

class Round2LogicTests(unittest.TestCase):
 def state(self):return {'employees_cache':[dict(emp(),language='tr'),dict(emp('2'),language='en'),dict(emp('3'),language='ar')],'shift_rules':rules(),'plan_ctx':{'start':DAY,'end':DAY},'sp_staffing_result_df':demand()}
 def test_every_group_has_11_hour_rest_even_when_not_in_rules(self):
  for group in rules()['work_type']:
   r=rules();r['work_type'][group].pop('min_rest_hours',None)
   history=[row(day=DAY-timedelta(days=1),start='16:00',end='23:00')]
   result=generate_plan([emp(group=group)],demand(slots=range(17,41)),r,list(r['work_type']),DAY,DAY,history=history)
   work=[x for x in result['plan'] if bounds(x)]
   self.assertTrue(work)
   self.assertTrue(all(bounds(x)[0].hour>=10 for x in work))
 def test_night_uses_separate_night_duration_and_apply_is_persistent(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.state();s.update(workspace_db_path=str(Path(d)/'db'),fixed_shift_records=[row(code='GECE',start='00:00',end='07:00')])
   init_db(s['workspace_db_path']);r=default_shift_rules()
   self.assertEqual(apply_rules(s,r,True),1)
   self.assertEqual(s['fixed_shift_records'][0]['end'],'08:00')
   restored={};hydrate(restored,s['workspace_db_path']);self.assertEqual(restored['fixed_shift_records'][0]['end'],'08:00')
   r['night']['normal']={}
   result=generate_plan([emp(group='akademi')],demand(slots=range(1,17)),r,list(r['work_type']),DAY,DAY,fixed=[s['fixed_shift_records'][0]],auto_fill=False)
   self.assertFalse(result['issues'])
   self.assertEqual(result['coverage'].Atanan.sum(),16)
 def test_language_switches_filter_independently_and_ignore_excluded_sources(self):
  s=self.state();s['fixed_shift_records']=[row(eid='2')];s['planning_languages']={'en':False,'ar':True}
  staff,fixed,_,_,issues=collect_inputs(s)
  self.assertEqual([e['employee_id'] for e in staff],['1','3']);self.assertFalse(fixed);self.assertFalse(issues)
  s['planning_languages']={'en':True,'ar':False}
  self.assertEqual([e['employee_id'] for e in collect_inputs(s)[0]],['1','2'])
 def test_excluded_language_does_not_count_old_auto_or_night_quota(self):
  s=self.state();s['planning_languages']={'en':False,'ar':False};s['draft_shift_plan']=[row(eid='2',source='auto')]
  s['shift_rules']['night'].update(normal={'tr':0,'en':1,'ar':1},mode='normal')
  result=preview_plan(s,True)
  self.assertEqual(result['coverage'].Atanan.sum(),0);self.assertFalse(result['issues'])
 def test_period_budget_stops_automatic_assignment(self):
  r=rules();targets=[{'group':'fulltime','start':str(DAY),'end':str(DAY+timedelta(days=6)),'hours':9}]
  result=generate_plan([emp()],demand(days=2),r,list(r['work_type']),DAY,DAY+timedelta(days=1),hour_targets=targets)
  self.assertEqual(sum(x['shift_code']=='WORK' for x in result['plan']),1)
  self.assertEqual(result['coverage'].Fazla.sum(),0)
 def test_hours_clip_overnight_to_selected_dates(self):
  x=row(start='22:00',end='02:00')
  self.assertEqual(overlap_hours(x,DAY,DAY),2)
  self.assertEqual(overlap_hours(x,DAY+timedelta(days=1),DAY+timedelta(days=1)),2)
 def test_matrix_has_day_names_and_distinguishes_missing_data(self):
  result=preview_plan(self.state());m=shortage_matrix(result['coverage'],DAY)
  self.assertEqual(m.shape,(48,7));self.assertIn('Pazartesi',m.columns[0]);self.assertTrue(pd.isna(m.iloc[0,0]));self.assertEqual(m.iloc[16,0],1)
  grid=calendar_grid(result,{'start':DAY,'end':DAY});self.assertIn('Pazartesi',grid.columns[1])
 def test_night_quota_is_warning_rest_is_blocker(self):
  result={'issues':[{'Sorun':'Gece EN: 1 gerekli, 0 kesin kayıt var'},{'Sorun':'Minimum dinlenme süresi sağlanmıyor'}]}
  self.assertEqual(len(blocking_issues(result)),1)

 def test_rule_apply_only_changes_selected_dates_and_keeps_outside_hours(self):
  s=self.state();s['fixed_shift_records']=[{'id':'night','employee_id':'1','shift_code':'GECE','start':'00:00','end':'07:00','start_date':str(DAY-timedelta(days=1)),'end_date':str(DAY+timedelta(days=1))}]
  apply_rules(s,default_shift_rules(),True)
  rows=s['fixed_shift_records'];self.assertEqual(len(rows),3)
  current=next(r for r in rows if r['start_date']==str(DAY))
  self.assertEqual(current['end'],'08:00')
  self.assertTrue(all(r['end']=='07:00' for r in rows if r!=current))
 def test_budget_includes_fixed_hours_earlier_in_month(self):
  from core.work_hours import save_target
  s=self.state();s['group_hour_targets']=[{'group':'fulltime','start':'2026-10-01','end':'2026-11-30','hours':9}]
  s['fixed_shift_records']=[row(day=DAY-timedelta(days=20))]
  staff,fixed,history,unavailable,issues=collect_inputs(s)
  result=generate_plan([staff[0]],demand(),rules(),list(rules()['work_type']),DAY,DAY,fixed=fixed,hour_targets=s['group_hour_targets'])
  self.assertEqual(result['plan'][0]['shift_code'],'OFF')

class Round2UITests(unittest.TestCase):
 def app(self,code):
  at=AppTest.from_string(code,default_timeout=30)
  s=Round2LogicTests().state();s.update(profile={'position':'wfm'},plan_ctx_confirmed=True,plan_group_priority=list(rules()['work_type']))
  for k,v in s.items():at.session_state[k]=v
  at.run();self.assertFalse(at.exception);return at
 def test_click_priority_and_publication_with_informative_warning(self):
  at=self.app('from modules.shift_planing.publish import render\nrender()')
  at.button(key='priority_reset').click().run()
  self.assertTrue(at.button(key='planning_generate').disabled)
  for group in ['akademi','dis_kaynak','fulltime']:at.button(key='priority_add_'+group).click().run()
  self.assertEqual(at.session_state['plan_group_priority'],['akademi','dis_kaynak','fulltime'])
  at.session_state['shift_rules']['night'].update(normal={'en':1},mode='normal')
  at.button(key='planning_generate').click().run();self.assertFalse(at.exception)
  self.assertTrue(at.button(key='planning_publish').disabled)
  at.checkbox(key='planning_accept_warnings').check().run()
  self.assertFalse(at.button(key='planning_publish').disabled)
  at.button(key='planning_publish').click().run();self.assertFalse(at.exception)
  self.assertTrue(at.session_state['published_shift_plan'])
 def test_rules_are_only_applied_on_save(self):
  at=self.app('from modules.shift_planing.current_plan import render\nrender()')
  at.session_state['shift_rules']=default_shift_rules();at.session_state['nav_current_plan_v2']='Mesai Kuralları';at.run()
  self.assertFalse(at.exception)
  at.time_input(key='rule_night_window_end').set_value(time(9)).run()
  self.assertEqual(at.session_state['shift_rules']['general']['night_window_end'],'08:00')
  at.button(key='rules_apply').click().run();self.assertFalse(at.exception)
  self.assertEqual(at.session_state['shift_rules']['general']['night_window_end'],'09:00')
 def test_publication_preserves_excluded_language_records(self):
  at=self.app('from modules.shift_planing.publish import render\nrender()')
  at.session_state['published_shift_plan']=[row(eid='2',start='09:00',end='18:00',source='auto')]
  at.toggle(key='planning_include_en').set_value(False).run()
  at.button(key='planning_generate').click().run();self.assertFalse(at.exception)
  self.assertFalse(at.button(key='planning_publish').disabled)
  at.button(key='planning_publish').click().run();self.assertFalse(at.exception)
  self.assertEqual(next(r for r in at.session_state['published_shift_plan'] if r['employee_id']=='2')['start'],'09:00')
 def test_work_hour_target_screen_save(self):
  at=self.app('from core.work_hours_ui import render_targets\nimport streamlit as st\nrender_targets(st.session_state)')
  at.button(key='hour_target_save').click().run();self.assertFalse(at.exception)
  self.assertEqual(at.session_state['group_hour_targets'][0]['hours'],180)

if __name__=='__main__':unittest.main()
