"""
Database Layer for DengueWatch Full-Stack Platform.
Utilizes an embedded SQLite database (denguewatch.db) with comprehensive schemas,
relational integrity, automated seeding, and CRUD helpers.
"""

import os
import sqlite3
import hashlib
import json
import csv
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "denguewatch.db")
NCDC_CSV = os.path.join(os.path.dirname(__file__), "ncdc_dengue_weekly.csv")
ALERTS_CSV = os.path.join(os.path.dirname(__file__), "realtime_reports", "realtime_state_alerts.csv")
BENCHMARKS_CSV = os.path.join(os.path.dirname(__file__), "benchmark_output", "benchmark_results.csv")

def get_db_connection() -> sqlite3.Connection:
    """Creates a database connection with dictionary-like row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def hash_password(password: str) -> str:
    """Returns SHA-256 hashed password with a fixed salt for deterministic security."""
    salt = "denguewatch_secure_salt_2026"
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plain password against stored hash."""
    return hash_password(plain_password) == hashed_password

def init_db():
    """Initializes all database tables with proper indexing and constraints."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'public', -- 'admin', 'officer', 'analyst', 'public'
        full_name TEXT NOT NULL,
        department TEXT DEFAULT 'Public Health Dept',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Surveillance Records Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS surveillance_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        state TEXT NOT NULL,
        week_start TEXT NOT NULL,
        cases INTEGER NOT NULL DEFAULT 0,
        year INTEGER NOT NULL,
        epi_week INTEGER NOT NULL,
        source TEXT DEFAULT 'NCDC/IDSP Surveillance',
        reported_by TEXT DEFAULT 'National Surveillance System',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(state, week_start)
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_surveillance_state ON surveillance_records(state);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_surveillance_week ON surveillance_records(week_start);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_surveillance_year_week ON surveillance_records(year, epi_week);")

    # 3. State Alerts Table (Real-time dynamic surveillance snapshot)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS state_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        state TEXT UNIQUE NOT NULL,
        latest_cases INTEGER NOT NULL DEFAULT 0,
        estimated_rt REAL NOT NULL DEFAULT 1.0,
        p75_threshold INTEGER NOT NULL DEFAULT 0,
        p95_threshold INTEGER NOT NULL DEFAULT 0,
        alert_level TEXT NOT NULL DEFAULT 'STABLE BASELINE',
        velocity_growth REAL DEFAULT 0.0,
        risk_score REAL DEFAULT 0.0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_level ON state_alerts(alert_level);")

    # 4. Benchmark Metrics Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS benchmark_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        state TEXT NOT NULL,
        horizon INTEGER NOT NULL,
        origin INTEGER DEFAULT 0,
        model TEXT NOT NULL,
        mase REAL NOT NULL,
        wql REAL NOT NULL,
        ppe_abs REAL,
        ppe_rel REAL,
        timing_err INTEGER DEFAULT 0
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_benchmark_model ON benchmark_metrics(model);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_benchmark_horizon ON benchmark_metrics(horizon);")

    # 5. Alert Subscriptions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alert_subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        state TEXT NOT NULL,
        alert_threshold TEXT NOT NULL DEFAULT 'ELEVATED TRANSMISSION',
        min_rt REAL DEFAULT 1.0,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sub_state ON alert_subscriptions(state);")

    # 6. Forecast Simulation History Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS forecast_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        state TEXT NOT NULL,
        model_name TEXT NOT NULL,
        horizon_weeks INTEGER NOT NULL,
        forecast_date TEXT NOT NULL,
        predicted_values TEXT NOT NULL, -- JSON formatted array
        context_cases TEXT NOT NULL,   -- JSON formatted recent cases
        created_by TEXT DEFAULT 'System',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 7. Audit Logs Table (Governance, Compliance & Security)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT NOT NULL,
        action TEXT NOT NULL,
        target_entity TEXT,
        details TEXT,
        ip_address TEXT DEFAULT '127.0.0.1',
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 8. Data Ingestion Records Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS data_ingestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        records_ingested INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL,
        uploaded_by TEXT NOT NULL,
        notes TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()

def seed_database_if_empty():
    """Seeds the database with baseline records, users, and benchmarks if empty."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Seed Users if table is empty
    cursor.execute("UPDATE users SET full_name = 'Dr. Prachi Sahoo' WHERE username = 'admin';")
    cursor.execute("UPDATE users SET full_name = 'Prachi Sahoo (State Officer)' WHERE username = 'officer_kerala';")
    cursor.execute("UPDATE users SET full_name = 'Prachi Sahoo (Research Fellow)' WHERE username = 'analyst_ai';")
    conn.commit()

    cursor.execute("SELECT COUNT(*) AS cnt FROM users;")
    if cursor.fetchone()['cnt'] == 0:
        default_users = [
            (
                "admin",
                "admin@denguewatch.gov.in",
                hash_password("Admin@123"),
                "admin",
                "Dr. Prachi Sahoo",
                "National Vector Borne Disease Control Program (NVBDCP)"
            ),
            (
                "officer_kerala",
                "officer.kerala@health.gov.in",
                hash_password("Officer@123"),
                "officer",
                "Prachi Sahoo (State Officer)",
                "Kerala State Directorate of Health Services"
            ),
            (
                "analyst_ai",
                "analyst@srisriuniversity.edu.in",
                hash_password("Analyst@123"),
                "analyst",
                "Prachi Sahoo (Research Fellow)",
                "School of AI & Data Science Informatics Lab"
            ),
            (
                "public_demo",
                "visitor@healthwatch.org",
                hash_password("Public@123"),
                "public",
                "Public Health Researcher",
                "Independent Epidemiology Observer"
            )
        ]
        cursor.executemany("""
            INSERT INTO users (username, email, password_hash, role, full_name, department)
            VALUES (?, ?, ?, ?, ?, ?);
        """, default_users)
        conn.commit()
        print("[Database] Seeded 4 default user accounts.")

    # 2. Seed Surveillance Records from CSV if empty
    cursor.execute("SELECT COUNT(*) AS cnt FROM surveillance_records;")
    if cursor.fetchone()['cnt'] == 0 and os.path.exists(NCDC_CSV):
        print("[Database] Seeding surveillance records from ncdc_dengue_weekly.csv (this takes ~1-2 seconds)...")
        with open(NCDC_CSV, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            records = []
            for row in reader:
                try:
                    records.append((
                        row["state"].strip(),
                        row["week_start"].strip(),
                        int(float(row.get("cases", 0))),
                        int(row.get("year", 2015)),
                        int(row.get("epi_week", 1)),
                        "NCDC/IDSP National Weekly Outbreak Bulletin"
                    ))
                except Exception:
                    continue

            cursor.executemany("""
                INSERT OR IGNORE INTO surveillance_records (state, week_start, cases, year, epi_week, source)
                VALUES (?, ?, ?, ?, ?, ?);
            """, records)
            conn.commit()
            print(f"[Database] Successfully seeded {len(records)} surveillance records.")

    # 3. Seed State Alerts from CSV if empty
    cursor.execute("SELECT COUNT(*) AS cnt FROM state_alerts;")
    if cursor.fetchone()['cnt'] == 0 and os.path.exists(ALERTS_CSV):
        with open(ALERTS_CSV, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            alerts = []
            for row in reader:
                try:
                    cases = int(float(row.get("Latest Week Cases", 0)))
                    rt = float(row.get("Estimated Rt", 1.0))
                    p75 = int(float(row.get("75th Pctile Threshold", 0)))
                    p95 = int(float(row.get("95th Pctile Threshold", 0)))
                    level = row.get("Epidemic Alert Level", "STABLE BASELINE").strip()
                    growth = round(((rt - 1.0) * 100), 1) if rt > 0 else 0.0
                    risk = round((cases / (p95 + 1e-5)) * (1.5 if rt > 1.2 else 1.0), 2)
                    alerts.append((
                        row["State/UT"].strip(),
                        cases,
                        rt,
                        p75,
                        p95,
                        level,
                        growth,
                        risk
                    ))
                except Exception:
                    continue

            cursor.executemany("""
                INSERT OR REPLACE INTO state_alerts (state, latest_cases, estimated_rt, p75_threshold, p95_threshold, alert_level, velocity_growth, risk_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, alerts)
            conn.commit()
            print(f"[Database] Seeded {len(alerts)} state alert records.")

    # 4. Seed Benchmark Metrics from CSV if empty
    cursor.execute("SELECT COUNT(*) AS cnt FROM benchmark_metrics;")
    if cursor.fetchone()['cnt'] == 0 and os.path.exists(BENCHMARKS_CSV):
        with open(BENCHMARKS_CSV, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            benchmarks = []
            for row in reader:
                try:
                    benchmarks.append((
                        row.get("state", "").strip(),
                        int(row.get("horizon", 1)),
                        int(row.get("origin", 0)),
                        row.get("model", "").strip(),
                        float(row.get("MASE", 0.0)),
                        float(row.get("WQL", 0.0)),
                        float(row.get("PPE_Abs", 0.0)) if row.get("PPE_Abs") else None,
                        float(row.get("PPE_Rel", 0.0)) if row.get("PPE_Rel") else None,
                        int(row.get("Timing_Err", 0)) if row.get("Timing_Err") else 0
                    ))
                except Exception:
                    continue

            cursor.executemany("""
                INSERT INTO benchmark_metrics (state, horizon, origin, model, mase, wql, ppe_abs, ppe_rel, timing_err)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, benchmarks)
            conn.commit()
            print(f"[Database] Seeded {len(benchmarks)} benchmark evaluation rows.")

    # 5. Seed Default Subscriptions if empty
    cursor.execute("SELECT COUNT(*) AS cnt FROM alert_subscriptions;")
    if cursor.fetchone()['cnt'] == 0:
        default_subs = [
            ("health.director@kerala.gov.in", "Kerala", "ELEVATED TRANSMISSION", 1.1),
            ("epidem.maharashtra@gov.in", "Maharashtra", "HIGH OUTBREAK SURGE", 1.3),
            ("surveillance.tn@gov.in", "Tamil Nadu", "ELEVATED TRANSMISSION", 1.0),
            ("odisha.healthalerts@odisha.gov.in", "Odisha", "ALL", 0.8),
            ("delhi.surveillance@delhi.gov.in", "Delhi", "ELEVATED TRANSMISSION", 1.15)
        ]
        cursor.executemany("""
            INSERT INTO alert_subscriptions (email, state, alert_threshold, min_rt)
            VALUES (?, ?, ?, ?);
        """, default_subs)
        conn.commit()

    # 6. Seed Initial Audit Log
    cursor.execute("SELECT COUNT(*) AS cnt FROM audit_logs;")
    if cursor.fetchone()['cnt'] == 0:
        cursor.execute("""
            INSERT INTO audit_logs (user_id, username, action, target_entity, details)
            VALUES (1, 'admin', 'SYSTEM_INITIALIZATION', 'DATABASE', 'DengueWatch Full-Stack platform initialized with 10-year NCDC longitudinal database.');
        """)
        conn.commit()

    conn.close()

# Ensure schema exists on module load
init_db()
seed_database_if_empty()
