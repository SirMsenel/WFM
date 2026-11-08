# Personel Takip / Personel Listesi — bu ekranın / servisin uygulama kodu.
import pandas as pd
import streamlit as st
from ortak.personel import get_people,WORK_LABELS,LANG_LABELS


def render():
    st.subheader('Personel Listesi')
    profile=st.session_state.get('profile') or {}
    if profile.get('position') not in {'tl','wfm','manager','moderator'}:
        st.info('Personel listesi yönetim ve takım lideri rolleri içindir.');return
    if st.button('Listeyi Yenile',key='personnel_refresh'):
        get_people(st.session_state,True)
    include_inactive=st.toggle('Ayrılan personelleri de göster',value=False,key='personnel_inactive')
    from ortak.personel_deposu import list_people
    people=list_people(st.session_state,True) if include_inactive else get_people(st.session_state)
    if profile.get('position')=='tl':
        people=[p for p in people if p.get('team_lead')==profile.get('full_name') or str(p.get('employee_id'))==str(profile.get('employee_id'))]
    df=pd.DataFrame(people)
    if df.empty:
        st.info('Gösterilecek personel yok.');return
    a,b,c,d=st.columns([2,1,1,1])
    query=a.text_input('Personel ara',placeholder='Ad, sicil, kullanıcı adı, takım lideri veya yönetici',key='personnel_search')
    from ortak.roller_ve_yetkiler import ROLE_LABELS
    position=b.selectbox('Pozisyon',['Tümü']+sorted(df.position.dropna().unique()),format_func=lambda r:ROLE_LABELS.get(r,r),key='personnel_position')
    location=c.selectbox('Şehir',['Tümü']+sorted(df.location.dropna().unique()),key='personnel_city')
    work=d.selectbox('Çalışma biçimi',['Tümü']+sorted(df.work_type.dropna().unique()),format_func=lambda k:WORK_LABELS.get(k,k),key='personnel_work')
    for col,value in [('position',position),('location',location),('work_type',work)]:
        if value!='Tümü':df=df[df[col]==value]
    if query.strip():
        df=df[df[[c for c in ['full_name','team_lead','manager','sicil_no','username'] if c in df]].fillna('').astype(str).apply(lambda c:c.str.contains(query.strip(),case=False,regex=False)).any(axis=1)]
    st.caption(f'{len(df)} personel gösteriliyor.')
    df['sicil_no']=df.get('sicil_no',df.employee_id.astype(str))
    df['username']=df.get('username','')
    df['company']=df.get('company','')
    output=df[['company','sicil_no','username','full_name','position','location','work_type','language','team_lead','manager']].copy()
    output['position']=output.position.map(lambda r:ROLE_LABELS.get(r,r))
    output['work_type']=output.work_type.map(lambda k:WORK_LABELS.get(k,k))
    output['language']=output.language.map(lambda k:LANG_LABELS.get(k,k))
    output=output.rename(columns={'company':'Şirket','sicil_no':'Sicil no','username':'Kullanıcı adı','full_name':'Ad soyad','position':'Pozisyon','location':'Şehir',
                                 'work_type':'Çalışma biçimi','language':'Dil','team_lead':'Takım lideri','manager':'Yönetici'})
    st.dataframe(output,hide_index=True,use_container_width=True,height=530)
    st.download_button('Personel Listesi CSV İndir',output.to_csv(index=False).encode('utf-8-sig'),'personel_listesi.csv','text/csv')
