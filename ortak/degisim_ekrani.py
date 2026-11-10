"""Vardiya Değişim Ekranı — karşılıklı gün seçimi, hücre düzenleme ve Planlama onayı."""
from datetime import datetime
from html import escape
import pandas as pd
import streamlit as st
from ortak.personel import get_people,visible_people,WORK_LABELS,LANG_LABELS
from ortak.planlama import SHIFT_LABELS
from ortak.vardiya_degisimleri import validate_changes
from ortak.talep_yerlestirme import resolve_swap
from ortak.degisim_onaylari import submit_change,change_requests,decide_change
from ortak.takvim_gorunumu import render_calendar
from modules.vardiya_plani.vardiya_motoru import bounds


def render_change_form(state,key='change',fixed_kind=None):
    profile=state.get('profile') or {};role=profile.get('position');all_people={str(p['employee_id']):p for p in get_people(state) if p.get('position')=='agent'}
    rows=state.get('published_shift_plan',[])
    if not rows:st.info('Değişiklik için önce yayınlanmış bir vardiya olmalı.');return
    visible=visible_people(profile,list(all_people.values()));byid={str(p['employee_id']):p for p in visible}
    if not byid:st.info('Bu kapsamda personel yok.');return
    kinds=['Vardiya değişimi','Erken çıkış','Geç giriş','Yıllık izin','Mazeret izni']
    if role=='tl':kinds.append('Rapor')
    if role=='agent':kinds=kinds[:3]
    kind=fixed_kind or st.selectbox('Ne değiştirmek istiyorsun?',kinds,key=key+'_kind')
    if kind not in kinds:st.warning('Bu işlem türü için yetkin yok.');return
    person_id=str(profile.get('employee_id')) if role=='agent' else st.selectbox('Vardiyası değişecek personel',list(byid),format_func=lambda i:byid[i]['full_name'],key=key+'_person')
    if person_id not in byid:st.info('Personel bulunamadı.');return
    person=byid[person_id];own=[r for r in rows if str(r['employee_id'])==person_id]
    if not own:st.info('Seçilen personelin yayınlanmış vardiyası yok.');return
    changes=[];swap_dates=[];other=None
    if kind=='Vardiya değişimi':
        st.info('İki kişinin aynı günkü vardiyaları karşılıklı yer değiştirir. OFF alıp vereceksen iki günü birlikte seç. Her haftanın OFF sayısı ve çalışma saati korunur.')
        candidates={i:p for i,p in all_people.items() if i!=person_id and p.get('work_type')==person.get('work_type') and (p.get('language') or 'tr')==(person.get('language') or 'tr') and (role!='tl' or i in byid)}
        if not candidates:st.info('Aynı grup ve dilde uygun karşı personel yok.');return
        other=st.selectbox('Kiminle karşılıklı değişecek?',list(candidates),format_func=lambda i:candidates[i]['full_name'],key=key+'_other')
        common=sorted({r['date'] for r in own}&{r['date'] for r in rows if str(r['employee_id'])==other})
        def description(day):
            pair=[next(r for r in rows if str(r['employee_id'])==i and r['date']==day) for i in (person_id,other)]
            return f"{pd.Timestamp(day):%d.%m.%Y} · "+' ↔ '.join((f"{r.get('start')}–{r.get('end')}" if bounds(r) else SHIFT_LABELS.get(r['shift_code'],r['shift_code'])) for r in pair)
        swap_dates=st.multiselect('Değiştirilecek günler',common,format_func=description,key=key+'_days')
        if swap_dates:
            selected_people=[person,candidates[other]]
            before=[r for r in rows if str(r['employee_id']) in {person_id,other} and r['date'] in swap_dates]
            st.markdown('**Şimdiki vardiyalar**');render_calendar(before,selected_people,min(swap_dates),max(swap_dates),key=key+'_before',height=160)
            try:
                changes=resolve_swap(state,{'id':'Önizleme','employee_id':person_id,'targets':[candidates[other]],'start_date':min(swap_dates),'end_date':max(swap_dates),'swap_dates':swap_dates})
                st.markdown('**Onaylanırsa oluşacak vardiyalar**');render_calendar(changes,selected_people,min(swap_dates),max(swap_dates),key=key+'_after',height=160)
            except ValueError as exc:st.warning(str(exc))
    else:
        days=sorted({r['date'] for r in own})
        selected=st.multiselect('Düzenlenecek günler',days,format_func=lambda d:f'{pd.Timestamp(d):%d.%m.%Y}',key=key+'_attendance_days')
        before=[r for r in own if r['date'] in selected]
        if before:
            st.markdown('**Başlangıç / Bitiş hücresine tıklayarak yeni saati yaz.**' if kind in {'Erken çıkış','Geç giriş'} else '**Seçilen günlere uygulanacak durum**')
            source=pd.DataFrame([{'Ad soyad':person['full_name'],'Tarih':r['date'],'Durum':SHIFT_LABELS.get(r['shift_code'],r['shift_code']),'Başlangıç':r.get('start') or '', 'Bitiş':r.get('end') or ''} for r in before])
            editable=kind in {'Erken çıkış','Geç giriş'}
            edited=st.data_editor(source,disabled=['Ad soyad','Tarih','Durum']+(['Başlangıç'] if kind=='Erken çıkış' else ['Bitiş'] if kind=='Geç giriş' else ['Başlangıç','Bitiş']),hide_index=True,use_container_width=True,key=key+'_cells_'+kind+'_'+str(selected))
            for i,r in enumerate(before):
                if editable:
                    if (edited.iloc[i]['Başlangıç'],edited.iloc[i]['Bitiş'])!=(r.get('start') or '',r.get('end') or ''):changes.append(dict(r,start=edited.iloc[i]['Başlangıç'],end=edited.iloc[i]['Bitiş']))
                else:changes.append(dict(r,shift_code={'Rapor':'RAPOR','Yıllık izin':'YILLIK_IZIN','Mazeret izni':'MAZERET_IZNI'}[kind],start=None,end=None))
    reason=st.text_area('Değişiklik gerekçesi',key=key+'_reason',placeholder='Değişiklik neden gerekli?')
    valid=False
    if changes:
        try:
            validate_changes(state,changes,kind,reason,submitting=True)
            st.success('Kurallar uygun. Takvim, Planlama onayından sonra değişir.');valid=True
        except ValueError as exc:st.warning(str(exc))
    if st.button('Değişiklik Talebini Gönder',disabled=not valid,key=key+'_submit',type='primary'):
        try:
            if role=='agent':
                from ortak.talep_servisi import create_request
                if kind=='Vardiya değişimi':payload={'type':'Vardiya Değişim Talebi','start_date':min(swap_dates),'end_date':max(swap_dates),'targets':[all_people[other]],'swap_dates':swap_dates,'note':reason}
                else:
                    if len(changes)!=1:raise ValueError('Erken/geç giriş için her günün saatini ayrı talepte ilet.')
                    r=changes[0];payload={'type':'Erken Çıkış Talebi' if kind=='Erken çıkış' else 'Geç Giriş Talebi','start_date':r['date'],'end_date':r['date'],'overtime_start':r.get('start'),'overtime_end':r.get('end'),'note':reason}
                item=create_request(state,payload)
            else:item=submit_change(state,changes,kind,reason)
            st.success('Talep kaydedildi. '+('Takım Lideri ardından Planlama onayı bekleniyor.' if role=='agent' else 'Planlama onayı bekleniyor.'));state['change_form_notice']=item['id']
        except ValueError as exc:st.error(str(exc))


