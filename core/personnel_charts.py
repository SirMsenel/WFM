import altair as alt
import pandas as pd
import streamlit as st
from core.personnel import LANG_LABELS,WORK_LABELS

CITIES={'Ankara':(32.86,39.93),'Istanbul':(28.98,41.01),'İstanbul':(28.98,41.01),
        'Izmir':(27.14,38.42),'İzmir':(27.14,38.42),'Konya':(32.49,37.87),
        'Diyarbakir':(40.23,37.91),'Diyarbakır':(40.23,37.91),'Adana':(35.32,37.0),
        'Bursa':(29.06,40.19),'Antalya':(30.71,36.9),'Gaziantep':(37.38,37.07),
        'Kayseri':(35.49,38.72),'Trabzon':(39.72,41.0),'Erzurum':(41.28,39.90),
        'Eskişehir':(30.52,39.78),'Eskisehir':(30.52,39.78),'Mersin':(34.64,36.80),
        'Samsun':(36.34,41.28),'Van':(43.38,38.50),'Kocaeli':(29.94,40.77)}
# A local schematic coastline keeps the map usable without a map-token or tiles.
BOUNDARY=[[26.0,40.0],[26.3,41.7],[28.1,42.0],[29.1,41.2],[31.0,41.1],[33.1,42.0],
          [35.1,42.0],[36.5,41.3],[38.0,41.0],[40.1,41.1],[41.5,41.5],[43.4,41.1],
          [44.8,39.7],[44.3,38.4],[44.7,37.2],[42.0,37.3],[41.0,37.1],[38.0,36.8],
          [36.6,36.2],[36.1,35.9],[35.7,36.8],[34.0,36.3],[32.0,36.1],[30.6,36.8],
          [29.0,36.6],[28.0,36.7],[27.3,37.0],[27.2,38.0],[26.3,38.3],[26.9,39.4],[26.0,40.0]]


def location_map(counts):
    points=pd.DataFrame([{'Şehir':city,'Personel':count,'Boylam':CITIES[city][0],'Enlem':CITIES[city][1]}
                         for city,count in counts.items() if city in CITIES])
    outline=alt.Data(values=[{'type':'Feature','geometry':{'type':'Polygon','coordinates':[BOUNDARY]}}])
    base=alt.Chart(outline).mark_geoshape(fill='#eef5fa',stroke='#bfd1df',strokeWidth=1)
    if not points.empty:
        markers=alt.Chart(points).mark_circle(color='#117d99',opacity=.78,stroke='white',strokeWidth=2).encode(
            longitude='Boylam:Q',latitude='Enlem:Q',size=alt.Size('Personel:Q',scale=alt.Scale(range=[180,2100]),legend=None),
            tooltip=['Şehir:N','Personel:Q'])
        labels=alt.Chart(points).mark_text(dy=-23,fontSize=11,color='#24445b').encode(longitude='Boylam:Q',latitude='Enlem:Q',text='Şehir:N')
        base=base+markers+labels
    st.altair_chart(base.project(type='mercator').properties(height=260),use_container_width=True)
    unknown=[city for city in counts if city not in CITIES]
    st.caption('Şehir merkezlerine göre şematik dağılım. Noktaların büyüklüğü personel sayısını gösterir.')
    if unknown:
        st.caption('Haritada konumu tanımlı olmayan şehirler: '+', '.join(unknown))


def donut(counts,title,labels):
    from html import escape
    st.markdown(f'**{title}**')
    values=pd.DataFrame([{'Grup':labels.get(k,k),'Personel':v} for k,v in counts.items()])
    if values.empty:
        st.info('Kayıt yok.');return
    colors=['#118aa1','#6574c4','#e9a450','#699d78']
    ring=alt.Chart(values).mark_arc(innerRadius=50,outerRadius=76,cornerRadius=3).encode(
        theta='Personel:Q',color=alt.Color('Grup:N',scale=alt.Scale(domain=values.Grup.tolist(),range=colors[:len(values)]),legend=None),
        tooltip=['Grup:N','Personel:Q'])
    center=alt.Chart(pd.DataFrame({'Toplam':[int(values.Personel.sum())]})).mark_text(fontSize=26,fontWeight='bold',color='#173e50').encode(text='Toplam:Q')
    st.altair_chart((ring+center).properties(height=180),use_container_width=True)
    for i,record in enumerate(values.to_dict('records')):
        st.markdown(f'<div style="display:flex;justify-content:space-between;padding:5px 0;font-size:13px"><span><span style="color:{colors[i%len(colors)]}">●</span> {escape(str(record["Grup"]))}</span><b>{record["Personel"]}</b></div>',unsafe_allow_html=True)


def render_summary(summary):
    st.markdown('### Aktif Personel Özeti')
    a,b,c=st.columns([1.7,1,1])
    with a:
        st.metric('Toplam aktif personel',summary['total'])
        location_map(summary['location'])
    with b:
        donut(summary['language'],'Dil dağılımı',LANG_LABELS)
    with c:
        donut(summary['work_type'],'Çalışma biçimi',WORK_LABELS)
