# Kayit Merkezi — bu ekranın / servisin uygulama kodu.
"""Veri ve Kayıt Merkezi — değişmez kaynaklar ve işlem geçmişi."""
import pandas as pd
import streamlit as st
from ortak.roller_ve_yetkiler import require,init_governance
from ortak.calisma_alani_deposu import connect,loads


def render():
    state=st.session_state;st.title('🗃️ Veri ve Kayıt Merkezi')
    try:require(state,'kayit_merkezi')
    except ValueError as exc:st.info(str(exc));return
    kind=st.selectbox('Kayıt alanı',['Günlük / 30 dk tahminler','Interval profilleri','Vardiya değişiklikleri','Talep kayıtları','Personel işlemleri','Yetki ve denetim geçmişi'],key='registry_area')
    path=state['workspace_db_path'];init_governance(path);rows=[]
    if kind=='Günlük / 30 dk tahminler':
        from ortak.tahmin_kayit_servisi import runs,slots
        versions=runs(path)
        if versions:
            ident=st.selectbox('Tahmin sürümü',[r['id'] for r in versions],key='registry_forecast')
            frame=slots(ident,path);st.dataframe(frame.groupby('tarih',as_index=False).predicted.sum().rename(columns={'tarih':'Tarih','predicted':'Günlük tahmin'}),hide_index=True,use_container_width=True);rows=frame.to_dict('records')
    elif kind=='Interval profilleri':
        from ortak.tahmin_kayit_servisi import profile_versions
        versions=profile_versions(path)
        if versions:
            ident=st.selectbox('Profil sürümü',[r['id'] for r in versions],key='registry_profile');rows=next(r['frame'] for r in versions if r['id']==ident).to_dict('records')
    elif kind=='Talep kayıtları':
        from ortak.talep_servisi import refresh
        rows=refresh(state)
    elif kind=='Personel işlemleri':
        from ortak.personel_is_akisi import proposals
        rows=proposals(state)
    else:
        table='shift_change_batches' if kind=='Vardiya değişiklikleri' else 'audit_events'
        with connect(path) as db:
            raw=db.execute('SELECT * FROM '+table+' ORDER BY rowid DESC').fetchall()
        if kind=='Vardiya değişiklikleri':
            for r in raw:
                payload=loads(r['payload'])
                for old,new in zip(payload['before'],payload['after']):rows.append({'Kayıt':payload['id'],'Tarih':payload['date'],'İşlemi yapan':payload['actor'],'İşlem':payload['type'],'Gerekçe':payload['reason'],'Sicil':new.get('sicil_no',new['employee_id']),'Kullanıcı adı':new.get('username',''),'Vardiya günü':new['date'],'Eski değer':str({k:old.get(k) for k in ['shift_code','start','end']}),'Yeni değer':str({k:new.get(k) for k in ['shift_code','start','end']})})
        else:rows=[{'Tarih':r['created_at'],'Alan':r['category'],'İşlemi yapan':r['actor'],'İçerik':r['payload']} for r in raw]
    if not rows:st.info('Henüz kayıt yok.');return
    frame=pd.DataFrame(rows)
    for col in frame:
        if frame[col].map(lambda v:isinstance(v,(dict,list))).any():frame[col]=frame[col].map(str)
    st.dataframe(frame,hide_index=True,use_container_width=True,height=550)
    st.download_button('Görünen Kayıtları CSV İndir',frame.to_csv(index=False).encode('utf-8-sig'),'kayit_merkezi.csv','text/csv')
