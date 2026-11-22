"""Yabancı dil ihtiyacını ve vardiya taslağını ana plandan bağımsız yönetir."""
import pandas as pd
import streamlit as st

from ortak.calisma_alani_deposu import save_keys


LABELS={'en':'İngilizce','ar':'Arapça'}


def _calendar(result):
    from ortak.planlama import calendar_grid
    from ortak.vardiya_gorunumu import cell_style
    grid=calendar_grid({**result,'source_rows':result['plan'],'exam_keys':set()},result['period'])
    st.dataframe(grid.style.map(cell_style,subset=[c for c in grid if c not in {'Personel','Sicil no','Kullanıcı adı'}]),hide_index=True,use_container_width=True,height=470)


def _build(state,lang,demand):
    from modules.vardiya_plani.planlama_verileri import collect_inputs
    from modules.vardiya_plani.vardiya_motoru import generate_plan
    check=dict(state);check['planning_languages']={'tr':False,'en':lang=='en','ar':lang=='ar'}
    check['draft_shift_plan']=[r for r in state.get('draft_shift_plan',[]) if r.get('source')!='foreign_language_plan']
    staff,fixed,history,unavailable,issues=collect_inputs(check)
    order=[g for g in state.get('plan_group_priority',[]) if g in state['shift_rules']['work_type']]
    if set(order)!=set(state['shift_rules']['work_type']):order=list(state['shift_rules']['work_type'])
    ctx=state['plan_ctx']
    result=generate_plan(staff,demand,state['shift_rules'],order,ctx['start'],ctx['end'],fixed=fixed,history=history,unavailable=unavailable,strict_capacity=True,hour_targets=state.get('group_hour_targets',[]),languages=check['planning_languages'],exclude_early_hours=state.get('planning_exclude_early_hours',False),auto_night=state.get('shift_rules',{}).get('night',{}).get('auto_fill',True))
    result['issues']=issues+result['issues'];result['staff']=staff;result['period']={'start':str(ctx['start']),'end':str(ctx['end'])}
    return result


def _transfer(state,lang,result,ids):
    ids={str(eid) for eid in ids};start,end=result['period']['start'],result['period']['end']
    kept=[r for r in state.get('draft_shift_plan',[]) if not (r.get('source')=='foreign_language_plan' and r.get('language')==lang and start<=str(r.get('date'))<=end)]
    moved=[]
    for row in result['plan']:
        if str(row['employee_id']) in ids:moved.append({**row,'source':'foreign_language_plan','language':lang,'note':LABELS[lang]+' planından ana taslağa aktarıldı'})
    state['draft_shift_plan']=kept+moved
    transferred=dict(state.get('foreign_language_transferred_ids') or {});transferred[lang]=sorted(ids);state['foreign_language_transferred_ids']=transferred
    inclusion=dict(state.get('language_demand_inclusion') or {});inclusion[lang]=False;state['language_demand_inclusion']=inclusion
    for key in ('planning_result','planning_result_fingerprint','_status_plan_cache'):state.pop(key,None)
    save_keys(state)


