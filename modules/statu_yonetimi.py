"""Planlama ve yönetim için gerekçeli operasyonel statü iptali."""
import hashlib
import pandas as pd
import streamlit as st
from ortak.statu_iptalleri import targets,cancel_targets,events,now_local
from ortak.statu_kapasite_raporu import capacity_visible


def render():
    s=st.session_state
    if not capacity_visible(s.get('profile',{})):st.info('Statü yönetimi Planlama ve yönetim içindir.');return
    st.subheader('Statü Yönetimi');st.caption('Haklar silinmez. İptal edilen statü ve gerekçesi kaydedilir; başlamış statünün yalnızca kalan kısmı iptal edilir. Vardiya saatleri değişmez.')
    from ortak.personel_deposu import list_people
    people={str(p['employee_id']):p for p in list_people(s,True)}
    day=st.date_input('Yönetilecek gün',now_local().date(),key='cancel_status_day',format='DD.MM.YYYY');mode=st.segmented_control('İşlem',['Atanmış statüler','Açık koçluk saatleri'],default='Atanmış statüler',key='cancel_status_mode') or 'Atanmış statüler'
    kinds=st.multiselect('Statü türleri',['Yemek','Mola','Koçluk','Cuma'],default=['Yemek','Mola','Koçluk'],key='cancel_status_kinds') if mode=='Atanmış statüler' else []
    query=st.text_input('Personel ara',key='cancel_status_search') if mode=='Atanmış statüler' else ''
    current=now_local();items=[r for r in targets(s) if r['status'] in {'Planlı','Onaylı','Açık'} and pd.Timestamp(r['end'])>current and pd.Timestamp(r['start']).date()<=day<=pd.Timestamp(r['end']).date() and ((r['source']=='coaching_openings')==(mode=='Açık koçluk saatleri')) and (not kinds or r['kind'] in kinds) and (not query or query.casefold() in people.get(str(r['employee_id']),{}).get('full_name','').casefold())]
    if items:
        all_selected=st.checkbox('Listelenenlerin tamamını seç',key='cancel_status_all')
        frame=pd.DataFrame([{'Seç':all_selected,'Personel':people.get(str(r['employee_id']),{}).get('full_name','Ortak koçluk alanı'),'Statü':r['kind'],'Başlangıç':pd.Timestamp(r['start']).strftime('%d.%m %H:%M'),'Bitiş':pd.Timestamp(r['end']).strftime('%d.%m %H:%M'),'Durum':'Başladı · kalan süre iptal edilir' if pd.Timestamp(r['start'])<current else 'Henüz başlamadı',**({'Kalan kontenjan':int(r.get('remaining_capacity',1))} if mode=='Açık koçluk saatleri' else {})} for r in items])
        version=hashlib.sha1(repr([(r['id'],r['status'],r['start'],r['end'],r.get('remaining_capacity')) for r in items]).encode()).hexdigest()[:12]
        edited=st.data_editor(frame,disabled=[c for c in frame if c!='Seç'],hide_index=True,use_container_width=True,key='cancel_status_editor_'+version+'_'+str(all_selected))
        selected=[r for i,r in enumerate(items) if bool(edited.iloc[i]['Seç'])];reason=st.text_area('Operasyonel iptal gerekçesi',placeholder='Örn. beklenmedik çağrı artışı, hat sorunu…',key='cancel_status_reason')
        if st.button(f'Seçilen {len(selected)} Kaydı Gerekçeyle İptal Et',disabled=not selected or not reason.strip(),key='cancel_status_apply',type='primary'):
            try:
                done=cancel_targets(s,[r['id'] for r in selected],reason,{r['id']:r for r in selected});s['cancel_status_notice']=f'{len(done)} kayıt iptal edildi. Hak ve eksik süre raporda korunuyor.';st.rerun()
            except ValueError as exc:st.warning(str(exc))
    else:st.info('Bu gün ve filtrelerde iptal edilebilir, tamamlanmamış kayıt yok.')
    if s.get('cancel_status_notice'):st.success(s.pop('cancel_status_notice'))
    history=events(s)
    with st.expander('İptal Geçmişi'):
        if history:st.dataframe([{'İşlem zamanı':r['created_at'],'Personel':r['name'],'Statü':r['kind'],'İptal başlangıcı':r['start'],'İptal bitişi':r['end'],'İptal dakika':r['cancelled_minutes'],'İşlemi yapan':r['actor_name'],'Gerekçe':r['reason']} for r in history],hide_index=True,use_container_width=True)
        else:st.caption('İptal kaydı yok.')
