"""Fatura Mutabakat — parametre, aylık hesap ve kişi bazlı ödeme detayı."""
import pandas as pd
import streamlit as st

from ortak.fatura_servisi import STATUS_LABELS,profiles,save_profile,delete_profile,calculate,summary
from ortak.personel import get_people,WORK_LABELS


def _month(state,key):
    from ortak.demo_zamani import today
    return st.date_input('Hesap ayı',value=today(state).replace(day=1),key=key,format='DD.MM.YYYY').replace(day=1)


def parameters():
    from ortak.personel_deposu import list_people
    s=st.session_state;people=[p for p in list_people(s,True) if p.get('position')=='agent'];companies=sorted({str(p.get('company') or 'Belirtilmemiş') for p in people})
    st.markdown('### Şirket ve Kaynak Ücret Parametreleri')
    with st.container(border=True):
        a,b,c=st.columns(3);company=a.selectbox('Şirket',companies,key='bill_company');group=b.selectbox('Kaynak grubu',list(WORK_LABELS),format_func=WORK_LABELS.get,key='bill_group');method=c.segmented_control('Ücretlendirme',['Günlük','Aylık'],default='Aylık',key='bill_method') or 'Aylık'
        a,b=st.columns(2);amount=a.number_input('Günlük / aylık birim ücret',min_value=0.,value=25000.,step=100.,key='bill_amount');basis=b.selectbox('Aylık gün katsayısı',['Takvim günü','30 gün sabit'],key='bill_basis',disabled=method!='Aylık')
        paid=st.multiselect('Ödeme yapılacak vardiya statüleri',list(STATUS_LABELS),default=['WORK','MESAI','GECE','OFF','YILLIK_IZIN','RAPOR'],format_func=STATUS_LABELS.get,key='bill_paid_statuses')
        st.caption('Seçilmeyen ücretsiz izin, koşullu rapor veya diğer statüler ödeme katsayısına dahil edilmez.')
        st.markdown('#### Vergi, Kesinti ve Ekler')
        tax_default=pd.DataFrame([{'Vergi / kalem':'KDV','Oran (%)':20.,'Yön':'Artı','Uygulama':'Ana hesaba ekle'}])
        taxes=st.data_editor(tax_default,num_rows='dynamic',hide_index=True,use_container_width=True,key='bill_tax_editor',column_config={'Vergi / kalem':st.column_config.TextColumn(required=True),'Oran (%)':st.column_config.NumberColumn(min_value=0,max_value=100,step=.1,required=True),'Yön':st.column_config.SelectboxColumn(options=['Artı','Eksi'],required=True),'Uygulama':st.column_config.SelectboxColumn(options=['Ana hesaba ekle','Vergiden düş'],required=True)})
        if st.button('Parametreyi Kaydet',type='primary',key='bill_profile_save'):
            try:
                tax_rows=[{'name':r['Vergi / kalem'],'rate':r['Oran (%)'],'direction':r['Yön'],'application':r['Uygulama']} for r in taxes.to_dict('records')]
                save_profile(s,{'company':company,'group':group,'method':method,'amount':amount,'coefficient_basis':basis,'paid_statuses':paid,'taxes':tax_rows});st.success('Fatura parametresi kaydedildi.');st.rerun()
            except (ValueError,TypeError) as exc:st.warning(str(exc))
    items=profiles(s)
    if not items:st.info('Henüz kayıtlı şirket/kaynak parametresi yok.');return
    st.markdown('### Kayıtlı Parametreler')
    for offset in range(0,len(items),3):
        for col,item in zip(st.columns(3),items[offset:offset+3]):
            with col.container(border=True):
                st.markdown(f'<div style="padding:13px;border-radius:14px;background:linear-gradient(135deg,#edf7f8,#f7f3fb)"><small>{item["method"].upper()}</small><h4 style="margin:5px 0">{item["company"]}</h4><b>{WORK_LABELS.get(item["group"],item["group"])}</b><div style="font-size:24px;font-weight:800;color:#2d7d8c;margin-top:10px">{item["amount"]:,.2f} TL</div><div style="font-size:11px;margin-top:8px">{len(item["paid_statuses"])} ücretli statü · {len(item.get("taxes",[]))} vergi/kesinti</div></div>',unsafe_allow_html=True)
                if st.button('Kaydı Sil',key='bill_delete_'+item['id'],use_container_width=True):delete_profile(s,item['id']);st.rerun()


