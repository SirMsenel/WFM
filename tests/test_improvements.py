from copy import deepcopy
from datetime import date,datetime,timedelta
import unittest
import numpy as np
import pandas as pd

from core.interval_service import (build_weekly_distribution,prepare_intervals,recency_weights,calendar_flags,record_used_profile)
from core.shift_edits import edit_shifts,undo_edit
from modules.shift_planing.planning_data import collect_inputs
from modules.shift_planing.engine import generate_plan,bounds
from test_planning import DAY,emp,row,rules,demand


def intervals(days=84,end='2026-11-08'):
    days=pd.date_range(end=end,periods=days)
    records=[]
    for day in days:
        shape=np.ones(48)*3
        shape[16+day.weekday():22+day.weekday()]=100
        for s,n in enumerate(shape):records.append({'tarih':day+pd.Timedelta(minutes=s*30),'slot':s+1,'cagri_sayisi':n})
    return pd.DataFrame(records)


class IntervalTests(unittest.TestCase):
    def test_matrix_and_all_window_weights(self):
        result=build_weekly_distribution(intervals(),'2026-11-09')
        profile=result['profile']
        self.assertEqual(len(profile),336)
        self.assertEqual(len(result['scores']),6)
        self.assertAlmostEqual(result['scores']['Başarı ağırlığı (%)'].sum(),100)
        self.assertTrue(np.allclose(profile.groupby('Gün')['Oran(%)'].sum(),100))
        self.assertFalse(profile.duplicated(['Tarih','Slot']).any())
        self.assertTrue((profile['Oran(%)']>=0).all())
    def test_future_rows_do_not_change_forecast_or_calibration(self):
        raw=intervals()
        first=build_weekly_distribution(raw,'2026-11-09')
        future=intervals(7,'2026-11-15');future.cagri_sayisi*=10000
        second=build_weekly_distribution(pd.concat([raw,future]),'2026-11-09')
        pd.testing.assert_frame_equal(first['profile'],second['profile'])
        pd.testing.assert_frame_equal(first['scores'],second['scores'])
    def test_holdout_truth_never_enters_its_own_candidate_training(self):
        raw=intervals();first=build_weekly_distribution(raw,'2026-11-09')
        changed=raw.copy()
        changed.loc[(changed.tarih>='2026-11-02')&(changed.slot==48),'cagri_sayisi']*=200
        second=build_weekly_distribution(changed,'2026-11-09')
        for name,frame in first['validation_window_profiles'].items():
            pd.testing.assert_frame_equal(frame,second['validation_window_profiles'][name])
        self.assertFalse(first['scores'].equals(second['scores']))
    def test_incomplete_day_excluded_not_zero_filled(self):
        raw=intervals();raw=raw.drop(raw.index[-1])
        _,_,matrix,quality=prepare_intervals(raw)
        self.assertEqual(quality['Eksik veya sıfır gün'],1)
        self.assertNotIn(pd.Timestamp('2026-11-08'),matrix.index)
        result=build_weekly_distribution(raw,'2026-11-09')
        self.assertEqual(result['meta']['validation_end'],'2026-11-01')
    def test_recency_is_logarithmic_and_monotone(self):
        ages=np.array([0,7,30,365]);weights=recency_weights(ages)
        self.assertEqual(weights[0],1)
        self.assertTrue((np.diff(weights)<0).all())
        np.testing.assert_allclose(weights,1/(1+np.log1p(ages/7)))
    def test_calendar_uses_same_payment_and_holiday_flags(self):
        flags=calendar_flags(pd.to_datetime(['2026-03-20','2026-01-09','2026-01-19']))
        self.assertEqual(flags.loc['2026-03-20','Bayram'],1)
        self.assertEqual(flags.loc['2026-01-09','EKSTRE_KESIM'],1)
        self.assertEqual(flags.loc['2026-01-19','SON_ODEME'],1)
    def test_used_profile_is_recorded_only_on_staffing_use(self):
        result=build_weekly_distribution(intervals(),'2026-11-09')
        state={};forecast=pd.DataFrame({'tarih':pd.date_range('2026-11-09',periods=7),'y_pred':100})
        record_used_profile(state,forecast,result['profile'])
        self.assertIn('2026-11-09',state['interval_used_profiles'])
        state={};record_used_profile(state,forecast.iloc[:3],result['profile'])
        self.assertEqual(state['interval_used_profiles'],{})
    def test_previous_used_distribution_is_compared_to_validation_truth(self):
        raw=intervals();first=build_weekly_distribution(raw,'2026-11-09')
        previous=first['actual_validation']
        second=build_weekly_distribution(raw,'2026-11-09',previous_profiles={'2026-11-02':previous})
        self.assertEqual(second['meta']['baseline_mae'],0)
        self.assertIn('kullanılmış',second['meta']['baseline_name'])
    def test_zero_or_invalid_history_is_rejected(self):
        raw=intervals();raw.cagri_sayisi=0
        with self.assertRaises(ValueError):prepare_intervals(raw)
        raw=intervals();raw.loc[0,'cagri_sayisi']=-1
        with self.assertRaises(ValueError):prepare_intervals(raw)


