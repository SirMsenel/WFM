import streamlit as st
from html import escape
from ortak.bildirimler import items,mark_read,mark_many_read


def render():
    s=st.session_state
    st.markdown('''<div style="padding:20px 22px;border:1px solid #d9e7ed;border-radius:21px;background:linear-gradient(135deg,#edf8f8,#f7f4fb);margin-bottom:14px"><div style="font-size:21px;font-weight:800;color:#315c6c">🔔 Bildirim Kutusu</div><div style="font-size:12px;color:#6b7f89;margin-top:5px">Hesabına ait vardiya, talep, onay ve uygulama haberlerini tek yerde takip et.</div></div>''',unsafe_allow_html=True)
    records=items(s);a,b=st.columns([2,1],vertical_alignment='bottom');categories=['Tümü']+sorted({p['Konu'] for p in records});kind=a.selectbox('Bildirim konusu',categories,key='notice_category');unread=b.toggle('Yalnızca okunmamışlar',False,key='notice_unread');chosen=[p for p in records if (kind=='Tümü' or p['Konu']==kind) and (not unread or not p['Okundu'])]
    if not chosen:st.info('Bu görünümde bildirim yok.');return
    summary,action=st.columns([4,1.45],vertical_alignment='center')
    summary.markdown(f'<div style="padding:11px 14px;border-radius:13px;background:#f3f8fa;color:#56717d;font-size:13px"><b>{len(chosen)}</b> bildirim gösteriliyor</div>',unsafe_allow_html=True)
    if action.button('Tümünü Okundu Yap',key='notices_all_read',use_container_width=True):
        mark_many_read(s,[p['id'] for p in chosen])
        st.rerun()
    colors=['#178d93','#7867ab','#bd8442','#4e82a7','#ae688d']
    for index,p in enumerate(chosen):
        color='#8a9aa3' if p['Okundu'] else colors[index%len(colors)]
        with st.container(border=False):
            body,button=st.columns([5.4,1],vertical_alignment='center')
            body.markdown(f'<div style="margin-top:10px;padding:16px 18px;border:1px solid {color}32;border-left:5px solid {color};border-radius:16px;background:linear-gradient(135deg,{color}0d,#fff)"><div style="display:flex;justify-content:space-between;gap:12px;color:{color}"><b>{escape(p["Başlık"])}</b><small>{escape(p["Tarih"][:16].replace("T"," "))}</small></div><div style="font-size:13px;color:#566b76;margin-top:8px;line-height:1.55">{escape(str(p["İçerik"]))}</div><div style="display:inline-block;margin-top:10px;padding:4px 9px;border-radius:999px;background:{color}12;color:{color};font-size:10px;font-weight:750">{escape(p["Konu"])}</div></div>',unsafe_allow_html=True)
            if not p['Okundu'] and button.button('Okundu',key='read_'+p['id'],use_container_width=True):
                mark_read(s,p['id']);st.rerun()