def render_change_approvals(state,key='change_review'):
    role=(state.get('profile') or {}).get('position')
    items=change_requests(state)
    if role not in {'wfm','manager','moderator','planning_manager'}:items=[r for r in items if r['requester'].get('username')==state['profile'].get('username')]
    if not items:st.info('Henüz değişiklik talebi yok.');return
    st.dataframe([{'Kayıt':r['id'],'İşlem':r['kind'],'İleten':r['requester'].get('full_name'),'Durum':r['status'],'Gerekçe':r['reason']} for r in items],hide_index=True,use_container_width=True)
    if role!='wfm':return
    pending={r['id']:r for r in items if r['status']=='Planlama onayı'}
    if not pending:st.info('Onay bekleyen değişiklik yok.');return
    ident=st.selectbox('İncelenecek değişiklik',list(pending),format_func=lambda i:pending[i]['kind']+' · '+str(pending[i]['requester'].get('full_name'))+' · '+pending[i]['created_at'][:10],key=key+'_pick');item=pending[ident]
    lookup={str(e['employee_id']):e for e in get_people(state)}
    st.dataframe([{'Personel':lookup.get(str(a['employee_id']),{}).get('full_name',a['employee_id']),'Tarih':a['date'],'Eski':str(b['shift_code'])+' '+str(b.get('start') or '')+'–'+str(b.get('end') or ''),'Yeni':str(a['shift_code'])+' '+str(a.get('start') or '')+'–'+str(a.get('end') or '')} for b,a in zip(item['before'],item['changes'])],hide_index=True,use_container_width=True)
    st.write('**Gerekçe:** '+item['reason']);note=st.text_input('Ret gerekçesi',key=key+'_note');a,b=st.columns(2)
    for col,caption,approve in [(a,'Onayla ve Takvime Uygula',True),(b,'Değişikliği Reddet',False)]:
        if col.button(caption,key=key+'_'+str(approve)):
            try:decide_change(state,item,approve,note);st.rerun()
            except ValueError as exc:st.error(str(exc))