class EditTests(unittest.TestCase):
    def test_single_edit_delete_and_undo(self):
        original=row();state={'draft_shift_plan':[original]}
        edit_shifts(state,deletions=[('1',str(DAY))])
        self.assertFalse(state['draft_shift_plan'])
        undo_edit(state)
        self.assertEqual(state['draft_shift_plan'],[original])
        self.assertFalse(state['plan_removed_assignments'])
    def test_addition_undo_restores_original_row(self):
        original=row();state={'draft_shift_plan':[original]}
        edit_shifts(state,[row(start='09:00',end='18:00')])
        undo_edit(state)
        self.assertEqual(state['draft_shift_plan'],[original])
    def test_undo_does_not_overwrite_other_users_edit(self):
        state={'draft_shift_plan':[row()]}
        edit_shifts(state,[row(start='09:00',end='18:00')])
        state['draft_shift_plan'][0]['end']='19:00'
        with self.assertRaises(ValueError):undo_edit(state)
    def test_history_contains_only_changed_row(self):
        state={'draft_shift_plan':[row(str(i)) for i in range(1000)]}
        edit_shifts(state,[row('1',start='09:00',end='18:00')])
        self.assertEqual(len(state['shift_edit_history'][0]['before']),1)
    def test_locked_external_cannot_be_deleted(self):
        state={'draft_shift_plan':[row(source='fixed_external')]}
        with self.assertRaises(ValueError):edit_shifts(state,deletions=[('1',str(DAY))])


class RuleAndInputTests(unittest.TestCase):
    def test_fulltime_no_night_rule_blocks_overnight_auto(self):
        df=demand(days=2,slots=range(43,49))
        result=generate_plan([emp()],df,rules(),['fulltime','akademi','dis_kaynak'],DAY,DAY+timedelta(days=1))
        for assignment in result['plan']:
            if bounds(assignment):
                self.assertLessEqual(bounds(assignment)[1],datetime.combine(date.fromisoformat(assignment['date'])+timedelta(days=1),datetime.min.time()))
    def test_night_quotas_are_checked(self):
        r=rules();r['night'].update(mode='normal',normal={'tr':1})
        result=generate_plan([dict(emp(group='akademi'),language='tr')],demand(),r,['fulltime','akademi','dis_kaynak'],DAY,DAY)
        self.assertTrue(any('Gece TR' in x['Sorun'] for x in result['issues']))
    def test_published_night_and_leave_imported_and_exam_blocks_day(self):
        state={'employees_cache':[emp(group='akademi')],'plan_ctx':{'start':DAY,'end':DAY+timedelta(days=1)},
               'published_shift_plan':[row(code='GECE',start='00:00',end='07:00',source='legacy')],
               'acad_exam_calendar':{'u1':{'2026-Sinav':{'Tarih':[str(DAY+timedelta(days=1))],'Saat':['10:00']}}}}
        employees,fixed,history,unavailable,issues=collect_inputs(state)
        self.assertEqual(fixed[0]['shift_code'],'GECE')
        self.assertEqual((unavailable['1'][0][1]-unavailable['1'][0][0]).total_seconds(),86400)
        self.assertFalse(issues)
    def test_deleted_published_manual_night_stays_deleted(self):
        state={'employees_cache':[emp(group='akademi')],'plan_ctx':{'start':DAY,'end':DAY},
               'published_shift_plan':[row(code='GECE',start='00:00',end='07:00',source='manual_single')],
               'plan_removed_assignments':[['1',str(DAY)]]}
        self.assertFalse(collect_inputs(state)[1])


if __name__=='__main__':unittest.main()

class CalendarEffectTests(unittest.TestCase):
    def test_matching_statement_days_change_shape_not_just_labels(self):
        raw=intervals(160)
        days=raw.tarih.dt.normalize()
        flags=calendar_flags(pd.DatetimeIndex(days.unique()))
        effect_days=set(flags[flags.EKSTRE_KESIM==1].index)
        raw.loc[days.isin(effect_days),'cagri_sayisi']=2
        raw.loc[days.isin(effect_days)&(raw.slot==40),'cagri_sayisi']=1500
        result=build_weekly_distribution(raw,'2026-11-09')
        profile=result['profile']
        monday=profile[(profile.Gün=='Pazartesi')&(profile.Slot==40)]['Oran(%)'].iloc[0]
        from unittest.mock import patch
        original=calendar_flags
        def without_statement(dates):
            flags=original(dates)
            flags['EKSTRE_KESIM']=0
            return flags
        with patch('core.interval_service.calendar_flags',side_effect=without_statement):
            control=build_weekly_distribution(raw,'2026-11-09')['profile']
        without=control[(control.Gün=='Pazartesi')&(control.Slot==40)]['Oran(%)'].iloc[0]
        self.assertGreater(monday,without*2)
        self.assertTrue(any('EKSTRE_KESIM' in n and 'benzer gün' in n for n in result['meta']['calendar_notes']))
