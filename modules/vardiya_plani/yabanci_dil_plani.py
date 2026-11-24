"""Yabancı dil ihtiyacını ve vardiya taslağını ana plandan bağımsız yönetir."""
from copy import deepcopy
from itertools import permutations,islice
import pandas as pd
import streamlit as st

from ortak.calisma_alani_deposu import save_keys


LABELS={'en':'İngilizce','ar':'Arapça'}


def _foreign_demand(frame):
    """Yabancı dil motoru yalnızca doğrudan girilen kişi ihtiyacını kullanır."""
    result=frame[['Tarih','Slot','Planlanan Agent']].copy()
    result['Tarih']=pd.to_datetime(result['Tarih']).dt.normalize()
    result['Slot']=pd.to_numeric(result['Slot'],errors='raise').astype(int)
    result['Planlanan Agent']=pd.to_numeric(result['Planlanan Agent'],errors='raise').fillna(0).clip(lower=0)
    return result


def _calendar(state, result, lang, demand):
    from ortak.planlama import calendar_grid
    from ortak.vardiya_gorunumu import cell_style
    grid=calendar_grid({**result,'source_rows':result['plan'],'exam_keys':set()},result['period'])
    styled = grid.style.map(cell_style, subset=list(grid.columns[1:]))
    form_key = 'foreign_shift_' + lang
    with st.form(form_key):
        edited = st.data_editor(styled, disabled=['Personel'], hide_index=True, use_container_width=True,
                                height=470, key=form_key + str(state.get(form_key+'_revision', 0)))
        save = st.form_submit_button('Vardiya düzeltmelerini kaydet')
    if save:
        from ortak.yayin_hucre_duzenleyici import changes_from_grid
        try:
            changes = changes_from_grid(grid, edited, result['staff'], dict(result['period'], rows=result['plan']))
            if not changes:
                st.info('Takvimde değişen hücre yok.')
                return
            revised = {(str(row['employee_id']), row['date']):row for row in result['plan']}
            for change in changes:
                key = (change['employee_id'], change['date'])
                if revised[key]['source'] not in {'auto','auto_night','foreign_manual'}:
                    raise ValueError('Kesin kayıtlar kendi kaynağından düzenlenir.')
                if change['shift_code']=='MESAI':
                    change['shift_code']='WORK'
                if change['shift_code']=='WORK' and not change['start']:
                    raise ValueError('Çalışma için başlangıç ve bitiş saatini girin.')
                revised[key] = {**revised[key], **change, 'source':'foreign_manual'}
            updated = _build(state, lang, demand, list(revised.values()))
            state['foreign_language_plans'] = {**state['foreign_language_plans'], lang:updated}
            state[form_key+'_revision'] = state.get(form_key+'_revision', 0)+1
            save_keys(state)
            st.rerun()
        except (ValueError,KeyError,TypeError) as exc:
            st.error(str(exc))


def _interval_result(result,lang):
    """Bağımsız dil planının günlük halkalarını ve 7x48 sonucunu gösterir."""
    coverage=result.get('coverage',pd.DataFrame()).copy()
    if coverage.empty:return
    from ortak.planlama_gorunumu import daily_coverage_summary,coverage_comparison_matrix,styled_coverage_comparison
    daily_coverage_summary(result,LABELS[lang]+' · Günlük İhtiyaç Karşılama')
    st.markdown('### '+LABELS[lang]+' · 30 Dakikalık Plan Sonucu')
    start=pd.Timestamp(result.get('period',{}).get('start') or pd.to_datetime(coverage['Tarih']).min()).normalize()
    end=pd.Timestamp(result.get('period',{}).get('end') or pd.to_datetime(coverage['Tarih']).max()).normalize()
    weeks=list(pd.date_range(start,end,freq='7D')) or [start]
    chosen=st.selectbox('İncelenecek hafta',weeks,format_func=lambda day:f'{day:%d.%m.%Y} – {min(day+pd.Timedelta(days=6),end):%d.%m.%Y}',key='foreign_result_week_'+lang) if len(weeks)>1 else weeks[0]
    st.caption('Hücre biçimi: vardiyaya yazılan/planlanan · fark. Kırmızı eksik, yeşil fazla, gri tam karşılanan dilimdir; — ihtiyaç sayacına dahil değildir.')
    matrix=coverage_comparison_matrix(coverage,chosen)
    st.dataframe(styled_coverage_comparison(matrix),use_container_width=True,height=540)


