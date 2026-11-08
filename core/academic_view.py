import pandas as pd
import streamlit as st
from core.personnel import get_people,visible_people


def academic_records(state,profile):
    people=visible_people(profile,get_people(state));allowed={e.get('username'):e for e in people};output={'Dersler':[],'Sınavlar':[],'Bayram':[]}
    for source,kind in [('acad_schedules','Dersler'),('acad_exam_calendar','Sınavlar'),('acad_bayram_requests','Bayram')]:
        for user,terms in state.get(source,{}).items():
            if user not in allowed:continue
            person=allowed[user]
            for term,records in terms.items():
                for row in pd.DataFrame(records).fillna('').to_dict('records'):
                    info={'Personel':person['full_name'],'Personel No':str(person['employee_id']),'Hesap':user,'Takım lideri':person.get('team_lead'),'Dönem':term}
                    if kind=='Dersler':
                        for day,value in row.items():
                            if day!='Saat' and str(value).strip():output[kind].append({**info,'Gün':day,'Saat':row.get('Saat'),'Ders':value})
                    elif any(str(v).strip() for v in row.values()):output[kind].append({**info,**row})
    return output


def render_academic_browser(state):
    profile=state.get('profile') or {};data=academic_records(state,profile)
    st.caption('Takım lideri yalnızca kendi ekibini; WFM ve yönetici bütün personelleri görür. Personel kendi kayıtlarını düzenler.')
    query=st.text_input('Ders ve sınav kayıtlarında personel ara',key='academic_staff_search')
    kind=st.segmented_control('Okul bilgisi',['Dersler','Sınavlar','Bayram'],default='Dersler',key='academic_staff_kind') or 'Dersler'
    rows=[r for r in data[kind] if not query or query.casefold() in ' '.join(str(v) for v in r.values()).casefold()]
    if not rows:st.info('Bu kapsamda kayıt bulunamadı.');return
    st.dataframe(rows,hide_index=True,use_container_width=True,height=540)
    st.download_button('Görünen Okul Kayıtlarını CSV İndir',pd.DataFrame(rows).to_csv(index=False).encode('utf-8-sig'),'okul_kayitlari.csv','text/csv')
