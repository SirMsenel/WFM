import unittest
import sqlite3
from datetime import timedelta
import pandas as pd
from test_phase7 import Base
from test_planning import DAY,row,demand,emp


class SimulationActionTests(Base):
    def test_action_reaches_management_and_cannot_be_decided_twice(self):
        from ortak.simulasyon_aksiyonlari import submit,list_actions,decide
        ident=submit(self.s,'2027-01','Personel alım önerisi','Kapasite açığı',[{'Ay':'2027-01','Senaryo':'Normal'}])
        self.assertEqual(list_actions(self.s)[0]['status'],'Onay bekliyor')
        self.s['profile']={'position':'manager','username':'manager1','full_name':'Yönetici'}
        self.assertEqual(decide(self.s,ident,True,'Uygun'),'Onaylandı')
        with self.assertRaises(ValueError):decide(self.s,ident,True,'Tekrar')


class InverseErlangTests(unittest.TestCase):
    def test_more_agents_support_more_calls_at_same_service_level(self):
        from ortak.senaryolar import inverse_erlang_calls
        self.assertGreater(inverse_erlang_calls(20,300,.8,20),inverse_erlang_calls(10,300,.8,20))


class BillingTests(Base):
    def test_monthly_status_coefficient_and_tax_are_calculated(self):
        from ortak.fatura_servisi import save_profile,calculate
        self.s['profile']={'position':'wfm','username':'planner'}
        with sqlite3.connect(self.s['auth_db_path']) as db:db.execute("UPDATE employees SET company='ACME' WHERE employee_id=1")
        self.s['published_shift_plan']=[row('1',DAY),row('1',DAY+timedelta(days=1),'OFF',None,None)]
        save_profile(self.s,{'company':'ACME','group':'fulltime','method':'Aylık','amount':3000,'coefficient_basis':'30 gün sabit','paid_statuses':['WORK','OFF'],'taxes':[{'name':'KDV','rate':20,'direction':'Artı','application':'Ana hesaba ekle'}]})
        result=calculate(self.s,DAY)
        self.assertEqual(len(result),1);self.assertAlmostEqual(result.iloc[0]['Katsayı'],2/30);self.assertAlmostEqual(result.iloc[0]['Ana tutar'],200);self.assertAlmostEqual(result.iloc[0]['Net ödeme'],240)

    def test_billing_screen_renders_for_planning_role(self):
        from streamlit.testing.v1 import AppTest
        self.s['profile']={'position':'wfm','username':'planner','full_name':'Planlama'}
        at=AppTest.from_string('from modules.fatura_mutabakat import render\nrender()',default_timeout=60)
        for key,value in self.s.items():at.session_state[key]=value
        at.run()
        self.assertFalse(at.exception)


class NightPatternTests(unittest.TestCase):
    def test_hard_weekly_night_cohorts_cover_first_three_and_last_four_days(self):
        from ortak.varsayilan_kurallar import default_shift_rules
        from modules.vardiya_plani.vardiya_motoru import generate_plan
        rules=default_shift_rules();rules['night'].update(auto_fill=True,weekly_pattern_enabled=True,weekly_pattern_hard=True,normal={'tr':1,'en':0,'ar':0});rules['work_type']['akademi'].update(min_off_days=1,max_consecutive_days=6)
        people=[dict(emp('1','akademi'),language='tr',sicil_no='1'),dict(emp('2','akademi'),language='tr',sicil_no='2')]
        plan=generate_plan(people,demand(days=7,count=0,slots=range(1,49)),rules,list(rules['work_type']),DAY,DAY+timedelta(days=6),auto_night=True)
        nights=[r for r in plan['plan'] if r['shift_code']=='GECE'];self.assertEqual(len(nights),7)
        self.assertEqual({pd.Timestamp(r['date']).weekday() for r in nights if r['employee_id']=='2'},{0,1,2});self.assertEqual({pd.Timestamp(r['date']).weekday() for r in nights if r['employee_id']=='1'},{3,4,5,6})


class ShrinkageWidgetTests(Base):
    def test_saving_interval_rules_disables_general_slider_without_widget_collision(self):
        from streamlit.testing.v1 import AppTest
        from test_round4 import profile_frame
        frame=pd.DataFrame({'tarih':pd.date_range(DAY,periods=2),'y_pred':[100.,110.]})
        at=AppTest.from_string('from modules.mesai_plani.personel_ihtiyaci import render\nrender()',default_timeout=60)
        at.session_state['workspace_db_path']=self.s['workspace_db_path'];at.session_state['sp_forecast_df']=frame;at.session_state['sp_active_ratio_profile_df']=profile_frame(DAY);at.session_state['slot_shrinkage']=[{'start_slot':1,'end_slot':48,'rate':.25}];at.run()
        self.assertFalse(at.exception);at.button(key='save_slot_loss').click().run();self.assertFalse(at.exception)
        self.assertTrue(next(slider for slider in at.slider if slider.label=='Shrinkage (%)').disabled);self.assertEqual(at.session_state['staffing_shrinkage_mode'],'30 dk kuralları')


class ThemeTests(unittest.TestCase):
    def test_palette_does_not_recolor_action_buttons(self):
        from ortak.tema import css
        self.assertNotIn('button[aria-pressed="true"]',css());self.assertNotIn('button[kind="primary"]',css())


if __name__=='__main__':unittest.main()