def render():
    s=st.session_state;st.subheader('Yabancı Dil Vardiya Planlaması')
    lang=st.segmented_control('Planlanacak dil',['en','ar'],default='en',format_func=LABELS.get,key='foreign_plan_language') or 'en'
    ctx=s.get('plan_ctx') or {}
    if not s.get('plan_ctx_confirmed') or not ctx.get('start') or not ctx.get('end'):st.info('Önce Plan Dönem Seçimi ekranında dönemi onaylayın.');return
    source=s.get('sp_staffing_result_df')
    if source is None:st.info('Önce Personel Hesap ekranında ihtiyaç hesaplayın.');return
    saved=s.setdefault('language_demands',{}).get(lang);base=source.copy() if saved is None else saved.copy()
    with st.expander('Bu dilin yarım saatlik personel ihtiyacını tanımla'):
        table=base[['Tarih','Slot','Planlanan Agent']].copy();from ortak.saat_etiketleri import slot_label
        from ortak.cagri_tahmin_servisi import DAY_NAMES
        table['Tarih']=pd.to_datetime(table['Tarih']).dt.normalize();dates=sorted(table['Tarih'].unique());labels={pd.Timestamp(d).strftime('%d.%m')+' '+DAY_NAMES[pd.Timestamp(d).weekday()]:pd.Timestamp(d) for d in dates}
        wide=table.pivot(index='Slot',columns='Tarih',values='Planlanan Agent').reindex(range(1,49));wide.columns=[next(label for label,value in labels.items() if value==pd.Timestamp(d)) for d in wide.columns];wide.insert(0,'Yarım saat',[slot_label(slot) for slot in wide.index]);wide=wide.reset_index(drop=True)
        st.markdown('<div style="padding:12px 15px;border-radius:14px;background:#eef7f9;border:1px solid #d8e8ed"><b>30 Dakikalık Dil İhtiyacı</b><br><small>Satırlar saat aralığı, sütunlar tarih ve gün; hücreler planlanan agent sayısıdır.</small></div>',unsafe_allow_html=True)
        config={'Yarım saat':st.column_config.TextColumn('Yarım saat',width='small')};config.update({label:st.column_config.NumberColumn(label,min_value=0,step=1,required=True,width='small') for label in labels})
        edited=st.data_editor(wide,disabled=['Yarım saat'],hide_index=True,use_container_width=True,height=640,key='foreign_need_'+lang,column_config=config)
        if st.button('Dil İhtiyacını Kaydet',key='foreign_save_need'):
            values=edited.drop(columns=['Yarım saat']).apply(pd.to_numeric,errors='coerce')
            if values.isna().any().any() or (values<0).any().any():st.warning('İhtiyaç hücreleri boş veya negatif olamaz.')
            else:
                lookup={(str(day.date()),slot):float(values.iloc[slot-1][label]) for label,day in labels.items() for slot in range(1,49)}
                base['Planlanan Agent']=[lookup[(str(pd.Timestamp(day).date()),int(slot))] for day,slot in zip(base['Tarih'],base['Slot'])]
                base['Net Agent']=base['Planlanan Agent']*(1-base['Shrinkage (%)']/100) if 'Shrinkage (%)' in base else base['Planlanan Agent']*.7
                source_map=dict(s['language_demands']);source_map[lang]=base;s['language_demands']=source_map;save_keys(s);st.rerun()
    saved=s.get('language_demands',{}).get(lang)
    if saved is None:st.info('Bağımsız vardiya taslağı oluşturmak için önce bu dilin ihtiyacını kaydedin.');return
    header,action=st.columns([4,1.25],vertical_alignment='center')
    header.markdown(f'<div style="padding:15px 17px;border-radius:16px;background:linear-gradient(120deg,#edf8f8,#f5f1fa);border:1px solid #dbe8ed"><b style="color:#315f6d">{LABELS[lang]} · Bağımsız Vardiya Taslağı</b><br><small>Yalnızca bu dildeki personel ve bu dilin ihtiyacı kullanılır.</small></div>',unsafe_allow_html=True)
    if action.button('Taslağı Oluştur',key='foreign_generate_'+lang,type='primary',use_container_width=True):
        try:
            with st.spinner(LABELS[lang]+' vardiyaları oluşturuluyor…'):result=_build(s,lang,saved)
            plans=dict(s.get('foreign_language_plans') or {});plans[lang]=result;s['foreign_language_plans']=plans;save_keys(s);st.rerun()
        except (ValueError,TypeError,KeyError) as exc:st.error('Dil planı oluşturulamadı: '+str(exc))
    result=(s.get('foreign_language_plans') or {}).get(lang)
    if not result:return
    from ortak.planlama_gorunumu import coverage_summary,roster_summary
    roster_summary(result,LABELS[lang]+' Taslak Özeti');_calendar(result);coverage_summary(result,LABELS[lang]+' İhtiyaç Sonucu')
    people={str(p['employee_id']):p for p in result['staff']};current=(s.get('foreign_language_transferred_ids') or {}).get(lang,[])
    chosen=st.multiselect('Ana plana aktarılacak personeller',list(people),default=[eid for eid in current if eid in people],format_func=lambda eid:people[eid].get('full_name',eid),key='foreign_transfer_people_'+lang)
    a,b=st.columns(2)
    if a.button('Seçili Personelleri Ana Plana Aktar',disabled=not chosen,key='foreign_transfer_selected_'+lang,use_container_width=True):
        _transfer(s,lang,result,chosen);st.success(f'{len(chosen)} personelin {LABELS[lang]} vardiyası ana taslağa aktarıldı ve ana motorun aday havuzundan çıkarıldı.');st.rerun()
    if b.button('Tüm Dil Planını Ana Plana Aktar',key='foreign_transfer_all_'+lang,use_container_width=True):
        _transfer(s,lang,result,list(people));st.success(f'{LABELS[lang]} planının tamamı ana taslağa aktarıldı.');st.rerun()
