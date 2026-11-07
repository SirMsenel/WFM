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
               'dis_kaynak': {'shift_total_hours': 11,
                              'max_days_per_week': 6,
                              'night_allowed': False,
                              'max_end_time': '00:00',
                              'max_end_is_hard': False,
                              'override_required_if_violate': True}}}


def default_shift_rules():
    return deepcopy(SHIFT_RULES)
