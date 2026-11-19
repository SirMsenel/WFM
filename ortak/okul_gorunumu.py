# Ortak / Okul Gorunumu — bu ekranın / servisin uygulama kodu.
import pandas as pd
import streamlit as st
from ortak.personel import get_people,visible_people


def academic_records(state,profile):
    people=visible_people(profile,get_people(state));allowed={e.get('username'):e for e in people};output={'Dersler':[],'Sınavlar':[],'Bayram':[]}
    for source,kind in [('acad_schedules','Dersler'),('acad_exam_calendar','Sınavlar'),('acad_bayram_requests','Bayram')]:
        for user,terms in state.get(source,{}).items():
            if user not in allowed:continue
            person=allowed[user]
            for term,records in terms.items():
                for row in pd.DataFrame(records).fillna('').to_dict('records'):
                    info={'Personel':person['full_name'],'Sicil no':person.get('sicil_no') or str(person['employee_id']),'Kullanıcı adı':user,'Takım lideri':person.get('team_lead'),'Dönem':term}
                    if kind=='Dersler':
                        for day,value in row.items():
                            if day!='Saat' and str(value).strip():output[kind].append({**info,'Gün':day,'Saat':row.get('Saat'),'Ders':value})
                    elif any(str(v).strip() for v in row.values()):output[kind].append({**info,**row})
    return output


def render_academic_browser(state):
    from html import escape
    from math import ceil
    from ortak.cagri_tahmin_servisi import DAY_NAMES
    profile=state.get('profile') or {};data=academic_records(state,profile)
    a,b=st.columns([2,1])
    query=a.text_input('Ders ve sınav kayıtlarında personel ara',placeholder='Ad soyad veya takım lideri',key='academic_staff_search')
    kinds=['Dersler','Sınavlar','Bayram']
    kind=st.segmented_control('Okul bilgisi',kinds,default='Dersler',key='academic_staff_kind',label_visibility='collapsed') or 'Dersler'
    rows=[r for r in data[kind] if not query or query.casefold() in ' '.join(str(v) for v in r.values()).casefold()]
    if not rows:st.info('Bu kapsamda kayıt bulunamadı.');return
    grouped={}
    for r in rows:grouped.setdefault((r['Kullanıcı adı'],r['Dönem']),[]).append(r)
    pages=max(1,ceil(len(grouped)/8));page=b.number_input('Sayfa',min_value=1,max_value=pages,value=1,key='school_cards_page_'+kind)
    selected=list(grouped.values())[(page-1)*8:page*8]
    st.markdown('<style>.school-card{border:1px solid #dce6ee;border-radius:18px;overflow:hidden;margin:14px 0;background:#fff}.school-person{padding:16px 18px;background:#f2f7fb;display:flex;justify-content:space-between;color:#244756;font-weight:700}.school-week{display:grid;grid-template-columns:repeat(7,minmax(110px,1fr));overflow-x:auto}.school-day{padding:10px;border-right:1px solid #edf1f5;min-height:115px}.school-day-title{font-size:12px;font-weight:700;color:#5e7584;margin-bottom:10px}.school-event{border-left:3px solid #6c85c6;border-radius:8px;padding:9px;background:#edf2fc;margin:7px 0;font-size:12px;color:#304d70}.school-event b{display:block;margin-top:5px}</style>',unsafe_allow_html=True)
    for entries in selected:
        header='<div class="school-person"><span>'+escape(entries[0]['Personel'])+'</span><small>'+escape(str(entries[0]['Dönem']))+'</small></div>'
        if kind=='Dersler':
            cells=[]
            for day in DAY_NAMES:
                events=''.join('<div class="school-event">'+escape(str(r.get('Saat') or 'Saat belirtilmedi'))+'<b>'+escape(str(r.get('Ders') or 'Ders'))+'</b></div>' for r in entries if r.get('Gün')==day)
                cells.append('<div class="school-day"><div class="school-day-title">'+day+'</div>'+events+'</div>')
        else:
            cells=[]
            for r in entries:
                date=r.get('Tarih') or r.get('Başlangıç');stamp=pd.to_datetime(date,errors='coerce')
                title='Tarih belirtilmedi' if pd.isna(stamp) else stamp.strftime('%d.%m.%Y')+' '+DAY_NAMES[stamp.weekday()]
                timing=(str(r.get('Saat') or '')+' – '+str(r.get('Bitiş') or '')).strip(' –')
                detail=r.get('Ders') or r.get('Talep Türü') or kind
                cells.append('<div class="school-day"><div class="school-day-title">'+escape(title)+'</div><div class="school-event" style="background:'+('#fff5e0' if kind=='Sınavlar' else '#eef7ef')+'">'+escape(timing)+'<b>'+escape(str(detail))+'</b>'+escape(str(r.get('Açıklama') or r.get('Sınav Türü') or ''))+'</div></div>')
        st.markdown('<div class="school-card">'+header+'<div class="school-week">'+''.join(cells)+'</div></div>',unsafe_allow_html=True)
    st.download_button('Görünen Okul Kayıtlarını CSV İndir',pd.DataFrame(rows).to_csv(index=False).encode('utf-8-sig'),'okul_kayitlari.csv','text/csv')
