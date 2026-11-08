from copy import deepcopy
import pandas as pd
from core.planning import LEAVE_LABELS
from modules.shift_planing.planning_data import collect_inputs
from modules.shift_planing.engine import generate_plan


def prepare_manual(state,employee_ids,start,end,kind,begin=None,finish=None,note=''):
    from core.planning_guard import assert_can_plan
    assert_can_plan(state)
    if pd.Timestamp(start)>pd.Timestamp(end) or pd.Timestamp(start)<pd.Timestamp(state['plan_ctx']['start']) or pd.Timestamp(end)>pd.Timestamp(state['plan_ctx']['end']):
        raise ValueError('Elle giriş seçili plan dönemi içinde olmalı.')
    staff,fixed,history,unavailable,source_issues=collect_inputs(state)
    people={str(e['employee_id']):e for e in staff}
    rows={}
    for r in [*state.get('published_shift_plan',[]),*state.get('draft_shift_plan',[]),*fixed]:
        if str(r['employee_id']) not in people:continue
        if r.get('source')=='auto' and r.get('shift_code')=='OFF':continue
        rows[(str(r['employee_id']),str(r['date']))]=deepcopy(r)
    warnings=[];candidates=[]
    for eid in dict.fromkeys(map(str,employee_ids)):
        if eid not in people:raise ValueError('Seçili personel planlama listesinde bulunamadı.')
        person=people[eid];rule=state['shift_rules']['work_type'][person['work_type']]
        for day in pd.date_range(start,end):
            key=(eid,str(day.date()))
            if key in rows:
                old=rows[key];label=(f"{old['start']}–{old['end']}" if old.get('start') and old.get('end') else old.get('shift_code','Kayıt'))
                warnings.append({'Personel':person['full_name'],'Personel No':eid,'Tarih':key[1],'Vardiya':label,'Neden yazılmadı?':'Bu gün zaten dolu; mevcut kayıt korundu.'});continue
            a,b=None,None
            if kind in {'WORK','GECE','MESAI'}:
                if begin is None:raise ValueError('Başlangıç saati gerekli.')
                a=begin.strftime('%H:%M') if hasattr(begin,'strftime') else str(begin)
                if finish is not None:b=finish.strftime('%H:%M') if hasattr(finish,'strftime') else str(finish)
                elif kind=='GECE':b=state['shift_rules']['general']['night_window_end']
                else:
                    minute=int(a[:2])*60+int(a[3:])+int(60*float(rule.get('shift_total_hours',rule.get('shift_total_hours_max',7))))
                    b=f'{minute//60%24:02d}:{minute%60:02d}'
            candidates.append({'employee_id':eid,'date':key[1],'shift_code':kind,'start':a,'end':b,'source':'manual_candidate','note':note})
    if not candidates:return [],warnings
    result=generate_plan(staff,state['sp_staffing_result_df'],state['shift_rules'],list(state['shift_rules']['work_type']),
                         state['plan_ctx']['start'],state['plan_ctx']['end'],fixed=list(rows.values())+candidates,
                         history=history,unavailable=unavailable,auto_fill=False,hour_targets=state.get('group_hour_targets',[]),
                         languages=state.get('planning_languages'),exclude_early_hours=state.get('planning_exclude_early_hours',False),reject_invalid_sources=('manual_candidate',))
    for issue in result['issues']:
        if issue.get('source')=='manual_candidate':
            eid=issue['employee_id'];warnings.append({'Personel':people[eid]['full_name'],'Personel No':eid,'Tarih':issue['date'],'Vardiya':f"{issue.get('start') or '—'}–{issue.get('end') or '—'}",'Neden yazılmadı?':issue['Sorun']})
    additions=[dict(r,source='manual_single') for r in result['plan'] if r.get('source')=='manual_candidate']
    return additions,warnings
