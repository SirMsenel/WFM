import copy,json,tempfile,unittest
from pathlib import Path
from datetime import timedelta,time
import pandas as pd
import numpy as np
from streamlit.testing.v1 import AppTest
from test_planning import DAY,demand,emp,row,rules
from test_improvements import intervals
from core.forecast_service import DAY_NAMES
from core.workspace_store import init_db,hydrate,save_keys,connect
from core.forecast_ledger import capture_forecast,capture_profile,runs,slots,ingest_actuals,compare,performance,profile_versions,profile_accuracy
from core.interval_editing import rebalance_profile
from core.planning_guard import planning_problem,assert_can_plan
from core.plan_publication import publish_plan,publications,withdraw
from modules.shift_planing.planning_data import collect_inputs,fingerprint
from modules.shift_planing.engine import generate_plan,bounds
from core.planning import preview_plan
from core.request_service import create_request,act


def profile_frame(start=DAY):
 return pd.DataFrame([{'Tarih':pd.Timestamp(start)+pd.Timedelta(days=i),'Gün':DAY_NAMES[i],'Slot':s,'Oran(%)':100/48} for i in range(7) for s in range(1,49)])


def state():
 people=[dict(emp(),language='tr',team_lead='Lead'),dict(emp('2'),language='en',team_lead='Other')]
 return {'employees_cache':people,'shift_rules':rules(),'plan_ctx':{'start':DAY,'end':DAY},'plan_ctx_confirmed':True,'sp_staffing_result_df':demand(),
         'planning_languages':{'tr':True,'en':False,'ar':False},'plan_group_priority':list(rules()['work_type']),'profile':{'position':'wfm','username':'planner'}}


def draft(s):
 staff,fixed,history,unavailable,issues=collect_inputs(s)
 result=generate_plan(staff,s['sp_staffing_result_df'],s['shift_rules'],s['plan_group_priority'],s['plan_ctx']['start'],s['plan_ctx']['end'],fixed=fixed,history=history,unavailable=unavailable)
 result.update(staff=staff,period={k:str(v) for k,v in s['plan_ctx'].items()});result['issues']+=issues
 s['draft_shift_plan']=result['plan'];s['planning_result_fingerprint']=fingerprint(s)
 return result


class LedgerTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'db';init_db(self.path)
  self.s={'workspace_db_path':str(self.path),'sp_active_ratio_profile_name':'Test','sp_forecast_meta':{'model_name':'Model'},'profile':{'username':'planner'}}
  self.profile=profile_frame();self.forecast=pd.DataFrame({'tarih':pd.date_range(DAY,periods=7),'y_pred':[480.]*7})
 def tearDown(self):self.temp.cleanup()
 def test_immutable_versions_and_idempotence(self):
  first=capture_forecast(self.s,self.forecast,self.profile);old=slots(first,self.path)
  self.assertEqual(capture_forecast(self.s,self.forecast,self.profile),first)
  forecast=self.forecast.copy();forecast.y_pred*=2
  second=capture_forecast(self.s,forecast,self.profile)
  self.assertNotEqual(first,second);pd.testing.assert_frame_equal(slots(first,self.path),old)
  self.assertTrue(np.allclose(old.groupby('tarih').predicted.sum(),480))
  self.assertEqual(len(runs(self.path)),2)
 def test_partial_actuals_missing_is_not_zero_and_updates_keep_other_slots(self):
  ident=capture_forecast(self.s,self.forecast,self.profile)
  ingest_actuals(pd.DataFrame({'tarih':[str(DAY),str(DAY)],'slot':[17,18],'cagri_sayisi':[15,5]}),self.path)
  ingest_actuals(pd.DataFrame({'tarih':[str(DAY)],'slot':[17],'cagri_sayisi':[20]}),self.path)
  result=compare(ident,self.path);self.assertEqual(result.actual.notna().sum(),2)
  measured=performance(result);self.assertEqual(measured['actual'],25);self.assertAlmostEqual(measured['predicted'],20)
  self.assertAlmostEqual(measured['wape_pct'],60)
 def test_zero_forecast_percentage_is_undefined_not_infinite(self):
  self.forecast.y_pred=0;ident=capture_forecast(self.s,self.forecast,self.profile)
  ingest_actuals(pd.DataFrame({'tarih':[str(DAY)],'slot':[17],'cagri_sayisi':[5]}),self.path)
  frame=compare(ident,self.path);self.assertTrue(pd.isna(frame.loc[frame.slot==17,'difference_pct']).all())
 def test_profile_success_uses_only_complete_counted_days(self):
  ident=capture_profile(self.s,self.profile,{'name':'Before actuals'})
  raw=pd.DataFrame({'tarih':[str(DAY)]*38,'slot':[s for s in range(1,49) if not 7<=s<=16],'cagri_sayisi':[10]*38})
  ingest_actuals(raw,self.path);version=profile_versions(self.path)[0]
  result=profile_accuracy(version,self.path,True)
  measured=result[result.error_points.notna()]
  self.assertEqual(len(measured),38);self.assertTrue(np.allclose(measured.error_points,0))
  self.assertAlmostEqual(measured.actual_share.sum(),100)
  self.assertTrue(profile_accuracy(version,self.path,False).error_points.isna().all())
 def test_profile_archive_does_not_prune_after_twelve_weeks(self):
  for i in range(14):capture_profile(self.s,profile_frame(DAY+timedelta(weeks=i)),{'week':i})
  self.assertEqual(len(profile_versions(self.path)),14)
 def test_undated_legacy_profile_is_archived_with_actual_used_dates(self):
  from core.interval_service import record_used_profile
  generic=self.profile.drop(columns='Tarih')
  record_used_profile(self.s,self.forecast,generic)
  archived=profile_versions(self.path)[0]['frame']
  self.assertIn('Tarih',archived)
  self.assertEqual(set(pd.to_datetime(archived.Tarih)),set(self.forecast.tarih))
  self.assertEqual(len(archived),336)

 def test_invalid_actuals_are_atomic(self):
  with self.assertRaises(ValueError):ingest_actuals(pd.DataFrame({'tarih':[str(DAY)]*2,'slot':[1,1],'cagri_sayisi':[2,3]}),self.path)
  with connect(self.path) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM calls_interval').fetchone()[0],0)
 def test_capture_rejects_non_48_slot_profile(self):
  bad=self.profile.copy();bad.loc[bad.Slot==48,'Slot']=49
  with self.assertRaises(ValueError):capture_forecast(self.s,self.forecast,bad)


class RebalanceTests(unittest.TestCase):
 def test_increase_uses_early_hours_first_and_keeps_manual_cell(self):
  from modules.shift_planner.intraday_ratio import matrix_table
  original=profile_frame();matrix=matrix_table(original);edited=matrix.copy();edited.iloc[20,0]+=1
  result,pins=rebalance_profile(original,edited);out=matrix_table(result)
  self.assertAlmostEqual(out.iloc[20,0],edited.iloc[20,0]);self.assertIn(('Pazartesi',21),pins)
  self.assertAlmostEqual(out.iloc[6:16,0].sum(),matrix.iloc[6:16,0].sum()-1)
  self.assertAlmostEqual(out.iloc[0,0],matrix.iloc[0,0]);self.assertTrue(np.allclose(out.sum(),100))
 def test_excess_manual_total_is_rejected(self):
  from modules.shift_planner.intraday_ratio import matrix_table
  original=profile_frame();edited=matrix_table(original);edited.iloc[0,0]=90;edited.iloc[1,0]=90
  with self.assertRaises(ValueError):rebalance_profile(original,edited)
 def test_early_budget_exhaustion_uses_other_unpinned_slots(self):
  from modules.shift_planner.intraday_ratio import matrix_table
  original=profile_frame();edited=matrix_table(original);edited.iloc[20,0]=50
  result,_=rebalance_profile(original,edited);out=matrix_table(result)
  self.assertAlmostEqual(out.iloc[6:16,0].sum(),0);self.assertAlmostEqual(out.iloc[20,0],50);self.assertAlmostEqual(out.iloc[:,0].sum(),100)


class PublicationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'db';init_db(self.path);self.s=state();self.s['workspace_db_path']=str(self.path)
 def tearDown(self):self.temp.cleanup()
 def test_published_scope_blocks_same_language_but_allows_other_language(self):
  result=draft(self.s);publish_plan(self.s,result)
  self.assertEqual(planning_problem(self.s)['kind'],'published')
  with self.assertRaises(ValueError):assert_can_plan(self.s)
  self.s['planning_languages']={'tr':False,'en':True,'ar':False}
  self.assertIsNone(planning_problem(self.s));second=draft(self.s);publish_plan(self.s,second)
  self.assertEqual({r['language'] for r in self.s['published_shift_plan']},{'tr','en'})
 def test_undo_preserves_other_language_and_archive_then_reopens_editable_draft(self):
  publish_plan(self.s,draft(self.s));turkish=publications(self.s)[0]
  self.s['planning_languages']={'tr':False,'en':True,'ar':False};publish_plan(self.s,draft(self.s))
  withdraw(self.s,turkish,True)
  self.assertEqual({r['language'] for r in self.s['published_shift_plan']},{'en'})
  self.assertTrue(any(r['employee_id']=='1' and r['source']=='manual_single' for r in self.s['draft_shift_plan']))
  self.assertEqual(next(b for b in publications(self.s) if b['id']==turkish['id'])['status'],'withdrawn')
  loaded={};hydrate(loaded,self.path);self.assertEqual(loaded['published_shift_plan'],self.s['published_shift_plan'])
 def test_second_session_cannot_overwrite_existing_publication(self):
  other=copy.deepcopy(self.s);result=draft(other)
  publish_plan(self.s,draft(self.s))
  with self.assertRaises(ValueError):publish_plan(other,result)
 def test_pending_tl_request_blocks_then_approved_leave_is_automatically_placed(self):
  self.s['profile']={'position':'agent','username':'u1','employee_id':'1','full_name':'Person 1','team_lead':'Lead'}
  req=create_request(self.s,{'type':'Yıllık İzin Talebi','start_date':str(DAY),'end_date':str(DAY),'note':'İzin'})
  self.assertEqual(planning_problem(self.s)['kind'],'requests')
  self.s['profile']={'position':'tl','username':'lead','full_name':'Lead'};req=act(self.s,req,'forward')
  self.assertEqual(planning_problem(self.s)['kind'],'requests')
  self.s['profile']={'position':'wfm','username':'planner'};req=act(self.s,req,'apply')
  self.assertIsNone(planning_problem(self.s))
  result=preview_plan(self.s);self.assertEqual(result['source_rows'][0]['shift_code'],'YILLIK_IZIN');self.assertEqual(result['coverage'].Atanan.sum(),0)
 def test_approved_swap_freezes_and_places_both_assignments(self):
  s=self.s;s['planning_languages']={'tr':True,'en':True,'ar':True}
  s['draft_shift_plan']=[row(start='08:00',end='17:00'),row(eid='2',start='09:00',end='18:00')]
  s['profile']={'position':'agent','username':'u1','employee_id':'1','full_name':'Person 1','team_lead':'Lead'}
  req=create_request(s,{'type':'Vardiya Değişim Talebi','start_date':str(DAY),'end_date':str(DAY),'note':'Swap','targets':[{'employee_id':'2','full_name':'Person 2','team_lead':'Other'}]})
  s['profile']={'position':'tl','username':'lead','full_name':'Lead'};req=act(s,req,'forward')
  s['profile']={'position':'tl','username':'other','full_name':'Other'};req=act(s,req,'forward')
  s['profile']={'position':'wfm','username':'planner'};req=act(s,req,'apply')
  self.assertEqual(len(req['resolved_assignments']),2)
  fixed=collect_inputs(s)[1];swapped={r['employee_id']:r for r in fixed if r['source']=='approved_request'}
  self.assertEqual(swapped['1']['start'],'09:00');self.assertEqual(swapped['2']['start'],'08:00')
  self.assertFalse(preview_plan(s)['issues'])
  s['draft_shift_plan'][1]['start']='10:00'
  self.assertEqual(next(r for r in collect_inputs(s)[1] if r['source']=='approved_request' and r['employee_id']=='1')['start'],'09:00')

 def test_stale_withdraw_cannot_remove_a_new_publication_with_same_times(self):
  s=self.s;publish_plan(s,draft(s));old=publications(s)[0]
  withdraw(s,old,False);publish_plan(s,draft(s))
  current=copy.deepcopy(s['published_shift_plan'])
  with self.assertRaises(ValueError):withdraw(s,old,False)
  self.assertEqual(s['published_shift_plan'],current)

 def test_request_outside_period_does_not_block(self):
  self.s['trk_requests']=[{'id':'later','employee_id':'1','type':'Genel Talep','start_date':str(DAY+timedelta(days=20)),'end_date':str(DAY+timedelta(days=20)),'queue':'TL','status':'Beklemede'}]
  self.assertIsNone(planning_problem(self.s))


