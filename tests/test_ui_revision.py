import copy
import tempfile
import unittest
from pathlib import Path
import pandas as pd
from streamlit.testing.v1 import AppTest
from test_planning import DAY, demand, emp, row, rules, run
from core.defaults import default_shift_rules,enforce_current_rules
from core.planning import school_term,preview_plan,calendar_grid
from core.profiles import manage_profiles
from core.workspace_store import save_keys,hydrate,init_db
from modules.shift_planing.planning_data import collect_inputs
from modules.shift_planner.intraday_ratio import matrix_table
from core.forecast_service import DAY_NAMES


class RevisionLogicTests(unittest.TestCase):
    def state(self):
        return {'employees_cache':[emp(group='akademi')], 'shift_rules':rules(),
                'plan_ctx':{'start':DAY,'end':DAY},'sp_staffing_result_df':demand()}
    def test_saved_outsource_duration_migrates_without_resetting_other_rules(self):
        with tempfile.TemporaryDirectory() as temp:
            s={'workspace_db_path':str(Path(temp)/'state.db'),'shift_rules':default_shift_rules(),'plan_ctx_confirmed':True}
            s['shift_rules']['work_type']['dis_kaynak']['shift_total_hours']=11
            s['shift_rules']['work_type']['akademi']['min_rest_hours']=13
            init_db(s['workspace_db_path']);enforce_current_rules(s);save_keys(s)
            loaded={};hydrate(loaded,s['workspace_db_path'])
            self.assertEqual(loaded['shift_rules']['work_type']['dis_kaynak']['shift_total_hours'],10)
            self.assertEqual(loaded['shift_rules']['work_type']['akademi']['min_rest_hours'],13)
            self.assertFalse(loaded['plan_ctx_confirmed'])
    def test_auto_never_overfills_or_extends_past_demand(self):
        narrow=run(df=demand(slots=range(17,23)))
        self.assertTrue(all(r['shift_code']=='OFF' for r in narrow['plan']))
        self.assertGreater(narrow['coverage']['Eksik'].sum(),0)
        partially_fixed=run(staff=[emp(),emp('2')],fixed=[row(end='09:00')])
        self.assertFalse((partially_fixed['coverage']['Atanan']>partially_fixed['coverage']['İhtiyaç']).any())
        self.assertEqual(sum(r.get('source')=='auto' and r['shift_code']=='WORK' for r in partially_fixed['plan']),0)
    def test_fixed_excess_is_reported_without_deleting_it(self):
        result=run(df=demand(count=0),fixed=[row()])
        self.assertEqual(result['plan'][0]['shift_code'],'WORK')
        self.assertGreater(result['coverage']['Fazla'].sum(),0)
    def test_semester_is_selected_by_each_actual_date(self):
        self.assertEqual(school_term('2027-01-10'),'2026-Güz')
        self.assertEqual(school_term('2027-02-10'),'2027-Bahar')
        self.assertEqual(school_term('2027-09-10'),'2027-Güz')
        s=self.state();s['planning_class_term']='2026-Bahar'
        s['acad_schedules']={'u1':{'2026-Güz':{'Saat':['08:00-10:00'],'Pazartesi':['Math']},
                                    '2026-Bahar':{'Saat':['12:00-14:00'],'Pazartesi':['Old']}}}
        blocks=collect_inputs(s)[3]['1']
        self.assertEqual(blocks[0][0].hour,8)
    def test_approved_marriage_leave_replaces_old_auto_in_preview(self):
        s=self.state();s['draft_shift_plan']=[row(source='auto')]
        s['trk_requests']=[{'id':'marriage','created_by':'u1','type':'Evlilik İzni Talebi','status':'Uygulandı',
                            'queue':'Closed','start_date':str(DAY),'end_date':str(DAY)}]
        result=preview_plan(s,include_auto=True)
        self.assertEqual(result['source_rows'][0]['shift_code'],'EVLILIK_IZNI')
        self.assertEqual(result['coverage']['Atanan'].sum(),0)
        self.assertFalse(result['issues'])
        self.assertIn('Evlilik izni',calendar_grid(result,s['plan_ctx']).iloc[0].tolist())
    def test_matrix_has_all_days_slots_and_daily_totals(self):
        profile=pd.DataFrame([{'Gün':d,'Slot':slot,'Oran(%)':100/48} for d in DAY_NAMES for slot in range(1,49)])
        table=matrix_table(profile)
        self.assertEqual(table.shape,(48,7))
        self.assertEqual(list(table.columns),DAY_NAMES)
        self.assertTrue((abs(table.sum()-100)<1e-6).all())
    def test_profile_activate_requires_one_and_delete_invalidates_usage(self):
        with tempfile.TemporaryDirectory() as temp:
            profile=pd.DataFrame({'Gün':['Pazartesi'],'Slot':[1],'Oran(%)':[100.]})
            s={'workspace_db_path':str(Path(temp)/'s.db'),'sp_ratio_profiles':[{'name':n,'profile_df':profile} for n in ['A','B']]}
            init_db(s['workspace_db_path'])
            with self.assertRaises(ValueError):manage_profiles(s,['A','B'],'activate')
            manage_profiles(s,['B'],'activate')
            self.assertEqual(s['sp_active_ratio_profile_name'],'B')
            manage_profiles(s,['A','B'],'delete')
            self.assertFalse(s['sp_ratio_profiles']);self.assertIsNone(s['sp_active_ratio_profile_df'])
            self.assertIsNone(s['sp_staffing_result_df']);self.assertFalse(s['plan_ctx_confirmed'])


class RevisionUITests(unittest.TestCase):
    def app(self,code):
        at=AppTest.from_string(code,default_timeout=30)
        values={'profile':{'position':'wfm'},'shift_rules':rules(),'employees_cache':[emp()],
                'plan_ctx':{'start':DAY,'end':DAY},'plan_ctx_confirmed':True,'sp_staffing_result_df':demand()}
        for k,v in values.items():at.session_state[k]=v
        at.run();self.assertFalse(at.exception)
        return at
    def test_map_and_donuts_render(self):
        at=self.app("from core.personnel_charts import render_summary\nrender_summary({'total':3,'location':{'İstanbul':2,'Ankara':1},'language':{'tr':2,'en':1},'work_type':{'fulltime':2,'akademi':1}})")
        self.assertEqual(at.metric[0].value,'3')
    def test_manual_assignment_uses_selected_period_and_updates_coverage(self):
        at=self.app('from modules.shift_planing.shift_hours import render\nrender()')
        at.multiselect(key='manual_people_v2').select('1').run()
        next(b for b in at.button if b.label=='Seçili Günlere Yerleştir').click().run()
        self.assertFalse(at.exception)
        rows=at.session_state['draft_shift_plan']
        self.assertEqual((rows[0]['start'],rows[0]['end']),('08:00','17:00'))
        self.assertEqual(rows[0]['date'],str(DAY))
        at.button(key='shift_undo').click().run();self.assertFalse(at.exception)
        self.assertFalse(at.session_state['draft_shift_plan'])
    def test_period_card_and_confirmation(self):
        at=self.app('from modules.shift_planing.period import render\nrender()')
        at.button(key='vp_unconfirm').click().run()
        self.assertFalse(at.session_state['plan_ctx_confirmed'])
        at.button(key='vp_confirm').click().run()
        self.assertTrue(at.session_state['plan_ctx_confirmed'])
        self.assertFalse(at.exception)

if __name__=='__main__':unittest.main()
