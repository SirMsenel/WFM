# Ortak / Calisma Alani Deposu — bu ekranın / servisin uygulama kodu.
"""Local SQLite workbench. Requests use optimistic versions across sessions."""
from contextlib import contextmanager
from datetime import date, datetime
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import os

import numpy as np
import pandas as pd

DEFAULT_DB = Path(os.environ.get("WFM_WORKSPACE_DB_PATH",str(Path(__file__).resolve().parents[1] / "data" / "wfm_demo.db")))
STATE_KEYS = ("planning_exam_hours", "planning_exclude_early_hours", "planning_languages", "group_hour_targets", "acad_schedules", "acad_exam_calendar", "acad_bayram_requests",
              "fixed_shift_records", "shift_overrides", "draft_shift_plan", "published_shift_plan",
              "shift_rules", "plan_group_priority", "cf_forecast_options", "sp_forecast_df", "sp_forecast_meta",
              "sp_ratio_profiles", "sp_active_ratio_profile_df", "sp_active_ratio_profile_name",
              "sp_staffing_result_df", "plan_ctx", "plan_ctx_confirmed", "planning_class_term", "demo_initial_staffing_done",
              "sp_active_ratio_profile_meta", "interval_last_used_profile", "interval_used_profiles", "shift_edit_history", "plan_removed_assignments",
              "demo_initial_profile_done")


def _encode(value):
    if isinstance(value, pd.DataFrame):
        return {"__frame__": value.to_json(orient="table", date_format="iso", index=False)}
    if isinstance(value, (date, datetime)):
        return {"__date__": value.isoformat(), "datetime": isinstance(value, datetime)}
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Cannot persist {type(value)}")


def _decode(value):
    if "__frame__" in value:
        return pd.read_json(io.StringIO(value["__frame__"]), orient="table")
    if "__date__" in value:
        return datetime.fromisoformat(value["__date__"]) if value.get("datetime") else date.fromisoformat(value["__date__"])
    return value


def dumps(value):
    return json.dumps(value, default=_encode, ensure_ascii=False, sort_keys=True, allow_nan=False)


def loads(value):
    return json.loads(value, object_hook=_decode)


@contextmanager
def connect(path=DEFAULT_DB):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=20)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA foreign_keys=ON")
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db(path=DEFAULT_DB):
    with connect(path) as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS calls_daily(tarih TEXT PRIMARY KEY, cagri_sayisi INTEGER NOT NULL CHECK(cagri_sayisi>=0), aht_sec REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS calls_interval(tarih TEXT NOT NULL, slot INTEGER NOT NULL CHECK(slot BETWEEN 1 AND 48), cagri_sayisi INTEGER NOT NULL, aht_sec REAL NOT NULL, PRIMARY KEY(tarih,slot));
        CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY, version INTEGER NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS request_events(id INTEGER PRIMARY KEY, request_id TEXT NOT NULL REFERENCES requests(id), sequence INTEGER NOT NULL, payload TEXT NOT NULL, UNIQUE(request_id,sequence));
        CREATE TABLE IF NOT EXISTS work_state(key TEXT PRIMARY KEY, payload TEXT NOT NULL);
        ''')


def get_requests(path=DEFAULT_DB):
    with connect(path) as con:
        return [loads(r[0]) for r in con.execute("SELECT payload FROM requests ORDER BY id")]


def put_request(row, expected_version=None, path=DEFAULT_DB):
    """Talebi ve olay geçmişini tek işlemde yazar."""
    with connect(path) as con:
        con.execute("BEGIN IMMEDIATE")
        return put_request_in_transaction(con, row, expected_version)


def put_request_in_transaction(con, row, expected_version=None):
    """Vardiya değişimi ile aynı SQLite işlemi içinde de kullanılabilir."""
    row = dict(row)
    existing = con.execute("SELECT version,payload FROM requests WHERE id=?", (row["id"],)).fetchone()
    if expected_version is None:
        if existing:
            raise ValueError("Bu talep zaten kayıtlı.")
        version = 1
    else:
        if not existing or existing["version"] != expected_version:
            raise ValueError("Talep başka bir kullanıcı tarafından değiştirildi. Listeyi yenileyin.")
        old = loads(existing["payload"])
        for field in ("created_by", "created_at", "type", "start_date", "end_date", "note", "attachment", "targets", "generated_ref"):
            if row.get(field) != old.get(field):
                raise ValueError("Gönderilen talep içeriği değiştirilemez; yeni bir kayıt oluşturun.")
        if row.get("events", [])[:len(old.get("events", []))] != old.get("events", []):
            raise ValueError("İşlem geçmişi değiştirilemez.")
        if old.get('resolved_assignments') is not None and row.get('resolved_assignments')!=old.get('resolved_assignments'):
            raise ValueError('Onaylanan vardiya değişiminin saatleri değiştirilemez.')
        version = expected_version+1
    row["version"] = version
    con.execute("INSERT INTO requests VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET version=excluded.version,payload=excluded.payload",
                (row["id"], version, dumps(row)))
    for seq, event in enumerate(row.get("events", [])):
        con.execute("INSERT OR IGNORE INTO request_events(request_id,sequence,payload) VALUES(?,?,?)", (row["id"], seq, dumps(event)))
    return row


def save_keys(state, keys=STATE_KEYS):
    path = state.get("workspace_db_path")
    if not path:
        return
    baseline = dict(state.get("workspace_baseline", {}))
    with connect(path) as con:
        for key in keys:
            if key not in state:
                continue
            payload = dumps(state[key])
            digest = hashlib.sha256(payload.encode()).hexdigest()
            if baseline.get(key) != digest:
                con.execute("INSERT INTO work_state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload", (key,payload))
                baseline[key] = digest
    state["workspace_baseline"] = baseline


def hydrate(state, path=DEFAULT_DB):
    """Call before rendering widgets. Flush local edits, then read shared data."""
    already_loaded = state.get("workspace_hydrated_path") == str(path)
    state["workspace_db_path"] = str(path)
    if already_loaded:
        save_keys(state)
    baseline = dict(state.get("workspace_baseline", {}))
    with connect(path) as con:
        for row in con.execute("SELECT key,payload FROM work_state"):
            key, payload = row["key"], row["payload"]
            if key not in STATE_KEYS:
                continue
            digest=hashlib.sha256(payload.encode()).hexdigest()
            if baseline.get(key)!=digest or key not in state:
                state[key] = loads(payload)
            baseline[key] = digest
    state["workspace_baseline"] = baseline
    state["workspace_hydrated_path"] = str(path)
    state["trk_requests"] = get_requests(path)


def load_calls(interval=False, path=DEFAULT_DB):
    with connect(path) as con:
        if interval:
            df = pd.read_sql_query("SELECT * FROM calls_interval ORDER BY tarih,slot", con)
            df["tarih"] = pd.to_datetime(df["tarih"])+pd.to_timedelta((df["slot"]-1)*30,unit="m")
        else:
            df = pd.read_sql_query("SELECT * FROM calls_daily ORDER BY tarih", con)
            df["tarih"] = pd.to_datetime(df["tarih"])
    return df
