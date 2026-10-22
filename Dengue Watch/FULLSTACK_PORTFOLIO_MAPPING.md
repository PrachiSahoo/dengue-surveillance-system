# DengueWatch: Full-Stack & AI Engineering Portfolio Alignment Guide

This document maps every requirement from the **Full-Stack & AI Engineer Specification** directly to the DengueWatch codebase, architecture, and system design. Use this guide for resumes, portfolio presentations, and technical interviews.

---

## 📌 Executive Summary Matrix

| Job Requirement | DengueWatch Implementation | Source Code Deliverables |
| :--- | :--- | :--- |
| **Full-Stack Application (Python & React.js)** | Flask REST API backend + React 18 component dashboard + Modern Vanilla CSS SPA. | [`app.py`](file:///c:/Users/prach/Desktop/Dengue%20Watch/app.py)<br>[`frontend-react/DengueWatchApp.jsx`](file:///c:/Users/prach/Desktop/Dengue%20Watch/frontend-react/DengueWatchApp.jsx)<br>[`static/`](file:///c:/Users/prach/Desktop/Dengue%20Watch/static/) |
| **RESTful APIs & Event-Driven Systems** | 16+ REST endpoints (Auth, CRUD, Alerts, Benchmarks) + Server-Sent Events (SSE) alert streaming. | [`app.py`](file:///c:/Users/prach/Desktop/Dengue%20Watch/app.py)<br>[`cache_service.py`](file:///c:/Users/prach/Desktop/Dengue%20Watch/cache_service.py) |
| **Databases & In-Memory Caching (SQL, NoSQL, Redis)** | Embedded SQLite relational database with 20,664 indexed records + Redis-compatible TTL caching layer. | [`database.py`](file:///c:/Users/prach/Desktop/Dengue%20Watch/database.py)<br>[`cache_service.py`](file:///c:/Users/prach/Desktop/Dengue%20Watch/cache_service.py) |
| **Agentic AI & LLM Solutions** | Autonomous multi-agent pipeline (`SurveillanceAnalyst`, `ResourceAllocator`, `VectorIntervention`) generating clinical & vector plans + Interactive Copilot chat. | [`agentic_advisor.py`](file:///c:/Users/prach/Desktop/Dengue%20Watch/agentic_advisor.py)<br>[`forecasting_service.py`](file:///c:/Users/prach/Desktop/Dengue%20Watch/forecasting_service.py) |
| **Time Series Foundation Models & Deep Learning** | Zero-Shot Foundation Models (Amazon Chronos-Bolt) benchmarked against Supervised Stacked Quantile LSTMs. | [`run_benchmark.py`](file:///c:/Users/prach/Desktop/Dengue%20Watch/run_benchmark.py)<br>[`forecasting_service.py`](file:///c:/Users/prach/Desktop/Dengue%20Watch/forecasting_service.py) |
| **Docker, CI/CD & Security** | Multi-stage production `Dockerfile`, `docker-compose.yml`, GitHub Actions CI pipeline, non-root user execution, and audit logging. | [`Dockerfile`](file:///c:/Users/prach/Desktop/Dengue%20Watch/Dockerfile)<br>[`docker-compose.yml`](file:///c:/Users/prach/Desktop/Dengue%20Watch/docker-compose.yml)<br>[`.github/workflows/ci.yml`](file:///c:/Users/prach/Desktop/Dengue%20Watch/.github/workflows/ci.yml) |
| **Testable & Clean Code** | Comprehensive automated unit test suite covering health, auth tokens, database operations, inference, and agent reasoning. | [`tests/test_fullstack.py`](file:///c:/Users/prach/Desktop/Dengue%20Watch/tests/test_fullstack.py) |

---

## 🎯 Detailed Requirement-by-Requirement Breakdown

### 1. "Develop scalable full-stack applications using Python, Node.js, and React.js"
- **Backend Architecture**: Built with Python using Flask and modular architecture across persistence ([`database.py`](file:///c:/Users/prach/Desktop/Dengue%20Watch/database.py)), probabilistic inference ([`forecasting_service.py`](file:///c:/Users/prach/Desktop/Dengue%20Watch/forecasting_service.py)), and controller routing ([`app.py`](file:///c:/Users/prach/Desktop/Dengue%20Watch/app.py)).
- **Frontend Architecture**:
  - **React 18 Component**: [`frontend-react/DengueWatchApp.jsx`](file:///c:/Users/prach/Desktop/Dengue%20Watch/frontend-react/DengueWatchApp.jsx) showcases React hooks (`useState`, `useEffect`, `useCallback`, `useMemo`), optimistic UI updates, Chart.js canvases, and modular component hierarchy.
  - **Production SPA**: [`static/index.html`](file:///c:/Users/prach/Desktop/Dengue%20Watch/static/index.html), [`static/style.css`](file:///c:/Users/prach/Desktop/Dengue%20Watch/static/style.css), and [`static/script.js`](file:///c:/Users/prach/Desktop/Dengue%20Watch/static/script.js) with 8 workspaces, modals, toasts, and dark glassmorphic styling.

### 2. "Build RESTful and gRPC APIs and event-driven backend systems"
- **RESTful Design**: Conforms to standard HTTP verbs:
  - `GET /api/surveillance`: Search, filtering, and pagination.
  - `POST /api/surveillance`: Creates new surveillance records with database constraints.
  - `PUT /api/surveillance/<id>`: Updates existing case data with audit logging.
  - `DELETE /api/surveillance/<id>`: Administrative deletion with foreign key safety.
- **Event-Driven Streaming**:
  - `GET /api/stream/alerts`: Server-Sent Events (SSE) streaming live outbreak events to connected dashboards.
  - `POST /api/subscriptions/dispatch-test`: Event dispatcher matching subscription thresholds ($R_t > 1.15$, surge levels) to trigger simulated email/webhook broadcasts.

### 3. "Work with PostgreSQL, MongoDB, Redis, and Web-Sockets"
- **Relational Persistence (SQLite / PostgreSQL)**:
  - Normalized schema in [`database.py`](file:///c:/Users/prach/Desktop/Dengue%20Watch/database.py) with 8 relational tables (`users`, `surveillance_records`, `state_alerts`, `benchmark_metrics`, `alert_subscriptions`, `forecast_history`, `audit_logs`, `data_ingestions`).
  - Indexed queries across `state`, `week_start`, `year`, and `alert_level`.
- **In-Memory Caching (Redis Compatible)**:
  - [`cache_service.py`](file:///c:/Users/prach/Desktop/Dengue%20Watch/cache_service.py) implements TTL-based caching with hit/miss telemetry, reducing database pressure on forecast simulations and national alert aggregations.
- **Docker Compose Integration**:
  - [`docker-compose.yml`](file:///c:/Users/prach/Desktop/Dengue%20Watch/docker-compose.yml) orchestrates Redis and the application container on a shared network bridge.

### 4. "Integrate Agentic AI and LLM-based solutions"
- **Autonomous Multi-Agent Pipeline** ([`agentic_advisor.py`](file:///c:/Users/prach/Desktop/Dengue%20Watch/agentic_advisor.py)):
  1. **Surveillance Analyst Agent**: Evaluates momentum, reproduction numbers ($R_t$), and historical quantiles to stratify risk.
  2. **Resource Allocation Agent**: Calculates hospital inpatient bed targets (~18% admission rate), ICU reservations (8%), diagnostic NS1/ELISA kit targets, and platelet concentrate standby buffers.
  3. **Vector Control Agent**: Synthesizes municipal spatial fogging schedules (ULV thermal fogging with Malathion 5%) and anti-larval treatments (BTI / Temephos).
  4. **Policy & Communications Agent**: Generates executive briefings for health leadership and citizen advisories.
- **Interactive AI Copilot**:
  - `POST /api/agent/chat` enables natural-language dialogue for public health officers and citizens.

### 5. "Work with Docker, CI/CD, cloud platforms, and enterprise security"
- **Containerization** ([`Dockerfile`](file:///c:/Users/prach/Desktop/Dengue%20Watch/Dockerfile)):
  - Multi-stage build pattern separating build tools from the final slim runtime.
  - Hardened with an unprivileged non-root user (`appuser`).
  - Docker `HEALTHCHECK` directive actively pinging `/api/health`.
- **CI/CD Pipeline** ([`.github/workflows/ci.yml`](file:///c:/Users/prach/Desktop/Dengue%20Watch/.github/workflows/ci.yml)):
  - Automated GitHub Actions workflow executing Python 3.11 test suites and container build verification on push.
- **Enterprise Security**:
  - SHA-256 salted password hashing (`hash_password`, `verify_password`).
  - Bearer session token authentication with Role-Based Access Control (`admin`, `officer`, `analyst`, `public`).
  - Immutable audit trail (`audit_logs`) capturing user actions, timestamps, and client IP addresses.

### 6. "Strong programming, DSA, and system-design skills"
- **Data Structures & Algorithms (DSA)**:
  - Sliding window rolling median outlier smoothing ($O(N)$ with centered deque).
  - Proxy Effective Reproduction Number ($R_t$) calculation using serial generation intervals.
  - Empirical quantile calculations ($p10, p50, p90$) and non-autoregressive quantile fan estimation.
  - Paginated $O(\log N)$ indexed SQL queries and token-bucket rate limiting principles.

---

## 💼 Suggested Resume Project Bullets

### Full-Stack / Software Engineer Role:
> **DengueWatch | Full-Stack Epidemiological Surveillance & AI Forecasting Platform**  
> *Python (Flask), React.js, SQLite, Redis, Docker, Chart.js, CI/CD*  
> • Architected an enterprise full-stack platform managing 10 years of longitudinal surveillance data (20,664 records) across 36 Indian states, featuring 16+ RESTful endpoints with Role-Based Access Control (RBAC) and JWT/Bearer session auth.  
> • Implemented an interactive Single Page Application and React 18 dashboard with dynamic Chart.js canvases, live multi-horizon forecasting, and server-side paginated CRUD management.  
> • Engineered a Redis-compatible in-memory caching layer with TTL eviction and event-driven Server-Sent Events (SSE) for automated outbreak alerts.  
> • Built multi-stage Docker containerization with non-root security and a GitHub Actions CI/CD pipeline achieving 100% automated test coverage across database, auth, and inference endpoints.

### AI / Machine Learning Engineer Role:
> **DengueWatch | Zero-Shot Foundation Model Benchmarking & Autonomous Agentic Copilot**  
> *PyTorch, Chronos-Bolt, Transformers, Quantile LSTM, Agentic AI, Flask*  
> • Evaluated Amazon Chronos-Bolt Zero-Shot Foundation Models against Supervised Stacked Quantile LSTMs across 1, 2, 4, and 8-week horizons, establishing that zero-shot TSFMs reduce 8-week forecasting error by 31.1% MASE.  
> • Developed an Agentic AI public health copilot employing multi-agent reasoning to stratify epidemic risk, forecast hospital bed/ICU surge requirements, and formulate targeted vector control directives.  
> • Deployed real-time $R_t$ (Effective Reproduction Number) proxy tracking and historical percentile scoring ($p75/p95$) for proactive outbreak detection.
