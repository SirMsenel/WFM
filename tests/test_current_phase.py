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


class NavigationAndLanguageScopeTests(unittest.TestCase):
    def test_section_can_be_changed_after_widget_without_mutating_widget_key(self):
        from streamlit.testing.v1 import AppTest
        at=AppTest.from_string('''
import streamlit as st
from ortak.gezinme import sections,select_section
def first():
    if st.button('Taslağa geç',key='go_draft'):
        select_section(st.session_state,'nav_demo','Taslak')
        st.rerun()
sections('nav_demo',{'Oluştur':first,'Taslak':lambda:st.write('Taslak ekranı')},single_line=True)
''',default_timeout=30)
        at.run();at.button(key='go_draft').click().run()
        self.assertFalse(at.exception);self.assertEqual(at.session_state['nav_demo'],'Taslak')

    def test_foreign_language_need_is_added_only_when_explicitly_enabled(self):
        from ortak.plan_ihtiyaci import demand
        base=pd.DataFrame({'Tarih':[pd.Timestamp('2026-11-23')],'Slot':[1],'Planlanan Agent':[10.],'Net Agent':[7.]})
        foreign=pd.DataFrame({'Tarih':[pd.Timestamp('2026-11-23')],'Slot':[1],'Planlanan Agent':[2.],'Net Agent':[1.4]})
        state={'sp_staffing_result_df':base,'language_demands':{'en':foreign},'language_demand_inclusion':{'en':False}}
        self.assertEqual(demand(state).iloc[0]['Planlanan Agent'],10)
        state['language_demand_inclusion']['en']=True
        self.assertEqual(demand(state).iloc[0]['Planlanan Agent'],12)

    def test_foreign_language_plan_never_exceeds_its_own_need(self):
        from test_planning_round2 import Round2LogicTests
        from modules.vardiya_plani.yabanci_dil_plani import _build
        state=Round2LogicTests().state();state.update(plan_ctx_confirmed=True,plan_group_priority=list(state['shift_rules']['work_type']))
        for person in state['employees_cache']:person['language']='en'
        need=state['sp_staffing_result_df'].copy();need['Planlanan Agent']=1
        result=_build(state,'en',need)
        self.assertLessEqual(result['coverage']['Atanan'].max(),1)

    def test_foreign_plan_reorders_groups_to_close_early_gap_and_ignores_main_draft(self):
        from ortak.varsayilan_kurallar import default_shift_rules
        from modules.vardiya_plani.yabanci_dil_plani import _build
        day=pd.Timestamp('2026-11-23').date()
        people=[dict(emp(str(index),group),language='en',username='en'+str(index)) for index,group in enumerate(['akademi','akademi','fulltime','fulltime'],1)]
        schedules={person['username']:{'2026-Güz':{'Saat':['08:00-11:00'],'Pazartesi':['Ders']}} for person in people if person['work_type']=='akademi'}
        need=pd.DataFrame([{'Tarih':day,'Slot':slot,'Planlanan Agent':2 if 17<=slot<=48 else 0,'Net Agent':2 if 17<=slot<=48 else 0} for slot in range(1,49)])
        state={'employees_cache':people,'shift_rules':default_shift_rules(),'plan_ctx':{'start':day,'end':day},'plan_ctx_confirmed':True,'plan_group_priority':['akademi','fulltime','dis_kaynak'],'planning_languages':{'tr':True,'en':True,'ar':True},'draft_shift_plan':[dict(row('3',day),source='manual_single')],'fixed_shift_records':[],'shift_overrides':[],'published_shift_plan':[],'trk_requests':[],'group_hour_targets':[],'status_rules':{'enabled':False},'acad_schedules':schedules}
        result=_build(state,'en',need);active=result['coverage'][result['coverage'].Slot.between(17,48)]
        self.assertEqual(active['Eksik'].sum(),0);self.assertFalse(any(record.get('source')=='manual_single' for record in result['plan']))

    def test_only_selected_foreign_person_counts_in_main_plan_and_others_are_reserved(self):
        from unittest.mock import patch
        from modules.vardiya_plani.yabanci_dil_plani import _transfer
        from modules.vardiya_plani.planlama_verileri import collect_inputs
        from ortak.varsayilan_kurallar import default_shift_rules
        day=pd.Timestamp('2026-11-23').date()
        people=[dict(emp('A'),language='en',username='english_only'),dict(emp('B'),language='en',username='bilingual')]
        result={'staff':people,'period':{'start':str(day),'end':str(day)},'plan':[
            dict(row('A',day),full_name='English Only'),dict(row('B',day),full_name='Bilingual')]}
        state={'employees_cache':people,'planning_languages':{'tr':True,'en':False,'ar':False},'plan_ctx':{'start':day,'end':day},
               'shift_rules':default_shift_rules(),'draft_shift_plan':[],'fixed_shift_records':[],'shift_overrides':[],
               'published_shift_plan':[],'trk_requests':[],'group_hour_targets':[]}
        with patch('modules.vardiya_plani.yabanci_dil_plani.save_keys'):_transfer(state,'en',result,['B'])
        self.assertEqual(state['foreign_language_reserved_ids']['en'],['A','B'])
        self.assertEqual(state['foreign_language_transferred_ids']['en'],['B'])
        self.assertEqual({record['employee_id'] for record in state['draft_shift_plan']},{'B'})
        staff,fixed,_,_,_=collect_inputs(state)
        self.assertEqual({person['employee_id'] for person in staff},{'B'})
        self.assertEqual({record['employee_id'] for record in fixed},{'B'})

    def test_reserved_foreign_person_stays_out_even_when_language_toggle_is_on(self):
        from modules.vardiya_plani.planlama_verileri import collect_inputs
        from ortak.varsayilan_kurallar import default_shift_rules
        day=pd.Timestamp('2026-11-23').date()
        people=[dict(emp('A'),language='en',username='english_only'),dict(emp('B'),language='en',username='other_english')]
        state={'employees_cache':people,'planning_languages':{'tr':True,'en':True,'ar':True},'foreign_language_reserved_ids':{'en':['A']},
               'plan_ctx':{'start':day,'end':day},'shift_rules':default_shift_rules(),'draft_shift_plan':[],
               'fixed_shift_records':[],'shift_overrides':[],'published_shift_plan':[],'trk_requests':[],'group_hour_targets':[]}
        staff=collect_inputs(state)[0]
        self.assertEqual({person['employee_id'] for person in staff},{'B'})

    def test_foreign_period_card_reports_only_transferred_capacity(self):
        from modules.vardiya_plani.olustur_kontrol_yayinla import foreign_plan_period_summary
        day=pd.Timestamp('2026-11-23').date()
        state={'foreign_language_plans':{'en':{'period':{'start':str(day),'end':str(day)},'staff':[emp('A'),emp('B')]}},
               'foreign_language_transferred_ids':{'en':['B']},'draft_shift_plan':[
                   dict(row('A',day),source='foreign_language_plan',language='en'),
                   dict(row('B',day),source='foreign_language_plan',language='en')]}
        item=foreign_plan_period_summary(state,{'start':day,'end':day},'en')
        self.assertTrue(item['planned']);self.assertEqual(item['planned_people'],2)
        self.assertEqual(item['impact_people'],1);self.assertEqual(item['impact_shifts'],1);self.assertEqual(item['impact_hours'],9)

    def test_demo_exam_fixture_has_and_migrates_end_time(self):
        from ortak.ornek_veri import ensure_demo_exam_end_times
        state={'acad_exam_calendar':{'u1':{'2026-Sinav':{'Tarih':['2026-11-23'],'Saat':['10:00'],'Ders':['Vize']}}}}
        self.assertTrue(ensure_demo_exam_end_times(state));self.assertEqual(state['acad_exam_calendar']['u1']['2026-Sinav']['Bitiş'],['12:00'])


