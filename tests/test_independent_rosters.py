import copy
import sqlite3

from test_phase7 import Base
from test_planning import DAY, demand, emp, rules
from datetime import datetime, time, timedelta
from modules.vardiya_plani.vardiya_motoru import generate_plan
from modules.vardiya_plani.yabanci_dil_plani import _build, _transfer
from modules.vardiya_plani.planlama_verileri import fingerprint
from ortak.personel import planner_people
from ortak.planlama import preview_plan
from ortak.planlama_gorunumu import coverage_comparison_matrix
from ortak.yayin_onaylari import submit, vote, is_current, proposals
from ortak.calisma_alani_deposu import connect, loads


class IndependentRosters(Base):
    def test_three_tickets_survive_other_publications_and_fresh_approver_session(self):
        s = self.s
        with sqlite3.connect(s['auth_db_path']) as db:
            db.execute("UPDATE employees SET language='en' WHERE employee_id=2")
            db.execute("UPDATE employees SET language='ar' WHERE employee_id=3")
        s.pop('employees_cache')
        planner_people(s)
        s['planning_languages'] = {'en': False, 'ar': False, 'tr': True}
        ids = []
        for lang in ('en','ar'):
            result = _build(s, lang, demand())
            s.setdefault('foreign_language_plans', {})[lang] = result
            _transfer(s,lang,result,[result['staff'][0]['employee_id']])
            ids.append(submit(s,result,{lang:True, 'tr':False, ('ar' if lang=='en' else 'en'):False}))
        result = preview_plan(s,True)
        result['period'] = {'start':str(DAY),'end':str(DAY)}
        s['planning_result_fingerprint'] = fingerprint(s)
        ids.append(submit(s,result))
        s.pop('employees_cache')
        for ident in ids:
            self.planner('first')
            self.assertTrue(is_current(s,next(p for p in proposals(s) if p['id']==ident)))
            self.assertFalse(vote(s,ident))
            self.planner('second')
            self.assertTrue(vote(s,ident))
        self.assertEqual({p['status'] for p in proposals(s)}, {'Yayınlandı'})
        with connect(s['workspace_db_path']) as db:
            self.assertEqual(loads(db.execute("SELECT payload FROM work_state WHERE key='planning_languages'").fetchone()[0]),s['planning_languages'])

    def test_edited_shift_contribution_follows_actual_slots(self):
        s = self.s
        s['employees_cache'][1]['language']='en'
        s['planning_languages']={'tr':True,'en':False,'ar':False}
        result=_build(s,'en',demand())
        rows=copy.deepcopy(result['plan'])
        rows[0].update(start='09:00',end='18:00',source='foreign_manual')
        result=_build(s,'en',demand(),rows)
        s['foreign_language_plans']={'en':result}
        _transfer(s,'en',result,[rows[0]['employee_id']])
        coverage=preview_plan(s, True)['coverage']
        matrix=coverage_comparison_matrix(coverage,DAY)
        self.assertEqual(matrix.iloc[16,0],(0,1))
        self.assertEqual(matrix.iloc[18,0],(1,1))

    def test_transfer_notice_and_editable_calendar_survive_rerun(self):
        from streamlit.testing.v1 import AppTest
        self.s['employees_cache'][1]['language']='en'
        self.s['language_demands']={'en':demand(slots=range(1,49))}
        app=AppTest.from_string('from modules.vardiya_plani.yabanci_dil_plani import render\nrender()', default_timeout=30)
        for key,value in self.s.items():
            app.session_state[key]=value
        app.run().button(key='foreign_generate_en').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any(button.label=='Vardiya düzeltmelerini kaydet' for button in app.button))
        app.button(key='foreign_transfer_all_en').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('kişi kapasitesi' in item.value for item in app.success))

    def test_unused_capacity_can_cover_provisional_off_while_respecting_weekly_limit(self):
        cfg=rules()
        cfg['off_rules']={'distribution':'İhtiyaca göre dağıt'}
        cfg['work_type']['fulltime']['min_off_days']=2
        need=demand(days=7,count=2)
        need.loc[need.Tarih==DAY,'Planlanan Agent']=1
        unavailable={'1':[(datetime.combine(DAY+timedelta(days=1),time()),
                            datetime.combine(DAY+timedelta(days=4),time()))]}
        result=generate_plan([emp()],need,cfg,list(cfg['work_type']),DAY,DAY+timedelta(days=6),
                             unavailable=unavailable,gap_overstaff_limit=1)
        self.assertEqual(result['coverage'].loc[result['coverage'].Tarih==DAY,'Eksik'].sum(),0)
        self.assertLessEqual(sum(row['shift_code']=='WORK' for row in result['plan']),5)

    def test_fixed_standard_hours_with_higher_ceiling(self):
        cfg=rules()
        cfg['work_type']['fulltime']['shift_total_hours_max']=10
        people=[emp(str(i)) for i in range(24)]
        result=generate_plan(people,demand(count=12),cfg,list(cfg['work_type']),DAY,DAY)
        self.assertEqual(result['coverage'].Eksik.sum(),0)
        self.assertEqual(sum(r['shift_code']=='WORK' for r in result['plan']),12)

    def test_foreign_overstaff_limit_is_separate_from_turkish_limit(self):
        s=self.s
        s['employees_cache']=[dict(emp(str(i)),language='en') for i in range(1,4)]
        need=demand(count=2)
        need.loc[need.Slot==25,'Planlanan Agent']=0
        s['shift_rules']['capacity']={'max_overstaff':9}
        for allowed in (0,1,2):
            s['shift_rules']['capacity']['foreign_max_overstaff']=allowed
            result=_build(s,'en',need)
            self.assertEqual(result['coverage'].loc[result['coverage'].Slot==25,'Atanan'].iloc[0],allowed)
            self.assertEqual(s['shift_rules']['capacity']['max_overstaff'],9)

    def test_two_saved_votes_can_publish_after_reason_without_third_vote(self):
        from ortak.talep_servisi import create_request
        from ortak.donem_kilitleri import record_bypass,planning_problem
        from ortak.calisma_alani_deposu import dumps
        self.s['profile']={'position':'agent','username':'u1','employee_id':'1','team_lead':'Lead'}
        create_request(self.s,{'type':'Yıllık İzin Talebi','start_date':str(DAY)})
        self.planner('p1')
        with self.assertRaisesRegex(ValueError,'bekleyen talepler'):
            self.queue()
        # An already queued ticket from the previous version with both votes.
        record_bypass(self.s,self.s['plan_ctx'],planning_problem(self.s),'İlk inceleme')
        ident=self.queue()
        self.s['planning_bypass']={}
        with connect(self.s['workspace_db_path']) as db:
            item=loads(db.execute('SELECT payload FROM plan_approvals WHERE id=?',(ident,)).fetchone()[0])
            db.execute("DELETE FROM work_state WHERE key='planning_bypass'")
            item['votes']=[{'actor':'p1'},{'actor':'p2'}]
            db.execute('UPDATE plan_approvals SET payload=? WHERE id=?',(dumps(item),ident))
        with self.assertRaisesRegex(ValueError,'bekleyen talepler'):
            vote(self.s,ident)
        record_bypass(self.s,self.s['plan_ctx'],planning_problem(self.s),'Dönemde ayrıca değerlendirilecek')
        self.assertTrue(vote(self.s,ident))
        self.assertEqual(len(proposals(self.s)[0]['votes']),2)

    def test_simulated_timed_request_matches_person_and_times_at_publication(self):
        from ortak.talep_simulasyonu import finalize_in_memory
        base={'queue':'SIMULATION','status':'Simülasyonda','type':'Gece Vardiyası Talebi','start_date':str(DAY),'start_time':'00:00','end_time':'08:00'}
        s={'trk_requests':[dict(base,created_by='u1'),dict(base,employee_id='2'),dict(base,employee_id='3')]}
        shifts=[dict(employee_id=i,date=str(DAY),shift_code='GECE',start='00:00',end=end) for i,end in [('1','08:00'),('2','07:00')]]
        finalize_in_memory(s,shifts,DAY,DAY,'planlama',[emp('1'),emp('2')])
        self.assertEqual([r['status'] for r in s['trk_requests']],['Onaylandı','Reddedildi','Simülasyonda'])

    def test_daily_donut_totals_match_visible_gross_comparison_cells(self):
        import pandas as pd
        from streamlit.testing.v1 import AppTest
        frame=pd.DataFrame({'Tarih':[DAY]*3,'Slot':[17,18,19],'İhtiyaç':[2,1,8],
                            'Toplam brüt ihtiyaç':[4,2,8],'Aktarılan kişi':[2,1,0],
                            'Atanan':[0.4,1.5,0],'Brüt Atanan':[1,3,0],'Sayaca Dahil':[True,True,False]})
        matrix=coverage_comparison_matrix(frame,DAY)
        self.assertEqual([matrix.iloc[i,0] for i in (16,17,18)],[(3,4),(4,2),None])
        app=AppTest.from_string("import streamlit as st\nfrom ortak.planlama_gorunumu import daily_gap_summary\ndaily_gap_summary({'coverage':st.session_state['coverage']})")
        app.session_state['coverage']=frame
        app.run()
        self.assertFalse(app.exception)
        html=''.join(m.value for m in app.markdown)
        self.assertIn('>−1<',html)
        self.assertIn('>+2<',html)

    def test_midshift_meal_when_line_has_spare_capacity(self):
        import pandas as pd
        from test_planning import row
        from ortak.statuler import defaults,meal_plan
        cfg=defaults()
        cfg.update(enabled=True,automatic=True)
        cfg['groups']['fulltime'].update(meal_minutes=30)
        coverage=demand(slots=range(17,35)).assign(Atanan=4,İhtiyaç=1,Eksik=0,Fazla=3)
        items,_,_=meal_plan({'status_rules':cfg},[row()],coverage,[emp()])
        meal=next(r for r in items if r['kind']=='Yemek')
        self.assertEqual((pd.Timestamp(meal['start']).strftime('%H:%M'),pd.Timestamp(meal['end']).strftime('%H:%M')),('12:15','12:45'))

    def test_draft_suggestions_follow_selected_day_and_time(self):
        from streamlit.testing.v1 import AppTest
        import pandas as pd
        app=AppTest.from_string("""
import streamlit as st
from ortak.eksik_aksiyonlari import render_actions
from unittest.mock import patch
def find(s,day,first,last,**kwargs):
    st.session_state['tested_range']=(day,first,last,kwargs['exact_window'])
    return [],[]
with patch('ortak.eksik_aksiyonlari.suggestions',find):
    render_actions(st.session_state,{'coverage':st.session_state['test_coverage']},'draft_action_gaps')
""")
        app.session_state['test_coverage']=pd.DataFrame({'Tarih':[DAY],'Slot':[29],'Eksik':[2]})
        app.run()
        self.assertNotIn('tested_range',app.session_state)
        app.selectbox(key='draft_action_gaps_from').set_value(28).run()
        app.selectbox(key='draft_action_gaps_until').set_value(31).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['tested_range'],(str(DAY),28,31,True))

    def test_new_pending_request_after_submission_needs_its_own_reason(self):
        from ortak.talep_servisi import create_request
        from ortak.donem_kilitleri import record_bypass,planning_problem
        ident=self.queue()
        self.assertFalse(vote(self.s,ident))
        self.s['profile']={'position':'agent','username':'u1','employee_id':'1','team_lead':'Lead'}
        create_request(self.s,{'type':'Yıllık İzin Talebi','start_date':str(DAY)})
        self.planner('other')
        with self.assertRaisesRegex(ValueError,'bekleyen talepler'):
            vote(self.s,ident)
        self.assertEqual(len(proposals(self.s)[0]['votes']),1)
        record_bypass(self.s,self.s['plan_ctx'],planning_problem(self.s),'Bir sonraki değerlendirmeye bırakıldı')
        self.assertTrue(vote(self.s,ident))

    def test_monday_uses_both_ends_when_shift_candidates_have_equal_gain(self):
        cfg=rules()
        cfg['work_type']['fulltime']['shift_total_hours']=3
        people=[emp(str(i)) for i in range(7)]
        need=demand(slots=range(17,38))
        need['Planlanan Agent']=[v for v in [1,1,2,2,5,1,4] for _ in range(3)]
        result=generate_plan(people,need,cfg,list(cfg['work_type']),DAY,DAY,gap_overstaff_limit=1)
        self.assertLessEqual(result['coverage'].Eksik.sum(),15)
        self.assertLessEqual(result['coverage'].Fazla.max(),1)
        self.assertFalse(result['issues'])