class CalendarAndScopeTests(unittest.TestCase):
 def test_due_date_is_based_on_real_rolled_cut_date(self):
  from core.billing_calendar import billing_flag
  days=pd.Series(pd.to_datetime(['2024-02-29','2024-03-01','2024-03-11','2024-02-12','2026-04-10','2026-05-11']))
  self.assertEqual(billing_flag(days,'cut').tolist()[:2],[0,1])
  self.assertEqual(billing_flag(days,'due').tolist(),[0,0,1,0,0,1])
 def test_feature_future_and_training_cut_flags_match(self):
  from modules.call_forecast.predict_ui import _son_odeme_flag,_ekstre_kesim_flag
  from core.billing_calendar import billing_flag
  days=pd.Series(pd.date_range('2024-01-01','2027-12-31'))
  pd.testing.assert_series_equal(_son_odeme_flag(days),billing_flag(days,'due'))
  pd.testing.assert_series_equal(_ekstre_kesim_flag(days),billing_flag(days,'cut'))
  from modules.call_forecast.feature_engineering import apply_feature_pipeline
  engineered,_=apply_feature_pipeline(pd.DataFrame({'tarih':days,'calls':1}),'tarih',selected_bank_features=['EKSTRE_KESIM','SON_ODEME'])
  np.testing.assert_array_equal(engineered['EKSTRE_KESIM'],_ekstre_kesim_flag(days))
  np.testing.assert_array_equal(engineered['SON_ODEME'],_son_odeme_flag(days))
 def test_each_weekday_has_its_own_moving_average(self):
  from modules.shift_planner.history_comparison import grouped_rolling
  dates=pd.date_range('2026-01-01',periods=120)
  frame=grouped_rolling(pd.DataFrame({'tarih':dates,'cagri_sayisi':dates.weekday*100.}))
  for col in ['7 günlük hareketli ortalama','30 günlük hareketli ortalama']:np.testing.assert_allclose(frame[col],dates.weekday*100.)
 def test_far_future_reference_still_has_two_and_month_weekday_history(self):
  from modules.shift_planner.history_comparison import interval_references
  result=interval_references(intervals(),'2026-12-07','2026-11-08')
  self.assertTrue(result['Son 2 hafta aynı gün ort.'].notna().all());self.assertTrue(result['Son 30 gün aynı gün ort.'].notna().all())
 def test_team_and_self_scope(self):
  from core.personnel import visible_people
  people=state()['employees_cache']
  self.assertEqual([e['employee_id'] for e in visible_people({'position':'tl','full_name':'Lead'},people)],['1'])
  self.assertEqual(len(visible_people({'position':'wfm'},people)),2)
  self.assertEqual([e['employee_id'] for e in visible_people({'position':'agent','employee_id':'2'},people)],['2'])
 def test_timed_exam_allows_other_hours_but_missing_end_blocks_day(self):
  s=state();s['employees_cache']=[dict(emp(group='akademi'),language='tr')]
  s['acad_exam_calendar']={'u1':{'2026-Sinav':{'Tarih':[str(DAY)],'Saat':['10:00'],'Bitiş':['12:00'],'Ders':['Exam']}}};s['planning_exam_hours']=True
  staff,fixed,history,unavailable,issues=collect_inputs(s)
  self.assertEqual((unavailable['1'][0][1]-unavailable['1'][0][0]).total_seconds(),7200)
  s['sp_staffing_result_df']=demand(slots=range(17,39));result=draft(s)
  work=[r for r in result['plan'] if bounds(r)];self.assertTrue(work);self.assertTrue(all(bounds(r)[0].hour>=12 for r in work))
  del s['acad_exam_calendar']['u1']['2026-Sinav']['Bitiş'];s['draft_shift_plan']=[]
  self.assertEqual(draft(s)['plan'][0]['shift_code'],'OFF')
 def test_shift_window_hours_and_statuses(self):
  from core.shift_display import shift_stats,cell_style
  records=[row(day=DAY,start='08:00',end='13:00'),row(day=DAY+timedelta(days=1),start='13:00',end='17:00'),row(day=DAY+timedelta(days=2),start='17:00',end='00:00'),row(day=DAY+timedelta(days=3),code='GECE',start='00:00',end='08:00'),row(day=DAY+timedelta(days=4),code='RAPOR',start=None,end=None)]
  stats=shift_stats(records,DAY,DAY+timedelta(days=4));self.assertEqual(stats['parts'],{'Sabah':5.,'İkindi':4.,'Akşam':7.,'Gece':8.});self.assertEqual(stats['total_hours'],24);self.assertEqual(stats['night_count'],1)
  self.assertEqual(stats['status_counts']['RAPOR'],1)
  self.assertEqual(len({cell_style(s) for s in ['08:00','13:00','17:00','00:00','OFF','Rapor','Yıllık izin']}),7)


