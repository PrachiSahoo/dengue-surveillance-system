# DengueWatch: End-to-End Full-Stack Epidemiological Surveillance & AI Forecasting Platform

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Flask 3.0](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![SQLite 3](https://img.shields.io/badge/database-SQLite%203-lightgrey.svg)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**DengueWatch** is a production-grade, end-to-end **Full-Stack Epidemiological Surveillance and Predictive Forecasting Platform**. It integrates a 10-year longitudinal dengue dataset (2015–2025) across 36 Indian States and Union Territories, benchmarks cutting-edge **Zero-Shot Time Series Foundation Models (Chronos-Bolt)** against **Supervised Stacked Quantile LSTMs**, and deploys an interactive, role-based web application.

---

## 🏗️ Full-Stack System Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CLIENT TIER (Modern Web SPA)                          │
│  • Vanilla CSS Glassmorphic Design System (Rich Dark Mode & Glow Accents)   │
│  • Chart.js Interactive Canvases (Forecasting Fans, Doughnuts, Trends)       │
│  • Executive Dashboard, AI Sandbox, CRUD Registry, Ingestion & Subscriptions│
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ RESTful HTTP / JSON / Bearer Tokens
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                    APPLICATION TIER (Flask REST API)                        │
│  • Auth & RBAC Middleware: Admin, Health Officer, Analyst, Public Visitor   │
│  • Probabilistic Forecasting Engine: Chronos-Bolt, Stacked LSTM, Ensemble   │
│  • Dynamic Outbreak Assessment: Proxy Rt and 75th/95th Percentile Scoring   │
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
- **National KPIs**: High Alert Outbreak Surges, Elevated Transmission Zones, National Average $R_t$ ($1.05$), and total surveillance volume ($20,664$ records).
- **Live Alert Ticker**: Dynamic marquee surfacing active surge regions (e.g., Tamil Nadu, Odisha, Maharashtra, Kerala).
- **State Surveillance Matrix**: Instant search and filtering by transmission severity.
- **National Epidemiological Visualizations**: Interactive doughnut distribution and top case burden bar charts.

### 2. 🔮 Live AI Forecasting Sandbox
- **Interactive Multi-Horizon Predictions**: Select any Indian State/UT and simulate forecasts across **1, 2, 4, or 8 weeks**.
- **Model Comparison**: Switch dynamically between **Chronos-Bolt Zero-Shot**, **Stacked Quantile LSTM**, and **Hybrid Ensemble**.
- **Probabilistic Fan Visualizer**: Renders historical context alongside predicted median ($p50$) and shaded confidence intervals ($p10$ to $p90$) against historical 75th/95th percentile epidemic thresholds.
- **Automated Public Health Advisory**: Generates actionable municipal guidance based on projected case trajectories.

### 3. 📈 Longitudinal State Drilldown
- Multi-year chronological case series charts with seasonal baseline thresholds.
- Key state metrics: Current cases, estimated $R_t$, 75th percentile warning line, and 95th percentile epidemic cap.

### 4. 📋 Surveillance Data Management (Full CRUD Portal)
- **Read & Filter**: Paginated tabular view with state, year, and keyword search filters.
- **Create**: Health Officers and Admins can log new weekly outbreak case reports with immediate database synchronization.
- **Update**: Edit existing records with validation.
- **Delete**: Authorized administrative record deletion with confirmation and audit tracking.
- **Export**: Instant filtered CSV export download.

### 5. 🏆 Empirical Model Benchmarks & Leaderboard
- Comprehensive evaluation across 1, 2, 4, and 8-week horizons using **MASE** (Mean Absolute Scaled Error), **WQL** (Weighted Quantile Loss), and **PPE** (Peak Prediction Error).
- **Key Takeaways**:
  - **Short-Term ($h=1$)**: Chronos-Bolt wins with **$0.643$ MASE** vs LSTM's **$0.910$ MASE** (-29.3% error gap). Zero-shot provides instant deployment without local retraining cost.
  - **Mid-Term ($h=4$)**: Model parity. Both architectures perform competitively.
  - **Long-Term ($h=8$)**: **Chronos-Bolt strongly outperforms** (-31.1% MASE reduction). Stacked-LSTM suffers from autoregressive error compounding, whereas foundation models preserve macro-trends.

### 6. 🔔 Outbreak Subscriptions & Emergency Notification Dispatcher
- Public health officers can register email endpoints for specific states and set custom $R_t$ or alert cutoffs.
- **Simulated Emergency Dispatcher**: Evaluates active subscriptions against current state alerts and triggers instant simulated alerts.

### 7. 📥 Outbreak Bulletin & Dataset Ingestion
- Drag-and-drop CSV uploader for new NCDC surveillance bulletins.
- Validates schema (`state`, `week_start`, `cases`), updates records, and automatically recomputes state $R_t$ and alert thresholds.

### 8. 🛡️ Security, Governance & Audit Trail
- Traceability log recording every login, record creation, update, deletion, and batch ingestion with IP addresses and timestamps.
- **Role-Based Access Control (RBAC)**:
  - **Admin**: Full system permissions, user management, record deletion.
  - **Health Officer**: Report cases, edit surveillance entries, trigger notification dispatches.
  - **Analyst**: Ingest bulletins, run forecasts, view benchmarks.
  - **Public Visitor**: Read-only access to surveillance dashboards and forecasts.

---

## 🚀 Quickstart & Setup Guide

### 1. Prerequisites
- Python 3.10 or higher
- Git

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/your-username/DengueWatch.git
cd "Dengue Watch"

# Create and activate virtual environment (optional)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
```

### 3. Launch the Application
```bash
python app.py
```

*The application will automatically initialize and seed the SQLite database (`denguewatch.db`) with 20,664+ surveillance records, real-time alerts, and benchmarks.*

Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 🔑 Default Evaluator Demo Accounts

For quick evaluation, click **"🔑 Switch Role / Login"** in the top navigation bar to access instant 1-click demo logins:

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
 ┣ 📜 app.py                      # Flask RESTful API server & session controller
 ┣ 📜 database.py                 # SQLite database schema, migrations, and seeding
 ┣ 📜 forecasting_service.py      # Live probabilistic forecasting & risk scoring engine
 ┣ 📜 ncdc_dengue_weekly.csv      # Standardized 10-yr longitudinal dataset (2015–2025)
 ┣ 📜 requirements.txt            # Python dependencies
 ┣ 📜 run_benchmark.py            # Deep learning benchmark engine (Chronos-Bolt vs LSTM)
 ┣ 📜 realtime_analysis.py        # Offline Rt analysis & diagnostic image generator
 ┣ 📂 static/                     # Frontend Single Page Application
 ┃ ┣ 📜 index.html               # Semantic HTML5 SPA layout & accessible components
 ┃ ┣ 📜 style.css                # Modern CSS design system (Glassmorphism & animations)
 ┃ ┗ 📜 script.js                # Client controller, Chart.js integrations & CRUD logic
 ┣ 📂 benchmark_output/           # Benchmark metrics and deployment guidelines
 ┃ ┣ 📜 benchmark_results.csv
 ┃ ┗ 📜 deployment_guidelines.csv
 ┗ 📂 realtime_reports/           # Generated alert summaries and Kerala dashboard PNG
   ┣ 📜 realtime_state_alerts.csv
   ┗ 📜 realtime_dashboard_Kerala.png
```

---

## 👤 Author & Academic Affiliation

*   **Prachi Sahoo**

*Faculty of Engineering & Technology, School of AI & Data Science, Sri Sri University.*
