import copy,tempfile,unittest
from pathlib import Path
from datetime import timedelta,time
import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest
from test_planning import DAY,demand,emp,row,rules
from test_improvements import intervals
from core.manual_assignments import prepare_manual
from core.planning import preview_plan
from core.planning_ui import shortage_matrix,issue_table
from core.interval_service import build_weekly_distribution
from core.workspace_store import init_db,hydrate
from modules.shift_planing.engine import generate_plan,bounds
from modules.shift_planner.history_comparison import grouped_rolling

class Round3LogicTests(unittest.TestCase):
 def state(self,group='akademi',days=1):
  return {'employees_cache':[emp(group=group)],'shift_rules':rules(),'sp_staffing_result_df':demand(days=days),
          'plan_ctx':{'start':DAY,'end':DAY+timedelta(days=days-1)}}
 def test_approved_general_request_does_not_block_roster(self):
  from modules.shift_planing.planning_data import collect_inputs
  s=self.state();s['trk_requests']=[{'id':'g','created_by':'u1','type':'Genel Talep','status':'Onaylandı','queue':'Closed','note':'Bilgilendirme'}]
  self.assertFalse(collect_inputs(s)[4])
 def test_manual_rejects_academy_10_hours_before_saving(self):
  for code in ['WORK','MESAI']:
   state=self.state();original=copy.deepcopy(state)
   added,errors=prepare_manual(state,['1'],DAY,DAY,code,time(8),time(18))
   self.assertFalse(added);self.assertTrue(any('en fazla 7 saat' in r['Neden yazılmadı?'] for r in errors))
   self.assertNotIn('draft_shift_plan',state)
 def test_filled_manual_auto_and_published_days_are_never_overwritten(self):
  for key,source in [('draft_shift_plan','manual_single'),('draft_shift_plan','auto')]:
   state=self.state(days=2);state[key]=[row(source=source)]
   added,errors=prepare_manual(state,['1'],DAY,DAY+timedelta(days=1),'WORK',time(8))
   self.assertEqual([r['date'] for r in added],[str(DAY+timedelta(days=1))])
   self.assertEqual(errors[0]['Tarih'],str(DAY));self.assertIn('dolu',errors[0]['Neden yazılmadı?'])
 def test_automatic_off_placeholder_can_be_filled(self):
  state=self.state();state['draft_shift_plan']=[row(source='auto',code='OFF',start=None,end=None)]
  added,errors=prepare_manual(state,['1'],DAY,DAY,'WORK',time(8))
  self.assertEqual(len(added),1);self.assertFalse(errors)
 def test_manual_rest_and_exam_prevent_work(self):
  state=self.state();state['published_shift_plan']=[row(day=DAY-timedelta(days=1),start='17:00',end='23:00')]
  added,errors=prepare_manual(state,['1'],DAY,DAY,'WORK',time(8))
  self.assertFalse(added);self.assertTrue(any('dinlenme' in r['Neden yazılmadı?'] for r in errors))
  state=self.state();state['acad_exam_calendar']={'u1':{'2026-Sinav':{'Tarih':[str(DAY)],'Ders':['Exam']}}}
  added,errors=prepare_manual(state,['1'],DAY,DAY,'WORK',time(8))
  self.assertFalse(added);self.assertTrue(errors)
 def test_consecutive_limit_applies_across_iso_week_boundary(self):
  r=rules();r['work_type']['fulltime']['max_consecutive_days']=2
  history=[row(day=DAY-timedelta(days=i)) for i in [1,2]]
  result=generate_plan([emp()],demand(),r,list(r['work_type']),DAY,DAY,history=history)
  self.assertEqual(result['plan'][0]['shift_code'],'OFF')
 def test_manual_bulk_never_creates_seven_consecutive_days(self):
  s=self.state(days=8)
  added,errors=prepare_manual(s,['1'],DAY,DAY+timedelta(days=7),'WORK',time(8))
  days={pd.Timestamp(r['date']).date() for r in added}
  self.assertEqual(len(added),7);self.assertNotIn(DAY+timedelta(days=6),days)
  self.assertTrue(any('Üst üste' in e['Neden yazılmadı?'] or 'Haftalık' in e['Neden yazılmadı?'] for e in errors))
 def test_excluded_early_slots_are_not_missing_or_counted_in_matrix(self):
  r=rules();result=generate_plan([emp()],demand(slots=range(7,17)),r,list(r['work_type']),DAY,DAY,exclude_early_hours=True)
  self.assertEqual(result['coverage'].Eksik.sum(),0)
  self.assertEqual(result['coverage']['Ham Eksik'].sum(),10)
  self.assertFalse(result['coverage']['Sayaca Dahil'].any())
  self.assertTrue(shortage_matrix(result['coverage'],DAY).iloc[6:16,0].isna().all())
 def test_0700_entry_survives_effective_counter_exclusion(self):
  r=rules();r['boosts']={'weekday_0700_fulltime_extra_enabled':True,'weekday_0700_fulltime_extra_count':1}
  result=generate_plan([emp()],demand(slots=range(15,33)),r,list(r['work_type']),DAY,DAY,exclude_early_hours=True)
  self.assertEqual(result['plan'][0]['start'],'07:00');self.assertEqual(result['coverage'].Eksik.sum(),0)
 def test_conflict_table_shows_person_date_shift_and_required_duration(self):
  s=self.state();s['fixed_shift_records']=[row(start='08:00',end='18:00')]
  result=preview_plan(s);table=issue_table(result)
  self.assertIn('Mevcut vardiya',table);self.assertIn('Olması gereken',table)
  self.assertEqual(table.iloc[0]['Personel'],'Person 1');self.assertIn('08:00–18:00',table.iloc[0]['Mevcut vardiya'])
  self.assertIn('7 saat',table.iloc[0]['Olması gereken'])
 def test_rolling_never_mixes_weekdays_and_weekends(self):
  dates=pd.date_range('2026-10-01',periods=45)
  out=grouped_rolling(pd.DataFrame({'tarih':dates,'cagri_sayisi':np.where(dates.weekday<5,100.,1000.)}))
  for col in ['7 günlük hareketli ortalama','30 günlük hareketli ortalama']:
   self.assertTrue((out.loc[out['Gün türü']=='Hafta içi',col]==100).all())
   self.assertTrue((out.loc[out['Gün türü']=='Hafta sonu',col]==1000).all())
 def test_iqr_holdout_actuals_remain_raw_and_training_is_leakage_free(self):
  raw=intervals();first=build_weekly_distribution(raw,'2026-11-09',use_iqr=True)
  raw.loc[(raw.tarih>='2026-11-02')&(raw.slot==48),'cagri_sayisi']*=200
  second=build_weekly_distribution(raw,'2026-11-09',use_iqr=True)
  for name,frame in first['validation_window_profiles'].items():pd.testing.assert_frame_equal(frame,second['validation_window_profiles'][name])
  self.assertFalse(first['actual_validation'].equals(second['actual_validation']))
  self.assertTrue(first['meta']['iqr_used']);self.assertTrue(np.allclose(second['profile'].groupby('Gün')['Oran(%)'].sum(),100))

