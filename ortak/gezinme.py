# Ortak / Gezinme — bu ekranın / servisin uygulama kodu.
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


def select_section(state,key,page):
    """Bir sonraki render başlamadan bölüm seç.

    Segmented control oluşturulduktan sonra onun session-state anahtarına yazmak
    Streamlit'te WidgetAlreadyInstantiatedError üretir. Bekleyen seçim, sections
    çalışmaya başladığında widget oluşturulmadan uygulanır.
    """
    state[key]=page
    state[key+'_control_pending']=page


def sections(key,pages,single_line=False):
    labels=list(pages)
    control=key+'_control'
    pending=st.session_state.pop(control+'_pending',None)
    if pending in labels:
        st.session_state[key]=pending
        st.session_state[control]=pending
    if st.session_state.get(key) not in labels:st.session_state[key]=labels[0]
    if st.session_state.get(control)!=st.session_state[key]:st.session_state[control]=st.session_state[key]
    def changed():
        selected=st.session_state.get(control) or labels[0]
        if control not in st.session_state:return
        if st.session_state.get('main_page') and selected!=st.session_state.get(key):
            history=list(st.session_state.get('navigation_history',[]))
            history.append({'page':st.session_state['main_page'],'sections':{k:v for k,v in st.session_state.items() if k.startswith('nav_') and not k.endswith('_control')}})
            st.session_state['navigation_history']=history[-25:]
        st.session_state[key]=selected
    if single_line:
        # Vardiya ekranı da diğer ekranlarla aynı segmented-control görünümünü
        # kullanır. Alan yetmezse seçenekler ortalanmış biçimde ikinci satıra
        # geçer; ayrı sütun düğmeleri gibi sıkışıp okunmaz hâle gelmez.
        st.markdown(f'''<style>
        .st-key-{key}-section-tabs [role="radiogroup"]{{display:flex!important;flex-wrap:wrap!important;justify-content:center!important;gap:.28rem!important}}
        .st-key-{key}-section-tabs [role="radiogroup"] label{{flex:0 0 auto!important;white-space:nowrap!important}}
        .st-key-{key}-section-tabs [role="radiogroup"] p{{font-size:.78rem!important}}
        </style>''',unsafe_allow_html=True)
        with st.container(key=key+'_section_tabs'):
            st.markdown('<div class="wfm-section-label">Bu ekranın bölümleri</div><div class="wfm-section-rule"></div>',unsafe_allow_html=True)
            selected=st.segmented_control('Bölümler',labels,key=control,selection_mode='single',on_change=changed,label_visibility='collapsed')
        pages[selected or st.session_state[key]]()
        return
    with st.container(key=key+'_section_tabs'):
        st.markdown('<div class="wfm-section-label">Bu ekranın bölümleri</div><div class="wfm-section-rule"></div>',unsafe_allow_html=True)
        selected=st.segmented_control('Bölümler',labels,key=control,selection_mode='single',on_change=changed,label_visibility='collapsed')
    pages[selected or st.session_state[key]]()
