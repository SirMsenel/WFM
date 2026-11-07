"""Shared Turkish labels, receipt, content and timeline for every request screen."""
import pandas as pd
import streamlit as st
from core.status_style import badge,cell_style

from core.request_service import TYPE_LABELS, is_terminal, act, refresh, visible


def formatted(value, clock=False):
    if not value:
        return '—'
    stamp=pd.to_datetime(value,errors='coerce')
    return str(value) if pd.isna(stamp) else stamp.strftime('%d.%m.%Y %H:%M' if clock else '%d.%m.%Y')


def stage(row):
    return {"TL":"Takım liderinde","TL_SWAP":"Takım lideri onaylarında","WFM":"Planlama değerlendirmesinde","Closed":"Sonuçlandı"}.get(row.get("queue"),"Değerlendirmede")


def title(row):
    return f"{row.get('created_by_name') or row.get('created_by','')} · {TYPE_LABELS.get(row.get('type'),row.get('type',''))} · {row.get('start_date') or 'Dönem bildirimi'} · {row['id'][-6:]}"


def rows_for_table(items):
    return [{"Kayıt no":r['id'],"Talep eden":r.get('created_by_name') or r.get('created_by'),
             "Talep türü":TYPE_LABELS.get(r.get('type'),r.get('type')),"Başlangıç":formatted(r.get('start_date')) if r.get('start_date') else 'Dönemlik',
             "Bitiş":formatted(r.get('end_date')),"Durum":r.get('status'),"Şu an kimde":stage(r),
             "Son işlemi yapan":(r.get('events') or [{}])[-1].get('actor_name',r.get('last_action_by','—')),
             "Son işlem":formatted(r.get('last_action_at') or r.get('created_at'),True)} for r in items]


def render_detail(req, key):
    with st.container(border=True):
        st.markdown("#### "+TYPE_LABELS.get(req.get('type'),req.get('type','Talep')))
        a,b,c = st.columns(3)
        a.caption("Durum")
        a.markdown(badge(req.get('status','—')),unsafe_allow_html=True)
        b.caption("Aşama")
        b.write(stage(req))
        c.caption("Kayıt no")
        c.write(req['id'])
        st.write(f"**Talep eden:** {req.get('created_by_name') or req.get('created_by')} · **Hesap:** {req.get('created_by')}")
        st.write(f"**İlgili liderler:** {', '.join(req.get('assigned_tls',[])) or '—'}")
        if req.get('tl_approvals'):
            st.write("**Onaylayan liderler:** "+', '.join(req['tl_approvals']))
        if req.get('start_date'):
            st.write(f"**Tarih:** {formatted(req['start_date'])} → {formatted(req.get('end_date') or req['start_date'])}")
        if req.get('overtime_start'):
            st.write(f"**Saat:** {req['overtime_start']} → {req.get('overtime_end') or 'Bitiş belirtilmemiş'}")
        if req.get('targets'):
            st.write("**Değişim yapılacak personel:** "+', '.join(t.get('full_name','') for t in req['targets']))
        st.write("**Personelin açıklaması**")
        st.write(req.get('note') or 'Açıklama eklenmemiş.')
        attachment = req.get('attachment')
        if attachment:
            st.markdown("##### Gönderilen İçerik")
            st.caption(attachment.get('title','Kayıt anındaki içerik'))
            if attachment.get('rows'):
                st.dataframe(pd.DataFrame(attachment['rows']),use_container_width=True,hide_index=True)
        if req.get('decision_note'):
            st.write("**Değerlendirme notu:** "+req['decision_note'])
    events = req.get('events',[])
    st.markdown("##### İşlem Geçmişi")
    if events:
        history=pd.DataFrame([{'Tarih':formatted(e.get('at'),True),'İşlemi yapan':e.get('actor_name') or e.get('actor'),
                              'İşlem':e.get('action'),'Önceki durum':e.get('from'),'Yeni durum':e.get('to'),'Not':e.get('note')} for e in events])
        st.dataframe(history.style.map(cell_style,subset=['Önceki durum','Yeni durum']),hide_index=True,use_container_width=True)
    else:
        st.caption("Eski kayıt: ayrıntılı işlem geçmişi bulunmuyor.")