class Round3UITests(unittest.TestCase):
 def app(self,code):
  at=AppTest.from_string(code,default_timeout=30)
  s=Round3LogicTests().state();s.update(profile={'position':'wfm'},plan_ctx_confirmed=True)
  for k,v in s.items():at.session_state[k]=v
  at.run();self.assertFalse(at.exception);return at
 def test_manual_ui_rejects_duration_and_supports_groups(self):
  at=self.app('from modules.shift_planing.shift_hours import render\nrender()')
  at.radio(key='manual_pick_mode').set_value('Grup seç').run()
  at.multiselect(key='manual_groups').select('akademi').run()
  at.checkbox(key='manual_custom_end_v2').check().run()
  self.assertTrue(at.button(key='manual_place').disabled)
  at.time_input(key='manual_finish_WORK').set_value(time(15)).run()
  self.assertFalse(at.button(key='manual_place').disabled)
  at.button(key='manual_place').click().run();self.assertFalse(at.exception)
  self.assertEqual(at.session_state['draft_shift_plan'][0]['end'],'15:00')
  self.assertTrue(at.button(key='manual_place').disabled)
  self.assertTrue(at.warning)
 def test_gap_accept_button_publishes_persistently_and_shows_grid(self):
  with tempfile.TemporaryDirectory() as d:
   at=self.app('from modules.shift_planing.publish import render\nrender()')
   path=str(Path(d)/'state.db');init_db(path);at.session_state['workspace_db_path']=path
   at.session_state['sp_staffing_result_df']=demand(count=3)
   at.button(key='planning_generate').click().run();self.assertFalse(at.exception)
   self.assertEqual(at.button(key='planning_publish').label,'Eksikleri Kabul Et ve Planı Yayınla')
   at.button(key='planning_publish').click().run();self.assertFalse(at.exception)
   loaded={};hydrate(loaded,path);self.assertEqual([{k:v for k,v in r.items() if k not in {'language','publication_id'}} for r in loaded['published_shift_plan']],at.session_state['planning_result']['plan'])
   self.assertTrue(any('Yayınlanan Vardiya Tablosu' in m.value for m in at.markdown))
 def test_historical_hours_date_picker_is_independent_of_plan(self):
  at=self.app('from core.work_hours_ui import render_hours_summary\nimport streamlit as st\nrender_hours_summary(st.session_state,st.session_state["employees_cache"])')
  original=dict(at.session_state['plan_ctx'])
  at.date_input(key='hours_history_range').set_value((DAY-timedelta(days=30),DAY-timedelta(days=1))).run()
  self.assertFalse(at.exception);self.assertEqual(at.session_state['plan_ctx'],original)
  self.assertFalse(any(x.label=='Personel bazında çalışma saatleri' for x in at.expander))

if __name__=='__main__':unittest.main()
