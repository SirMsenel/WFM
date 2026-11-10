"""Kayıt Başlıkları — kayıt içeriğini değiştirmeden anlaşılır kullanıcı başlıkları."""
from ortak.calisma_alani_deposu import connect,init_db


def title_for(path,ident,fallback):
    init_db(path)
    with connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS record_titles(id TEXT PRIMARY KEY,title TEXT NOT NULL)')
        row=db.execute('SELECT title FROM record_titles WHERE id=?',(ident,)).fetchone()
    return row[0] if row else fallback


def set_title(state,ident,title):
    if (state.get('profile') or {}).get('position') not in {'wfm','manager','moderator','planning_manager'}:raise ValueError('Kayıt başlığını yönetim rolleri değiştirebilir.')
    if not title.strip() or len(title.strip())>120:raise ValueError('1–120 karakterlik bir başlık girin.')
    path=state['workspace_db_path'];title_for(path,ident,'')
    with connect(path) as db:db.execute('INSERT INTO record_titles VALUES(?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title',(ident,title.strip()))


def title_editor(state,ident,fallback):
    import streamlit as st
    with st.expander('Kayıt başlığını düzenle'):
        title=st.text_input('Kayıt başlığı',value=title_for(state['workspace_db_path'],ident,fallback),key='record_title_'+ident,max_chars=120)
        if st.button('Başlığı Kaydet',key='record_title_save_'+ident):
            try:set_title(state,ident,title);st.success('Başlık kaydedildi.');st.rerun()
            except ValueError as exc:st.error(str(exc))


def record_picker(caption,records,label,key):
    """Widget değerini de görünen başlık olarak tutar; kimliği ayrı saklar."""
    import streamlit as st
    labels={}
    for r in records:
        text=label(r)
        if text in labels:text+=' · '+r['id'][-5:]
        labels[text]=r['id']
    current=st.session_state.get(key)
    if current not in labels:
        previous=st.session_state.get(key+'_id') or current
        st.session_state[key]=next((text for text,ident in labels.items() if ident==previous),next(iter(labels)))
    chosen=st.selectbox(caption,list(labels),key=key)
    st.session_state[key+'_id']=labels[chosen]
    return labels[chosen]
