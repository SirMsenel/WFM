# Ortak / Gece Kontrolleri — bu ekranın / servisin uygulama kodu.
import pandas as pd
from ortak.personel import LANG_LABELS


def night_gaps(state):
    from modules.vardiya_plani.planlama_verileri import collect_inputs
    if not state.get('plan_ctx') or not state.get('employees_cache'):return []
    staff,fixed,*_=collect_inputs(state);people={str(e['employee_id']):e for e in staff}
    rules=state.get('shift_rules',{}).get('night',{})
    if not rules.get('enabled'):return []
    target=rules.get(rules.get('mode','normal'),{});included=state.get('planning_languages',{})
    unique={(r['employee_id'],r['date']):r for r in fixed};result=[]
    for day in pd.date_range(state['plan_ctx']['start'],state['plan_ctx']['end']):
        for lang,number in target.items():
            if not included.get(lang,True):continue
            count=sum(r.get('shift_code')=='GECE' and r['date']==str(day.date()) and people.get(str(r['employee_id']),{}).get('language')==lang for r in unique.values())
            if count<int(number):result.append({'Tarih':str(day.date()),'Dil':LANG_LABELS.get(lang,lang),'Gerekli':int(number),'Yerleştirilen':count,'Eksik':int(number)-count})
    return result


def show_night_popup(state):
    import streamlit as st
    try:missing=night_gaps(state)
    except (ValueError,KeyError):return
    if not missing:return
    @st.dialog('Gece vardiyasında eksik personel var')
    def notice():
        st.warning('Kaydettiğin gece kuralları için aşağıdaki tarih/dil sayıları henüz tamamlanmamış. Vardiya Saatleri → Gece Kontrolü üzerinden yerleştirmeleri inceleyebilirsin.')
        st.dataframe(missing,hide_index=True,use_container_width=True)
        if st.button('Gece Eksiklerini Gördüm',key='night_gap_ack'):st.rerun()
    notice()