def _build(state,lang,demand,edited_rows=None):
    from modules.vardiya_plani.planlama_verileri import collect_inputs
    from modules.vardiya_plani.vardiya_motoru import generate_plan
    check=dict(state);check['planning_languages']={'tr':False,'en':lang=='en','ar':lang=='ar'}
    # Ana plana aktarılmış başka dil personeli, bağımsız dil motorunda aday
    # istisnası oluşturamaz. Her dil yalnızca kendi personel havuzundan kurulur.
    check['foreign_language_transferred_ids']={};check['foreign_language_reserved_ids']={}
    # Bağımsız dil planı ana taslaktaki otomatik/elle vardiyalardan etkilenmez.
    # İzin, gece, talep ve okul kayıtları kendi kaynaklarından yine korunur.
    check['draft_shift_plan']=[]
    from ortak.donem_kilitleri import assert_can_plan
    assert_can_plan(check)
    staff,fixed,history,unavailable,issues=collect_inputs(check)
    demand=_foreign_demand(demand)
    order=[g for g in state.get('plan_group_priority',[]) if g in state['shift_rules']['work_type']]
    if set(order)!=set(state['shift_rules']['work_type']):order=list(state['shift_rules']['work_type'])
    ctx=state['plan_ctx']
    # Her dil taslağı yabancı dil için kaydedilen toleransı kullanır.
    scoped_rules=deepcopy(state['shift_rules'])
    capacity=scoped_rules.setdefault('capacity',{})
    capacity['max_overstaff']=int(capacity.get('foreign_max_overstaff',0))
    scoped_rules.setdefault('boosts',{})['weekday_0700_fulltime_extra_enabled']=False
    # Bir grubun geç saatleri önce doldurması, sonraki grubun uzun vardiyasını
    # tamamen reddedip gün başında yapay açık bırakabiliyordu. En fazla altı
    # grup sırası denenir ve gerçek yarım saat açığı en düşük taslak seçilir.
    base_order=tuple(order)
    alternatives=(candidate for candidate in permutations(order) if candidate!=base_order)
    orders=[base_order]+list(islice(alternatives,5))
    if edited_rows is not None:
        fixed_keys = {(str(row['employee_id']),str(row['date'])) for row in fixed}
        for row in edited_rows:
            if row.get('source')=='auto' and row['shift_code']=='OFF':
                continue
            if (str(row['employee_id']),str(row['date'])) in fixed_keys:
                if row.get('source')=='foreign_manual':
                    raise ValueError('Bu hücrede kesin kayıt var.')
            else:
                fixed.append(row)
        orders=[base_order]
    result=None;best_score=None
    for candidate_order in orders:
        candidate=generate_plan(staff,demand,scoped_rules,list(candidate_order),ctx['start'],ctx['end'],fixed=fixed,history=history,unavailable=unavailable,auto_fill=edited_rows is None,strict_capacity=True,hour_targets=state.get('group_hour_targets',[]),languages=check['planning_languages'],exclude_early_hours=state.get('planning_exclude_early_hours',False),auto_night=False)
        counted=candidate['coverage'][candidate['coverage']['Sayaca Dahil']] if 'Sayaca Dahil' in candidate['coverage'] else candidate['coverage']
        hard=sum(row.get('severity')!='warning' for row in candidate.get('issues',[]))
        score=(float(counted['Eksik'].sum()),int((counted['Eksik']>0).sum()),hard,float(counted['Fazla'].sum()))
        if best_score is None or score<best_score:result,best_score=candidate,score
        if score[:2]==(0.,0):break
    from ortak.statuler import meal_plan
    status_state=dict(state);status_state['slot_shrinkage']=[];status_state['staffing_parameters']={'shrinkage':0};status_state['sp_staffing_result_df']=demand
    status_state['status_rules']=deepcopy(state.get('status_rules') or {});status_state['status_rules']['shrinkage_included']=False
    statuses,coverage,status_issues=meal_plan(status_state,result['plan'],result['coverage'],staff)
    # Yabancı dilde yemek/mola hakları planlanır ancak bu statüler için
    # shrinkage hesabı yapılmaz; eksik/fazla vardiyaya yazılan kişiyle ölçülür.
    assigned=pd.to_numeric(coverage.get('Brüt Atanan',coverage['Atanan']),errors='coerce').fillna(0)
    need=pd.to_numeric(coverage['İhtiyaç'],errors='coerce').fillna(0)
    coverage['Atanan']=assigned;coverage['Ham Eksik']=(need-assigned).clip(lower=0)
    coverage['Eksik']=coverage['Ham Eksik'];coverage['Fazla']=(assigned-need).clip(lower=0)
    if 'Sayaca Dahil' in coverage:coverage.loc[~coverage['Sayaca Dahil'],['Eksik','Fazla']]=0
    coverage=coverage.drop(columns=['Mola kaybı','Shrinkage statü bütçesi','Operasyon rezervi'],errors='ignore')
    result['breaks']=statuses;result['coverage']=coverage
    result['issues']=issues+result['issues']+status_issues;result['staff']=staff;result['period']={'start':str(ctx['start']),'end':str(ctx['end'])}
    return result


