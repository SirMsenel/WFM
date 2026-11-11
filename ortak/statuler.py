"""Statü kuralları, yarım saat shrinkage ve planlı yemeklerin kapasite etkisi."""
import pandas as pd
from modules.vardiya_plani.vardiya_motoru import bounds


def defaults():
    return {'operation_reserve_rate':.05,'coaching_slot_minutes':15,'groups':{g:{'meal_minutes':30,'meal_start':'12:00','meal_end':'15:00','break_first_minutes':60,'break_last_minutes':60,'break_minutes':15,'break_total_minutes':30,'break_per_hour_max':15,'coaching_multiple_per_week':False,'coaching_monthly_minutes':60,'coaching_chunk_minutes':15,'break_rules':[{'min_hours':0,'max_hours':4,'minutes':15},{'min_hours':4,'max_hours':24,'minutes':30}],'min_shift_hours':4,'relative':True,'after_start':3,'before_start':6} for g in ('fulltime','akademi','dis_kaynak')},'friday':{'enabled':False,'male_only':False,'start':'12:00','end':'14:00','minutes':60}}


def shrinkage_for(state,day,slot,fallback=.30):
    value=float(fallback)
    for rule in state.get('slot_shrinkage',[]):
        if (not rule.get('weekdays') or pd.Timestamp(day).weekday() in rule['weekdays']) and int(rule['start_slot'])<=slot<=int(rule['end_slot']):value=float(rule['rate'])
    if not 0<=value<1:raise ValueError('Shrinkage %0–%99 arasında olmalı.')
    return value


def meal_plan(state,rows,coverage,people):
    from ortak.statu_planlayici import plan,coaching_used
    import hashlib,json,copy
    cfg=state.get('status_rules') or {}
    if not cfg.get('enabled'):return [],coverage,[]
    used=coaching_used(state) if cfg.get('automatic') else {}
    source=state.get('sp_staffing_result_df')
    material=[rows,people,cfg,state.get('shift_rules',{}).get('night',{}),state.get('slot_shrinkage',[]),state.get('staffing_parameters',{}),[(str(k),v) for k,v in sorted(used.items())],coverage.to_json(date_format='iso',orient='split'),None if source is None else source.to_json(date_format='iso',orient='split')]
    signature=hashlib.sha256(json.dumps(material,default=str,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    cached=state.get('_status_plan_cache')
    if cached and cached['signature']==signature:return copy.deepcopy(cached['result'])
    result=plan(state,rows,coverage,people,used)
    state['_status_plan_cache']={'signature':signature,'result':copy.deepcopy(result)}
    return result
