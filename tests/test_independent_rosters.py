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
