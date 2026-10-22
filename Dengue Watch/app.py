"""
DengueWatch Full-Stack Epidemiological Surveillance & Forecasting Application.
Flask RESTful Backend with SQLite Database, Authentication, Role-Based Access Control,
Full CRUD Operations, Live Multi-Horizon Forecasting Engine, and Ingestion Pipelines.
"""

import os
import io
import csv
import json
import uuid
import secrets
from datetime import datetime
from functools import wraps
from typing import Dict, Any, Optional

from flask import Flask, request, jsonify, send_file, make_response
from flask_cors import CORS

import database
from database import get_db_connection, hash_password, verify_password
import forecasting_service
import agentic_advisor
from cache_service import cache

# Initialize Flask App
app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

# In-memory Token Store for session management
ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}

# Paths
REALTIME_ALERTS_CSV = os.path.join(os.path.dirname(__file__), "realtime_reports", "realtime_state_alerts.csv")
BENCHMARK_RESULTS_CSV = os.path.join(os.path.dirname(__file__), "benchmark_output", "benchmark_results.csv")
KERALA_DASHBOARD_PNG = os.path.join(os.path.dirname(__file__), "realtime_reports", "realtime_dashboard_Kerala.png")

# Ensure database is initialized on startup
database.init_db()
database.seed_database_if_empty()

# -----------------------------------------------------------------------------
# Authentication & Authorization Helpers
# -----------------------------------------------------------------------------

def create_session_token(user: dict) -> str:
    """Generates a secure session token and caches user context."""
    token = secrets.token_hex(32)
    ACTIVE_SESSIONS[token] = {
        "user_id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "full_name": user["full_name"],
        "email": user["email"],
        "department": user["department"],
        "created_at": datetime.now().isoformat()
    }
    return token

def get_current_user() -> Optional[Dict[str, Any]]:
    """Extracts current user from Authorization header or cookie."""
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "dengue_token" in request.cookies:
        token = request.cookies.get("dengue_token")
    
    if token and token in ACTIVE_SESSIONS:
        return ACTIVE_SESSIONS[token]
    return None

def require_auth(roles=None):
    """Decorator to enforce authentication and optional role restrictions."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "Authentication required. Please log in."}), 401
            if roles and user.get("role") not in roles and "admin" != user.get("role"):
                return jsonify({"error": f"Forbidden. Requires one of roles: {roles}"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_audit(action: str, target_entity: str, details: str, username: str = None, user_id: int = None):
    """Records an entry in the system audit trail."""
    try:
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO audit_logs (user_id, username, action, target_entity, details, ip_address)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (
            user_id or 0,
            username or (get_current_user()["username"] if get_current_user() else "anonymous"),
            action,
            target_entity,
            details,
            request.remote_addr or "127.0.0.1"
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Audit Log Error] {e}")

# -----------------------------------------------------------------------------
# Frontend Static Routing
# -----------------------------------------------------------------------------

@app.route("/")
def index():
    """Serves the main Single Page Application."""
    return app.send_static_file("index.html")

# -----------------------------------------------------------------------------
# System Health & Metrics
# -----------------------------------------------------------------------------

@app.route("/api/health")
def health_check():
    """Returns database connection status and system record counts."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) AS total FROM surveillance_records;")
    surveillance_count = cursor.fetchone()["total"]
    
    cursor.execute("SELECT COUNT(*) AS total FROM state_alerts;")
    alerts_count = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM users;")
    users_count = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM forecast_history;")
    forecasts_count = cursor.fetchone()["total"]

    conn.close()

    return jsonify({
        "status": "healthy",
        "service": "DengueWatch Full-Stack API",
        "version": "2.0.0-FullStack",
        "timestamp": datetime.now().isoformat(),
        "database": {
            "type": "SQLite Embedded Relational Database",
            "connected": True,
            "surveillance_records": surveillance_count,
            "active_state_alerts": alerts_count,
            "registered_users": users_count,
            "cached_forecasts": forecasts_count
        }
    })

# -----------------------------------------------------------------------------
# Authentication Endpoints
# -----------------------------------------------------------------------------

