import pandas as pd

WORK_LABELS={'fulltime':'Full Time','akademi':'Akademi','dis_kaynak':'Dış kaynak'}
LANG_LABELS={'tr':'Türkçe','en':'İngilizce','ar':'Arapça'}


def get_people(state,refresh=False):
    if refresh or not state.get('personnel_cache'):
        from core.demo_data import employees
        state['personnel_cache']=[e for e in employees() if e.get('position')!='moderator']
    return [dict(e) for e in state['personnel_cache'] if e.get('is_active',1)]


def planner_people(state):
    # Existing uploaded planning lists are preserved; otherwise use the database.
    if not state.get('employees_cache'):
        state['employees_cache']=[e for e in get_people(state) if e.get('position')=='agent']
    return state['employees_cache']


def personnel_summary(people):
    df=pd.DataFrame(people)
    if df.empty:
        return {'total':0,'location':{},'language':{},'work_type':{}}
    return {'total':len(df),**{field:df[field].fillna('Belirtilmemiş').value_counts().to_dict()
                               for field in ('location','language','work_type')}}