def _transfer(state,lang,result,ids):
    plan_ids={str(person['employee_id']) for person in result.get('staff',[])}
    ids={str(eid) for eid in ids}&plan_ids;start,end=result['period']['start'],result['period']['end']
    # Türkçe motora vardiya/statü kopyalanmaz. Yalnızca seçilen kişilerin dil
    # planındaki 30 dakikalık kapasitesi ihtiyaç hesabından sayısal olarak düşer.
    state['draft_shift_plan']=[r for r in state.get('draft_shift_plan',[]) if not (r.get('source')=='foreign_language_plan' and r.get('language')==lang and start<=str(r.get('date'))<=end)]
    transferred=dict(state.get('foreign_language_transferred_ids') or {});transferred[lang]=sorted(ids);state['foreign_language_transferred_ids']=transferred
    # Dil taslağındaki bütün personel ana motorun otomatik aday havuzundan
    # korunur. Yalnızca seçilen alt kümenin sayısal kapasitesi hesaba katılır.
    reserved=dict(state.get('foreign_language_reserved_ids') or {});reserved[lang]=sorted(plan_ids);state['foreign_language_reserved_ids']=reserved
    inclusion=dict(state.get('language_demand_inclusion') or {});inclusion[lang]=False;state['language_demand_inclusion']=inclusion
    for key in ('planning_result','planning_result_fingerprint','_status_plan_cache'):state.pop(key,None)
    save_keys(state)


