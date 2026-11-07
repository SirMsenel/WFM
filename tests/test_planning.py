import copy
from datetime import date, datetime, timedelta
import unittest

import pandas as pd

from modules.shift_planing.engine import generate_plan, bounds
from modules.shift_planing.planning_data import collect_inputs, fingerprint

DAY = date(2026, 11, 2)


def rules():
    return {'general': {'weekday_general_start': '08:00', 'weekend_general_start': '08:00', 'global_latest_end': '03:00'},
            'work_type': {'fulltime': {'shift_total_hours': 9, 'max_days_per_week_default': 5, 'allow_6th_day': False, 'night_allowed': False},
                          'akademi': {'shift_total_hours_max': 7, 'max_days_per_week': 6, 'min_rest_hours': 11, 'night_allowed': True, 'max_end_time': '03:00'},
                          'dis_kaynak': {'shift_total_hours': 11, 'max_days_per_week': 6, 'night_allowed': False, 'max_end_time': '00:00'}},
            'night': {'enabled': True, 'allowed_work_types': ['akademi']}}


def emp(eid='1', group='fulltime'):
    return {'employee_id': eid, 'username': f'u{eid}', 'full_name': f'Person {eid}', 'position': 'agent', 'work_type': group}


def demand(start=DAY, days=1, count=1, slots=range(17, 35)):
    return pd.DataFrame([{'Tarih': start+timedelta(days=d), 'Slot': s, 'Planlanan Agent': count}
                         for d in range(days) for s in slots])


def row(eid='1', day=DAY, code='WORK', start='08:00', end='17:00', source='manual_single'):
    return {'employee_id': eid, 'date': str(day), 'shift_code': code, 'start': start, 'end': end, 'source': source}


def run(staff=None, df=None, fixed=(), history=(), unavailable=None, order=None, r=None, start=DAY, end=DAY):
    return generate_plan(staff or [emp()], df if df is not None else demand(), r or rules(),
                         order or ['fulltime', 'akademi', 'dis_kaynak'], start, end,
                         fixed=fixed, history=history, unavailable=unavailable)


class EngineTests(unittest.TestCase):
    def test_covers_demand(self):
        result = run()
        self.assertEqual(result['coverage']['Eksik'].sum(), 0)
        self.assertEqual(result['plan'][0]['start'], '08:00')
        self.assertEqual(result['issues'], [])

    def test_priority(self):
        staff = [emp(), emp('2', 'akademi')]
        result = run(staff=staff, order=['akademi', 'fulltime', 'dis_kaynak'], df=demand(slots=range(17, 25)))
        codes = {r['employee_id']: r['shift_code'] for r in result['plan']}
        self.assertEqual(codes, {'1': 'OFF', '2': 'WORK'})

    def test_fixed_leave_wins_and_reports_manual_conflict(self):
        leave = row(code='YILLIK_IZIN', start=None, end=None, source='fixed_external')
        result = run(fixed=[leave, row()])
        self.assertEqual(result['plan'][0]['shift_code'], 'YILLIK_IZIN')
        self.assertGreater(result['coverage']['Eksik'].sum(), 0)
        self.assertEqual(len(result['issues']), 1)

    def test_midnight_coverage_uses_next_date(self):
        fixed = row(code='GECE', start='22:00', end='02:00')
        result = run(staff=[emp(group='akademi')], df=demand(days=2, slots=[1, 2, 45, 46]),
                     end=DAY+timedelta(days=1), fixed=[fixed])
        coverage = result['coverage']
        self.assertEqual(coverage[(coverage.Tarih == DAY+timedelta(days=1)) & (coverage.Slot == 1)]['Atanan'].iloc[0], 1)
        self.assertEqual(coverage[(coverage.Tarih == DAY) & (coverage.Slot == 1)]['Atanan'].iloc[0], 0)

    def test_school_avoided(self):
        block = (datetime(2026, 11, 2, 8), datetime(2026, 11, 2, 12))
        result = run(staff=[emp(group='akademi')], df=demand(slots=range(17, 39)), unavailable={'1': [block]})
        working = [r for r in result['plan'] if bounds(r)]
        self.assertTrue(working)
        self.assertTrue(all(bounds(r)[0] >= block[1] for r in working))

    def test_exam_day_block(self):
        interval = (datetime(2026, 11, 2), datetime(2026, 11, 3))
        result = run(unavailable={'1': [interval]})
        self.assertEqual(result['plan'][0]['shift_code'], 'OFF')

    def test_history_counts_iso_week(self):
        friday = DAY+timedelta(days=4)
        hist = [row(day=DAY+timedelta(days=i)) for i in range(4)]
        r = rules()
        r['work_type']['fulltime']['max_days_per_week_default'] = 4
        result = run(r=r, start=friday, end=friday+timedelta(days=1),
                     df=demand(start=friday, days=2), history=hist)
        self.assertTrue(all(x['shift_code'] == 'OFF' for x in result['plan']))

    def test_rest_against_future_fixed_row(self):
        next_day = DAY+timedelta(days=1)
        fixed = [row(day=next_day, start='08:00', end='15:00')]
        result = run(staff=[emp(group='akademi')], df=demand(days=2, slots=range(37, 48)), end=next_day, fixed=fixed)
        for r in result['plan']:
            if r['date'] == str(DAY) and bounds(r):
                self.assertLessEqual(bounds(r)[1], datetime(2026, 11, 2, 21))

    def test_adjacent_fixed_history_counts_week(self):
        last_day = DAY+timedelta(days=5)
        fixed = [row(day=DAY+timedelta(days=i), start='08:00', end='15:00') for i in range(5)]
        r = rules()
        r['work_type']['akademi']['max_days_per_week'] = 5
        result = run(staff=[emp(group='akademi')], start=last_day, end=last_day,
                     df=demand(start=last_day), fixed=fixed, r=r)
        self.assertEqual(result['plan'][0]['shift_code'], 'OFF')

    def test_no_mutation_and_determinism(self):
        fixed = [row()]
        original = copy.deepcopy(fixed)
        self.assertEqual(run(fixed=fixed)['plan'], run(fixed=fixed)['plan'])
        self.assertEqual(fixed, original)

    def test_invalid_demand(self):
        for slot, count in [(0, 1), (49, 1), (1.5, 1), (1, float('inf')), (1, -1)]:
            df = pd.DataFrame([{'Tarih': DAY, 'Slot': slot, 'Planlanan Agent': count}])
            with self.assertRaises(ValueError):
                run(df=df)

    def test_duplicate_demand(self):
        df = demand()
        with self.assertRaises(ValueError):
            run(df=pd.concat([df, df]))

    def test_group_end_limit(self):
        result = run(staff=[emp(group='dis_kaynak')], df=demand(slots=range(35, 49)))
        for r in result['plan']:
            if bounds(r):
                self.assertLessEqual(bounds(r)[1], datetime(2026, 11, 3))

    def test_manual_violation_is_visible(self):
        result = run(fixed=[row(start='08:00', end='20:00')])
        self.assertTrue(result['issues'])
        self.assertEqual(result['plan'][0]['end'], '20:00')

    def test_tomorrow_leave_blocks_overnight_work(self):
        tomorrow = DAY+timedelta(days=1)
        result = run(staff=[emp(group='akademi')], df=demand(days=2, slots=range(41,49)), end=tomorrow,
                     fixed=[row(day=tomorrow, code='YILLIK_IZIN', start=None, end=None)])
        for r in result['plan']:
            if bounds(r):
                self.assertLessEqual(bounds(r)[1], datetime(2026,11,3))

    def test_0700_boost_is_capped(self):
        r = rules()
        r['boosts'] = {'weekday_0700_fulltime_extra_enabled': True, 'weekday_0700_fulltime_extra_count': 1}
        result = run(staff=[emp(),emp('2')], df=demand(count=2,slots=range(15,33)),r=r)
        self.assertEqual(sum(x.get('start') == '07:00' for x in result['plan']),1)

    def test_zero_demand_has_no_unnecessary_work(self):
        result = run(df=demand(count=0))
        self.assertTrue(all(x['shift_code']=='OFF' for x in result['plan']))


