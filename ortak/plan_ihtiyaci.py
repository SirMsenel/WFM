"""Ortak veya dile özel planlama ihtiyacının tek seçicisi."""
def demand(state):
    lang=state.get('planning_demand_language');flags=state.get('planning_languages') or {}
    if lang and flags.get(lang) and not any(v for k,v in flags.items() if k!=lang):
        chosen=state.get('language_demands',{}).get(lang)
        if chosen is not None:return chosen
    base=state.get('sp_staffing_result_df')
    included={key for key,value in (state.get('language_demand_inclusion') or {}).items() if value}
    if base is None or not included:return base
    import pandas as pd
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
