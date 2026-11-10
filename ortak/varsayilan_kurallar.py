# Ortak / Varsayilan Kurallar — bu ekranın / servisin uygulama kodu.
from copy import deepcopy


SHIFT_RULES = {'general': {'weekday_general_start': '08:00',
             'weekend_general_start': '08:00',
             'global_latest_end': '03:00',
             'night_window_start': '00:00',
             'night_window_end': '08:00'},
 'boosts': {'weekday_0700_fulltime_extra_enabled': True, 'weekday_0700_fulltime_extra_count': 2},
 'night': {'enabled': True,
           'mode': 'normal',
           'normal': {'tr': 2, 'en': 1, 'ar': 1},
           'ramazan': {'tr': 3, 'en': 0, 'ar': 0},
           'ozel': {'tr': 2, 'en': 1, 'ar': 1},
           'allowed_work_types': ['akademi']},
 'work_type': {'fulltime': {'shift_total_hours': 9,
                            'prefer_daytime': True,
                            'daytime_window_start': '07:00',
                            'daytime_window_end': '19:00',
                            'max_days_per_week_default': 5,
                            'allow_6th_day': True,
                            'night_allowed': False},
               'akademi': {'shift_total_hours_max': 7,
                           'max_days_per_week': 6,
                           'min_rest_hours': 11,
                           'night_allowed': True,
                           'max_end_time': '03:00',
                           'max_end_is_hard': True,
                           'override_required_if_violate': True},
               'dis_kaynak': {'shift_total_hours': 10,
                              'max_days_per_week': 6,
                              'night_allowed': False,
                              'max_end_time': '00:00',
                              'max_end_is_hard': False,
                              'override_required_if_violate': True}}}


def default_shift_rules():
    rules=deepcopy(SHIFT_RULES)
    rules['off_rules']={'distribution':'İhtiyaca göre dağıt'}
    rules['capacity']={'max_overstaff':2,'min_overtime_hours':4}
    rules['publication_approvals']={'enabled':True}
    rules['school']={'holiday_priority':True,'summer_months':[6,7,8]}
    return rules


def enforce_current_rules(state):
    """Update old saved outsource durations without resetting user rules."""
    rules=state.get('shift_rules')
    if rules and rules.get('work_type',{}).get('dis_kaynak',{}).get('shift_total_hours')!=10:
        rules.setdefault('work_type',{}).setdefault('dis_kaynak',{})['shift_total_hours']=10
        state['shift_rules']=rules
        state['plan_ctx_confirmed']=False
    if rules:
        for group in rules.get('work_type',{}).values():
            group['min_rest_hours']=max(11,group.get('min_rest_hours',11))
            group['max_consecutive_days']=max(1,min(6,int(group.get('max_consecutive_days',group.get('max_days_per_week',group.get('max_days_per_week_default',6))))))
            if 'min_off_days' in group:group['min_off_days']=max(1,min(6,int(group['min_off_days'])))
    # A previous disabled widget may have cached the old display value.
    if state.get('rule_dk_shift_hours_fixed')!=10:
        state['rule_dk_shift_hours_fixed']=10
