# Ortak / Planlama — bu ekranın / servisin uygulama kodu.
"""Shared source import, preview, coverage and school-calendar selection."""
from datetime import date
import pandas as pd

LEAVE_LABELS={'YILLIK_IZIN':'Yıllık izin','EVLILIK_IZNI':'Evlilik izni','MAZERET_IZNI':'Mazeret izni',
              'RAPOR':'Rapor','UCRETSIZ_IZIN':'Ücretsiz izin','DOGUM_IZNI':'Doğum izni','BAYRAM':'Bayram izni'}
SHIFT_LABELS={**LEAVE_LABELS,'GECE':'Gece','SINAV':'Sınav','DERS':'Ders','OFF':'OFF','WORK':'Çalışma','MESAI':'Ek mesai'}
REQUEST_CODES={'Yıllık İzin Talebi':'YILLIK_IZIN','Evlilik İzni Talebi':'EVLILIK_IZNI',
               'Mazeret İzni Talebi':'MAZERET_IZNI','Rapor Bildirimi':'RAPOR','Ücretsiz İzin Talebi':'UCRETSIZ_IZIN',
               'Doğum İzni Talebi':'DOGUM_IZNI','Gece Vardiyası Talebi':'GECE','Mesai Talebi':'MESAI','Bayram Talebi':'BAYRAM'}


def school_term(day):
    day=pd.Timestamp(day)
    if day.month==1:
        return f'{day.year-1}-Güz'
    return f"{day.year}-{'Bahar' if day.month<=8 else 'Güz'}"


def preview_plan(state,include_auto=False):
    from modules.vardiya_plani.planlama_verileri import collect_inputs
    from modules.vardiya_plani.vardiya_motoru import generate_plan
    context=state.get('plan_ctx') or {}
    if not context.get('start') or not context.get('end'):
        raise ValueError('Önce plan dönemi seçin.')
    demand=state.get('sp_staffing_result_df')
    if demand is None or demand.empty:
        raise ValueError('Önce personel ihtiyacını hesaplayın.')
    staff,fixed,history,unavailable,issues=collect_inputs(state)
    actual_auto=[]
    if include_auto:
        fixed_keys={(str(r['employee_id']),str(r['date'])) for r in fixed}
        included_ids={str(e['employee_id']) for e in staff}
        actual_auto=[r for r in state.get('draft_shift_plan',[]) if r.get('source')=='auto' and str(r['employee_id']) in included_ids
                     and str(context['start'])<=str(r.get('date'))<=str(context['end'])
                     and (str(r['employee_id']),str(r['date'])) not in fixed_keys]
        fixed=fixed+actual_auto
    result=generate_plan(staff,demand,state['shift_rules'],list(state['shift_rules']['work_type']),
                         context['start'],context['end'],fixed=fixed,history=history,unavailable=unavailable,auto_fill=False,hour_targets=state.get('group_hour_targets',[]),languages=state.get('planning_languages'),exclude_early_hours=state.get('planning_exclude_early_hours',False))
    result['issues']=issues+result['issues']
    start,end=str(context['start']),str(context['end'])
    source_rows=[];names={str(e['employee_id']):e.get('full_name',str(e['employee_id'])) for e in staff}
    actual_keys={(str(r['employee_id']),str(r['date'])) for r in actual_auto}
    for row in result['plan']:
        if row.get('source')!='auto' or (row['employee_id'],row['date']) in actual_keys:
            source_rows.append({**row,'full_name':names[row['employee_id']]})
    exam_keys=set()
    for eid,blocks in unavailable.items():
        for begin,finish in blocks:
            if (finish-begin).total_seconds()==86400 and start<=str(begin.date())<=end:exam_keys.add((eid,str(begin.date())))
    if state.get('planning_exam_hours'):
        users={e.get('username'):str(e['employee_id']) for e in staff}
        for user,terms in state.get('acad_exam_calendar',{}).items():
            if user not in users:continue
            for records in terms.values():
                for day in pd.to_datetime(pd.DataFrame(records).get('Tarih',pd.Series(dtype=str)),errors='coerce').dropna():
                    if start<=str(day.date())<=end:exam_keys.add((users[user],str(day.date())))
    result['exam_hours']=state.get('planning_exam_hours',False)
    result.update(source_rows=source_rows,exam_keys=exam_keys,staff=staff,unavailable=unavailable)
    from ortak.statuler import meal_plan
    meals,coverage,meal_issues=meal_plan(state,result['plan'],result['coverage'],staff)
    result['breaks']=meals;result['coverage']=coverage;result['issues']+=meal_issues
    return result


def calendar_grid(result,context):
    days=pd.date_range(context['start'],context['end'])
    values={(r['employee_id'],r['date']):r for r in result['source_rows']}
    output=[]
    for emp in result['staff']:
        eid=str(emp['employee_id']);row={'Personel':emp.get('full_name',eid)}
        for d in days:
            key=(eid,str(d.date()));record=values.get(key)
            if key in result['exam_keys']:
                label='Sınav'
                if record and record.get('shift_code') in LEAVE_LABELS:
                    label+=' / '+LEAVE_LABELS[record['shift_code']]
                elif record and record.get('shift_code') not in {'OFF','SINAV'}:
                    label=(f"{record.get('start')}–{record.get('end')} · Sınav" if result.get('exam_hours') else label+' ⚠')
            elif record:
                code=record.get('shift_code')
                label=SHIFT_LABELS.get(code,code)
                if record.get('start') and record.get('end'):
                    label=f"{'Gece ' if code=='GECE' else ''}{record['start']}–{record['end']}"
            else:
                label='—'
            from ortak.cagri_tahmin_servisi import DAY_NAMES
            row[d.strftime('%d.%m')+' '+DAY_NAMES[d.weekday()]]=label
        output.append(row)
    return pd.DataFrame(output)


def shortage_summary(coverage):
    missing=coverage[coverage['Eksik']>0].copy()
    if missing.empty:
        return missing,pd.DataFrame(columns=['Tarih','Eksik personel-saat','En yüksek eksik','Eksik dilim'])
    daily=missing.groupby('Tarih',as_index=False).agg(**{'Eksik personel-saat':('Eksik',lambda s:float(s.sum()/2)),
                                                       'En yüksek eksik':('Eksik','max'),'Eksik dilim':('Eksik','size')})
    return missing,daily
