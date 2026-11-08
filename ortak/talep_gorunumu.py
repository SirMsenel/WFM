# Ortak / Talep Gorunumu — bu ekranın / servisin uygulama kodu.
"""Shared Turkish labels, receipt, content and timeline for every request screen."""
import pandas as pd
import streamlit as st
from ortak.durum_renkleri import badge,cell_style

from ortak.talep_servisi import TYPE_LABELS, is_terminal, act, refresh, visible


def formatted(value, clock=False):
    if not value:
        return '—'
    stamp=pd.to_datetime(value,errors='coerce')
    return str(value) if pd.isna(stamp) else stamp.strftime('%d.%m.%Y %H:%M' if clock else '%d.%m.%Y')


def stage(row):
    queue=row.get('queue')
    if queue in {'TL','TL_SWAP'}:
        waiting=[name for name in row.get('assigned_tls',[]) if name not in row.get('tl_approvals',[])]
        return 'Takım Lideri · '+(', '.join(waiting) if waiting else 'Atama bekleniyor')
    return {'WFM':'Planlama değerlendirmesinde','Closed':'Sonuçlandı'}.get(queue,'Değerlendirmede')


def title(row):
    return f"{row.get('created_by_name') or row.get('created_by','')} · {TYPE_LABELS.get(row.get('type'),row.get('type',''))} · {row.get('start_date') or 'Dönem bildirimi'} · {row['id'][-6:]}"


def rows_for_table(items):
    return [{"Kayıt no":r['id'],"Talep eden":r.get('created_by_name') or r.get('created_by'),
             "Talep türü":TYPE_LABELS.get(r.get('type'),r.get('type')),"Başlangıç":formatted(r.get('start_date')) if r.get('start_date') else 'Dönemlik',
             "Bitiş":formatted(r.get('end_date')),"Durum":r.get('status'),"Şu an kimde":stage(r),
             "Son işlemi yapan":(r.get('events') or [{}])[-1].get('actor_name',r.get('last_action_by','—')),
             "Son işlem":formatted(r.get('last_action_at') or r.get('created_at'),True)} for r in items]


def render_detail(req,key):
    st.markdown('### '+TYPE_LABELS.get(req.get('type'),req.get('type','Talep')))
    st.caption('Kayıt '+str(req['id']))
    from html import escape
    cards=[('Durum',req.get('status','—'),'#16786a'),('Değerlendirme aşaması',stage(req),'#5d56a8'),('Talep eden',req.get('created_by_name') or req.get('created_by',''),'#276a94')]
    for col,(label,value,color) in zip(st.columns(3),cards):
        col.markdown(f'<div style="height:124px;border:1px solid #dce6ed;border-top:4px solid {color};border-radius:16px;padding:15px;background:#f9fbfd;box-sizing:border-box"><div style="color:{color};font-weight:700;font-size:13px;margin-bottom:12px">{escape(label)}</div><div style="font-size:17px;font-weight:600;color:#203b4b;overflow-wrap:anywhere;max-height:66px;overflow:auto;line-height:1.3">{escape(str(value))}</div></div>',unsafe_allow_html=True)
    fields=[]
    if req.get('start_date'):fields.append(('Tarih',formatted(req['start_date'])+' → '+formatted(req.get('end_date') or req['start_date'])))
    if req.get('overtime_start'):fields.append(('Saat',str(req['overtime_start'])+' → '+str(req.get('overtime_end') or 'Belirtilmedi')))
    fields.append(('Onay beklenen',stage(req)))
    fields.append(('İlgili takım lideri',', '.join(req.get('assigned_tls',[])) or '—'))
    if req.get('targets'):fields.append(('Değişim yapılacak personel',', '.join(t.get('full_name','') for t in req['targets'])))
    st.dataframe(pd.DataFrame(fields,columns=['Bilgi','İçerik']),hide_index=True,use_container_width=True)
    st.markdown('#### Personelin Açıklaması')
    st.info(req.get('note') or 'Açıklama eklenmemiş.')
    attachment=req.get('attachment') or {}
    if attachment.get('rows'):
        st.markdown('#### Gönderilen Ders / Sınav / Talep İçeriği')
        frame=pd.DataFrame(attachment['rows']).fillna('')
        if 'Saat' in frame and any(c in frame for c in ['Pazartesi','Salı','Çarşamba']):
            frame=frame.melt(id_vars='Saat',var_name='Gün',value_name='Ders');frame=frame[frame.Ders.astype(str).str.strip()!=''][['Gün','Saat','Ders']]
        st.dataframe(frame,hide_index=True,use_container_width=True)
    if req.get('resolved_assignments'):
        st.markdown('#### Onaylanan Vardiya Değişimi')
        st.dataframe(req['resolved_assignments'],hide_index=True,use_container_width=True)
    if req.get('decision_note'):
        st.markdown('#### Değerlendirme Sonucu');st.write(req['decision_note'])
    with st.expander('İşlem Geçmişini Göster'):
        events=req.get('events',[])
        if events:
            history=pd.DataFrame([{'Tarih':formatted(e.get('at'),True),'İşlemi yapan':e.get('actor_name') or e.get('actor'),'İşlem':e.get('action'),'Durum':e.get('to'),'Not':e.get('note')} for e in events])
            st.dataframe(history.style.map(cell_style,subset=['Durum']),hide_index=True,use_container_width=True)
        else:st.caption('Ayrıntılı işlem geçmişi bulunmuyor.')


