# Ornek Calisma Alani — bu ekranın / servisin uygulama kodu.
from pathlib import Path
import pandas as pd
import streamlit as st

from ortak.servis_istemcisi import api_post
from ortak.ornek_veri import employees, load_demo_history
from ortak.calisma_alani_deposu import DEFAULT_DB, connect, load_calls, save_keys


from ortak.roller_ve_yetkiler import ROLE_LABELS


def render():
    st.title('Hazır Demo Veritabanı')
    if st.session_state.get('production_mode'):st.info('Kurumsal modda sentetik veri ve demo hesap işlemleri kapalı.');return
    st.info('Bu çalışma alanındaki çağrı, talep, okul ve vardiya kayıtları örnek veridir. Yaptığın işlemler SQLite veritabanına kaydedilir ve farklı demo hesaplarından görülebilir.')
    path=st.session_state.get('workspace_db_path',str(DEFAULT_DB))
    with connect(path) as con:
        count_daily=con.execute('SELECT count(*) FROM calls_daily').fetchone()[0]
        count_interval=con.execute('SELECT count(*) FROM calls_interval').fetchone()[0]
        count_requests=con.execute('SELECT count(*) FROM requests').fetchone()[0]
        period=con.execute('SELECT min(tarih),max(tarih) FROM calls_daily').fetchone()
    a,b,c=st.columns(3)
    a.metric('Günlük çağrı kaydı',count_daily)
    b.metric('30 dakikalık kayıt',count_interval)
    c.metric('Talep kaydı',count_requests)
    st.caption(f'Çağrı geçmişi: {period[0]} → {period[1]}. Personel listesi mevcut demo personel veritabanından alınır.')
    accounts=employees()
    st.markdown('### Rol Değiştirerek Akışı Dene')
    st.caption('Personel olarak talep gönder, ilgili takım lideri hesabıyla ilet, WFM hesabıyla sonuçlandır. Aynı kayıt ve işlem geçmişi hesaplar arasında korunur.')
    role=st.selectbox('Denenecek rol',list(ROLE_LABELS),format_func=ROLE_LABELS.get,key='demo_role_pick')
    candidates={e['username']:e for e in accounts if e['position']==role}
    pick=st.selectbox('Demo hesabı',list(candidates),format_func=lambda name:f"{candidates[name]['full_name']} · {name} · TL: {candidates[name].get('team_lead') or '—'}",key='demo_account_pick')
    if st.button('Bu Demo Hesabına Geç',key='demo_switch_user'):
        try:
            save_keys(st.session_state)
            login=api_post('/auth/login',{'username':pick,'password':'1234'})
            from ortak.erisim import enter_session
            st.session_state.update(auth_token=login['access_token'],profile=login['profile'])
            enter_session(st.session_state,login['profile'])
            st.rerun()
        except Exception as exc:
            st.error(f'Hesap değiştirilemedi: {exc}')
    summary=pd.DataFrame(accounts)[['full_name','username','position','work_type','language','location','team_lead']]
    st.dataframe(summary[summary.position==role].rename(columns={'full_name':'Ad soyad','username':'Hesap','position':'Rol','work_type':'Çalışma tipi','language':'Dil','location':'Lokasyon','team_lead':'Takım lideri'}),hide_index=True,use_container_width=True)
    st.markdown('### Çağrı Geçmişini İncele')
    resolution=st.radio('Veri görünümü',['Günlük','30 dakika'],horizontal=True,key='demo_call_resolution')
    calls=load_calls(resolution=='30 dakika',path)
    st.dataframe(calls.tail(500),hide_index=True,use_container_width=True)
    st.download_button('Çağrı Verisini CSV İndir',calls.to_csv(index=False).encode('utf-8-sig'),'demo_cagri_verisi.csv','text/csv')
    st.download_button('Örnek SQLite Veritabanını İndir',Path(path).read_bytes(),'wfm_demo.db','application/vnd.sqlite3')
