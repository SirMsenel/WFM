"""Ortak veya dile özel planlama ihtiyacının tek seçicisi."""
def demand(state):
    lang=state.get('planning_demand_language');flags=state.get('planning_languages') or {}
    if lang and flags.get(lang) and not any(v for k,v in flags.items() if k!=lang):
        chosen=state.get('language_demands',{}).get(lang)
        if chosen is not None:return chosen
    return state.get('sp_staffing_result_df')
