from datetime import datetime
from core.workspace_store import save_keys
from core.planning_ui import blocking_issues
from modules.shift_planing.planning_data import fingerprint


def publish_plan(state,result):
    if state.get('planning_result_fingerprint')!=fingerprint(state):raise ValueError('Taslak güncel değil. Yeniden oluşturun.')
    if blocking_issues(result):raise ValueError('Kayıt veya çalışma kuralı ihlallerini düzeltin; eksik ihtiyacın kabulü bu ihlalleri kaldırmaz.')
    start,end=result['period']['start'],result['period']['end']
    included={str(e['employee_id']) for e in result['staff']}
    previous=state.get('published_shift_plan',[])
    state['published_shift_plan']=[r for r in previous if not start<=str(r.get('date'))<=end or str(r['employee_id']) not in included]+[dict(r) for r in result['plan']]
    try:save_keys(state)
    except Exception:
        state['published_shift_plan']=previous;raise
    state['planning_result_fingerprint']=fingerprint(state)
    state['last_publication']={'start':start,'end':end,'count':len(result['plan']),'at':datetime.now().isoformat(),'fingerprint':state['planning_result_fingerprint']}