def calculation():
    s=st.session_state;month=_month(s,'bill_calc_month');frame=calculate(s,month)
    if frame.empty:st.info('Bu ay için kayıtlı sözleşmeye uyan personel/vardiya bulunamadı. Parametre ekranını kontrol edin.');return
    total=float(frame['Net ödeme'].sum());base=float(frame['Ana tutar'].sum());tax=float(frame['Vergi/ek kesinti'].sum())
    from ortak.modern_kartlar import metric_cards
    metric_cards([('Toplam ana tutar',f'{base:,.2f} TL'),('Vergi / ek / kesinti',f'{tax:+,.2f} TL'),('Net mutabakat',f'{total:,.2f} TL'),('Faturalanan personel',frame['Personel'].nunique())])
    grouped=summary(frame);st.dataframe(grouped.style.format({'Çalışma saati':'{:.2f}','Ana tutar':'{:,.2f} TL','Vergi/ek kesinti':'{:+,.2f} TL','Net ödeme':'{:,.2f} TL'}).background_gradient(subset=['Net ödeme'],cmap='BuGn'),hide_index=True,use_container_width=True)
    import plotly.express as px
    fig=px.bar(grouped,x='Şirket',y='Net ödeme',color='Kaynak',text_auto='.3s',barmode='group');fig.update_layout(height=390,margin=dict(l=15,r=15,t=35,b=20));st.plotly_chart(fig,use_container_width=True)
    st.download_button('Aylık Mutabakatı CSV İndir',frame.to_csv(index=False).encode('utf-8-sig'),f'fatura_mutabakat_{month:%Y_%m}.csv','text/csv')


def detail():
    s=st.session_state;month=_month(s,'bill_detail_month');frame=calculate(s,month)
    if frame.empty:st.info('Detay oluşturacak mutabakat kaydı yok.');return
    companies=sorted(frame['Şirket'].unique());company=st.selectbox('Şirket filtresi',companies,key='bill_detail_company');view=frame[frame['Şirket']==company].copy()
    tab1,tab2=st.tabs(['Ödeme ve Statü Detayı','Verimlilik ve Doluluk'])
    status_columns=[label for label in STATUS_LABELS.values() if label in view]
    with tab1:
        cols=['Sicil no','Personel','Kaynak','Yöntem','Ücretli gün','Katsayı']+status_columns+['Ana tutar','Vergi/ek kesinti','Net ödeme','Vergi detayı']
        st.dataframe(view[cols].style.format({'Katsayı':'{:.4f}','Ana tutar':'{:,.2f} TL','Vergi/ek kesinti':'{:+,.2f} TL','Net ödeme':'{:,.2f} TL'}),hide_index=True,use_container_width=True,height=520)
        st.caption('Aylık yöntemde her ücretli gün 1/takvim günü (veya seçilen 30 gün sabiti) katsayısı üretir; günlerin toplamı en fazla 1 aylık ücrete ulaşır.')
    with tab2:
        productive=view['Çalışma']+view['Ek mesai']+view['Gece'];paid=view['Ücretli gün'].replace(0,float('nan'));view['Ücretli gün verimliliği (%)']=100*productive/paid;view['Saat başı maliyet']=view['Net ödeme']/view['Çalışma saati'].replace(0,float('nan'))
        from ortak.modern_kartlar import metric_cards
        metric_cards([('Toplam çalışma saati',f'{view["Çalışma saati"].sum():.1f}'),('Ort. ücretli gün verimliliği',f'%{view["Ücretli gün verimliliği (%)"].mean():.1f}'),('Ort. saat başı maliyet',f'{view["Saat başı maliyet"].mean():,.2f} TL')])
        st.dataframe(view[['Sicil no','Personel','Çalışma saati','Ücretli gün','Ücretli gün verimliliği (%)','Saat başı maliyet']].style.format({'Çalışma saati':'{:.2f}','Ücretli gün verimliliği (%)':'{:.2f}','Saat başı maliyet':'{:,.2f} TL'}).background_gradient(subset=['Ücretli gün verimliliği (%)'],cmap='RdYlGn'),hide_index=True,use_container_width=True)


def render():
    s=st.session_state;st.title('🧾 Fatura Mutabakat')
    if (s.get('profile') or {}).get('position') not in {'wfm','planning_manager','manager','assistant_manager','moderator'}:st.info('Bu ekran planlama ve yönetim rolleri içindir.');return
    from ortak.gezinme import sections
    sections('nav_billing',{'Parametreler':parameters,'Aylık Hesap':calculation,'Hesap Detayı':detail})