class AdapterTests(unittest.TestCase):
    def state(self):
        return {'employees_cache': [emp(group='akademi')], 'plan_ctx': {'start': DAY, 'end': DAY},
                'sp_staffing_result_df': demand(), 'shift_rules': rules()}

    def test_approved_leave_and_identity(self):
        state = self.state()
        state['trk_requests'] = [{'id': 'r1', 'created_by': 'u1', 'type': 'Yıllık İzin Talebi',
                                  'status': 'Uygulandı', 'queue': 'Closed', 'start_date': str(DAY), 'end_date': str(DAY)}]
        employees, fixed, history, unavailable, issues = collect_inputs(state)
        self.assertEqual(issues, [])
        self.assertEqual(fixed[0]['employee_id'], '1')
        self.assertEqual(fixed[0]['shift_code'], 'YILLIK_IZIN')

    def test_waiting_request_not_applied(self):
        state = self.state()
        state['trk_requests'] = [{'id': 'r', 'created_by': 'u1', 'type': 'Yıllık İzin Talebi', 'queue': 'WFM', 'status': 'Planlamaya İletildi'}]
        self.assertEqual(collect_inputs(state)[1], [])

    def test_unknown_user_reported(self):
        state = self.state()
        state['fixed_shift_records'] = [dict(row(), employee_id='999')]
        self.assertTrue(collect_inputs(state)[4])

    def test_structured_class_and_exam(self):
        state = self.state()
        state['planning_class_term'] = '2026-Güz'
        state['acad_schedules'] = {'u1': {'2026-Güz': {'Saat': ['08:00-10:00'], 'Pazartesi': ['Math']}}}
        state['acad_exam_calendar'] = {'u1': {'2026-Sinav': {'Tarih': [str(DAY)], 'Saat': ['12:00'], 'Ders': ['Math']}}}
        employees, fixed, history, unavailable, issues = collect_inputs(state)
        self.assertFalse(issues)
        self.assertTrue(any((b-a).total_seconds() == 86400 for a,b in unavailable['1']))
        self.assertTrue(any((b-a).total_seconds() == 7200 for a,b in unavailable['1']))

    def test_stale_fingerprint(self):
        state = self.state()
        original = fingerprint(state)
        state['draft_shift_plan'] = [row()]
        self.assertNotEqual(original, fingerprint(state))

    def test_rebuild_same_result(self):
        state = self.state()
        state['fixed_shift_records'] = [row(code='YILLIK_IZIN', start=None, end=None)]
        employees, fixed, history, unavailable, issues = collect_inputs(state)
        first = run(staff=employees, fixed=fixed, history=history)
        state['draft_shift_plan'] = first['plan']
        employees, fixed, history, unavailable, issues = collect_inputs(state)
        second = run(staff=employees, fixed=fixed, history=history)
        self.assertEqual(first['plan'], second['plan'])
        self.assertEqual(second['issues'], [])

    def test_deleted_external_record_not_resurrected_from_draft(self):
        state = self.state()
        state['draft_shift_plan'] = [row(code='YILLIK_IZIN', start=None, end=None, source='fixed_external')]
        self.assertEqual(collect_inputs(state)[1], [])


if __name__ == '__main__':
    unittest.main()
