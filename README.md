# DengueWatch: End-to-End Full-Stack Epidemiological Surveillance & AI Forecasting Platform

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Flask 3.0](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![SQLite 3](https://img.shields.io/badge/database-SQLite%203-lightgrey.svg)](https://www.sqlite.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-blue.svg?logo=github-actions&logoColor=white)](.github/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/Tests-Passing%20(100%25)-brightgreen.svg)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**DengueWatch** is an enterprise-grade, end-to-end **Full-Stack Epidemiological Surveillance and Predictive Forecasting Platform**. It integrates a 10-year longitudinal dengue dataset (2015–2025) across 36 Indian States and Union Territories (20,664+ records), benchmarks cutting-edge **Zero-Shot Time Series Foundation Models (Chronos-Bolt)** against **Supervised Stacked Quantile LSTMs**, deploys an **Autonomous Multi-Agent AI Advisory Engine**, and delivers an interactive, role-based glassmorphic web application.

---

## 🏗️ Full-Stack System Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CLIENT TIER (Modern Web SPA)                          │
│  • Vanilla CSS Glassmorphic Design System (Rich Dark Mode & Dynamic Glow)   │
│  • Chart.js Interactive Canvases (Probabilistic Fans, Doughnuts, Time-Series)│
│  • Executive Dashboard, AI Sandbox, CRUD Registry, Ingestion & Subscriptions│
│  • Optional React Component: frontend-react/DengueWatchApp.jsx              │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ RESTful HTTP / JSON / Bearer Tokens
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                    APPLICATION TIER (Flask REST API)                        │
│  • Auth & RBAC Middleware: Admin, Health Officer, Analyst, Public Visitor   │
│  • Probabilistic Forecasting Engine: Chronos-Bolt, Stacked LSTM, Ensemble   │
│  • Multi-Agent AI Advisory Engine: 4 Autonomous Collaborative Agents        │
│  • Dynamic Outbreak Assessment: Proxy Rt and 75th/95th Percentile Scoring   │
│  • High-Performance Caching Layer: In-Memory LRU & Redis Support            │
│  • Ingestion & Export Pipelines: CSV Parser, Bulletin Sync & CSV Exporter   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Relational Queries & Transactions
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                   PERSISTENCE TIER (SQLite Database)                        │
│  • surveillance_records: 20,664+ weekly case entries (2015–2025)            │
│  • state_alerts: Real-time dynamic Rt & epidemic thresholds for 36 states   │
│  • benchmark_metrics: MASE, WQL, and PPE across 1, 2, 4, 8 week horizons    │
│  • users: Secure SHA-256 hashed credentials & role-based profiles           │
│  • alert_subscriptions: Automated notification triggers & dispatch logs     │
│  • audit_logs: Full compliance traceability & security logging              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🌟 Key Full-Stack Capabilities

### 1. 📊 Executive Command Center
- **National KPIs**: Real-time monitoring of High Alert Outbreak Surges, Elevated Transmission Zones, National Average $R_t$ ($1.05$), and total surveillance volume ($20,664$ records).
- **Live Alert Ticker**: Dynamic marquee surfacing active surge regions (e.g., Tamil Nadu, Odisha, Maharashtra, Kerala).
- **State Surveillance Matrix**: Instant search, sorting, and multi-tier filtering by transmission severity.
- **National Epidemiological Visualizations**: Interactive doughnut distribution and top case burden bar charts.

### 2. 🔮 Live AI Forecasting Sandbox
- **Interactive Multi-Horizon Predictions**: Select any Indian State/UT and simulate forecasts across **1, 2, 4, or 8 weeks**.
- **Model Comparison**: Switch dynamically between **Chronos-Bolt Zero-Shot**, **Stacked Quantile LSTM**, and **Hybrid Ensemble**.
- **Probabilistic Fan Visualizer**: Renders historical context alongside predicted median ($p50$) and shaded confidence intervals ($p10$ to $p90$) against historical 75th/95th percentile epidemic thresholds.

### 3. 🤖 Autonomous Multi-Agent Epidemiological Advisory Engine
An autonomous 4-agent collaborative reasoning workflow (`agentic_advisor.py`) that translates probabilistic time-series metrics into actionable clinical and municipal directives:
1. **Surveillance Analyst Agent**: Evaluates velocity, historical quantiles, and $R_t$ trajectory.
2. **Resource Allocation Agent**: Calculates dynamic estimates for hospital surge beds, NS1/IgM diagnostic kits, and platelet reserves.
3. **Vector Intervention Agent**: Specifies targeted spatial ultra-low volume (ULV) fogging, larvicidal application, and source reduction intervals.
4. **Policy & Communications Agent**: Generates executive municipal briefings and citizen public health warnings.

### 4. 📈 Longitudinal State Drilldown
- Multi-year chronological case series charts with seasonal baseline thresholds.
- Key state metrics: Current cases, estimated $R_t$, 75th percentile warning line, and 95th percentile epidemic cap.

### 5. 📋 Surveillance Data Management (Full CRUD Portal)
- **Read & Filter**: Paginated tabular view with state, year, and keyword search filters.
- **Create**: Health Officers and Admins can log new weekly outbreak case reports with immediate database synchronization.
- **Update**: Edit existing records with validation.
- **Delete**: Authorized administrative record deletion with confirmation and audit tracking.
- **Export**: Instant filtered CSV export download.

### 6. 🏆 Empirical Model Benchmarks & Leaderboard
- Comprehensive evaluation across 1, 2, 4, and 8-week horizons using **MASE** (Mean Absolute Scaled Error), **WQL** (Weighted Quantile Loss), and **PPE** (Peak Prediction Error).
- **Key Takeaways**:
  - **Short-Term ($h=1$)**: Chronos-Bolt wins with **$0.643$ MASE** vs LSTM's **$0.910$ MASE** (-29.3% error gap). Zero-shot provides instant deployment without local retraining cost.
  - **Mid-Term ($h=4$)**: Model parity. Both architectures perform competitively.
  - **Long-Term ($h=8$)**: **Chronos-Bolt strongly outperforms** (-31.1% MASE reduction). Stacked-LSTM suffers from autoregressive error compounding, whereas foundation models preserve macro-trends.

### 7. 🔔 Outbreak Subscriptions & Emergency Notification Dispatcher
- Public health officers can register email endpoints for specific states and set custom $R_t$ or alert cutoffs.
- **Simulated Emergency Dispatcher**: Evaluates active subscriptions against current state alerts and triggers instant simulated alerts.

### 8. 📥 Outbreak Bulletin & Dataset Ingestion
- Drag-and-drop CSV uploader for new NCDC surveillance bulletins.
- Validates schema (`state`, `week_start`, `cases`), updates records, and automatically recomputes state $R_t$ and alert thresholds.

### 9. 🛡️ Security, Governance & Audit Trail
- Traceability log recording every login, record creation, update, deletion, and batch ingestion with IP addresses and timestamps.
- **Role-Based Access Control (RBAC)**:
  - **Admin**: Full system permissions, user management, record deletion.
  - **Health Officer**: Report cases, edit surveillance entries, trigger notification dispatches.
  - **Analyst**: Ingest bulletins, run forecasts, view benchmarks.
  - **Public Visitor**: Read-only access to surveillance dashboards and forecasts.

---

## 🚀 Quickstart & Setup Guide

### 1. Prerequisites
- Python 3.10+ or [Docker](https://www.docker.com/)
- Git

### 2. Option A: Standard Local Setup

```bash
# Clone the repository
git clone https://github.com/PrachiSahoo/research.git
cd "Dengue Watch"

# Create and activate virtual environment
python -m venv .venv

# Windows (PowerShell / Command Prompt):
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

*The application automatically initializes and seeds the SQLite database (`denguewatch.db`) with 20,664+ surveillance records, real-time alerts, and benchmarks on first startup.*

Access the platform at:
```
http://127.0.0.1:5000
```

---

### 3. Option B: Docker & Docker Compose Deployment

Run the complete multi-tier containerized stack (Flask API + Redis Caching Layer) with one command:

```bash
docker compose up --build
```

To run in detached background mode:
```bash
docker compose up -d
```

---

### 4. 🧪 Running Automated Test Suite

Execute the full automated test suite verifying database integrity, REST APIs, RBAC authentication, forecasting calculations, and the Agentic AI advisor:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 🔑 Default Evaluator Demo Accounts

Click **"🔑 Switch Role / Login"** in the top navigation bar for instant 1-click demo logins:

| Role | Username | Password | Access Privileges |
| :--- | :--- | :--- | :--- |
| **System Admin** | `admin` | `Admin@123` | Full access: CRUD, delete records, audit logs, emergency dispatches |
| **Health Officer** | `officer_kerala` | `Officer@123` | Report new cases, edit records, trigger dispatches, update alerts |
| **AI Analyst** | `analyst_ai` | `Analyst@123` | Ingest CSV bulletins, run forecast simulations, view benchmarks |
| **Public Visitor** | `public_demo` | `Public@123` | Read-only surveillance access, interactive forecasting sandbox |

---

## 📂 Project Repository Structure

```text
📦 Dengue Watch
 ┣ 📂 .github/workflows/          # Automated GitHub Actions CI/CD pipeline
 ┃ ┗ 📜 ci.yml                   # Test suite execution & container build verification
 ┣ 📂 tests/                      # Automated full-stack test suite
 ┃ ┗ 📜 test_fullstack.py         # Unit & integration tests for API, DB, RBAC & AI
 ┣ 📂 frontend-react/             # React component alternative for SPA embedding
 ┃ ┗ 📜 DengueWatchApp.jsx
 ┣ 📜 Dockerfile                  # Multi-stage secure Docker container definition
 ┣ 📜 docker-compose.yml          # Container orchestration (Web App + Redis Caching)
 ┣ 📜 .dockerignore               # Docker build exclusions
 ┣ 📜 app.py                      # Flask RESTful API server, routing & RBAC middleware
 ┣ 📜 database.py                 # SQLite database schema, migrations, seeding & queries
 ┣ 📜 forecasting_service.py      # Probabilistic forecasting & dynamic risk scoring engine
 ┣ 📜 agentic_advisor.py          # Autonomous 4-Agent collaborative public health advisor
 ┣ 📜 cache_service.py            # High-performance In-Memory LRU & Redis cache service
 ┣ 📜 ncdc_dengue_weekly.csv      # Standardized 10-yr longitudinal dataset (2015–2025)
 ┣ 📜 requirements.txt            # Python dependencies
 ┣ 📜 run_benchmark.py            # Deep learning benchmark engine (Chronos-Bolt vs LSTM)
 ┣ 📜 realtime_analysis.py        # Offline Rt analysis & diagnostic image generator
 ┣ 📂 static/                     # Frontend Single Page Application
 ┃ ┣ 📜 index.html               # Semantic HTML5 SPA layout & accessible components
 ┃ ┣ 📜 style.css                # Modern CSS design system (Glassmorphism & animations)
 ┃ ┗ 📜 script.js                # Client controller, Chart.js canvases & CRUD logic
 ┣ 📂 benchmark_output/           # Benchmark metrics and deployment guidelines
 ┃ ┣ 📜 benchmark_results.csv
 ┃ ┗ 📜 deployment_guidelines.csv
 ┗ 📂 realtime_reports/           # Generated alert summaries and Kerala dashboard PNG
   ┣ 📜 realtime_state_alerts.csv
   ┗ 📜 realtime_dashboard_Kerala.png
```

---

## 👤 Author & Academic Affiliation

* **Prachi Sahoo**
* *Faculty of Engineering & Technology, School of AI & Data Science, Sri Sri University.*

