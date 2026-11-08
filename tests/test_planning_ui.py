"""Streamlit integration checks. No backend, network or saved-user data needed."""
import unittest
from datetime import timedelta

from streamlit.testing.v1 import AppTest
from test_planning import DAY, demand, emp, row, rules


class PlanningUITests(unittest.TestCase):
    def app(self, count=1, fixed=None):
        at = AppTest.from_string('from modules.shift_planing.publish import render\nrender()', default_timeout=30)
        for key, value in {
            'profile': {'position': 'wfm'}, 'shift_rules': rules(),
            'plan_group_priority': ['fulltime', 'akademi', 'dis_kaynak'],
            'plan_ctx': {'start': DAY, 'end': DAY}, 'plan_ctx_confirmed': True,
            'employees_cache': [emp()], 'sp_staffing_result_df': demand(count=count),
            'fixed_shift_records': fixed or [],
        }.items():
            at.session_state[key] = value
        at.run()
        self.assertFalse(at.exception)
        return at

    def button(self, at, key):
        return next(b for b in at.button if b.key == key)

    def test_create_publish_and_stale_guard(self):
        at = self.app()
        self.button(at, 'planning_generate').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state['planning_result']['coverage']['Eksik'].sum(), 0)
        self.button(at, 'planning_publish').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.session_state['published_shift_plan']), 1)
        at.session_state['shift_rules']['work_type']['fulltime']['shift_total_hours'] = 8
        at.run()
        self.assertFalse(any(b.key=='planning_publish' for b in at.button))
        self.assertTrue(at.warning)

    def test_unmet_demand_is_published_by_explicit_accept_button(self):
        at = self.app(count=2)
        self.button(at, 'planning_generate').click().run()
        self.assertFalse(at.exception)
        self.assertFalse(self.button(at, 'planning_publish').disabled)
        self.assertEqual(self.button(at, 'planning_publish').label,'Eksikleri Kabul Et ve Planı Yayınla')
        self.button(at, 'planning_publish').click().run()
        self.assertFalse(at.exception)
        self.assertTrue(at.session_state['published_shift_plan'])
        self.assertTrue(any('Yayınlanan Vardiya Tablosu' in x.value for x in at.markdown))

    def test_conflicting_fixed_row_prevents_publication(self):
        at = self.app(fixed=[row(start='08:00', end='20:00')])
        self.button(at, 'planning_generate').click().run()
        self.assertFalse(at.exception)
        self.assertTrue(at.session_state['planning_result']['issues'])
        self.assertTrue(self.button(at, 'planning_publish').disabled)

    def test_agents_cannot_generate(self):
        at = self.app()
        at.session_state['profile'] = {'position': 'agent'}
        at.run()
        self.assertFalse(at.exception)
        self.assertFalse(any(b.key == 'planning_generate' for b in at.button))

    def test_record_capture_and_delete(self):
        at = AppTest.from_string('from modules.all_shifts._fixed_records import render_fixed_records\nrender_fixed_records("YILLIK_IZIN", 2026, 11)')
        at.session_state['profile'] = {'position': 'wfm'}
        at.session_state['employees_cache'] = [emp()]
        at.session_state['personnel_cache'] = [emp()]
        at.run()
        at.multiselect[0].select('1')
        next(b for b in at.button if b.label == 'Kesin Kaydı Kaydet').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.session_state['fixed_shift_records']), 1)
        self.button(at, 'fixed_delete_YILLIK_IZIN').click().run()
        self.assertFalse(at.exception)
        self.assertFalse(at.session_state['fixed_shift_records'])


if __name__ == '__main__':
    unittest.main()