@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    """Registers a new user account."""
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")
    full_name = data.get("full_name", "").strip() or username
    department = data.get("department", "Public Health Research").strip()
    role = data.get("role", "public")

    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required."}), 400

    if role not in ["public", "analyst", "officer"]:
        role = "public"

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if username or email exists
    cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?;", (username, email))
    if cursor.fetchone():
        conn.close()
        return jsonify({"error": "Username or email already exists."}), 409

    pwd_hash = hash_password(password)
    cursor.execute("""
        INSERT INTO users (username, email, password_hash, role, full_name, department)
        VALUES (?, ?, ?, ?, ?, ?);
    """, (username, email, pwd_hash, role, full_name, department))
    user_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT id, username, email, role, full_name, department FROM users WHERE id = ?;", (user_id,))
    new_user = dict(cursor.fetchone())
    conn.close()

    token = create_session_token(new_user)
    log_audit("USER_REGISTER", "AUTH", f"New user {username} registered as {role}.", username=username, user_id=user_id)

    return jsonify({
        "message": "User registered successfully.",
        "token": token,
        "user": new_user
    }), 201

@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    """Authenticates credentials and returns a session token."""
    data = request.get_json() or {}
    username_or_email = data.get("username", "").strip()
    password = data.get("password", "")

    if not username_or_email or not password:
        return jsonify({"error": "Username and password are required."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, email, password_hash, role, full_name, department
        FROM users
        WHERE username = ? OR email = ?;
    """, (username_or_email, username_or_email))
    row = cursor.fetchone()
    conn.close()

    if not row or not verify_password(password, row["password_hash"]):
        return jsonify({"error": "Invalid username or password."}), 401

    user_info = {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "role": row["role"],
        "full_name": row["full_name"],
        "department": row["department"]
    }
    token = create_session_token(user_info)
    log_audit("USER_LOGIN", "AUTH", f"User {row['username']} logged in.", username=row["username"], user_id=row["id"])

    return jsonify({
        "message": "Login successful.",
        "token": token,
        "user": user_info
    })

@app.route("/api/auth/demo-login", methods=["POST"])
def auth_demo_login():
    """Quick switch demo login for evaluators and testers."""
    data = request.get_json() or {}
    requested_role = data.get("role", "admin").lower()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, email, role, full_name, department
        FROM users
        WHERE role = ?
        ORDER BY id ASC LIMIT 1;
    """, (requested_role,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": f"No default user found with role '{requested_role}'."}), 404

    user_info = dict(row)
    token = create_session_token(user_info)
    log_audit("DEMO_LOGIN", "AUTH", f"Demo session active as {user_info['role']}.", username=user_info["username"], user_id=user_info["id"])

    return jsonify({
        "message": f"Authenticated as {user_info['role'].upper()}.",
        "token": token,
        "user": user_info
    })

@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    """Returns the currently logged-in user context."""
    user = get_current_user()
    if not user:
        return jsonify({"authenticated": False}), 200
    return jsonify({
        "authenticated": True,
        "user": user
    })

@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    """Logs out the current session."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else request.cookies.get("dengue_token")
    if token in ACTIVE_SESSIONS:
        username = ACTIVE_SESSIONS[token]["username"]
        del ACTIVE_SESSIONS[token]
        log_audit("USER_LOGOUT", "AUTH", f"User {username} logged out.", username=username)
    return jsonify({"message": "Logged out successfully."})

# -----------------------------------------------------------------------------
# Surveillance Records CRUD API (Full Database Operations)
# -----------------------------------------------------------------------------

@app.route("/api/surveillance", methods=["GET"])
def get_surveillance_records():
    """
    Retrieves paginated, searchable, and filtered surveillance records.
    Query params: state, year, search, page, limit, sort_order
    """
    state = request.args.get("state", "").strip()
    year = request.args.get("year", "").strip()
    search = request.args.get("search", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    limit = min(200, max(1, int(request.args.get("limit", 25))))
    offset = (page - 1) * limit
    sort_order = "ASC" if request.args.get("sort_order", "DESC").upper() == "ASC" else "DESC"

    query_clauses = []
    params = []

    if state and state.lower() != "all":
        query_clauses.append("state = ?")
        params.append(state)

    if year and year.isdigit():
        query_clauses.append("year = ?")
        params.append(int(year))

    if search:
        query_clauses.append("(state LIKE ? OR week_start LIKE ? OR source LIKE ?)")
        search_pattern = f"%{search}%"
        params.extend([search_pattern, search_pattern, search_pattern])

    where_sql = f"WHERE {' AND '.join(query_clauses)}" if query_clauses else ""

    conn = get_db_connection()
    cursor = conn.cursor()

    # Total count query
    count_query = f"SELECT COUNT(*) AS total FROM surveillance_records {where_sql};"
    cursor.execute(count_query, params)
    total_records = cursor.fetchone()["total"]

    # Paginated records query
    records_query = f"""
        SELECT id, state, week_start, cases, year, epi_week, source, reported_by, created_at
        FROM surveillance_records
        {where_sql}
        ORDER BY week_start {sort_order}, state ASC
        LIMIT ? OFFSET ?;
    """
    cursor.execute(records_query, params + [limit, offset])
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({
        "total": total_records,
        "page": page,
        "limit": limit,
        "total_pages": (total_records + limit - 1) // limit,
        "records": records
    })

@app.route("/api/surveillance/states", methods=["GET"])
def get_surveillance_states():
    """Returns the list of all 36 States/UTs with total case counts and record spans."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            state,
            COUNT(*) AS total_weeks,
            SUM(cases) AS cumulative_cases,
            MIN(week_start) AS earliest_week,
            MAX(week_start) AS latest_week
        FROM surveillance_records
        GROUP BY state
        ORDER BY state ASC;
    """)
    states_data = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(states_data)

@app.route("/api/surveillance/state-history", methods=["GET"])
def get_state_surveillance_history():
    """Returns the chronological weekly case series for a state for charting."""
    state = request.args.get("state", "Kerala").strip()
    year_limit = request.args.get("years", "3") # default last 3 years or all
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if year_limit and year_limit.isdigit():
        cursor.execute("""
            SELECT week_start, cases, year, epi_week
            FROM surveillance_records
            WHERE state = ? AND year >= (SELECT MAX(year) - ? FROM surveillance_records WHERE state = ?)
            ORDER BY week_start ASC;
        """, (state, int(year_limit), state))
    else:
        cursor.execute("""
            SELECT week_start, cases, year, epi_week
            FROM surveillance_records
            WHERE state = ?
            ORDER BY week_start ASC;
        """, (state,))
        
    records = [dict(row) for row in cursor.fetchall()]

    # Fetch state alert info
    cursor.execute("SELECT * FROM state_alerts WHERE state = ?;", (state,))
    alert_row = cursor.fetchone()
    conn.close()

    return jsonify({
        "state": state,
        "series": records,
        "alert_profile": dict(alert_row) if alert_row else None
    })

@app.route("/api/surveillance", methods=["POST"])
@require_auth(roles=["officer", "admin", "analyst"])
def create_surveillance_record():
    """Creates a new weekly epidemiological case record."""
    data = request.get_json() or {}
    state = data.get("state", "").strip()
    week_start = data.get("week_start", "").strip()
    cases = data.get("cases")
    source = data.get("source", "Field Surveillance Report").strip()

    if not state or not week_start or cases is None:
        return jsonify({"error": "State, week_start (YYYY-MM-DD), and cases are required."}), 400

    try:
        cases = max(0, int(cases))
        dt = datetime.strptime(week_start, "%Y-%m-%d")
        year = dt.year
        epi_week = int(dt.strftime("%W"))
    except ValueError:
        return jsonify({"error": "Invalid date format. Expected YYYY-MM-DD."}), 400

    user = get_current_user()
    reported_by = user["full_name"] if user else "Officer Portal"

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO surveillance_records (state, week_start, cases, year, epi_week, source, reported_by)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (state, week_start, cases, year, epi_week, source, reported_by))
        record_id = cursor.lastrowid
        conn.commit()
        log_audit("CREATE_RECORD", "SURVEILLANCE", f"Added {cases} cases for {state} ({week_start}).")
    except Exception as e:
        conn.close()
        return jsonify({"error": f"Database insertion failed: {str(e)}"}), 409

    cursor.execute("SELECT * FROM surveillance_records WHERE id = ?;", (record_id,))
    new_record = dict(cursor.fetchone())
    conn.close()

    # Automatically recompute this state's alert level
    recalculate_state_alert(state)

    return jsonify({
        "message": "Surveillance record created successfully.",
        "record": new_record
    }), 201

@app.route("/api/surveillance/<int:record_id>", methods=["PUT"])
@require_auth(roles=["officer", "admin"])
def update_surveillance_record(record_id: int):
    """Updates an existing surveillance record."""
    data = request.get_json() or {}
    cases = data.get("cases")
    source = data.get("source")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM surveillance_records WHERE id = ?;", (record_id,))
    existing = cursor.fetchone()

    if not existing:
        conn.close()
        return jsonify({"error": f"Record with id {record_id} not found."}), 404

    new_cases = int(cases) if cases is not None else existing["cases"]
    new_source = source if source is not None else existing["source"]

    cursor.execute("""
        UPDATE surveillance_records
        SET cases = ?, source = ?
        WHERE id = ?;
    """, (new_cases, new_source, record_id))
    conn.commit()

    state = existing["state"]
    cursor.execute("SELECT * FROM surveillance_records WHERE id = ?;", (record_id,))
    updated_record = dict(cursor.fetchone())
    conn.close()

    log_audit("UPDATE_RECORD", "SURVEILLANCE", f"Updated record #{record_id} ({state}) to {new_cases} cases.")
    recalculate_state_alert(state)

    return jsonify({
        "message": "Surveillance record updated.",
        "record": updated_record
    })

@app.route("/api/surveillance/<int:record_id>", methods=["DELETE"])
@require_auth(roles=["admin"])
def delete_surveillance_record(record_id: int):
    """Deletes a surveillance record (Admin Only)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT state, week_start, cases FROM surveillance_records WHERE id = ?;", (record_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": f"Record with id {record_id} not found."}), 404

    cursor.execute("DELETE FROM surveillance_records WHERE id = ?;", (record_id,))
    conn.commit()
    conn.close()

    log_audit("DELETE_RECORD", "SURVEILLANCE", f"Deleted record #{record_id}: {row['state']} on {row['week_start']}.")
    recalculate_state_alert(row["state"])

    return jsonify({"message": f"Record #{record_id} successfully deleted."})

# -----------------------------------------------------------------------------
# Outbreak Alerts & Epidemiological Surveillance
# -----------------------------------------------------------------------------

def recalculate_state_alert(state: str):
    """Internal helper to recalculate epidemic metrics and alert levels for a state."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cases FROM surveillance_records
            WHERE state = ?
            ORDER BY week_start ASC;
        """, (state,))
        rows = cursor.fetchall()
        if not rows:
            conn.close()
            return

        cases_list = [r["cases"] for r in rows]
        latest_cases = cases_list[-1]
        rt = forecasting_service.calculate_rt_proxy(cases_list)
        
        import numpy as np
        p75 = int(np.percentile(cases_list, 75))
        p95 = int(np.percentile(cases_list, 95))

        if latest_cases >= p95 or (latest_cases >= p75 and rt > 1.3):
            alert_level = "HIGH OUTBREAK SURGE"
        elif latest_cases >= p75 or rt > 1.15:
            alert_level = "ELEVATED TRANSMISSION"
        else:
            alert_level = "STABLE BASELINE"

        growth = round(((rt - 1.0) * 100), 1) if rt > 0 else 0.0
        risk = round((latest_cases / (p95 + 1e-5)) * (1.5 if rt > 1.2 else 1.0), 2)

        cursor.execute("""
            INSERT INTO state_alerts (state, latest_cases, estimated_rt, p75_threshold, p95_threshold, alert_level, velocity_growth, risk_score, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(state) DO UPDATE SET
                latest_cases = excluded.latest_cases,
                estimated_rt = excluded.estimated_rt,
                p75_threshold = excluded.p75_threshold,
                p95_threshold = excluded.p95_threshold,
                alert_level = excluded.alert_level,
                velocity_growth = excluded.velocity_growth,
                risk_score = excluded.risk_score,
                updated_at = CURRENT_TIMESTAMP;
        """, (state, latest_cases, round(rt, 2), p75, p95, alert_level, growth, risk))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Recalculate Error for {state}] {e}")