class CurrentRosterRegressionTests(unittest.TestCase):
    def test_break_rule_selection_survives_first_rerun(self):
        from streamlit.testing.v1 import AppTest
        from ortak.statuler import defaults
        from test_planning import rules
        at=AppTest.from_string('from modules.statu_kurallari import render\nrender()',default_timeout=30)
        at.session_state['status_rules']=dict(defaults(),enabled=True);at.session_state['shift_rules']=rules();at.run()
        at.segmented_control(key='status_kind').set_value('Mola').run();at.selectbox(key='break_total_fulltime_1').set_value(20).run()
        self.assertFalse(at.exception);self.assertEqual(at.selectbox(key='break_total_fulltime_1').value,20);self.assertEqual(at.session_state['_break_rule_rows_fulltime'][0]['minutes'],20)

    def test_unapplied_simulated_request_is_rejected_when_period_is_published(self):
        from ortak.talep_simulasyonu import finalize_in_memory
        state={'trk_requests':[{'id':'r1','queue':'SIMULATION','status':'Simülasyonda','employee_id':'1','type':'Yıllık İzin Talebi','start_date':str(DAY),'end_date':str(DAY),'events':[]}]}
        finalize_in_memory(state,[row('1',DAY)],str(DAY),str(DAY),'planner')
        self.assertEqual(state['trk_requests'][0]['status'],'Reddedildi');self.assertEqual(state['trk_requests'][0]['queue'],'Closed')

    def test_coverage_comparison_uses_gross_assigned_and_shows_ratio_and_delta(self):
        from ortak.planlama_gorunumu import coverage_comparison_matrix,styled_coverage_comparison
        frame=pd.DataFrame([{'Tarih':DAY,'Slot':17,'İhtiyaç':10,'Atanan':4,'Brüt Atanan':5,'Sayaca Dahil':True},
                            {'Tarih':DAY,'Slot':18,'İhtiyaç':12,'Atanan':12,'Brüt Atanan':15,'Sayaca Dahil':True}])
        html=styled_coverage_comparison(coverage_comparison_matrix(frame,DAY)).to_html()
        self.assertIn('5/10',html);self.assertIn('−5',html);self.assertIn('15/12',html);self.assertIn('+3',html)

    def test_status_placement_preserves_manual_net_agent_floor(self):
        from ortak.statuler import defaults,meal_plan
        cfg=defaults();cfg.update(enabled=True,automatic=True,shrinkage_included=True,coaching_by_leader=False)
        rule=cfg['groups']['fulltime'];rule.update(min_shift_hours=0,meal_minutes=30,break_rules=[{'min_hours':0,'max_hours':24,'minutes':0}],coaching_monthly_minutes=0)
        coverage=pd.DataFrame([{'Tarih':DAY,'Slot':slot,'İhtiyaç':2,'Planlanan Agent':2,'Net Agent':1,'Shrinkage (%)':50,'Atanan':2,'Eksik':0,'Fazla':0,'Sayaca Dahil':True} for slot in range(17,21)])
        rows=[row('1',DAY,start='08:00',end='10:00'),row('2',DAY,start='08:00',end='10:00')]
        items,out,issues=meal_plan({'status_rules':cfg,'staffing_parameters':{'shrinkage':.5}},rows,coverage,[emp('1'),emp('2')])
        meals=[item for item in items if item['kind']=='Yemek'];self.assertEqual(len(meals),2)
        self.assertFalse(pd.Timestamp(meals[0]['start'])<pd.Timestamp(meals[1]['end']) and pd.Timestamp(meals[1]['start'])<pd.Timestamp(meals[0]['end']))
        self.assertTrue((out['Atanan']>=out['İhtiyaç']).all());self.assertFalse(issues)

    def test_erlang_approval_cards_read_saved_staffing_parameters(self):
        from ortak.planlama_gorunumu import erlang_summary_values
        coverage=pd.DataFrame({'Sayaca Dahil':[True],'AHT (sn)':[195],'Hedef SL (%)':[80],'SL (model) (%)':[82.4],'Hedef süre (sn)':[20],'Doluluk (%)':[84.5],'Shrinkage (%)':[25]})
        values=dict(erlang_summary_values({'coverage':coverage}))
        self.assertEqual(values['AHT'],'195 sn');self.assertEqual(values['Beklenen servis seviyesi'],'82.4%');self.assertEqual(values['Ortalama doluluk'],'84.5%')

    def test_publication_scope_keeps_transferred_foreign_capacity_out_of_turkish_batch(self):
        from ortak.yayin_servisi import publication_scope
        people=[dict(emp('1'),language='tr'),dict(emp('2'),language='en')]
        result={'staff':people,'plan':[row('1',DAY),dict(row('2',DAY),source='foreign_language_plan')],'issues':[],'breaks':[]}
        scoped=publication_scope(result,{'tr':True,'en':False,'ar':False})
        self.assertEqual({person['employee_id'] for person in scoped['staff']},{'1'});self.assertEqual({record['employee_id'] for record in scoped['plan']},{'1'})
        self.assertEqual({record['employee_id'] for record in result['plan']},{'1','2'})


if __name__=='__main__':unittest.main()
