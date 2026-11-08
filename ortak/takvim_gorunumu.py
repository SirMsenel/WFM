"""Takvim Görünümü — tüm ekranlarda yalnızca ad soyad, tarih ve vardiya hücreleri."""
import streamlit as st
from ortak.planlama import calendar_grid
from ortak.vardiya_gorunumu import cell_style


def render_calendar(rows,people,start,end,key=None,height=450):
    grid=calendar_grid({'source_rows':rows,'staff':people,'exam_keys':set()},{'start':start,'end':end})
    if grid.empty:st.info('Gösterilecek kayıt yok.');return grid
    st.dataframe(grid.style.map(cell_style,subset=[c for c in grid if c!='Personel']).set_properties(**{'text-align':'center'}),hide_index=True,use_container_width=True,height=height,key=key)
    return grid