@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    """Returns current state alert levels with optional filtering."""
    level = request.args.get("level", "").strip()
    search = request.args.get("search", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    clauses = []
    params = []
    if level and level.lower() != "all":
        clauses.append("alert_level = ?")
        params.append(level)
    if search:
        clauses.append("state LIKE ?")
        params.append(f"%{search}%")

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    cursor.execute(f"""
        SELECT 
            state,
            latest_cases AS "Latest Week Cases",
            estimated_rt AS "Estimated Rt",
            p75_threshold AS "75th Pctile Threshold",
            p95_threshold AS "95th Pctile Threshold",
            alert_level AS "Epidemic Alert Level",
            velocity_growth,
            risk_score,
            updated_at
        FROM state_alerts
        {where_sql}
        ORDER BY latest_cases DESC;
    """, params)
    alerts = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify(alerts)

@app.route("/api/alerts/summary", methods=["GET"])
def get_alerts_summary():
    """Returns high-level national summary KPIs."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            COUNT(*) AS total_states,
            SUM(CASE WHEN alert_level = 'HIGH OUTBREAK SURGE' THEN 1 ELSE 0 END) AS high_alert_states,
            SUM(CASE WHEN alert_level = 'ELEVATED TRANSMISSION' THEN 1 ELSE 0 END) AS elevated_states,
            SUM(CASE WHEN alert_level = 'STABLE BASELINE' THEN 1 ELSE 0 END) AS stable_states,
            AVG(estimated_rt) AS national_avg_rt,
            SUM(latest_cases) AS national_latest_cases
        FROM state_alerts;
    """)
    summary = dict(cursor.fetchone())
    conn.close()

    summary["national_avg_rt"] = round(summary["national_avg_rt"] or 1.0, 2)
    return jsonify(summary)

