# Ortak / Personel — bu ekranın / servisin uygulama kodu.
import os
import time
import pandas as pd

WORK_LABELS={'fulltime':'Full Time','akademi':'Akademi','dis_kaynak':'Dış kaynak'}
LANG_LABELS={'tr':'Türkçe','en':'İngilizce','ar':'Arapça'}


def get_people(state,refresh=False):
    if os.environ.get("WFM_PERSONNEL_API_URL") and time.monotonic()-state.get("_directory_checked",0)>300:refresh=True
    if state.get('workspace_db_path'):
        from ortak.calisma_alani_deposu import connect
        with connect(state['workspace_db_path']) as db:
            row=db.execute("SELECT value FROM metadata WHERE key='directory_revision'").fetchone()
        from datetime import datetime
        from zoneinfo import ZoneInfo
        revision=(row[0] if row else 'initial')+'|'+datetime.now(ZoneInfo('Europe/Istanbul')).date().isoformat()
        if state.get('_directory_revision')!=revision:
            refresh=True;state.pop('employees_cache',None);state['_directory_revision']=revision
    if refresh or not state.get('personnel_cache'):
        state.pop('employees_cache',None)
        from ortak.personel_deposu import list_people
        state['personnel_cache']=[e for e in list_people(state) if e.get('position')!='moderator']
        state['_directory_checked']=time.monotonic()
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


def visible_people(profile,people):
    role=profile.get('position');agents=[dict(e) for e in people if e.get('position','agent')=='agent']
    if role in {'wfm','manager','moderator','planning_manager'}:return agents
    if role=='tl':return [e for e in agents if str(e.get('team_lead','')).strip().casefold()==str(profile.get('full_name','')).strip().casefold()]
    return [e for e in agents if str(e.get('employee_id'))==str(profile.get('employee_id')) or e.get('username')==profile.get('username')]
