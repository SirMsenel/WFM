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

    def test_foreign_plan_result_restores_daily_ring_and_interval_list(self):
        from streamlit.testing.v1 import AppTest
        at=AppTest.from_string('''
import pandas as pd
from modules.vardiya_plani.yabanci_dil_plani import _interval_result
coverage=pd.DataFrame([{"Tarih":"2026-11-23","Slot":17,"İhtiyaç":2,"Net Agent":1.5,"Atanan":1.5,"Brüt Atanan":2,"Sayaca Dahil":True}])
_interval_result({"coverage":coverage},"en")
''',default_timeout=30).run()
        self.assertFalse(at.exception)
        self.assertTrue(any('Günlük İhtiyaç Karşılama' in item.value for item in at.markdown))
        self.assertTrue(any('30 Dakikalık Plan Sonucu' in item.value for item in at.markdown))
        matrix=at.dataframe[0].value
        self.assertEqual(matrix.index[16],'08:00–08:30')
        self.assertIn('23.11 Pazartesi',matrix.columns)
        self.assertEqual(matrix.iloc[16,0],'2/2 · 0')

    def test_foreign_language_build_never_reuses_transferred_people_from_other_language(self):
        from test_planning_round2 import Round2LogicTests
        from modules.vardiya_plani.yabanci_dil_plani import _build
        state=Round2LogicTests().state();state.update(plan_ctx_confirmed=True,plan_group_priority=list(state['shift_rules']['work_type']),status_rules={'enabled':False},
            foreign_language_transferred_ids={'en':['2']},foreign_language_reserved_ids={'en':['2']})
        result=_build(state,'ar',state['sp_staffing_result_df'])
        self.assertEqual({str(person['employee_id']) for person in result['staff']},{'3'})

    def test_foreign_plan_uses_direct_headcount_and_statuses_do_not_create_false_gap(self):
        from test_planning_round2 import Round2LogicTests
        from modules.vardiya_plani.yabanci_dil_plani import _build
        from ortak.statuler import defaults
        state=Round2LogicTests().state();cfg=defaults();cfg.update(enabled=True,automatic=True,shrinkage_included=True,coaching_by_leader=False)
        for rule in cfg['groups'].values():rule['coaching_monthly_minutes']=0
        state.update(plan_ctx_confirmed=True,plan_group_priority=list(state['shift_rules']['work_type']),status_rules=cfg,staffing_parameters={'shrinkage':.45},slot_shrinkage=[{'start_slot':1,'end_slot':48,'rate':.45}],group_hour_targets=[])
        need=state['sp_staffing_result_df'].assign(**{'Net Agent':.1,'Shrinkage (%)':90,'AHT (sn)':195,'Hedef SL (%)':80})
        result=_build(state,'en',need)
        self.assertEqual(result['coverage']['Eksik'].sum(),0);self.assertEqual(result['coverage']['Fazla'].sum(),0)
        self.assertNotIn('Shrinkage (%)',result['coverage']);self.assertNotIn('Net Agent',result['coverage']);self.assertNotIn('AHT (sn)',result['coverage'])
        self.assertTrue(any(item['kind']=='Yemek' for item in result['breaks']));self.assertTrue(any(item['kind']=='Mola' for item in result['breaks']))

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
        people=[dict(emp('A'),language='en',username='english_only'),dict(emp('B'),language='en',username='bilingual'),dict(emp('C'),language='tr',username='turkish')]
        result={'staff':people[:2],'period':{'start':str(day),'end':str(day)},'plan':[
            dict(row('A',day),full_name='English Only'),dict(row('B',day),full_name='Bilingual')]}
        state={'employees_cache':people,'planning_languages':{'tr':True,'en':False,'ar':False},'plan_ctx':{'start':day,'end':day},
               'shift_rules':default_shift_rules(),'draft_shift_plan':[],'fixed_shift_records':[],'shift_overrides':[],
               'published_shift_plan':[],'trk_requests':[],'group_hour_targets':[],'foreign_language_plans':{'en':result},
               'sp_staffing_result_df':pd.DataFrame([{'Tarih':day,'Slot':17,'Planlanan Agent':3.,'Net Agent':2.}])}
        with patch('modules.vardiya_plani.yabanci_dil_plani.save_keys'):_transfer(state,'en',result,['B'])
        self.assertEqual(state['foreign_language_reserved_ids']['en'],['A','B'])
        self.assertEqual(state['foreign_language_transferred_ids']['en'],['B'])
        self.assertFalse(state['draft_shift_plan'])
        staff,fixed,_,_,_=collect_inputs(state)
        self.assertEqual({person['employee_id'] for person in staff},{'C'})
        self.assertFalse(fixed)
        from ortak.plan_ihtiyaci import demand
        counted=demand(state).iloc[0]
        self.assertEqual(counted['Planlanan Agent'],2);self.assertEqual(counted['Net Agent'],1)

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
        state={'foreign_language_plans':{'en':{'period':{'start':str(day),'end':str(day)},'staff':[emp('A'),emp('B')],
                                               'plan':[dict(row('A',day),source='auto'),dict(row('B',day),source='auto')]}},
               'foreign_language_transferred_ids':{'en':['B']},'draft_shift_plan':[]}
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

    def test_publication_finalizes_only_requests_of_published_people(self):
        from ortak.talep_simulasyonu import finalize_in_memory
        request=lambda ident,eid:{'id':ident,'queue':'SIMULATION','status':'Simülasyonda','employee_id':eid,'type':'Yıllık İzin Talebi','start_date':str(DAY),'end_date':str(DAY),'events':[]}
        state={'trk_requests':[request('en-request','1'),request('ar-request','2')]}
        finalize_in_memory(state,[row('1',DAY)],str(DAY),str(DAY),'planner')
        by_id={item['id']:item for item in state['trk_requests']}
        self.assertEqual(by_id['en-request']['queue'],'Closed')
        self.assertEqual(by_id['ar-request']['queue'],'SIMULATION')

    def test_turkish_coverage_percentage_uses_served_need_and_excludes_disabled_slots(self):
        from ortak.planlama_gorunumu import coverage_metrics
        frame=pd.DataFrame([{'İhtiyaç':3,'Atanan':2,'Sayaca Dahil':True},{'İhtiyaç':3,'Atanan':4,'Sayaca Dahil':True},{'İhtiyaç':99,'Atanan':0,'Sayaca Dahil':False}])
        values=coverage_metrics(frame)
        self.assertAlmostEqual(values['rate'],5/6);self.assertEqual(values['left'],1);self.assertEqual(values['excess'],1)

    def test_main_engine_can_cross_filled_slots_to_close_a_small_gap(self):
        from modules.vardiya_plani.vardiya_motoru import generate_plan
        from test_planning import rules
        config=rules();config['capacity']={'max_overstaff':0,'recommendation_overstaff_limit':1};config['work_type']['akademi']['min_shift_hours']=4
        need=demand(count=0,slots=range(1,49));need.loc[need.Slot.isin([33,34]),'Planlanan Agent']=1
        without=generate_plan([emp('1','akademi')],need,config,list(config['work_type']),DAY,DAY)
        with_limit=generate_plan([emp('1','akademi')],need,config,list(config['work_type']),DAY,DAY,gap_overstaff_limit=1)
        self.assertGreater(without['coverage']['Eksik'].sum(),0)
        self.assertEqual(with_limit['coverage']['Eksik'].sum(),0);self.assertGreater(with_limit['coverage']['Fazla'].sum(),0)

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

    def test_mandatory_meal_and_break_are_not_dropped_when_net_floor_has_no_room(self):
        from ortak.statuler import defaults,meal_plan
        cfg=defaults();cfg.update(enabled=True,automatic=True,shrinkage_included=True,coaching_by_leader=False)
        rule=cfg['groups']['fulltime'];rule.update(min_shift_hours=0,meal_minutes=30,break_rules=[{'min_hours':0,'max_hours':24,'minutes':10}],break_preferred_minutes=10,coaching_monthly_minutes=0)
        coverage=pd.DataFrame([{'Tarih':DAY,'Slot':slot,'İhtiyaç':1,'Planlanan Agent':1,'Net Agent':1,'Shrinkage (%)':0,'Atanan':1,'Eksik':0,'Fazla':0,'Sayaca Dahil':True} for slot in range(17,35)])
        items,out,issues=meal_plan({'status_rules':cfg,'staffing_parameters':{'shrinkage':0}},[row('1',DAY,start='08:00',end='17:00')],coverage,[emp('1')])
        self.assertEqual(sum(item['kind']=='Yemek' for item in items),1)
        self.assertEqual(sum((pd.Timestamp(item['end'])-pd.Timestamp(item['start'])).total_seconds()/60 for item in items if item['kind']=='Mola'),10)
        self.assertGreater(out['Eksik'].sum(),0)
        self.assertFalse(any('tamamlanamadı' in issue['Sorun'] for issue in issues))

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

    def test_turkish_status_scope_excludes_foreign_capacity_rows(self):
        from modules.vardiya_plani.olustur_kontrol_yayinla import status_scope
        people=[dict(emp('1'),language='tr'),dict(emp('2'),language='en')]
        plan=[row('1',DAY),dict(row('2',DAY),source='foreign_language_plan',language='en')]
        scoped_plan,scoped_staff=status_scope(plan,people,[plan[1]])
        self.assertEqual({record['employee_id'] for record in scoped_plan},{'1'});self.assertEqual({person['employee_id'] for person in scoped_staff},{'1'})

    def test_foreign_approval_ignores_turkish_staffing_changes_and_keeps_zero_gap(self):
        import tempfile
        from pathlib import Path
        from test_planning_round2 import Round2LogicTests
        from modules.vardiya_plani.yabanci_dil_plani import _build
        from ortak.statuler import defaults
        from ortak.calisma_alani_deposu import init_db,save_keys
        from ortak.yayin_onaylari import submit,proposals,is_current,vote
        with tempfile.TemporaryDirectory() as folder:
            state=Round2LogicTests().state();cfg=defaults();cfg.update(enabled=True,automatic=True,shrinkage_included=True,coaching_by_leader=False)
            for rule in cfg['groups'].values():rule['coaching_monthly_minutes']=0
            state.update(workspace_db_path=str(Path(folder)/'w.db'),profile={'position':'wfm','username':'planner1'},plan_ctx_confirmed=True,plan_group_priority=list(state['shift_rules']['work_type']),status_rules=cfg,group_hour_targets=[],fixed_shift_records=[],shift_overrides=[],trk_requests=[],plan_overrides=[],acad_schedules={},acad_exam_calendar={})
            init_db(state['workspace_db_path']);save_keys(state)
            result=_build(state,'en',state['sp_staffing_result_df']);ident=submit(state,result,{'tr':False,'en':True,'ar':False})
            item=next(record for record in proposals(state) if record['id']==ident)
            self.assertEqual(item['rate'],0);self.assertTrue(is_current(state,item))
            state['sp_staffing_result_df']=state['sp_staffing_result_df'].assign(**{'Planlanan Agent':99});state['slot_shrinkage']=[{'start_slot':1,'end_slot':48,'rate':.8}];save_keys(state)
            item=next(record for record in proposals(state) if record['id']==ident)
            self.assertTrue(is_current(state,item));self.assertFalse(vote(state,ident))
            state['profile']={'position':'wfm','username':'planner2'};self.assertTrue(vote(state,ident))

    def test_parallel_language_approvals_stay_current_with_display_revision(self):
        import copy,tempfile
        from pathlib import Path
        from test_round5 import make_state
        from test_round4 import draft
        from ortak.calisma_alani_deposu import connect,save_keys
        from ortak.yayin_onaylari import submit,proposals,is_current
        with tempfile.TemporaryDirectory() as folder:
            state=make_state(Path(folder)/'w.db',Path(folder)/'a.db');state.update(profile={'position':'wfm','username':'planner1'},plan_ctx={'start':DAY,'end':DAY},plan_group_priority=list(state['shift_rules']['work_type']),published_shift_plan=[])
            state['sp_staffing_result_df']=demand();save_keys(state)
            with connect(state['workspace_db_path']) as db:db.execute("INSERT INTO metadata VALUES('directory_revision','rev-1') ON CONFLICT(key) DO UPDATE SET value=excluded.value")
            state['_directory_revision']='rev-1|2026-11-23'
            result=draft(state);english=copy.deepcopy(result);arabic=copy.deepcopy(result)
            for person in english['staff']:person['language']='en'
            for person in arabic['staff']:person['language']='ar'
            first=submit(state,english,{'tr':False,'en':True,'ar':False})
            state['foreign_language_plans']={'en':english,'ar':arabic};save_keys(state)
            second=submit(state,arabic,{'tr':False,'en':False,'ar':True})
            items={item['id']:item for item in proposals(state)}
            self.assertTrue(is_current(state,items[first]));self.assertTrue(is_current(state,items[second]))


if __name__=='__main__':unittest.main()