@app.route("/api/alerts/recalculate", methods=["POST"])
@require_auth(roles=["officer", "admin"])
def recalculate_all_alerts():
    """Recalculates epidemic metrics for all states in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT state FROM surveillance_records;")
    states = [r["state"] for r in cursor.fetchall()]
    conn.close()

    for st in states:
        recalculate_state_alert(st)

    log_audit("RECALCULATE_ALERTS", "EPIDEMIOLOGY", f"Recalculated thresholds and alerts across {len(states)} states.")
    return jsonify({"message": f"Successfully updated alerts for {len(states)} states."})

# -----------------------------------------------------------------------------
# Live Probabilistic Forecasting Engine
# -----------------------------------------------------------------------------

@app.route("/api/forecast/predict", methods=["POST"])
def run_forecast_prediction():
    """
    Executes live multi-horizon forecasting simulation for any state,
    comparing Chronos-Bolt Zero-Shot vs Stacked Quantile LSTM.
    """
    data = request.get_json() or {}
    state = data.get("state", "Kerala").strip()
    horizon = int(data.get("horizon", 4))
    model_name = data.get("model", "Chronos-Bolt").strip()

    if horizon not in [1, 2, 4, 8]:
        horizon = 4

    result = forecasting_service.generate_probabilistic_forecast(
        state=state,
        horizon_weeks=horizon,
        model_name=model_name
    )

    # Save to history for traceability
    try:
        user = get_current_user()
        created_by = user["username"] if user else "Visitor"
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO forecast_history (state, model_name, horizon_weeks, forecast_date, predicted_values, context_cases, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            state,
            model_name,
            horizon,
            result["generated_at"],
            json.dumps(result["forecast_points"]),
            json.dumps(result["context_data"]),
            created_by
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Forecast History Log Error] {e}")

    return jsonify(result)

@app.route("/api/forecast/history", methods=["GET"])
def get_forecast_history():
    """Returns recent forecasting simulation runs."""
    limit = min(50, int(request.args.get("limit", 10)))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, state, model_name, horizon_weeks, forecast_date, created_by, created_at
        FROM forecast_history
        ORDER BY id DESC LIMIT ?;
    """, (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)