def render_center(audience='all', key='requests'):
    state = st.session_state
    if state.get('request_notice'):st.success(state.pop('request_notice'))
    profile = state.get('profile') or {}
    role = profile.get('position')
    items = [r for r in refresh(state) if visible(r,profile)]
    if audience == 'planning':
        planning_scope=st.radio('Talep akışı',['Planlamaya ulaşanlar','Planlamaya iletilmeyi bekleyenler','Tüm talepler'],horizontal=True,key=key+'_flow')
        if planning_scope=='Planlamaya ulaşanlar':items=[r for r in items if r.get('queue')=='WFM' or (is_terminal(r) and any(e.get('action','').startswith('Planlama') for e in r.get('events',[])))]
        elif planning_scope=='Planlamaya iletilmeyi bekleyenler':items=[r for r in items if r.get('queue') in {'TL','TL_SWAP'}]
    elif audience == 'tl':
        items = [r for r in items if profile.get('full_name') in r.get('assigned_tls',[])]
    pending = [r for r in items if not is_terminal(r)]
    a,b,c = st.columns(3)
    for col,card_title,count,status in [(a,'Değerlendirmede',len(pending),'Beklemede'),
                                    (b,'Onaylanan',sum(r.get('status') in {'Uygulandı','Onaylandı'} and is_terminal(r) for r in items),'Onaylandı'),
                                    (c,'Reddedilen',sum(r.get('status')=='Reddedildi' for r in items),'Reddedildi')]:
        with col.container(border=True):
            st.markdown(badge(status),unsafe_allow_html=True)
            st.metric(card_title,count)
    category = st.radio('Göster',['Bekleyen kayıtlar','Sonuçlanan kayıtlar','Tüm kayıtlar'],horizontal=True,key=key+'_category')
    search = st.text_input('Kayıt ara',placeholder='Personel, talep türü veya kayıt numarası',key=key+'_search')
    filtered = [r for r in items if (category=='Tüm kayıtlar' or (is_terminal(r)==(category=='Sonuçlanan kayıtlar')))
                and (not search or search.casefold() in (title(r)+' '+r['id']+' '+(r.get('note') or '')).casefold())]
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
    final_only=req.get('type') in {'Vardiya Değişim Talebi','Erken Çıkış Talebi','Geç Giriş Talebi','Rapor Bildirimi'}
    wfm_action = (role=='wfm' if final_only else role in {'wfm','manager','moderator'}) and req.get('queue')=='WFM'
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
            from ortak.planlama import REQUEST_CODES
            if action=='apply' and (req.get('type') in REQUEST_CODES or req.get('type') in {'Vardiya Değişim Talebi','Erken Çıkış Talebi','Geç Giriş Talebi'}):state['request_notice']='Onay kaydedildi. Yayınlanmış değişiklikler takvime uygulandı; gece ve izin kayıtları planlamanın kaynak listesine alındı.'
            elif action=='apply':state['request_notice']='Talep onaylandı. Okul kayıtları uygunluk kontrolünde kullanılır; genel talepler vardiya ataması oluşturmaz.'
            else:state['request_notice']='Talebin durumu güncellendi.'
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
