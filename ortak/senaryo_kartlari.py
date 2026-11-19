"""Simülasyon ayına göre güncellenen karşılaştırma kartları; hesapları değiştirmez."""
from html import escape
import pandas as pd
import streamlit as st


def render_scenarios(table,target_sl):
    months=sorted(table['Ay'].unique());st.markdown('### Senaryoları Karşılaştır')
    selected=st.select_slider('İncelenecek senaryo ayı',options=months,value=months[0],key='sim_scenario_month') if len(months)>1 else months[0]
    st.caption(f'{selected} · Aşağıdaki kartlar aynı ayın üç farklı koşulunu karşılaştırır.')
    selected_rows=table[table['Ay']==selected]
    for col,(name,color,icon,subtitle) in zip(st.columns(3),[('İyi','#208b77','↗','Daha düşük çağrı ve ayrılma'),('Normal','#567cb5','◉','Mevcut eğilimin devamı'),('Kötü','#bd6c68','↘','Daha yüksek çağrı ve ayrılma')]):
        data=selected_rows[selected_rows['Senaryo']==name]
        if data.empty:continue
        row=data.iloc[0];needed=int(row['Gerekli personel']);current=int(row['Mevcut personel']);gap=max(0,needed-current);sl=float(row['Simüle SL (%)']);fill=max(0,min(100,sl));delta=sl-float(target_sl);badge=f'{gap:,} kişi alım ihtiyacı' if gap else 'Personel kapasitesi yeterli';badge_color='#a4514b' if gap else '#208b77'
        col.markdown(f'''<div class="simulation-scenario-card" style="padding:22px;border-radius:20px;border:1px solid {color}44;border-top:5px solid {color};background:linear-gradient(150deg,{color}14,#fff);min-height:385px;box-shadow:0 6px 20px #193b4a08">
<div style="display:flex;justify-content:space-between;align-items:center;color:{color}"><b style="font-size:22px">{escape(name)} Senaryo</b><span style="font-size:27px">{icon}</span></div>
<div style="font-size:12px;color:#65798a;margin:7px 0 18px">{subtitle}</div>
<div style="color:#526d7c;font-size:12px">GEREKLİ PERSONEL</div><div style="font-size:38px;font-weight:800;color:{color};margin:4px 0 12px">{needed:,}<small style="font-size:14px;font-weight:500"> kişi</small></div>
<div style="display:flex;justify-content:space-between;gap:10px;color:#39596b;font-size:13px;border-top:1px solid {color}22;padding-top:12px"><span>Mevcut personel <b>{current:,}</b></span><span>Çağrı <b>{int(row['Çağrı tahmini']):,}</b></span></div>
<div style="display:flex;justify-content:space-between;margin:18px 0 7px;color:#39596b;font-size:13px"><span>Simüle servis seviyesi</span><b>%{sl:.2f}</b></div>
<div style="height:8px;border-radius:8px;background:{color}20;overflow:hidden"><div style="height:100%;width:{fill:.2f}%;background:{color};border-radius:8px"></div></div>
<div style="font-size:11px;margin:6px 0 15px;color:#65798a">Hedef %{target_sl:.0f} · Fark {delta:+.2f} yüzde puan</div>
<div style="padding:9px 10px;border-radius:10px;background:{badge_color}14;color:{badge_color};font-weight:650;font-size:13px">{badge}</div>
<div style="font-size:11px;color:#65798a;margin-top:12px">Tepe yarım saat: {int(row['Tepe yarım saat çağrı']):,} çağrı</div></div>''',unsafe_allow_html=True)
