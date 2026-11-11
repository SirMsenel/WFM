"""Takvim Görünümü — tüm ekranlarda yalnızca ad soyad, tarih ve vardiya hücreleri."""
import streamlit as st
from ortak.planlama import calendar_grid
from ortak.vardiya_gorunumu import cell_style


def render_calendar(rows,people,start,end,key=None,height=450):
    grid=calendar_grid({'source_rows':rows,'staff':people,'exam_keys':set()},{'start':start,'end':end})
    if grid.empty:st.info('Gösterilecek kayıt yok.');return grid
    modern_grid(grid,key or 'shared_roster')
    return grid


def modern_grid(grid,key):
    from html import escape
    import math
    if grid.empty:st.info('Kayıt yok.');return
    per_page=25;pages=math.ceil(len(grid)/per_page)
    page=st.number_input('Takvim sayfası',min_value=1,max_value=max(1,pages),value=1,key=key+'_page') if pages>1 else 1
    shown=grid.iloc[(page-1)*per_page:page*per_page]
    css='<style>.roster-shell{border:1px solid #dae5ee;border-radius:18px;overflow:auto;max-height:620px;box-shadow:0 5px 20px #173e5008}.modern-roster{border-collapse:separate;border-spacing:0;min-width:100%;font-size:12px}.modern-roster th{background:#edf5f8;color:#254c61;padding:13px 11px;position:sticky;top:0;z-index:2;white-space:nowrap;border-bottom:1px solid #dce7ed}.modern-roster td{padding:7px 9px;border-bottom:1px solid #eff3f7;text-align:center;white-space:nowrap}.modern-roster th:first-child,.modern-roster td:first-child{position:sticky;left:0;text-align:left;min-width:160px;background:#f8fbfd;z-index:1;font-weight:650;color:#24465a}.modern-roster th:first-child{z-index:3}.shift-pill{display:block;padding:8px 10px;border-radius:9px;min-width:90px}.modern-roster tr:hover td{border-bottom-color:#a5cdd6}</style>'
    head=''.join('<th>'+escape(str(c)).replace('\n','<br>')+'</th>' for c in grid)
    rows=[]
    for _,r in shown.iterrows():
        cells=[]
        for i,value in enumerate(r):
            text=escape(str(value)).replace("\n","<br>");cells.append('<td>'+text+'</td>' if i==0 else '<td><span class="shift-pill" style="'+cell_style(value)+'">'+text+'</span></td>')
        rows.append('<tr>'+''.join(cells)+'</tr>')
    st.markdown(css+'<div class="roster-shell"><table class="modern-roster"><thead><tr>'+head+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>',unsafe_allow_html=True)