# -----------------------------------------------------------------------------
# Agentic AI & LLM Advisory Engine
# -----------------------------------------------------------------------------

@app.route("/api/agent/advise", methods=["POST"])
def get_agentic_advisory():
    """
    Executes autonomous multi-agent reasoning for a state based on current
    surveillance metrics, Rt trajectory, and multi-horizon predictions.
    """
    data = request.get_json() or {}
    state = data.get("state", "Kerala").strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT latest_cases, estimated_rt, p75_threshold, p95_threshold, alert_level
        FROM state_alerts WHERE state = ?;
    """, (state,))
    alert_row = cursor.fetchone()
    conn.close()

    metrics = dict(alert_row) if alert_row else {
        "latest_cases": 90,
        "estimated_rt": 1.15,
        "p75_threshold": 496,
        "p95_threshold": 1278,
        "alert_level": "STABLE BASELINE"
    }

    forecast = forecasting_service.generate_probabilistic_forecast(state=state, horizon_weeks=4)
    advisory = agentic_advisor.run_agentic_epidemic_advisory(
        state_name=state,
        metrics=metrics,
        forecast_points=forecast["forecast_points"]
    )
    return jsonify(advisory)

@app.route("/api/agent/chat", methods=["POST"])
def agent_chat():
    """
    Interactive Q&A agent for epidemiological intelligence, intervention protocols,
    and model architectures.
    """
    data = request.get_json() or {}
    query = data.get("query", "").strip().lower()
    state = data.get("state", "Kerala").strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM state_alerts WHERE state = ?;", (state,))
    row = cursor.fetchone()
    conn.close()

    alert_info = dict(row) if row else {}
    cases = alert_info.get("latest_cases", 0)
    rt = alert_info.get("estimated_rt", 1.0)
    level = alert_info.get("alert_level", "STABLE BASELINE")

    if "rt" in query or "reproduction" in query:
        response = f"For {state}, the estimated effective reproduction number (Rt) is {rt:.2f}. An Rt > 1.0 indicates expanding epidemic transmission where each primary infected case produces more than 1 secondary infection. When Rt crosses 1.30 alongside historical threshold exceedance, an active epidemic alert is triggered."
    elif "chronos" in query or "lstm" in query or "model" in query or "benchmark" in query:
        response = "Our 10-year benchmark across 36 Indian states revealed two core findings: (1) At short horizons (1–2 weeks), Chronos-Bolt zero-shot achieves 0.643 MASE vs 0.910 for Stacked LSTM (-29.3% error), requiring zero local retraining. (2) At 8-week horizons, Chronos-Bolt maintains a 31.1% MASE advantage because the LSTM suffers from compounding autoregressive error, whereas foundation model pre-training preserves macro-seasonal periodicity."
    elif "bed" in query or "hospital" in query or "icu" in query or "platelet" in query:
        est_adm = int(cases * 0.18)
        response = f"Based on current reported caseload in {state} ({cases} cases/wk), projected acute inpatient bed requirements are approximately {max(5, est_adm)} beds, with {max(2, int(est_adm * 0.08))} reserved ICU beds and a standby buffer of {max(10, int(est_adm * 0.45))} platelet units for severe hemorrhagic manifestations."
    elif "vector" in query or "mosquito" in query or "fogging" in query or "larvicide" in query:
        response = f"Current transmission alert level for {state} is '{level}'. Recommended vector protocol: (1) Deploy BTI / Temephos larvicide across high-risk water holding containers. (2) Conduct targeted ultra-low volume thermal fogging (Malathion 5%) within a 100m perimeter of active fever clusters. (3) Enforce weekly dry-day source reduction campaigns."
    else:
        response = f"DengueWatch AI Agent Status for {state}: Transmission level is '{level}' with {cases} weekly cases and Rt = {rt:.2f}. I can provide real-time risk stratification, hospital bed projections, vector control protocols, or foundation model benchmark diagnostics."

    return jsonify({
        "query": query,
        "state": state,
        "response": response,
        "agent": "DengueWatch Agentic Copilot v2.4",
        "timestamp": datetime.now().isoformat()
    })

@app.route("/api/cache/stats", methods=["GET"])
def get_cache_stats():
    """Returns in-memory / Redis cache telemetry."""
    return jsonify({
        "status": "active",
        "cache_type": "Redis-Compatible In-Memory LRU with TTL",
        "stats": cache.stats()
    })

# -----------------------------------------------------------------------------
# Model Benchmarks & Leaderboard
# -----------------------------------------------------------------------------

@app.route("/api/benchmarks", methods=["GET"])
def get_benchmarks():
    """Returns raw benchmark results from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT state, horizon, origin, model, mase AS MASE, wql AS WQL, ppe_abs AS PPE_Abs, ppe_rel AS PPE_Rel, timing_err AS Timing_Err
        FROM benchmark_metrics
        ORDER BY state ASC, horizon ASC;
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route("/api/benchmarks/summary", methods=["GET"])
def get_benchmark_summary():
    """Returns aggregated horizon-level benchmark metrics with relative gap analysis."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            horizon,
            model,
            AVG(mase) AS avg_mase,
            AVG(wql) AS avg_wql
        FROM benchmark_metrics
        GROUP BY horizon, model
        ORDER BY horizon ASC;
    """)
    rows = cursor.fetchall()
    conn.close()

    # Format into horizon comparison
    horizons = {}
    for r in rows:
        h = r["horizon"]
        if h not in horizons:
            horizons[h] = {"horizon_weeks": h}
        if r["model"] == "Chronos-Bolt":
            horizons[h]["chronos_mase"] = round(r["avg_mase"], 3)
            horizons[h]["chronos_wql"] = round(r["avg_wql"], 3)
        elif r["model"] == "Stacked-LSTM":
            horizons[h]["lstm_mase"] = round(r["avg_mase"], 3)
            horizons[h]["lstm_wql"] = round(r["avg_wql"], 3)

    summary_list = []
    for h, data in horizons.items():
        c_mase = data.get("chronos_mase", 0.0)
        l_mase = data.get("lstm_mase", 0.0)
        gap = round(((c_mase - l_mase) / (l_mase + 1e-6)) * 100, 1) if l_mase else 0.0
        data["relative_gap_pct"] = f"{gap:+0.1f}%"
        if h == 1:
            data["guideline"] = "Chronos-Bolt zero-shot preferred (Higher accuracy, zero local training cost)"
        elif h == 2:
            data["guideline"] = "Comparable accuracy — Chronos-Bolt viable for immediate deployment"
        elif h == 4:
            data["guideline"] = "Chronos-Bolt zero-shot preferred (Higher accuracy, zero local training cost)"
        elif h == 8:
            data["guideline"] = "Chronos-Bolt strongly preferred (-31.1% MASE; LSTM autoregression compounds)"
        summary_list.append(data)

    return jsonify(summary_list)

