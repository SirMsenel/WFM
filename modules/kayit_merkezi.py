"""Veri ve Kayıt Merkezi — anlaşılır başlıklarla, alt ekranlara ayrılmış sürümlü kayıtlar."""
import json
import pandas as pd
import streamlit as st
from ortak.roller_ve_yetkiler import require,init_governance
from ortak.calisma_alani_deposu import connect,loads
from ortak.gezinme import sections
from ortak.kayit_basliklari import title_for,title_editor,record_picker


def show_table(rows,name):
    if not rows:st.info('Henüz kayıt yok.');return
    frame=pd.DataFrame(rows)
    for col in frame:
        if frame[col].map(lambda v:isinstance(v,(dict,list))).any():frame[col]=frame[col].map(str)
    st.dataframe(frame,hide_index=True,use_container_width=True,height=520)
    st.download_button('CSV İndir',frame.to_csv(index=False).encode('utf-8-sig'),name+'.csv','text/csv',key='registry_csv_'+name)


def render_daily(state):
    from ortak.gunluk_tahmin_deposu import saved_daily,daily_label
    path=state['workspace_db_path'];records=saved_daily(path)
    if not records:st.info('Henüz günlük tahmin kaydı yok.');return
    byid={r['id']:r for r in records};ident=record_picker('Günlük tahmin kaydı',records,lambda r:daily_label(r,path),'registry_daily');record=byid[ident]
    title_editor(state,ident,daily_label(record,path));show_table(record['frame'].rename(columns={'tarih':'Tarih','y_pred':'Çağrı tahmini'}).to_dict('records'),'gunluk_tahminler')


def render_slots(state):
    from ortak.tahmin_kayit_servisi import runs,slots
    from modules.mesai_plani.guncel_takip import run_label
    records=runs(state['workspace_db_path']);byid={r['id']:r for r in records}
    if not records:st.info('Henüz kullanılan 30 dakikalık tahmin kaydı yok.');return
    ident=record_picker('30 dakikalık tahmin kaydı',records,lambda r:title_for(state['workspace_db_path'],r['id'],run_label(r)),'registry_slots')
    title_editor(state,ident,run_label(byid[ident]))
    from ortak.saat_etiketleri import slot_label
    frame=slots(ident,state['workspace_db_path']);frame['Saat aralığı']=frame.slot.map(slot_label)
    show_table(frame[['tarih','Saat aralığı','predicted','share']].rename(columns={'tarih':'Tarih','predicted':'Çağrı tahmini','share':'Dağılım (%)'}).to_dict('records'),'30_dk_tahminler')


def render_profiles(state):
    from ortak.tahmin_kayit_servisi import profile_versions
    from modules.mesai_plani.guncel_takip import profile_label
    versions=profile_versions(state['workspace_db_path']);byid={r['id']:r for r in versions}
    if not versions:st.info('Henüz profil kaydı yok.');return
    ident=record_picker('Interval dağılımı',versions,lambda r:title_for(state['workspace_db_path'],r['id'],profile_label(r)),'registry_profile')
    title_editor(state,ident,profile_label(byid[ident]));show_table(byid[ident]['frame'].to_dict('records'),'interval_profilleri')


