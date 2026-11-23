"""Ortak veya dile özel planlama ihtiyacının tek seçicisi."""


def transferred_capacity(state,frame):
    """Seçilen yabancı vardiyaların 30 dk kişi katkısını döndür."""
    import pandas as pd
    from modules.vardiya_plani.vardiya_motoru import bounds
    valid={(pd.Timestamp(day).strftime('%Y-%m-%d'),int(slot)) for day,slot in zip(frame['Tarih'],frame['Slot'])}
    people_by_slot={key:set() for key in valid}
    plans=state.get('foreign_language_plans') or {}
    for lang,raw_ids in (state.get('foreign_language_transferred_ids') or {}).items():
        selected={str(eid) for eid in raw_ids};result=plans.get(lang) or {}
        for row in result.get('plan',[]):
            eid=str(row.get('employee_id'))
            if eid not in selected:continue
            span=bounds(row)
            if not span:continue
            begin,end=map(pd.Timestamp,span)
            for moment in pd.date_range(begin,end-pd.Timedelta(minutes=30),freq='30min'):
                key=(moment.strftime('%Y-%m-%d'),moment.hour*2+moment.minute//30+1)
                if key in people_by_slot:people_by_slot[key].add(eid)
    return {key:len(ids) for key,ids in people_by_slot.items()}


def demand(state):
    lang=state.get('planning_demand_language');flags=state.get('planning_languages') or {}
    if lang and flags.get(lang) and not any(v for k,v in flags.items() if k!=lang):
        chosen=state.get('language_demands',{}).get(lang)
        if chosen is not None:return chosen
    base=state.get('sp_staffing_result_df')
    if base is not None:
        import pandas as pd
        if base.empty or not {'Tarih','Slot','Planlanan Agent'}<=set(base.columns):return base
        result=base.copy();keys=list(zip(pd.to_datetime(result['Tarih']).dt.strftime('%Y-%m-%d'),pd.to_numeric(result['Slot']).astype(int)))
        capacity=transferred_capacity(state,result)
        deduction=pd.Series([capacity.get(key,0) for key in keys],index=result.index,dtype=float)
        result['Planlanan Agent']=(pd.to_numeric(result['Planlanan Agent'],errors='coerce').fillna(0)-deduction).clip(lower=0)
        if 'Net Agent' in result:
            net=(pd.to_numeric(result['Net Agent'],errors='coerce').fillna(0)-deduction).clip(lower=0)
            result['Net Agent']=net.where(net<=result['Planlanan Agent'],result['Planlanan Agent'])
        base=result
    included={key for key,value in (state.get('language_demand_inclusion') or {}).items() if value}
    if base is None or not included:return base
    result=base.copy();result['_key']=list(zip(pd.to_datetime(result['Tarih']).dt.strftime('%Y-%m-%d'),pd.to_numeric(result['Slot']).astype(int)))
    planned={key:0. for key in result['_key']};net={key:0. for key in result['_key']}
    for language in included:
        frame=(state.get('language_demands') or {}).get(language)
        if frame is None or frame.empty:continue
        for row in frame.to_dict('records'):
            key=(pd.Timestamp(row['Tarih']).strftime('%Y-%m-%d'),int(row['Slot']))
            if key not in planned:continue
            planned[key]+=float(row.get('Planlanan Agent',0))
            net[key]+=float(row.get('Net Agent',row.get('Planlanan Agent',0)))
    result['Planlanan Agent']=pd.to_numeric(result['Planlanan Agent'],errors='coerce').fillna(0)+result['_key'].map(planned)
    if 'Net Agent' in result:result['Net Agent']=pd.to_numeric(result['Net Agent'],errors='coerce').fillna(0)+result['_key'].map(net)
    return result.drop(columns='_key')
