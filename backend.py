# backend.py
import uuid
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

app = FastAPI(title="WFM Backend - Step1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ACTIVE_DATASET_PATH: Path | None = None


@app.get("/")
def root():
    return {"service": "wfm-backend", "ok": True}


@app.get("/health")
def health():
    return {"ok": True}


def _read_any(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in [".xlsx", ".xls"]:
        return pd.read_excel(path)
    raise ValueError("Unsupported file type")


@app.post("/data/upload")
async def upload_data(file: UploadFile = File(...)):
    global ACTIVE_DATASET_PATH

    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in [".csv", ".xlsx", ".xls"]:
        raise HTTPException(status_code=400, detail="Sadece CSV veya Excel kabul ediyorum.")

    safe_name = f"{uuid.uuid4().hex}{suffix}"
    dst = DATA_DIR / safe_name

    content = await file.read()
    dst.write_bytes(content)

    try:
        df = _read_any(dst)
    except Exception as e:
        dst.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Dosya okunamadı: {e}")

    ACTIVE_DATASET_PATH = dst
    return {
        "dataset_id": safe_name,
        "rows": int(df.shape[0]),
        "cols": int(df.shape[1]),
        "columns": df.columns.tolist(),
    }


@app.get("/data/preview")
def preview(n: int = 50):
    if ACTIVE_DATASET_PATH is None or not ACTIVE_DATASET_PATH.exists():
        raise HTTPException(status_code=404, detail="Aktif dataset yok. Önce upload yap.")

    df = _read_any(ACTIVE_DATASET_PATH)
    head = df.head(n)
    return {
        "path": ACTIVE_DATASET_PATH.name,
        "rows": int(df.shape[0]),
        "cols": int(df.shape[1]),
        "columns": df.columns.tolist(),
        "preview": head.to_dict(orient="records"),
    }


@app.get("/data/all")
def get_all():
    if ACTIVE_DATASET_PATH is None or not ACTIVE_DATASET_PATH.exists():
        raise HTTPException(status_code=404, detail="Aktif dataset yok. Önce upload yap.")

    df = _read_any(ACTIVE_DATASET_PATH)

    return {
        "path": ACTIVE_DATASET_PATH.name,
        "rows": int(df.shape[0]),
        "cols": int(df.shape[1]),
        "columns": df.columns.tolist(),
        "data": df.to_dict(orient="records"),
    }


@app.get("/data/query")
def query_data(
    search: str | None = None,
    limit: int = Query(100, ge=1, le=10000),
    offset: int = Query(0, ge=0),
):
    if ACTIVE_DATASET_PATH is None or not ACTIVE_DATASET_PATH.exists():
        raise HTTPException(status_code=404, detail="Aktif dataset yok. Önce upload yap.")

    df = _read_any(ACTIVE_DATASET_PATH)

    if search:
        s = str(search).lower()
        mask = df.astype(str).apply(lambda col: col.str.lower().str.contains(s, na=False))
        df = df[mask.any(axis=1)]

    total = int(df.shape[0])
    page = df.iloc[offset : offset + limit]

    return {
        "path": ACTIVE_DATASET_PATH.name,
        "total_rows": total,
        "offset": offset,
        "limit": limit,
        "columns": df.columns.tolist(),
        "rows": page.to_dict(orient="records"),
    }

@app.get("/employees/summary")
def employees_summary():
    """
    Aktif kullanıcıya sahip (users.is_active=1) çalışanların özetini döner.
    Moderator hariçtir.
    """
    with _conn() as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        # Toplam aktif (moderator hariç)
        cur.execute("""
            SELECT COUNT(*) AS c
            FROM employees e
            JOIN users u ON u.employee_id = e.employee_id
            WHERE u.is_active=1
              AND lower(e.position) != 'moderator'
        """)
        total = int(cur.fetchone()["c"])

        # Lokasyon kırılım
        cur.execute("""
            SELECT e.location AS k, COUNT(*) AS c
            FROM employees e
            JOIN users u ON u.employee_id = e.employee_id
            WHERE u.is_active=1
              AND lower(e.position) != 'moderator'
            GROUP BY e.location
            ORDER BY c DESC
        """)
        by_location = [{"key": r["k"], "count": int(r["c"])} for r in cur.fetchall()]

        # Dil kırılım
        cur.execute("""
            SELECT e.language AS k, COUNT(*) AS c
            FROM employees e
            JOIN users u ON u.employee_id = e.employee_id
            WHERE u.is_active=1
              AND lower(e.position) != 'moderator'
            GROUP BY e.language
            ORDER BY c DESC
        """)
        by_language = [{"key": r["k"], "count": int(r["c"])} for r in cur.fetchall()]

        # Çalışma biçimi kırılım
        cur.execute("""
            SELECT e.work_type AS k, COUNT(*) AS c
            FROM employees e
            JOIN users u ON u.employee_id = e.employee_id
            WHERE u.is_active=1
              AND lower(e.position) != 'moderator'
            GROUP BY e.work_type
            ORDER BY c DESC
        """)
        by_work_type = [{"key": r["k"], "count": int(r["c"])} for r in cur.fetchall()]

    return {
        "total_active": total,
        "by_location": by_location,
        "by_language": by_language,
        "by_work_type": by_work_type,
    }

@app.get("/employees/query")
def employees_query(
    search: str | None = None,
    position: str | None = None,
    location: str | None = None,
    work_type: str | None = None,
    language: str | None = None,
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    """
    Employees tablosunu listeler (sayfalı + filtreli).
    Not: Şimdilik demo olduğu için auth zorunlu yapmadım.
    İstersen sonra Depends(_auth_required) ile kilitleriz.
    """
    where = []
    params = []

    if search:
        s = f"%{search.strip().lower()}%"
        where.append("(lower(full_name) LIKE ? OR lower(team_lead) LIKE ? OR lower(manager) LIKE ?)")
        params.extend([s, s, s])

    if position:
        where.append("lower(position) = ?")
        params.append(position.strip().lower())

    if location:
        where.append("lower(location) = ?")
        params.append(location.strip().lower())

    if work_type:
        where.append("lower(work_type) = ?")
        params.append(work_type.strip().lower())

    if language:
        where.append("lower(language) = ?")
        params.append(language.strip().lower())

    # moderator hariç (her durumda)
    base_condition = "lower(position) != 'moderator'"

    if where:
        where_sql = " WHERE " + base_condition + " AND " + " AND ".join(where)
    else:
        where_sql = " WHERE " + base_condition

    with _conn() as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        cur.execute(f"SELECT COUNT(*) as c FROM employees{where_sql}", params)
        total = int(cur.fetchone()["c"])

        cur.execute(
            f"""
            SELECT employee_id, full_name, team_lead, manager, location, work_type, position, language
            FROM employees
            {where_sql}
            ORDER BY employee_id ASC
            LIMIT ? OFFSET ?
            """,
            params + [int(limit), int(offset)],
        )
        rows = [dict(r) for r in cur.fetchall()]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": rows,
    }

# ----------------------------
# AUTH (Demo) - Employees + Users (SQLite)
# ----------------------------
import os
import sqlite3
import random
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import Depends, Header
from jose import jwt, JWTError
from passlib.context import CryptContext


AUTH_DB_PATH = DATA_DIR / "auth_demo.db"

JWT_SECRET = os.environ.get("WFM_JWT_SECRET", "dev_secret_change_me")
JWT_ALG = "HS256"
JWT_EXPIRE_MINUTES = 60 * 12  # 12 saat

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

LOCATIONS = ["Ankara", "Istanbul", "Izmir", "Konya", "Diyarbakir", "Adana"]
WORK_TYPES = ["fulltime", "akademi", "dis_kaynak"]
LANGS = ["tr", "ar", "en"]
FIRST_NAMES = [
    "Ahmet","Mehmet","Ayse","Fatma","Zeynep","Ali","Mustafa","Elif","Merve","Can",
    "Ece","Burak","Cem","Seda","Derya","Hakan","Emre","Deniz","Esra","Kaan",
    "Irem","Omer","Gizem","Serkan","Melis","Yusuf","Sinem","Berk","Asli","Eren"
]
LAST_NAMES = [
    "Yilmaz","Kaya","Demir","Sahin","Celik","Yildiz","Aydin","Ozdemir","Arslan","Dogan",
    "Kilic","Aslan","Cetin","Koc","Kurt","Ozkan","Simsek","Polat","Tas","Guler"
]

def _hash_password(p: str) -> str:
    return pwd_context.hash(p)

def _verify_password(p: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(p, hashed)
    except Exception:
        return False

def _create_token(payload: Dict[str, Any]) -> str:
    exp = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    to_encode = payload.copy()
    to_encode["exp"] = exp
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALG)

def _decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError:
        return None

def _slug_username(full_name: str, suffix: int) -> str:
    parts = re.split(r"\\s+", full_name.strip())
    base = f"{parts[0]}.{parts[-1]}".lower()
    return f"{base}{suffix:02d}"

def _conn():
    AUTH_DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(str(AUTH_DB_PATH))

def _init_auth_db():
    with _conn() as con:
        cur = con.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS employees(
            employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            team_lead TEXT,
            manager TEXT,
            location TEXT,
            work_type TEXT,
            position TEXT,
            language TEXT
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            employee_id INTEGER NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(employee_id) REFERENCES employees(employee_id)
        )
        """)
        con.commit()

def _seed_200_if_empty():
    TARGET_NON_MOD = 200  # moderator hariç gerçek personel

    with _conn() as con:
        cur = con.cursor()

        # moderator hariç kaç kişi var?
        cur.execute("SELECT COUNT(*) FROM employees WHERE lower(position) != 'moderator'")
        non_mod_count = int(cur.fetchone()[0] or 0)
        if non_mod_count >= TARGET_NON_MOD:
            return

        # temizle
        cur.execute("DELETE FROM users")
        cur.execute("DELETE FROM employees")
        con.commit()

        random.seed(42)

        # ---- Dağılımlar (az yönetici/TL) ----
        MANAGER_N = 3
        WFM_N = 2
        TL_N = 10

        # Agents: 200 - (manager+wfm+tl)
        AGENT_N = TARGET_NON_MOD - (MANAGER_N + WFM_N + TL_N)
        if AGENT_N <= 0:
            raise RuntimeError("Dağılım hatalı: agent sayısı <= 0")

        # ---- Managers ----
        managers = []
        for _ in range(MANAGER_N):
            full_name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
            loc = random.choice(LOCATIONS)
            cur.execute(
                "INSERT INTO employees(full_name, team_lead, manager, location, work_type, position, language) VALUES(?,?,?,?,?,?,?)",
                (full_name, "", full_name, loc, "fulltime", "manager", "tr"),
            )
            managers.append((full_name, loc))

        # ---- WFM ----
        for _ in range(WFM_N):
            full_name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
            loc = random.choice(LOCATIONS)
            cur.execute(
                "INSERT INTO employees(full_name, team_lead, manager, location, work_type, position, language) VALUES(?,?,?,?,?,?,?)",
                (full_name, "", full_name, loc, "fulltime", "wfm", "tr"),
            )

        # ---- TL ----
        tls = []
        for _ in range(TL_N):
            mgr_name, mgr_loc = random.choice(managers)
            full_name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
            cur.execute(
                "INSERT INTO employees(full_name, team_lead, manager, location, work_type, position, language) VALUES(?,?,?,?,?,?,?)",
                (full_name, full_name, mgr_name, mgr_loc, "fulltime", "tl", "tr"),
            )
            tls.append((full_name, mgr_name, mgr_loc))

        # ---- Agents (EXACT dil + EXACT akademi) ----
        # Dil: 20 en, 25 ar, kalanı tr
        langs = (["en"] * 20) + (["ar"] * 25) + (["tr"] * (AGENT_N - 45))
        random.shuffle(langs)

        # Çalışma biçimi: 85 akademi, kalanı fulltime/dis_kaynak
        work_types = (["akademi"] * 85)
        remaining = AGENT_N - 85
        # kalanları dağıtalım (örn: %70 fulltime, %30 dış kaynak)
        full_n = int(round(remaining * 0.70))
        dis_n = remaining - full_n
        work_types += (["fulltime"] * full_n) + (["dis_kaynak"] * dis_n)
        random.shuffle(work_types)

        # Lokasyon dağılımını garantiye al (round-robin)
        loc_cycle = LOCATIONS[:]  # ["Ankara", "Istanbul", ...]
        random.shuffle(loc_cycle)

        for i in range(AGENT_N):
            tl_name, mgr, _tl_loc = random.choice(tls)

            # her lokasyondan kesin olsun diye i%len(LOCATIONS)
            loc = loc_cycle[i % len(loc_cycle)]

            full_name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
            cur.execute(
                "INSERT INTO employees(full_name, team_lead, manager, location, work_type, position, language) VALUES(?,?,?,?,?,?,?)",
                (full_name, tl_name, mgr, loc, work_types[i], "agent", langs[i]),
            )

        # ---- MODERATOR (System user) ----
        # Personel sayısına dahil değil. UI zaten listelemeden hariç tutuyor.
        full_name = "System Moderator"
        cur.execute(
            "INSERT INTO employees(full_name, team_lead, manager, location, work_type, position, language) VALUES(?,?,?,?,?,?,?)",
            (full_name, "", full_name, "Istanbul", "superuser", "moderator", "tr"),
        )
        moderator_emp_id = cur.lastrowid

        cur.execute(
            "INSERT INTO users(username, password_hash, employee_id, is_active) VALUES(?,?,?,1)",
            ("moderator", _hash_password("1234"), moderator_emp_id),
        )

        # ---- USERS (diğer tüm çalışanlar) ----
        cur.execute("SELECT employee_id, full_name FROM employees")
        all_emps = cur.fetchall()

        used = set(["moderator"])
        for emp_id, full_name in all_emps:
            if int(emp_id) == int(moderator_emp_id):
                continue

            suffix = 1
            while True:
                uname = _slug_username(full_name, suffix)
                if uname not in used:
                    used.add(uname)
                    break
                suffix += 1

            cur.execute(
                "INSERT INTO users(username, password_hash, employee_id, is_active) VALUES(?,?,?,1)",
                (uname, _hash_password("1234"), emp_id),
            )

        con.commit()

@app.on_event("startup")
def _startup_auth():
    _init_auth_db()
    _seed_200_if_empty()

def _get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with _conn() as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("""
            SELECT u.username, u.is_active, e.*
            FROM users u
            JOIN employees e ON e.employee_id = u.employee_id
            WHERE u.username = ?
            LIMIT 1
        """, (username,))
        row = cur.fetchone()
        return dict(row) if row else None

def _get_password_hash(username: str) -> Optional[str]:
    with _conn() as con:
        cur = con.cursor()
        cur.execute("SELECT password_hash FROM users WHERE username=? AND is_active=1 LIMIT 1", (username,))
        r = cur.fetchone()
        return r[0] if r else None

def _auth_required(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1].strip()
    payload = _decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = _get_user_by_username(username)
    if not user or not int(user.get("is_active", 0)) == 1:
        raise HTTPException(status_code=401, detail="User inactive or not found")
    return user

@app.post("/auth/login")
def auth_login(body: Dict[str, Any]):
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", "")).strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="username/password gerekli")

    pw_hash = _get_password_hash(username)
    if not pw_hash or not _verify_password(password, pw_hash):
        raise HTTPException(status_code=401, detail="Hatalı kullanıcı adı veya şifre")

    user = _get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    pos = str(user.get("position") or "").lower()
    is_superuser = pos in {"moderator", "wfm", "manager"}
    is_mod = pos == "moderator"

    token = _create_token({
        "sub": username,
        "role": pos,
        "employee_id": user.get("employee_id"),
        "is_superuser": is_superuser,
    })

    # Base profile: herkes için ortak
    profile = {
        "username": username,
        "employee_id": user.get("employee_id"),
        "full_name": user.get("full_name"),
        "position": pos,
        "work_type": user.get("work_type"),
        "is_superuser": is_superuser,
    }

    # Moderator hariç detaylar
    if not is_mod:
        profile.update({
            "team_lead": user.get("team_lead"),
            "manager": user.get("manager"),
            "location": user.get("location"),
            "language": user.get("language"),
        })

    return {
        "access_token": token,
        "token_type": "bearer",
        "profile": profile,
    }

@app.get("/auth/me")
def auth_me(user: Dict[str, Any] = Depends(_auth_required)):
    pos = str(user.get("position") or "").lower()
    is_superuser = pos in {"moderator", "wfm", "manager"}
    is_mod = pos == "moderator"

    base = {
        "username": user.get("username"),
        "employee_id": user.get("employee_id"),
        "full_name": user.get("full_name"),
        "position": pos,
        "work_type": user.get("work_type"),
        "is_superuser": is_superuser,
    }

    if not is_mod:
        base.update({
            "team_lead": user.get("team_lead"),
            "manager": user.get("manager"),
            "location": user.get("location"),
            "language": user.get("language"),
        })

    return base

@app.get("/auth/demo_users")
def auth_demo_users(limit: int = 20):
    """Sadece demo amaçlı: ilk N kullanıcıyı döndürür."""
    with _conn() as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("""
            SELECT u.username, e.full_name, e.position, e.location, e.team_lead, e.manager
            FROM users u JOIN employees e ON e.employee_id = u.employee_id
            WHERE u.is_active=1
            ORDER BY e.employee_id ASC
            LIMIT ?
        """, (int(limit),))
        rows = [dict(r) for r in cur.fetchall()]
        return {"items": rows, "default_password": "1234"}
