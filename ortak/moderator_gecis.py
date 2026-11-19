"""Moderatör, şifre istemeden gerçek kullanıcı görünümüne geçer ve geri döner."""
import streamlit as st


def render(state,api_get,api_post):
    origin=state.get('_moderator_origin')
    if not origin and state.get('profile',{}).get('position')!='moderator':return
    with st.expander('Kullanıcı Görünümü · Moderatör'):
        if origin:
            st.info('İşlem yapan: '+origin['profile']['username']+' · Görünüm: '+state['profile']['username'])
            if st.button('Moderatör Hesabına Dön',key='return_moderator'):
                from ortak.erisim import enter_session
                state.update(auth_token=origin['token'],profile=origin['profile']);state.pop('_moderator_origin',None);enter_session(state,state['profile']);st.rerun()
        token=(origin or {}).get('token') or state['auth_token']
        try:
            accounts=api_get('/auth/switch-users',token=token)['items']
            roles=sorted({p['position'] for p in accounts});from ortak.roller_ve_yetkiler import ROLE_LABELS
            role=st.selectbox('Görüntülenecek rol',roles,format_func=lambda r:ROLE_LABELS.get(r,r),key='moderator_role')
            people={p['username']:p for p in accounts if p['position']==role};pick=st.selectbox('Kullanıcı',list(people),format_func=lambda i:people[i]['full_name']+' · '+i,key='moderator_user_'+role)
            if st.button('Bu Kullanıcı Görünümüne Geç',key='moderator_switch'):
                original=origin or {'token':state['auth_token'],'profile':dict(state['profile'])};result=api_post('/auth/switch-user',{'username':pick},token=token)
                state['_moderator_origin']=original;state.update(auth_token=result['access_token'],profile=result['profile'])
                from ortak.erisim import enter_session
                enter_session(state,state['profile']);st.rerun()
        except Exception as e:st.error('Kullanıcı listesi alınamadı: '+str(e))