def render_publications(state):
    from ortak.yayin_servisi import publications
    from ortak.takvim_gorunumu import render_calendar
    from ortak.personel_deposu import list_people
    with st.expander('2026 Örnek Vardiya Geçmişi'):
        from ortak.sabit_demo import history_rows
        from datetime import date
        day=st.date_input('Geçmiş dönemin başlangıcı',date(2026,11,1),key='registry_history_day');finish=min(day+pd.Timedelta(days=13),date(2026,11,9))
        if day<=finish:
            history=history_rows(state,day,finish)
            if history:render_calendar(history,list_people(state,True),day,finish,key='registry_history')
            else:st.info('Seçilen dönemde geçmiş vardiya kaydı yok.')
        else:st.info('Sabit örnek geçmiş 9 Kasım 2026 tarihinde biter.')
    records=publications(state)
    if not records:st.info('Henüz açıklanmış vardiya yok.');return
    byid={r['id']:r for r in records};path=state['workspace_db_path']
    def label(i):
        r=byid[i];return title_for(path,i,f"{pd.Timestamp(r['start']):%d.%m.%Y} – {pd.Timestamp(r['end']):%d.%m.%Y} · {', '.join(r.get('languages',[])).upper()} · {'Yayında' if r['status']=='active' else 'Geri alındı'}")
    ident=record_picker('Açıklanan vardiya dönemi',records,lambda r:label(r['id']),'registry_publication');record=byid[ident]
    title_editor(state,ident,label(ident));lookup={str(e['employee_id']):e for e in list_people(state,True)}
    people=[lookup.get(i,{'employee_id':i,'full_name':i}) for i in sorted({str(r['employee_id']) for r in record['rows']})]
    render_calendar(record['rows'],people,record['start'],record['end'],key='registry_roster')
    with st.expander('İlk açıklanan sürüm'):
        with connect(path) as db:raw=db.execute('SELECT payload FROM publication_batches WHERE id=?',(ident,)).fetchone()
        original=loads(raw[0]) if raw else record
        render_calendar(original['rows'],people,original['start'],original['end'],key='registry_original')


def render_changes(state):
    from ortak.degisim_ekrani import render_change_approvals
    render_change_approvals(state,'registry_change_review')
    with connect(state['workspace_db_path']) as db:raw=db.execute('SELECT payload FROM shift_change_batches ORDER BY rowid DESC').fetchall()
    from ortak.personel_deposu import list_people
    people={str(p['employee_id']):p for p in list_people(state,True)};rows=[]
    for item in raw:
        p=loads(item[0])
        for old,new in zip(p['before'],p['after']):rows.append({'Personel':people.get(str(new['employee_id']),{}).get('full_name',new['employee_id']),'Vardiya tarihi':new['date'],'İşlem':p['type'],'Eski değer':f"{old['shift_code']} {old.get('start') or ''}–{old.get('end') or ''}",'Yeni değer':f"{new['shift_code']} {new.get('start') or ''}–{new.get('end') or ''}",'Gerekçe':p['reason'],'İşlemi yapan':p['actor'],'Kayıt zamanı':p['date']})
    st.markdown('#### Uygulanan değişiklikler');show_table(rows,'vardiya_degisimleri')


def render_requests(state):
    from ortak.talep_servisi import refresh
    from ortak.talep_gorunumu import rows_for_table
    show_table(rows_for_table(refresh(state)),'talep_kayitlari')


def render_hr(state):
    from ortak.personel_is_akisi import proposals
    show_table([{'Personel':r['values'].get('full_name'),'İşlem':r['kind'],'Durum':r['stage'],'Tarih':r['values'].get('effective_date'),'İleten':r['created_by'],'Yönetici':r['manager'],'Gerekçe':r['reason']} for r in proposals(state)],'personel_islemleri')


def render_audit(state):
    with connect(state['workspace_db_path']) as db:raw=db.execute('SELECT * FROM audit_events ORDER BY rowid DESC').fetchall()
    show_table([{'Tarih':r['created_at'],'Alan':r['category'],'İşlemi yapan':r['actor'],'İçerik':r['payload']} for r in raw],'denetim_gecmisi')


def render():
    state=st.session_state;st.title('🗃️ Veri ve Kayıt Merkezi')
    try:require(state,'kayit_merkezi')
    except ValueError as exc:st.info(str(exc));return
    init_governance(state['workspace_db_path'])
    sections('nav_registry',{'Günlük Tahminler':lambda:render_daily(state),'30 Dakikalık Tahminler':lambda:render_slots(state),'Interval Profilleri':lambda:render_profiles(state),'Açıklanan Vardiyalar':lambda:render_publications(state),'Vardiya Değişimleri':lambda:render_changes(state),'Talep Kayıtları':lambda:render_requests(state),'Personel İşlemleri':lambda:render_hr(state),'Yetki Geçmişi':lambda:render_audit(state)})
