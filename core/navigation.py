import streamlit as st


def navigate(state,page):
    current=state.get('main_page')
    if current and current!=page:
        history=list(state.get('navigation_history',[]))
        history.append({'page':current,'sections':{k:v for k,v in state.items() if k.startswith('nav_') and not k.endswith('_control')}})
        state['navigation_history']=history[-25:]
    state['main_page']=page


def go_back(state):
    history=list(state.get('navigation_history',[]))
    if not history:return
    previous=history.pop();state['navigation_history']=history
    state['main_page']=previous['page'];state.update(previous['sections'])


def sections(key,pages):
    labels=list(pages)
    if st.session_state.get(key) not in labels:st.session_state[key]=labels[0]
    control=key+'_control'
    if st.session_state.get(control)!=st.session_state[key]:st.session_state[control]=st.session_state[key]
    def changed():
        selected=st.session_state[control] or labels[0]
        if st.session_state.get('main_page') and selected!=st.session_state[key]:
            history=list(st.session_state.get('navigation_history',[]))
            history.append({'page':st.session_state['main_page'],'sections':{k:v for k,v in st.session_state.items() if k.startswith('nav_') and not k.endswith('_control')}})
            st.session_state['navigation_history']=history[-25:]
        st.session_state[key]=selected
    selected=st.segmented_control('Alt ekran',labels,key=control,selection_mode='single',on_change=changed)
    pages[selected or st.session_state[key]]()
