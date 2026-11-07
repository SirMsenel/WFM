import altair as alt
import pandas as pd
import streamlit as st


def daily_chart(frame, date_col, columns, height=310,y_title='Çağrı sayısı'):
    """Discrete calendar dates: no artificial noon/midnight ticks on daily data."""
    df=frame[[date_col]+list(columns)].copy().sort_values(date_col)
    dates=pd.to_datetime(df[date_col])
    df['Tarih']=dates.dt.strftime('%d.%m.%Y')
    order=list(dict.fromkeys(df.Tarih))
    plot=df.melt(id_vars='Tarih',value_vars=list(columns),var_name='Seri',value_name='Değer')
    chart=alt.Chart(plot).mark_line(point=True).encode(
        x=alt.X('Tarih:O',sort=order,axis=alt.Axis(labelAngle=-35,labelOverlap=True),title='Tarih'),
        y=alt.Y('Değer:Q',title=y_title),color=alt.Color('Seri:N',legend=alt.Legend(orient='bottom')),
        tooltip=['Tarih:N','Seri:N',alt.Tooltip('Değer:Q',format=',.1f')]).properties(height=height)
    st.altair_chart(chart,use_container_width=True)


def slot_heatmap(frame,value='Oran(%)',height=260):
    from core.forecast_service import DAY_NAMES
    df=frame.copy()
    df['Saat']=df.Slot.map(lambda s:f'{(int(s)-1)//2:02d}:{((int(s)-1)%2)*30:02d}')
    order=[f'{s//2:02d}:{(s%2)*30:02d}' for s in range(48)]
    chart=alt.Chart(df).mark_rect(cornerRadius=2).encode(
        x=alt.X('Saat:O',sort=order,axis=alt.Axis(values=order[::4],labelAngle=0),title='30 dakikalık dilimler'),
        y=alt.Y('Gün:N',sort=DAY_NAMES,title=None),
        color=alt.Color(f'{value}:Q',scale=alt.Scale(scheme='tealblues'),title=value),
        tooltip=['Gün:N','Saat:N',alt.Tooltip(f'{value}:Q',format='.3f')]).properties(height=height)
    st.altair_chart(chart,use_container_width=True)
