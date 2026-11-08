# Tum Vardiyalar / Vardiya Duzenleme — bu ekranın / servisin uygulama kodu.
"""Tüm Vardiyalar — yayın üzerinde gerekçeli, kayıtlı ve toplam koruyan değişiklik."""
import pandas as pd
import streamlit as st
from ortak.personel import get_people,visible_people
from ortak.planlama import SHIFT_LABELS
from ortak.vardiya_degisimleri import validate_changes,apply_changes
from ortak.roller_ve_yetkiler import permissions


def render():
    state=st.session_state;caps=permissions(state)
    st.subheader('Vardiya Değişim Alanı')
    if 'vardiya_degistir' not in caps:st.info('Vardiya değişikliği için yetkiniz yok.');return
    from ortak.personel_deposu import list_people
    people=visible_people(state.get('profile') or {},list_people(state,True) if state.get('all_include_inactive') else get_people(state));byid={str(p['employee_id']):p for p in people}
    rows=[r for r in state.get('published_shift_plan',[]) if str(r['employee_id']) in byid]
    if not rows:st.info('Bu kapsamda yayınlanmış vardiya yok.');return
    dates=sorted({r['date'] for r in rows});start,end=pd.Timestamp(dates[0]).date(),pd.Timestamp(dates[-1]).date()
    chosen=st.date_input('Değişiklik tarih aralığı',value=(start,end),key='edit_roster_dates')
    if len(chosen)!=2:return
    selected=st.multiselect('Personeller (sicil / kullanıcı adı)',list(byid),format_func=lambda i:f"{byid[i]['full_name']} · {byid[i].get('sicil_no',i)} · {byid[i].get('username','')}",key='edit_roster_people')
    rows=[r for r in rows if str(chosen[0])<=r['date']<=str(chosen[1]) and str(r['employee_id']) in selected]
    if not rows:st.info('Personel ve tarih seçin.');return
    kinds=['Vardiya değişimi','Erken çıkış','Geç giriş','Yıllık izin','Mazeret izni']
    if 'rapor_gir' in caps:kinds.append('Rapor')
    kind=st.selectbox('Değişiklik türü',kinds,key='edit_roster_kind')
    reason=st.text_area('Reason / değişiklik gerekçesi',key='edit_roster_reason')
    table=pd.DataFrame([{'Personel':byid[str(r['employee_id'])]['full_name'],'Sicil no':byid[str(r['employee_id'])].get('sicil_no',str(r['employee_id'])),'Kullanıcı adı':byid[str(r['employee_id'])].get('username',''),'Tarih':r['date'],'Statü':r['shift_code'],'Başlangıç':r.get('start') or '', 'Bitiş':r.get('end') or ''} for r in rows])
    signature=__import__('hashlib').sha1(table.to_json().encode()).hexdigest()[:10]
    edited=st.data_editor(table,disabled=['Personel','Sicil no','Kullanıcı adı','Tarih'],hide_index=True,use_container_width=True,key='published_edit_'+signature,column_config={'Statü':st.column_config.SelectboxColumn(options=list(SHIFT_LABELS))})
    changes=[]
    for i,row in edited.iterrows():
        old=rows[i];a=row['Başlangıç'] or None;b=row['Bitiş'] or None
        if (row['Statü'],a,b)!=(old['shift_code'],old.get('start'),old.get('end')):changes.append({**old,'shift_code':row['Statü'],'start':a,'end':b})
    valid=False
    if changes:
        try:
            before,after=validate_changes(state,changes,kind,reason)
            st.success('Kontrol başarılı. '+('Her personelin OFF sayısı ve çalışma saati korunuyor.' if kind=='Vardiya değişimi' else 'İşlem ayrı bir gerekçeli devam/izin kaydı olarak saklanacak.'));valid=True
            st.dataframe([{'Sicil':byid[str(r['employee_id'])].get('sicil_no',r['employee_id']),'Tarih':r['date'],'Eski':f"{old['shift_code']} {old.get('start') or ''}–{old.get('end') or ''}",'Yeni':f"{r['shift_code']} {r.get('start') or ''}–{r.get('end') or ''}"} for old,r in zip(before,after)],hide_index=True,use_container_width=True)
        except ValueError as exc:st.warning(str(exc))
    st.caption('Vardiya değişiminde tek bir gün yerine birden fazla gün/personeli birlikte düzenleyebilirsin. OFF ve toplam saat dengesi sağlanmayan işlem kaydedilmez.')
    if st.button('Değişiklikleri Gerekçeyle Kaydet',disabled=not valid,key='published_edit_save'):
        try:
            ident=apply_changes(state,changes,kind,reason);st.success('Değişiklik kaydedildi: '+ident)
        except ValueError as exc:st.error(str(exc))
