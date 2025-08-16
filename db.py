# db.py — простая обёртка над SQLite для сотрудников и расписаний
import sqlite3
from pathlib import Path
from typing import List, Dict, Any

DB_PATH = Path(__file__).with_name("scheduler.db")

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    part_time INTEGER NOT NULL DEFAULT 0,   -- 1=частичная занятость (всегда 1-я, без дежурств)
    can_duty INTEGER NOT NULL DEFAULT 1,    -- 1=может дежурить
    can_support INTEGER NOT NULL DEFAULT 1  -- 1=может идти на обеспечение
);

CREATE TABLE IF NOT EXISTS schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_id INTEGER NOT NULL,
    y INTEGER NOT NULL,
    m INTEGER NOT NULL,
    d INTEGER NOT NULL,
    shift TEXT,        -- '1' | '2' | 'В' | 'ОТП' | 'БОЛ' | 'КМД' | 'ОБЕС' | NULL
    duty INTEGER,      -- 0/1
    UNIQUE(emp_id, y, m, d),
    FOREIGN KEY(emp_id) REFERENCES employees(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS absences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_id INTEGER NOT NULL,
    dt TEXT NOT NULL,       -- YYYY-MM-DD
    type TEXT NOT NULL,     -- 'ОТП' | 'БОЛ' | 'КМД'
    FOREIGN KEY(emp_id) REFERENCES employees(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS fixed_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dt TEXT NOT NULL,   -- YYYY-MM-DD
    shift INTEGER,      -- 1 | 2 | NULL (весь день)
    type TEXT NOT NULL, -- 'ОБЕС' и т.п.
    required_count INTEGER NOT NULL DEFAULT 1
);
"""

SEED_EMPLOYEES = [
    ("Иванов И.И.", 0, 1, 1),
    ("Петров П.П.", 0, 1, 1),
    ("Сидоров С.С.", 0, 1, 1),
    ("Смирнов Н.Н.", 0, 1, 1),
    ("Кузнецов К.К.", 0, 1, 1),
    ("Попов П.П.", 0, 1, 1),
    ("Васильев В.В.", 0, 1, 1),
    ("Соколов С.С.", 0, 1, 1),
    ("Михайлов М.М.", 0, 1, 1),
    ("Новиков Н.Н.", 0, 1, 1),
    ("Фёдоров Ф.Ф.", 0, 1, 1),
    ("Морозов М.М.", 0, 1, 1),
    ("Волков В.В.", 0, 1, 1),
    ("Егорова Е.Е.", 1, 0, 0),  # частичная занятость: 1-я смена, без дежурств/обеспечений
    ("Кузьмина А.А.", 1, 0, 0),
]

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    return conn

def init_db():
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        # если нет сотрудников — посеять демо
        cur = conn.execute("SELECT COUNT(*) FROM employees")
        if cur.fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO employees(name,part_time,can_duty,can_support) VALUES (?,?,?,?)",
                SEED_EMPLOYEES
            )
        conn.commit()
    finally:
        conn.close()

def load_employees() -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT id, name, part_time, can_duty, can_support FROM employees ORDER BY id")
        rows = cur.fetchall()
        return [
            {
                "id": r[0], "name": r[1],
                "part_time": bool(r[2]),
                "can_duty": bool(r[3]),
                "can_support": bool(r[4]),
            } for r in rows
        ]
    finally:
        conn.close()

def upsert_employee(name: str, part_time: bool=False, can_duty: bool=True, can_support: bool=True):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO employees(name,part_time,can_duty,can_support) VALUES (?,?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET part_time=excluded.part_time, can_duty=excluded.can_duty, can_support=excluded.can_support",
            (name, int(part_time), int(can_duty), int(can_support))
        )
        conn.commit()
    finally:
        conn.close()

def remove_employee(name: str):
    conn = get_conn()
    try:
        emp_id = conn.execute("SELECT id FROM employees WHERE name=?", (name,)).fetchone()
        if emp_id:
            conn.execute("DELETE FROM employees WHERE id=?", (emp_id[0],))
            conn.commit()
    finally:
        conn.close()

def save_month_schedule(y: int, m: int, schedule: Dict[str, Dict[int, Dict[str, any]]]):
    """schedule[emp_name][day] = {'shift': '1'|'2'|'В'|'ОТП'|'БОЛ'|'КМД'|'ОБЕС'|'' , 'duty': bool}"""
    conn = get_conn()
    try:
        # соответствие имя -> id
        map_ids = {r["name"]: r["id"] for r in load_employees()}
        for emp_name, days in schedule.items():
            emp_id = map_ids.get(emp_name)
            if not emp_id:
                continue
            for d, payload in days.items():
                shift = payload.get("shift") or None
                duty = 1 if payload.get("duty") else 0
                conn.execute(
                    "INSERT INTO schedule(emp_id,y,m,d,shift,duty) VALUES (?,?,?,?,?,?) "
                    "ON CONFLICT(emp_id,y,m,d) DO UPDATE SET shift=excluded.shift, duty=excluded.duty",
                    (emp_id, y, m, d, shift, duty)
                )
        conn.commit()
    finally:
        conn.close()

def load_month_schedule(y: int, m: int) -> Dict[str, Dict[int, Dict[str, any]]]:
    conn = get_conn()
    try:
        id2name = {rid: nm for rid, nm in conn.execute("SELECT id, name FROM employees")}
        cur = conn.execute("SELECT emp_id, d, shift, duty FROM schedule WHERE y=? AND m=?", (y, m))
        result = {}
        for emp_id, d, shift, duty in cur.fetchall():
            name = id2name.get(emp_id, f"emp#{emp_id}")
            result.setdefault(name, {})[d] = {"shift": shift or "", "duty": bool(duty)}
        return result
    finally:
        conn.close()