def render():
    s=st.session_state;st.subheader('Yabancı Dil Vardiya Planlaması')
    lang=st.segmented_control('Planlanacak dil',['en','ar'],default='en',format_func=LABELS.get,key='foreign_plan_language') or 'en'
    ctx=s.get('plan_ctx') or {}
    if not s.get('plan_ctx_confirmed') or not ctx.get('start') or not ctx.get('end'):st.info('Önce Plan Dönem Seçimi ekranında dönemi onaylayın.');return
    from ortak.donem_kilitleri import render_guard
    from ortak.personel import planner_people
    planner_people(s)
    if not render_guard(s,{'tr':False,'en':lang=='en','ar':lang=='ar'},requests_only=True):return
    source=s.get('sp_staffing_result_df')
    if source is None:st.info('Önce Personel Hesap ekranında ihtiyaç hesaplayın.');return
    saved=s.setdefault('language_demands',{}).get(lang);base=_foreign_demand(source if saved is None else saved)
    with st.expander('Bu dilin yarım saatlik personel ihtiyacını tanımla'):
        table=base[['Tarih','Slot','Planlanan Agent']].copy();from ortak.saat_etiketleri import slot_label
        from ortak.cagri_tahmin_servisi import DAY_NAMES
        table['Tarih']=pd.to_datetime(table['Tarih']).dt.normalize();dates=sorted(table['Tarih'].unique());labels={pd.Timestamp(d).strftime('%d.%m')+' '+DAY_NAMES[pd.Timestamp(d).weekday()]:pd.Timestamp(d) for d in dates}
        wide=table.pivot(index='Slot',columns='Tarih',values='Planlanan Agent').reindex(range(1,49));wide.columns=[next(label for label,value in labels.items() if value==pd.Timestamp(d)) for d in wide.columns];wide.insert(0,'Yarım saat',[slot_label(slot) for slot in wide.index]);wide=wide.reset_index(drop=True)
        st.markdown('<div style="padding:12px 15px;border-radius:14px;background:#eef7f9;border:1px solid #d8e8ed"><b>30 Dakikalık Dil İhtiyacı</b><br><small>Her yarım saat için doğrudan planlanacak kişi sayısını gir. Yabancı dil planında shrinkage veya Erlang C uygulanmaz.</small></div>',unsafe_allow_html=True)
        config={'Yarım saat':st.column_config.TextColumn('Yarım saat',width='small')};config.update({label:st.column_config.NumberColumn(label,min_value=0,step=1,required=True,width='small') for label in labels})
        edited=st.data_editor(wide,disabled=['Yarım saat'],hide_index=True,use_container_width=True,height=640,key='foreign_need_'+lang,column_config=config)
        if st.button('Dil İhtiyacını Kaydet',key='foreign_save_need'):
            values=edited.drop(columns=['Yarım saat']).apply(pd.to_numeric,errors='coerce')
            if values.isna().any().any() or (values<0).any().any():st.warning('İhtiyaç hücreleri boş veya negatif olamaz.')
            else:
                lookup={(str(day.date()),slot):float(values.iloc[slot-1][label]) for label,day in labels.items() for slot in range(1,49)}
                base['Planlanan Agent']=[lookup[(str(pd.Timestamp(day).date()),int(slot))] for day,slot in zip(base['Tarih'],base['Slot'])]
                source_map=dict(s['language_demands']);source_map[lang]=_foreign_demand(base);s['language_demands']=source_map;save_keys(s);st.rerun()
    saved=s.get('language_demands',{}).get(lang)
    if saved is None:st.info('Bağımsız vardiya taslağı oluşturmak için önce bu dilin ihtiyacını kaydedin.');return
    header,action=st.columns([4,1.25],vertical_alignment='center')
    header.markdown(f'<div style="padding:15px 17px;border-radius:16px;background:linear-gradient(120deg,#edf8f8,#f5f1fa);border:1px solid #dbe8ed"><b style="color:#315f6d">{LABELS[lang]} · Bağımsız Vardiya Taslağı</b><br><small>Yalnızca bu dildeki personel ve bu dilin ihtiyacı kullanılır.</small></div>',unsafe_allow_html=True)
    if action.button('Otomatik Vardiya Yaz',key='foreign_generate_'+lang,type='primary',use_container_width=True):
        try:
            with st.spinner(LABELS[lang]+' vardiyaları oluşturuluyor…'):result=_build(s,lang,saved)
            revision_key='foreign_shift_'+lang+'_revision'
            s[revision_key]=s.get(revision_key,0)+1
            plans=dict(s.get('foreign_language_plans') or {});plans[lang]=result;s['foreign_language_plans']=plans;save_keys(s);st.rerun()
        except (ValueError,TypeError,KeyError) as exc:st.error('Dil planı oluşturulamadı: '+str(exc))
    result=(s.get('foreign_language_plans') or {}).get(lang)
    if not result:return
    if result.get('period') != {'start':str(ctx['start']),'end':str(ctx['end'])}:
        st.info('Seçili dönem için bu dilin vardiya taslağını oluşturun.')
        return
    from ortak.planlama_gorunumu import coverage_summary,roster_summary,blocking_issues,render_issues
    roster_summary(result,LABELS[lang]+' Taslak Özeti');_calendar(s,result,lang,saved);coverage_summary(result,LABELS[lang]+' İhtiyaç Sonucu');_interval_result(result,lang)
    hard=blocking_issues(result)
    if result.get('issues'):
        with st.expander('Kural kontrolleri',expanded=bool(hard)):render_issues(result)
    accepted=True
    soft_required = any(issue.get('severity')=='warning' and issue.get('override_required',True) for issue in result.get('issues',[]))
    soft_accepted = not soft_required or st.checkbox('Esnek kural uyarılarını inceledim ve onaylıyorum',key='foreign_accept_soft_'+lang)
    if hard:accepted=st.checkbox('Kesin kural uyarılarını gördüm; bu dil planını Planlama onayıyla göndermek istiyorum',key='foreign_accept_hard_'+lang)
    people={str(p['employee_id']):p for p in result['staff']};current=(s.get('foreign_language_transferred_ids') or {}).get(lang,[])
    chosen=st.multiselect('Türkçe ihtiyacından düşülecek personeller',list(people),default=[eid for eid in current if eid in people],format_func=lambda eid:people[eid].get('full_name',eid),key='foreign_transfer_people_'+lang)
    st.caption('Dil planındaki personeller korunur ve ana motor vardiyalarını değiştiremez. Yalnızca burada seçtiklerinin vardiya kapasitesi ana plandaki Türkçe ihtiyacından düşülür.')
    notice = s.pop('foreign_transfer_notice_'+lang, None)
    if notice:
        st.success(notice)
    a,b=st.columns(2)
    if a.button('Seçili Kapasiteyi Ana Plana Aktar',disabled=not chosen,key='foreign_transfer_selected_'+lang,use_container_width=True):
        _transfer(s,lang,result,chosen);s['foreign_transfer_notice_'+lang]=(f'{len(chosen)} personelin 30 dakikalık kapasitesi Türkçe ihtiyacından düşülecek; vardiya ve statüleri bağımsız kalacak.');st.rerun()
    if b.button('Tüm Dil Kapasitesini Ana Plana Aktar',key='foreign_transfer_all_'+lang,use_container_width=True):
        _transfer(s,lang,result,list(people));s['foreign_transfer_notice_'+lang]=(f'{LABELS[lang]} planının 30 dakikalık kişi kapasitesi Türkçe ihtiyacına işlendi.');st.rerun()
    st.markdown('#### Bağımsız Dil Planı Yayını')
    st.caption('Bu seçenek planı ana Türkçe motoruna yeniden hesaplatmadan yalnızca seçili dil için onaylar/yayınlar.')
    approvals=s.get('shift_rules',{}).get('publication_approvals',{}).get('enabled')
    label='Dil Planını Yayın Onayına Gönder' if approvals else 'Dil Planını Doğrudan Yayınla'
    if st.button(label,key='foreign_publish_'+lang,type='primary',use_container_width=True,disabled=not (accepted and soft_accepted)):
        scope={'tr':False,'en':lang=='en','ar':lang=='ar'}
        try:
            if approvals:
                from ortak.yayin_onaylari import submit
                approval_state=dict(s);approval_state.update(planning_accept_hard=accepted,planning_accept_soft=soft_accepted)
                ident=submit(approval_state,result,planning_languages=scope);s['workspace_baseline']=approval_state.get('workspace_baseline',s.get('workspace_baseline',{}));st.success('Bağımsız dil planı onaya gönderildi: '+ident)
            else:
                from modules.vardiya_plani.planlama_verileri import fingerprint
                from ortak.yayin_servisi import publish_plan
                original=deepcopy(s.get('planning_languages'));check=dict(s);check['planning_languages']=scope;check.update(planning_accept_hard=accepted,planning_accept_soft=soft_accepted);check['planning_result_fingerprint']=fingerprint(check)
                publish_plan(check,result)
                for key in ('published_shift_plan','last_publication','trk_requests','workspace_baseline'):
                    if key in check:s[key]=check[key]
                s['planning_languages']=original;save_keys(s);st.success(LABELS[lang]+' planı bağımsız olarak yayınlandı.')
        except (ValueError,OSError) as exc:st.error(str(exc))