def render_center(audience='all', key='requests'):
    state = st.session_state
    profile = state.get('profile') or {}
    role = profile.get('position')
    items = [r for r in refresh(state) if visible(r,profile)]
    if audience == 'planning':
        items = [r for r in items if r.get('queue')=='WFM' or (is_terminal(r) and any(e.get('action','').startswith('Planlama') for e in r.get('events',[])))]
    elif audience == 'tl':
        items = [r for r in items if profile.get('full_name') in r.get('assigned_tls',[])]
    pending = [r for r in items if not is_terminal(r)]
    a,b,c = st.columns(3)
    for col,title,count,status in [(a,'Değerlendirmede',len(pending),'Beklemede'),
                                    (b,'Onaylanan',sum(r.get('status') in {'Uygulandı','Onaylandı'} and is_terminal(r) for r in items),'Onaylandı'),
                                    (c,'Reddedilen',sum(r.get('status')=='Reddedildi' for r in items),'Reddedildi')]:
        with col.container(border=True):
            st.markdown(badge(status),unsafe_allow_html=True)
            st.metric(title,count)
    category = st.radio('Göster',['Bekleyen kayıtlar','Sonuçlanan kayıtlar','Tüm kayıtlar'],horizontal=True,key=key+'_category')
    search = st.text_input('Kayıt ara',placeholder='Personel, talep türü veya kayıt numarası',key=key+'_search')
    filtered = [r for r in items if (category=='Tüm kayıtlar' or (is_terminal(r)==(category=='Sonuçlanan kayıtlar')))
                and (not search or search.casefold() in (title(r)+' '+r['id']+' '+r.get('note','')).casefold())]
    filtered.sort(key=lambda r:r.get('created_at',''),reverse=True)
    if not filtered:
        st.info('Bu görünümde kayıt yok.')
        return
    st.caption('Detayını görmek istediğin kaydın satırına tıkla. Başlangıçta ilk kayıt gösterilir.')
    event=st.dataframe(pd.DataFrame(rows_for_table(filtered)).style.map(cell_style,subset=['Durum']),hide_index=True,use_container_width=True,
                       on_select='rerun',selection_mode='single-row',key=key+'_table')
    picked=event.selection.rows
    index=picked[0] if picked and picked[0]<len(filtered) else 0
    req=filtered[index]
    st.divider()
    render_detail(req,key)
    if is_terminal(req):
        return
    tl_action = role=='tl' and req.get('queue') in {'TL','TL_SWAP'} and profile.get('full_name') in req.get('assigned_tls',[]) and profile.get('full_name') not in req.get('tl_approvals',[])
    wfm_action = role in {'wfm','manager','moderator'} and req.get('queue')=='WFM'
    own = req.get('created_by')==profile.get('username')
    if not (tl_action or wfm_action or own):
        st.caption('Talep ilgili değerlendirme aşamasında. Bu hesapta işlem beklenmiyor.')
        return
    with st.form(key+'_action_form_'+req['id']):
        note = st.text_area('Değerlendirme notu / ret gerekçesi',key=key+'_action_note_'+req['id'])
        action = None
        a,b = st.columns(2)
        if tl_action or wfm_action:
            if a.form_submit_button('Onayla ve Planlamaya İlet' if tl_action else 'Onayla ve Plana Al'):
                action = 'forward' if tl_action else 'apply'
            if b.form_submit_button('Gerekçeyle Reddet'):
                action = 'reject'
        elif own:
            if a.form_submit_button('Talebimi Geri Çek'):
                action='cancel'
    if action:
        try:
            act(state,req,action,note)
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