class Round4UITests(unittest.TestCase):
 def app(self,code,s=None):
  at=AppTest.from_string(code,default_timeout=40)
  for k,v in (s or state()).items():at.session_state[k]=v
  at.run();self.assertFalse(at.exception,[(x.message,x.stack_trace) for x in at.exception]);return at
 def test_request_search_no_longer_calls_a_string(self):
  s=state();s['profile']={'position':'wfm'};s['trk_requests']=[{'id':'REQ-123','created_by':'u1','created_by_name':'Person 1','type':'Genel Talep','note':'Açıklama','queue':'WFM','status':'Planlamaya İletildi'}]
  at=self.app('from core.request_ui import render_center\nrender_center("planning","test_search")',s)
  at.text_input(key='test_search_search').set_value('Person').run();self.assertFalse(at.exception)
  at.text_input(key='test_search_search').set_value('not-found').run();self.assertFalse(at.exception);self.assertTrue(at.info)
 def test_published_popup_blocks_generation_and_other_language_can_be_selected(self):
  s=state();s['published_shift_plan']=[dict(row(),language='tr')]
  at=self.app('from modules.shift_planing.publish import render\nrender()',s)
  self.assertFalse(any(b.key=='planning_generate' for b in at.button));self.assertTrue(at.warning)
  at.button(key='guard_ack').click().run()
  at.toggle(key='planning_include_tr').set_value(False).run()
  at.toggle(key='planning_include_en').set_value(True).run()
  self.assertFalse(at.exception);self.assertTrue(any(b.key=='planning_generate' for b in at.button))
 def test_navigation_keeps_subpage_when_widget_is_removed(self):
  at=self.app('''
import streamlit as st
from core.navigation import sections
st.session_state.setdefault('show',True)
if st.button('Switch'):st.session_state['show']=not st.session_state['show']
if st.session_state['show']:sections('nav_test',{'A':lambda:st.write('A page'),'B':lambda:st.write('B page')})
else:st.write('Other page')
''')
  at.session_state['nav_test']='B';at.run();at.button[0].click().run();at.button[0].click().run()
  self.assertEqual(at.session_state['nav_test'],'B');self.assertFalse(at.exception)
 def test_academic_team_browser_hides_other_team_and_searches(self):
  s=state();s['profile']={'position':'tl','full_name':'Lead'};s['personnel_cache']=s['employees_cache']
  s['acad_schedules']={'u1':{'2026-Güz':{'Saat':['08:00-10:00'],'Pazartesi':['Math']}},'u2':{'2026-Güz':{'Saat':['08:00-10:00'],'Pazartesi':['Secret']}}}
  at=self.app('from modules.tracking.class_schedule import render\nrender()',s)
  self.assertTrue(any('Math' in str(df.value) for df in at.dataframe));self.assertFalse(any('Secret' in str(df.value) for df in at.dataframe))
  at.text_input(key='academic_staff_search').set_value('Person 2').run();self.assertFalse(at.exception);self.assertTrue(at.info)
 def test_tracking_personnel_summary_has_four_time_windows(self):
  s=state();s['profile']=dict(s['employees_cache'][0]);s['published_shift_plan']=[dict(row(),language='tr')]
  at=self.app('from modules.tracking.my_shift import render\nrender()',s)
  at.date_input(key='my_shift_range_v2').set_value((DAY,DAY)).run();self.assertFalse(at.exception)
  self.assertTrue(any('Gece adedi' in m.value for m in at.markdown));self.assertTrue(at.dataframe)

if __name__=='__main__':unittest.main()
