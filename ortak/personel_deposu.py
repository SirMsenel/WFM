# Ortak / Personel Deposu — bu ekranın / servisin uygulama kodu.
"""Personel Deposu — kimlik veritabanı adaptörü ve sicil eşleştirmesi."""
import os,sqlite3
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

DEFAULT_AUTH=Path(__file__).resolve().parents[1]/'data'/'auth_demo.db'


def auth_path(state=None):return str((state or {}).get('auth_db_path') or os.environ.get('WFM_AUTH_DB_PATH') or DEFAULT_AUTH)


def ensure_identity(path):
    with sqlite3.connect(path) as db:
        cols={r[1] for r in db.execute('PRAGMA table_info(employees)')}
        for name in ('sicil_no','employment_start','employment_end','company'):
            if name not in cols:db.execute('ALTER TABLE employees ADD COLUMN '+name+' TEXT')
        db.execute("UPDATE employees SET sicil_no=CAST(employee_id AS TEXT) WHERE sicil_no IS NULL OR trim(sicil_no)=''")
        db.execute('CREATE UNIQUE INDEX IF NOT EXISTS employees_sicil_unique ON employees(sicil_no)')


def list_people(state=None,include_inactive=False):
    if os.environ.get('WFM_PERSONNEL_API_URL'):
        from ortak.kurumsal_baglanti import KurumsalPersonelSaglayici
        result=KurumsalPersonelSaglayici().list_people()
        today=datetime.now(ZoneInfo('Europe/Istanbul')).date().isoformat()
        for r in result:
            if r.get('employment_end') and r['employment_end']<=today:r['is_active']=False
        return result if include_inactive else [r for r in result if r.get('is_active',True)]
    path=auth_path(state);ensure_identity(path)
    with sqlite3.connect(path) as db:
        db.row_factory=sqlite3.Row
        rows=[dict(r) for r in db.execute('SELECT e.*,u.username,u.is_active FROM employees e JOIN users u ON e.employee_id=u.employee_id ORDER BY e.employee_id')]
    today=datetime.now(ZoneInfo('Europe/Istanbul')).date().isoformat()
    for r in rows:
        if r.get('employment_end') and r['employment_end']<=today:r['is_active']=0
        r['registry_no']=r.get('sicil_no') or str(r['employee_id'])
    return rows if include_inactive else [r for r in rows if r['is_active']]
