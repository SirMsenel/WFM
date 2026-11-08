# Ayarlar — bu ekranın / servisin uygulama kodu.
"""Ayarlar — Planlama tarafından yönetilen yetkilendirme ve bağlantı durumu."""
import streamlit as st
from ortak.roller_ve_yetkiler import ROLE_LABELS,CAPTIONS,permissions,save_permissions


def render():
    state=st.session_state;st.title('⚙️ Ayarlar')
    if (state.get('profile') or {}).get('position')!='wfm':st.info('Yetkilendirme ayarlarını Planlama yönetir.');return
    st.subheader('Yetkilendirme')
    role=st.selectbox('Rol',list(ROLE_LABELS),format_func=ROLE_LABELS.get,key='permission_role')
    existing=permissions(state,role)
    options=[k for k in CAPTIONS if (k!='rapor_gir' or role=='tl') and (k!='yetki_yonet' or role=='wfm') and (k!='kayit_merkezi' or role in {'wfm','manager','moderator'})]
    chosen=st.multiselect('İzin verilen işlemler',options,default=[k for k in existing if k in options],format_func=CAPTIONS.get,key='permission_flags_'+role)
    reason=st.text_input('Yetki değişikliği gerekçesi',key='permission_reason')
    if st.button('Yetkileri Kaydet',key='permission_save'):
        try:save_permissions(state,role,chosen,reason);st.success('Yetkiler kaydedildi ve kayıt merkezine işlendi.')
        except ValueError as exc:st.error(str(exc))
    st.subheader('Kurumsal Bağlantı Hazırlığı')
    from ortak.kurumsal_baglanti import connection_status
    st.dataframe(connection_status(),hide_index=True,use_container_width=True)
    st.caption('Bağlantı adresleri ve erişim sırları sunucu ortam değişkenlerinden alınır; şifre/token burada gösterilmez. Ayrıntılar KURUMSAL_BAGLANTI.md dosyasında.')