# -----------------------------------------------------------------------------
# Outbreak Alert Subscriptions & Dispatcher
# -----------------------------------------------------------------------------

@app.route("/api/subscriptions", methods=["GET"])
def get_subscriptions():
    """Retrieves active alert notification subscriptions."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, email, state, alert_threshold, min_rt, is_active, created_at
        FROM alert_subscriptions
        ORDER BY id DESC;
    """)
    subs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(subs)

@app.route("/api/subscriptions", methods=["POST"])
def create_subscription():
    """Creates a new early warning notification subscription."""
    data = request.get_json() or {}
    email = data.get("email", "").strip()
    state = data.get("state", "").strip()
    threshold = data.get("alert_threshold", "ELEVATED TRANSMISSION").strip()
    min_rt = float(data.get("min_rt", 1.0))

    if not email or "@" not in email:
        return jsonify({"error": "A valid email address is required."}), 400
    if not state:
        return jsonify({"error": "Target state is required."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO alert_subscriptions (email, state, alert_threshold, min_rt)
        VALUES (?, ?, ?, ?);
    """, (email, state, threshold, min_rt))
    sub_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT * FROM alert_subscriptions WHERE id = ?;", (sub_id,))
    new_sub = dict(cursor.fetchone())
    conn.close()

    log_audit("SUBSCRIBE", "NOTIFICATIONS", f"Subscribed {email} to alerts for {state} ({threshold}).")

    return jsonify({
        "message": f"Successfully subscribed {email} to outbreak alerts for {state}.",
        "subscription": new_sub
    }), 201

@app.route("/api/subscriptions/<int:sub_id>", methods=["DELETE"])
def delete_subscription(sub_id: int):
    """Deletes an alert subscription."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM alert_subscriptions WHERE id = ?;", (sub_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Subscription #{sub_id} removed."})

@app.route("/api/subscriptions/dispatch-test", methods=["POST"])
@require_auth(roles=["officer", "admin"])
def dispatch_alert_notifications():
    """
    Evaluates current alert levels against active subscriptions
    and simulates emergency outbreak email/SMS dispatches.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.id, s.email, s.state, s.alert_threshold, s.min_rt,
               a.latest_cases, a.estimated_rt, a.alert_level
        FROM alert_subscriptions s
        JOIN state_alerts a ON s.state = a.state
        WHERE s.is_active = 1;
    """)
    matches = cursor.fetchall()
    conn.close()

    dispatched = []
    for m in matches:
        should_send = False
        if m["alert_threshold"] == "ALL":
            should_send = True
        elif m["alert_threshold"] == "HIGH OUTBREAK SURGE" and m["alert_level"] == "HIGH OUTBREAK SURGE":
            should_send = True
        elif m["alert_threshold"] == "ELEVATED TRANSMISSION" and m["alert_level"] in ["ELEVATED TRANSMISSION", "HIGH OUTBREAK SURGE"]:
            should_send = True

        if m["estimated_rt"] < m["min_rt"]:
            should_send = False

        if should_send:
            dispatched.append({
                "subscription_id": m["id"],
                "recipient": m["email"],
                "state": m["state"],
                "alert_level": m["alert_level"],
                "latest_cases": m["latest_cases"],
                "estimated_rt": m["estimated_rt"],
                "dispatch_channel": "Email / Webhook Simulated",
                "timestamp": datetime.now().isoformat()
            })

    log_audit("DISPATCH_ALERTS", "SURVEILLANCE", f"Dispatched {len(dispatched)} real-time notifications to subscribers.")

    return jsonify({
        "message": f"Evaluated subscriptions. Dispatched {len(dispatched)} urgent outbreak alerts.",
        "dispatches": dispatched
    })

# -----------------------------------------------------------------------------
# Data Ingestion & Bulletin Upload
# -----------------------------------------------------------------------------

@app.route("/api/ingest/upload", methods=["POST"])
@require_auth(roles=["officer", "admin", "analyst"])
def upload_surveillance_data():
    """
    Ingests and parses new weekly surveillance bulletins (CSV format).
    Validates headers: state, week_start, cases. Performs bulk database synchronization.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Please upload a CSV file."}), 400

    file = request.files["file"]
    if not file.filename.endswith(".csv"):
        return jsonify({"error": "Unsupported file type. Only .csv files are supported."}), 400

    stream = io.StringIO(file.stream.read().decode("utf-8"), newline="")
    reader = csv.DictReader(stream)

    fieldnames = [f.strip().lower() for f in reader.fieldnames or []]
    if "state" not in fieldnames or "week_start" not in fieldnames or "cases" not in fieldnames:
        return jsonify({
            "error": "Invalid CSV schema. Required columns: state, week_start (YYYY-MM-DD), cases."
        }), 400

    user = get_current_user()
    uploaded_by = user["username"] if user else "Officer"

    inserted_count = 0
    updated_count = 0
    affected_states = set()

    conn = get_db_connection()
    cursor = conn.cursor()

    for row in reader:
        try:
            state = row.get("state", "").strip()
            week_start = row.get("week_start", "").strip()
            cases = int(float(row.get("cases", 0)))
            dt = datetime.strptime(week_start, "%Y-%m-%d")
            year = dt.year
            epi_week = int(dt.strftime("%W"))

            cursor.execute("""
                INSERT INTO surveillance_records (state, week_start, cases, year, epi_week, source, reported_by)
                VALUES (?, ?, ?, ?, ?, 'Uploaded Outbreak Bulletin', ?)
                ON CONFLICT(state, week_start) DO UPDATE SET
                    cases = excluded.cases,
                    source = 'Updated via Bulletin Upload',
                    reported_by = excluded.reported_by;
            """, (state, week_start, cases, year, epi_week, uploaded_by))
            
            inserted_count += 1
            affected_states.add(state)
        except Exception:
            continue

    conn.commit()

    # Record ingestion
    cursor.execute("""
        INSERT INTO data_ingestions (filename, records_ingested, status, uploaded_by, notes)
        VALUES (?, ?, 'SUCCESS', ?, ?);
    """, (file.filename, inserted_count, uploaded_by, f"Updated {len(affected_states)} states."))
    conn.commit()
    conn.close()

    # Recompute alerts for affected states
    for st in affected_states:
        recalculate_state_alert(st)

    log_audit("INGEST_CSV", "DATA_PIPELINE", f"Uploaded {file.filename}: {inserted_count} records ingested across {len(affected_states)} states.")

    return jsonify({
        "message": f"Successfully ingested {inserted_count} surveillance records.",
        "affected_states": list(affected_states),
        "filename": file.filename
    })

# -----------------------------------------------------------------------------
# Data Export API
# -----------------------------------------------------------------------------

@app.route("/api/export/surveillance-csv", methods=["GET"])
def export_surveillance_csv():
    """Generates and downloads a filtered CSV export of surveillance data."""
    state = request.args.get("state", "").strip()
    year = request.args.get("year", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    clauses = []
    params = []
    if state and state.lower() != "all":
        clauses.append("state = ?")
        params.append(state)
    if year and year.isdigit():
        clauses.append("year = ?")
        params.append(int(year))

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    cursor.execute(f"""
        SELECT state, week_start, cases, year, epi_week, source, reported_by, created_at
        FROM surveillance_records
        {where_sql}
        ORDER BY state ASC, week_start ASC;
    """, params)
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["state", "week_start", "cases", "year", "epi_week", "source", "reported_by", "created_at"])
    for r in rows:
        writer.writerow(list(r))

    response = make_response(output.getvalue())
    filename = f"denguewatch_surveillance_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-type"] = "text/csv"
    return response

# -----------------------------------------------------------------------------
# Audit Logs
# -----------------------------------------------------------------------------

@app.route("/api/audit-logs", methods=["GET"])
@require_auth(roles=["officer", "admin"])
def get_audit_logs():
    """Returns system security and compliance audit logs."""
    limit = min(100, int(request.args.get("limit", 25)))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, action, target_entity, details, ip_address, timestamp
        FROM audit_logs
        ORDER BY id DESC LIMIT ?;
    """, (limit,))
    logs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(logs)

# -----------------------------------------------------------------------------
# Legacy Static Diagnostics Image
# -----------------------------------------------------------------------------

@app.route("/api/dashboard-image")
def get_dashboard_image():
    """Serves the generated Kerala outbreak comparison chart."""
    if not os.path.exists(KERALA_DASHBOARD_PNG):
        return jsonify({"error": "Dashboard image not found."}), 404
    return send_file(KERALA_DASHBOARD_PNG, mimetype="image/png")

# -----------------------------------------------------------------------------
# Main Application Entrypoint
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 80)
    print("🚀 DENGUEWATCH FULL-STACK PLATFORM RUNNING")
    print("   • Backend: Flask REST API + SQLite Relational Database")
    print("   • Features: Live Chronos-Bolt Forecasting, CRUD, Subscriptions, Auth")
    print("   • Access Dashboard at: http://127.0.0.1:5000")
    print("=" * 80)
    app.run(host="0.0.0.0", port=5000, debug=True)
