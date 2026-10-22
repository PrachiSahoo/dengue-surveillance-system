/**
 * DengueWatch Full-Stack Client-Side Controller
 * Single Page Application Logic, Live Chart.js Visualizations,
 * Role-Based Access Control, CRUD Handlers, and Forecasting Sandbox
 */

// Global Application State
const state = {
    currentUser: null,
    token: localStorage.getItem('dengue_token') || null,
    statesList: [],
    alerts: [],
    benchmarks: [],
    activeTab: 'tab-overview',
    surveillancePage: 1,
    surveillanceTotalPages: 1,
    selectedHorizon: 4,
    charts: {
        alertDistribution: null,
        topBurden: null,
        forecast: null,
        drilldown: null,
        benchmarks: null
    }
};

// Document Ready Initialization
document.addEventListener('DOMContentLoaded', async () => {
    initNavigationTabs();
    initHorizonToggles();
    await verifyAuthSession();
    await loadInitialData();
});

// ----------------------------------------------------------------------------
// Authentication & Session Management
// ----------------------------------------------------------------------------

async function verifyAuthSession() {
    if (!state.token) {
        updateAuthUI(null);
        return;
    }

    try {
        const res = await fetch('/api/auth/me', {
            headers: { 'Authorization': `Bearer ${state.token}` }
        });
        const data = await res.json();
        if (data.authenticated && data.user) {
            state.currentUser = data.user;
            updateAuthUI(data.user);
        } else {
            handleLogout();
        }
    } catch (err) {
        console.warn('Auth verification failed:', err);
        updateAuthUI(null);
    }
}

function updateAuthUI(user) {
    const nameEl = document.getElementById('user-display-name');
    const roleEl = document.getElementById('user-role-pill');
    const logoutBtn = document.getElementById('btn-logout');

    if (user) {
        nameEl.innerText = user.full_name || user.username;
        roleEl.innerText = user.role.toUpperCase();
        roleEl.className = `role-pill role-${user.role.toLowerCase()}`;
        logoutBtn.style.display = 'inline-flex';
    } else {
        nameEl.innerText = 'Visitor';
        roleEl.innerText = 'PUBLIC';
        roleEl.className = 'role-pill role-public';
        logoutBtn.style.display = 'none';
    }
}

async function handleDemoLogin(role) {
    try {
        const res = await fetch('/api/auth/demo-login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Login failed');

        state.token = data.token;
        state.currentUser = data.user;
        localStorage.setItem('dengue_token', data.token);
        updateAuthUI(data.user);
        closeModal('modal-auth');
        showToast(`Signed in as ${data.user.role.toUpperCase()}: ${data.user.full_name}`, 'success');
        
        // Refresh tables that might have permission changes
        loadSurveillanceRecords(state.surveillancePage);
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function handleRegularLogin(e) {
    e.preventDefault();
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;

    try {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Invalid credentials');

        state.token = data.token;
        state.currentUser = data.user;
        localStorage.setItem('dengue_token', data.token);
        updateAuthUI(data.user);
        closeModal('modal-auth');
        showToast(`Welcome back, ${data.user.full_name}!`, 'success');
        loadSurveillanceRecords(state.surveillancePage);
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function handleLogout() {
    if (state.token) {
        fetch('/api/auth/logout', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${state.token}` }
        }).catch(() => {});
    }
    state.token = null;
    state.currentUser = null;
    localStorage.removeItem('dengue_token');
    updateAuthUI(null);
    showToast('You have been logged out.', 'info');
    loadSurveillanceRecords(state.surveillancePage);
}

// ----------------------------------------------------------------------------
// Navigation Tabs
// ----------------------------------------------------------------------------

function initNavigationTabs() {
    const tabs = document.querySelectorAll('.nav-tab-btn');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetId = tab.getAttribute('data-tab');
            switchTab(targetId);
        });
    });
}

function switchTab(tabId) {
    state.activeTab = tabId;

    // Update Tab Buttons
    document.querySelectorAll('.nav-tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
    });

    // Update Panes
    document.querySelectorAll('.tab-pane').forEach(pane => {
        if (pane.id === tabId) {
            pane.style.display = 'block';
        } else {
            pane.style.display = 'none';
        }
    });

    // Trigger lazy loads
    if (tabId === 'tab-forecast') {
        if (!state.charts.forecast) executeForecastSimulation();
    } else if (tabId === 'tab-drilldown') {
        loadStateDrilldown();
    } else if (tabId === 'tab-surveillance') {
        loadSurveillanceRecords(state.surveillancePage);
    } else if (tabId === 'tab-benchmarks') {
        loadBenchmarksData();
    } else if (tabId === 'tab-subscriptions') {
        loadSubscriptions();
    } else if (tabId === 'tab-audit') {
        loadAuditLogs();
    }
}

function initHorizonToggles() {
    const buttons = document.querySelectorAll('.horizon-btn');
    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            buttons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.selectedHorizon = parseInt(btn.getAttribute('data-horizon'));
            executeForecastSimulation();
        });
    });
}

// ----------------------------------------------------------------------------
// Initial Data Loading
// ----------------------------------------------------------------------------

async function loadInitialData() {
    try {
        // Fetch states list
        const statesRes = await fetch('/api/surveillance/states');
        state.statesList = await statesRes.json();
        populateStateDropdowns(state.statesList);

        // Fetch real-time alerts
        await loadAlertsAndKPIs();
    } catch (err) {
        console.error('Failed to load initial dataset:', err);
    }
}

function populateStateDropdowns(states) {
    const dropdownIds = [
        'forecast-state-select',
        'drilldown-state-select',
        'crud-state-filter',
        'sub-state',
        'record-state'
    ];

    dropdownIds.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;

        // Preserve "all" option if it exists
        const hasAll = el.querySelector('option[value="all"]');
        el.innerHTML = hasAll ? '<option value="all">All States</option>' : '';

        states.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.state;
            opt.innerText = s.state;
            el.appendChild(opt);
        });

        // Set default selection
        if (id === 'forecast-state-select' || id === 'drilldown-state-select') {
            el.value = 'Kerala';
        }
    });
}

// ----------------------------------------------------------------------------
// TAB 1: Executive Overview & State Matrix
// ----------------------------------------------------------------------------

async function loadAlertsAndKPIs() {
    try {
        const [alertsRes, summaryRes] = await Promise.all([
            fetch('/api/alerts'),
            fetch('/api/alerts/summary')
        ]);

        state.alerts = await alertsRes.json();
        const summary = await summaryRes.json();

        // Update KPIs
        document.getElementById('kpi-high-alert').innerText = summary.high_alert_states || 0;
        document.getElementById('kpi-elevated-alert').innerText = summary.elevated_states || 0;
        document.getElementById('kpi-national-rt').innerText = parseFloat(summary.national_avg_rt || 1.0).toFixed(2);

        // Update Alert Ticker
        const highStates = state.alerts.filter(a => a['Epidemic Alert Level'] === 'HIGH OUTBREAK SURGE');
        const elevatedStates = state.alerts.filter(a => a['Epidemic Alert Level'] === 'ELEVATED TRANSMISSION');

        if (highStates.length > 0 || elevatedStates.length > 0) {
            const surgeNames = highStates.map(s => `🔴 ${s.state} (${s['Latest Week Cases']} cases, Rt=${s['Estimated Rt']})`).join(' | ');
            const elevatedNames = elevatedStates.slice(0, 4).map(s => `🟠 ${s.state} (Rt=${s['Estimated Rt']})`).join(' | ');
            document.getElementById('alert-ticker-text').innerHTML = `
                <strong>Active Surge Alert:</strong> ${surgeNames || 'None'} &nbsp;|&nbsp; <strong>Elevated Watch:</strong> ${elevatedNames}
            `;
        } else {
            document.getElementById('alert-ticker-text').innerText = '✅ All 36 States and Union Territories reporting within stable historical baseline transmission limits.';
        }

        renderStateAlertsTable(state.alerts);
        renderOverviewCharts(state.alerts);
    } catch (err) {
        console.error('Error fetching alerts:', err);
    }
}

function renderStateAlertsTable(alerts) {
    const tbody = document.getElementById('state-alerts-tbody');
    tbody.innerHTML = '';

    if (!alerts || alerts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No matching state alerts found.</td></tr>';
        return;
    }

    alerts.forEach(row => {
        const tr = document.createElement('tr');
        const level = row['Epidemic Alert Level'] || 'STABLE BASELINE';
        let badgeClass = 'status-stable';
        if (level.includes('HIGH')) badgeClass = 'status-high';
        else if (level.includes('ELEVATED')) badgeClass = 'status-elevated';

        tr.innerHTML = `
            <td><strong>${row.state}</strong></td>
            <td style="font-family:var(--font-mono); font-weight:600;">${row['Latest Week Cases']}</td>
            <td style="font-family:var(--font-mono); color:${parseFloat(row['Estimated Rt']) > 1.0 ? '#f87171' : '#34d399'};">
                ${parseFloat(row['Estimated Rt']).toFixed(2)}
            </td>
            <td><span class="status-badge ${badgeClass}">${level}</span></td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="drilldownToState('${row.state}')">
                    Analyze 🔍
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function filterAlertsTable() {
    const search = document.getElementById('alert-search-input').value.toLowerCase();
    const level = document.getElementById('alert-level-select').value;

    const filtered = state.alerts.filter(row => {
        const matchesSearch = row.state.toLowerCase().includes(search);
        const matchesLevel = level === 'all' || row['Epidemic Alert Level'] === level;
        return matchesSearch && matchesLevel;
    });

    renderStateAlertsTable(filtered);
}

function drilldownToState(stateName) {
    const select = document.getElementById('drilldown-state-select');
    if (select) select.value = stateName;
    switchTab('tab-drilldown');
}

function renderOverviewCharts(alerts) {
    // 1. Alert Distribution Doughnut Chart
    const counts = {
        high: alerts.filter(a => a['Epidemic Alert Level'] === 'HIGH OUTBREAK SURGE').length,
        elevated: alerts.filter(a => a['Epidemic Alert Level'] === 'ELEVATED TRANSMISSION').length,
        stable: alerts.filter(a => a['Epidemic Alert Level'] === 'STABLE BASELINE').length
    };

    const ctxDist = document.getElementById('chart-alert-distribution').getContext('2d');
    if (state.charts.alertDistribution) state.charts.alertDistribution.destroy();

    state.charts.alertDistribution = new Chart(ctxDist, {
        type: 'doughnut',
        data: {
            labels: ['High Surge', 'Elevated Watch', 'Stable Baseline'],
            datasets: [{
                data: [counts.high, counts.elevated, counts.stable],
                backgroundColor: ['#ef4444', '#f59e0b', '#10b981'],
                borderColor: '#0f172a',
                borderWidth: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 11 } } }
            },
            cutout: '65%'
        }
    });

    // 2. Top Case Burden States Bar Chart
    const topStates = [...alerts].sort((a, b) => b['Latest Week Cases'] - a['Latest Week Cases']).slice(0, 6);
    const ctxBurden = document.getElementById('chart-top-burden').getContext('2d');
    if (state.charts.topBurden) state.charts.topBurden.destroy();

    state.charts.topBurden = new Chart(ctxBurden, {
        type: 'bar',
        data: {
            labels: topStates.map(s => s.state),
            datasets: [{
                label: 'Latest Week Cases',
                data: topStates.map(s => s['Latest Week Cases']),
                backgroundColor: 'rgba(56, 189, 248, 0.8)',
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { display: false } },
                y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } }
            }
        }
    });
}

// ----------------------------------------------------------------------------
// TAB 2: AI Forecasting Sandbox
// ----------------------------------------------------------------------------

async function executeForecastSimulation() {
    const targetState = document.getElementById('forecast-state-select').value || 'Kerala';
    const model = document.getElementById('forecast-model-select').value;
    const horizon = state.selectedHorizon || 4;
    const btn = document.getElementById('btn-run-forecast');

    btn.disabled = true;
    btn.innerText = 'Calculating...';

    try {
        const res = await fetch('/api/forecast/predict', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(state.token ? { 'Authorization': `Bearer ${state.token}` } : {})
            },
            body: JSON.stringify({ state: targetState, horizon: horizon, model: model })
        });

        const forecast = await res.json();
        renderForecastChart(forecast);
        renderForecastTable(forecast);
        renderForecastGuidance(forecast);
    } catch (err) {
        showToast(`Simulation failed: ${err.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.innerText = '⚡ Generate Forecast';
    }
}

function renderForecastChart(forecast) {
    const ctx = document.getElementById('chart-forecast-sandbox').getContext('2d');
    if (state.charts.forecast) state.charts.forecast.destroy();

    const contextData = forecast.context_data || [];
    const forecastPoints = forecast.forecast_points || [];

    const labels = [
        ...contextData.map(d => d.week_start),
        ...forecastPoints.map(d => d.week_start)
    ];

    const historicalValues = contextData.map(d => d.cases);
    const lastHistoricalVal = historicalValues[historicalValues.length - 1];

    // Align forecast points directly following the historical series
    const p10Data = new Array(contextData.length - 1).fill(null).concat([lastHistoricalVal, ...forecastPoints.map(f => f.p10)]);
    const p50Data = new Array(contextData.length - 1).fill(null).concat([lastHistoricalVal, ...forecastPoints.map(f => f.p50)]);
    const p90Data = new Array(contextData.length - 1).fill(null).concat([lastHistoricalVal, ...forecastPoints.map(f => f.p90)]);

    const p75 = forecast.epidemic_thresholds.p75;
    const p95 = forecast.epidemic_thresholds.p95;

    state.charts.forecast = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Historical Reported Cases',
                    data: historicalValues.concat(new Array(forecastPoints.length).fill(null)),
                    borderColor: '#94a3b8',
                    backgroundColor: '#94a3b8',
                    borderWidth: 2,
                    pointRadius: 3,
                    tension: 0.2
                },
                {
                    label: `${forecast.model_name} Median Forecast (p50)`,
                    data: p50Data,
                    borderColor: '#38bdf8',
                    backgroundColor: '#38bdf8',
                    borderWidth: 3,
                    borderDash: [5, 4],
                    pointRadius: 4,
                    tension: 0.3
                },
                {
                    label: 'Forecast Upper Bound (p90)',
                    data: p90Data,
                    borderColor: 'rgba(56, 189, 248, 0.4)',
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: false,
                    tension: 0.3
                },
                {
                    label: 'Confidence Interval Fan (p10–p90)',
                    data: p10Data,
                    borderColor: 'rgba(56, 189, 248, 0.4)',
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: '-1', // Fill between p90 and p10
                    backgroundColor: 'rgba(56, 189, 248, 0.15)',
                    tension: 0.3
                },
                {
                    label: `75th Pctile Threshold (${p75})`,
                    data: new Array(labels.length).fill(p75),
                    borderColor: 'rgba(245, 158, 11, 0.65)',
                    borderWidth: 1.5,
                    borderDash: [8, 4],
                    pointRadius: 0,
                    fill: false
                },
                {
                    label: `95th Pctile Epidemic Surge Cap (${p95})`,
                    data: new Array(labels.length).fill(p95),
                    borderColor: 'rgba(239, 68, 68, 0.8)',
                    borderWidth: 1.5,
                    borderDash: [4, 4],
                    pointRadius: 0,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'top', labels: { color: '#cbd5e1', font: { size: 11 } } },
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            if (ctx.raw === null) return null;
                            return `${ctx.dataset.label}: ${Math.round(ctx.raw)} cases`;
                        }
                    }
                }
            },
            scales: {
                x: { ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.04)' } },
                y: { beginAtZero: true, ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.05)' } }
            }
        }
    });
}

function renderForecastTable(forecast) {
    const tbody = document.querySelector('#forecast-quantiles-table tbody');
    tbody.innerHTML = '';

    forecast.forecast_points.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="font-family:var(--font-mono); font-weight:600;">+${row.step} Wk</td>
            <td>${row.week_start}</td>
            <td style="font-family:var(--font-mono); color:var(--text-muted);">${row.p10}</td>
            <td style="font-family:var(--font-mono); font-weight:700; color:var(--cyan-glow);">${row.p50}</td>
            <td style="font-family:var(--font-mono); color:#f87171;">${row.p90}</td>
        `;
        tbody.appendChild(tr);
    });

    // Risk Banner
    const banner = document.getElementById('forecast-risk-banner');
    const titleEl = document.getElementById('forecast-risk-title');
    const descEl = document.getElementById('forecast-risk-desc');

    banner.className = `risk-banner ${forecast.risk_evaluation.alert_theme}`;
    banner.style.display = 'flex';
    titleEl.innerText = forecast.risk_evaluation.projected_alert;
    descEl.innerText = `${forecast.risk_evaluation.recommendation} (Projected peak: ${forecast.risk_evaluation.max_projected_cases} cases).`;
}

function renderForecastGuidance(forecast) {
    const benchmarkData = forecast.benchmarks[forecast.model_name];
    document.getElementById('benchmark-mase-display').innerText = benchmarkData ? `${benchmarkData.mase} MASE` : '0.643 MASE';
    document.getElementById('benchmark-wql-display').innerText = benchmarkData ? `${benchmarkData.wql} WQL` : '1.254 WQL';
    document.getElementById('benchmark-guideline-display').innerText = forecast.deployment_recommendation;
}

// ----------------------------------------------------------------------------
// TAB 3: State Outbreak Drilldown
// ----------------------------------------------------------------------------

async function loadStateDrilldown() {
    const targetState = document.getElementById('drilldown-state-select').value || 'Kerala';

    try {
        const res = await fetch(`/api/surveillance/state-history?state=${encodeURIComponent(targetState)}&years=4`);
        const data = await res.json();

        const profile = data.alert_profile || {};
        document.getElementById('drilldown-cases').innerText = profile.latest_cases || '-';
        document.getElementById('drilldown-rt').innerText = profile.estimated_rt ? profile.estimated_rt.toFixed(2) : '-';
        document.getElementById('drilldown-p75').innerText = profile.p75_threshold || '-';
        document.getElementById('drilldown-p95').innerText = profile.p95_threshold || '-';

        const ctx = document.getElementById('chart-state-history').getContext('2d');
        if (state.charts.drilldown) state.charts.drilldown.destroy();

        const series = data.series || [];
        const labels = series.map(d => d.week_start);
        const cases = series.map(d => d.cases);
        const p75 = profile.p75_threshold || 0;
        const p95 = profile.p95_threshold || 0;

        state.charts.drilldown = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: `${targetState} Weekly Dengue Cases`,
                        data: cases,
                        borderColor: '#38bdf8',
                        backgroundColor: 'rgba(56, 189, 248, 0.1)',
                        borderWidth: 2,
                        pointRadius: 2,
                        fill: true,
                        tension: 0.2
                    },
                    {
                        label: `75th Pctile Threshold (${p75})`,
                        data: new Array(labels.length).fill(p75),
                        borderColor: 'rgba(245, 158, 11, 0.75)',
                        borderWidth: 1.5,
                        borderDash: [6, 4],
                        pointRadius: 0,
                        fill: false
                    },
                    {
                        label: `95th Pctile Epidemic Outbreak Threshold (${p95})`,
                        data: new Array(labels.length).fill(p95),
                        borderColor: 'rgba(239, 68, 68, 0.85)',
                        borderWidth: 1.5,
                        borderDash: [4, 4],
                        pointRadius: 0,
                        fill: false
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top', labels: { color: '#94a3b8' } }
                },
                scales: {
                    x: { ticks: { color: '#64748b', maxTicksLimit: 12 }, grid: { color: 'rgba(255,255,255,0.03)' } },
                    y: { beginAtZero: true, ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.05)' } }
                }
            }
        });
    } catch (err) {
        showToast('Failed to load state profile: ' + err.message, 'error');
    }
}

// ----------------------------------------------------------------------------
// TAB 4: Surveillance Registry CRUD Operations
// ----------------------------------------------------------------------------

let debounceTimer = null;
function debounceLoadSurveillance() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        loadSurveillanceRecords(1);
    }, 300);
}

async function loadSurveillanceRecords(page = 1) {
    state.surveillancePage = page;
    const search = document.getElementById('crud-search').value.trim();
    const stateFilter = document.getElementById('crud-state-filter').value;
    const yearFilter = document.getElementById('crud-year-filter').value;

    const url = `/api/surveillance?page=${page}&limit=20&search=${encodeURIComponent(search)}&state=${encodeURIComponent(stateFilter)}&year=${encodeURIComponent(yearFilter)}`;

    try {
        const res = await fetch(url);
        const data = await res.json();

        state.surveillanceTotalPages = data.total_pages || 1;
        document.getElementById('pagination-info').innerText = `Page ${data.page} of ${data.total_pages || 1} (${data.total.toLocaleString()} records)`;
        document.getElementById('crud-total-indicator').innerText = `Total: ${data.total.toLocaleString()} surveillance entries`;

        document.getElementById('btn-prev-page').disabled = page <= 1;
        document.getElementById('btn-next-page').disabled = page >= data.total_pages;

        renderSurveillanceTable(data.records);
    } catch (err) {
        showToast('Error loading surveillance data: ' + err.message, 'error');
    }
}

function changeSurveillancePage(delta) {
    const newPage = state.surveillancePage + delta;
    if (newPage >= 1 && newPage <= state.surveillanceTotalPages) {
        loadSurveillanceRecords(newPage);
    }
}

function renderSurveillanceTable(records) {
    const tbody = document.getElementById('surveillance-crud-tbody');
    tbody.innerHTML = '';

    if (!records || records.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;">No surveillance records found.</td></tr>';
        return;
    }

    const canEdit = state.currentUser && ['officer', 'admin', 'analyst'].includes(state.currentUser.role);
    const canDelete = state.currentUser && state.currentUser.role === 'admin';

    records.forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="font-family:var(--font-mono); color:var(--text-muted);">${r.id}</td>
            <td><strong>${r.state}</strong></td>
            <td>${r.week_start}</td>
            <td style="font-family:var(--font-mono); font-weight:700; color:var(--cyan-glow);">${r.cases}</td>
            <td>${r.year}</td>
            <td>Wk ${r.epi_week}</td>
            <td style="font-size:0.8rem; color:var(--text-secondary); max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${r.source}">${r.source || 'NCDC'}</td>
            <td style="font-size:0.8rem; color:var(--text-muted);">${r.reported_by || 'National System'}</td>
            <td>
                <div style="display:flex; gap:0.35rem;">
                    <button class="btn btn-secondary btn-sm" onclick="openEditRecordModal(${JSON.stringify(r).replace(/"/g, '&quot;')})" ${canEdit ? '' : 'disabled title="Requires Officer or Admin role"'}>
                        ✏️ Edit
                    </button>
                    <button class="btn btn-danger btn-sm" onclick="handleDeleteRecord(${r.id}, '${r.state}', '${r.week_start}')" ${canDelete ? '' : 'disabled title="Requires Admin role"'}>
                        🗑️
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function openAddRecordModal() {
    if (!state.currentUser || !['officer', 'admin', 'analyst'].includes(state.currentUser.role)) {
        showToast('Please log in as an Officer or Admin to report new cases.', 'info');
        openAuthModal();
        return;
    }

    document.getElementById('modal-record-title').innerText = 'Report New Surveillance Record';
    document.getElementById('record-id').value = '';
    document.getElementById('record-state').value = 'Kerala';
    document.getElementById('record-week-start').value = new Date().toISOString().split('T')[0];
    document.getElementById('record-cases').value = '';
    document.getElementById('record-source').value = 'District Health Hospital Weekly Bulletin';

    openModal('modal-record');
}

function openEditRecordModal(record) {
    document.getElementById('modal-record-title').innerText = `Edit Record #${record.id} (${record.state})`;
    document.getElementById('record-id').value = record.id;
    document.getElementById('record-state').value = record.state;
    document.getElementById('record-week-start').value = record.week_start;
    document.getElementById('record-cases').value = record.cases;
    document.getElementById('record-source').value = record.source || '';

    openModal('modal-record');
}

async function handleSaveRecord(e) {
    e.preventDefault();
    const id = document.getElementById('record-id').value;
    const recordState = document.getElementById('record-state').value;
    const weekStart = document.getElementById('record-week-start').value;
    const cases = parseInt(document.getElementById('record-cases').value);
    const source = document.getElementById('record-source').value;

    const payload = {
        state: recordState,
        week_start: weekStart,
        cases: cases,
        source: source
    };

    const isEdit = !!id;
    const url = isEdit ? `/api/surveillance/${id}` : '/api/surveillance';
    const method = isEdit ? 'PUT' : 'POST';

    try {
        const res = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${state.token}`
            },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed to save record');

        closeModal('modal-record');
        showToast(isEdit ? 'Record successfully updated.' : 'New case report logged into database.', 'success');
        loadSurveillanceRecords(state.surveillancePage);
        loadAlertsAndKPIs(); // Refresh alerts
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function handleDeleteRecord(id, stateName, date) {
    if (!confirm(`Are you sure you want to delete surveillance record #${id} (${stateName} on ${date})? This action is logged in the audit trail.`)) {
        return;
    }

    try {
        const res = await fetch(`/api/surveillance/${id}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${state.token}` }
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed to delete record');

        showToast(data.message, 'success');
        loadSurveillanceRecords(state.surveillancePage);
        loadAlertsAndKPIs();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function exportSurveillanceCSV() {
    const stateFilter = document.getElementById('crud-state-filter').value;
    const yearFilter = document.getElementById('crud-year-filter').value;
    window.location.href = `/api/export/surveillance-csv?state=${encodeURIComponent(stateFilter)}&year=${encodeURIComponent(yearFilter)}`;
}

// ----------------------------------------------------------------------------
// TAB 5: Model Benchmarks
// ----------------------------------------------------------------------------

async function loadBenchmarksData() {
    try {
        const [benchRes, summaryRes] = await Promise.all([
            fetch('/api/benchmarks'),
            fetch('/api/benchmarks/summary')
        ]);

        state.benchmarks = await benchRes.json();
        const summary = await summaryRes.json();

        renderBenchmarksChart(summary);
        renderBenchmarksTable(state.benchmarks);
    } catch (err) {
        console.error('Error loading benchmarks:', err);
    }
}

function renderBenchmarksChart(summary) {
    const ctx = document.getElementById('chart-benchmarks-comparison').getContext('2d');
    if (state.charts.benchmarks) state.charts.benchmarks.destroy();

    const labels = summary.map(s => `${s.horizon_weeks} Week${s.horizon_weeks > 1 ? 's' : ''}`);
    const chronosMase = summary.map(s => s.chronos_mase);
    const lstmMase = summary.map(s => s.lstm_mase);

    state.charts.benchmarks = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Chronos-Bolt (Zero-Shot TSFM)',
                    data: chronosMase,
                    backgroundColor: 'rgba(56, 189, 248, 0.85)',
                    borderRadius: 6
                },
                {
                    label: 'Stacked Quantile LSTM (Supervised)',
                    data: lstmMase,
                    backgroundColor: 'rgba(129, 140, 248, 0.85)',
                    borderRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top', labels: { color: '#cbd5e1' } },
                title: { display: true, text: 'Mean Absolute Scaled Error (MASE) — Lower is Better', color: '#94a3b8' }
            },
            scales: {
                x: { ticks: { color: '#94a3b8' }, grid: { display: false } },
                y: { beginAtZero: true, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } }
            }
        }
    });
}

function renderBenchmarksTable(records) {
    const tbody = document.getElementById('benchmarks-tbody');
    tbody.innerHTML = '';

    // Group rows by state and horizon
    const grouped = {};
    records.forEach(r => {
        const key = `${r.state}_${r.horizon}`;
        if (!grouped[key]) {
            grouped[key] = { state: r.state, horizon: r.horizon, chronos_mase: null, lstm_mase: null };
        }
        if (r.model === 'Chronos-Bolt') grouped[key].chronos_mase = r.MASE;
        if (r.model === 'Stacked-LSTM') grouped[key].lstm_mase = r.MASE;
    });

    const rows = Object.values(grouped).slice(0, 40);
    rows.forEach(r => {
        const tr = document.createElement('tr');
        const cMase = r.chronos_mase !== null ? r.chronos_mase.toFixed(3) : '-';
        const lMase = r.lstm_mase !== null ? r.lstm_mase.toFixed(3) : '-';

        let deltaText = '-';
        let rec = 'Chronos-Bolt zero-shot viable';
        if (r.chronos_mase !== null && r.lstm_mase !== null) {
            const gap = ((r.chronos_mase - r.lstm_mase) / r.lstm_mase) * 100;
            deltaText = `${gap > 0 ? '+' : ''}${gap.toFixed(1)}%`;
            if (gap < -10) rec = 'Chronos-Bolt Strongly Preferred';
            else if (gap > 10) rec = 'Stacked-LSTM Preferred';
            else rec = 'Model Parity';
        }

        tr.innerHTML = `
            <td><strong>${r.state}</strong></td>
            <td>${r.horizon} Wk</td>
            <td style="font-family:var(--font-mono); font-weight:600; color:var(--cyan-glow);">${cMase}</td>
            <td style="font-family:var(--font-mono); font-weight:600; color:var(--indigo-purple);">${lMase}</td>
            <td style="font-family:var(--font-mono);">${deltaText}</td>
            <td style="font-size:0.8rem; color:#e2e8f0;">${rec}</td>
        `;
        tbody.appendChild(tr);
    });
}

function filterBenchmarkTable() {
    const query = document.getElementById('benchmark-filter-input').value.toLowerCase();
    const rows = document.querySelectorAll('#benchmarks-tbody tr');
    rows.forEach(r => {
        const stateName = r.cells[0].innerText.toLowerCase();
        r.style.display = stateName.includes(query) ? '' : 'none';
    });
}

// ----------------------------------------------------------------------------
// TAB 6: Subscriptions & Emergency Dispatch
// ----------------------------------------------------------------------------

async function loadSubscriptions() {
    try {
        const res = await fetch('/api/subscriptions');
        const subs = await res.json();
        renderSubscriptionsTable(subs);
    } catch (err) {
        console.error('Error fetching subscriptions:', err);
    }
}

function renderSubscriptionsTable(subs) {
    const tbody = document.getElementById('subscriptions-tbody');
    tbody.innerHTML = '';

    if (!subs || subs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No active subscriptions.</td></tr>';
        return;
    }

    subs.forEach(s => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${s.email}</strong></td>
            <td>${s.state}</td>
            <td><span class="status-badge status-elevated">${s.alert_threshold}</span></td>
            <td style="font-family:var(--font-mono);">${s.min_rt}</td>
            <td>
                <button class="btn btn-danger btn-sm" onclick="handleDeleteSubscription(${s.id})">
                    Unsubscribe
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function handleCreateSubscription(e) {
    e.preventDefault();
    const email = document.getElementById('sub-email').value.trim();
    const targetState = document.getElementById('sub-state').value;
    const threshold = document.getElementById('sub-threshold').value;
    const minRt = parseFloat(document.getElementById('sub-min-rt').value);

    try {
        const res = await fetch('/api/subscriptions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email,
                state: targetState,
                alert_threshold: threshold,
                min_rt: minRt
            })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed to create subscription');

        showToast(data.message, 'success');
        document.getElementById('sub-email').value = '';
        loadSubscriptions();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function handleDeleteSubscription(id) {
    try {
        const res = await fetch(`/api/subscriptions/${id}`, { method: 'DELETE' });
        const data = await res.json();
        showToast(data.message, 'info');
        loadSubscriptions();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function triggerSimulatedDispatch() {
    if (!state.currentUser || !['officer', 'admin'].includes(state.currentUser.role)) {
        showToast('Please log in as a Health Officer or Admin to trigger dispatch.', 'info');
        openAuthModal();
        return;
    }

    try {
        const res = await fetch('/api/subscriptions/dispatch-test', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${state.token}` }
        });
        const data = await res.json();

        const box = document.getElementById('dispatch-results-box');
        const list = document.getElementById('dispatch-results-list');
        box.style.display = 'block';

        if (data.dispatches && data.dispatches.length > 0) {
            list.innerHTML = data.dispatches.map(d => `
                <div style="margin-bottom:0.35rem; color:#38bdf8;">
                    [${d.timestamp.split('T')[1].split('.')[0]}] DISPATCHED &rarr; <strong>${d.recipient}</strong> (${d.state}): 
                    <span style="color:#f87171;">${d.alert_level}</span> (Rt=${d.estimated_rt}, Cases=${d.latest_cases})
                </div>
            `).join('');
            showToast(`Simulated dispatch sent to ${data.dispatches.length} subscribers.`, 'success');
        } else {
            list.innerHTML = '<span style="color:#94a3b8;">No states currently match active threshold conditions.</span>';
            showToast('Evaluated subscriptions: No active thresholds breached.', 'info');
        }
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ----------------------------------------------------------------------------
// TAB 7: Ingestion & File Upload
// ----------------------------------------------------------------------------

let selectedFile = null;

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        selectedFile = file;
        document.getElementById('selected-file-info').style.display = 'block';
        document.getElementById('file-name-display').innerText = `Selected File: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    }
}

async function uploadSelectedFile() {
    if (!selectedFile) return;

    if (!state.currentUser || !['officer', 'admin', 'analyst'].includes(state.currentUser.role)) {
        showToast('Please log in as an Officer or Admin to ingest bulletins.', 'info');
        openAuthModal();
        return;
    }

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
        showToast('Uploading and parsing bulletin CSV...', 'info');
        const res = await fetch('/api/ingest/upload', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${state.token}` },
            body: formData
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Ingestion failed');

        showToast(data.message, 'success');
        document.getElementById('selected-file-info').style.display = 'none';
        selectedFile = null;
        document.getElementById('csv-file-input').value = '';

        loadAlertsAndKPIs();
        loadSurveillanceRecords(1);
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ----------------------------------------------------------------------------
// TAB 8: Audit Logs & Telemetry
// ----------------------------------------------------------------------------

async function loadAuditLogs() {
    try {
        const [auditRes, healthRes] = await Promise.all([
            fetch('/api/audit-logs', {
                headers: state.token ? { 'Authorization': `Bearer ${state.token}` } : {}
            }),
            fetch('/api/health')
        ]);

        const health = await healthRes.json();
        document.getElementById('audit-db-rows').innerText = health.database.surveillance_records.toLocaleString();

        if (auditRes.ok) {
            const logs = await auditRes.json();
            renderAuditLogsTable(logs);
        } else {
            document.getElementById('audit-logs-tbody').innerHTML = `
                <tr><td colspan="6" style="text-align:center; color:var(--text-muted);">
                    Audit logs are restricted to authenticated Health Officers and Admins.
                </td></tr>
            `;
        }
    } catch (err) {
        console.error('Error loading audit telemetry:', err);
    }
}

function renderAuditLogsTable(logs) {
    const tbody = document.getElementById('audit-logs-tbody');
    tbody.innerHTML = '';

    if (!logs || logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;">No audit events recorded.</td></tr>';
        return;
    }

    logs.forEach(l => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="font-family:var(--font-mono); font-size:0.78rem; color:var(--text-muted);">${l.timestamp}</td>
            <td><strong>${l.username}</strong></td>
            <td><span class="status-badge status-stable">${l.action}</span></td>
            <td style="font-family:var(--font-mono); font-size:0.8rem;">${l.target_entity}</td>
            <td style="font-size:0.82rem;">${l.details}</td>
            <td style="font-family:var(--font-mono); font-size:0.78rem; color:var(--text-secondary);">${l.ip_address}</td>
        `;
        tbody.appendChild(tr);
    });
}

// ----------------------------------------------------------------------------
// Modals & Floating Toasts
// ----------------------------------------------------------------------------

function openModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('open');
}

function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove('open');
}

function openAuthModal() {
    openModal('modal-auth');
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '❌';
    if (type === 'warning') icon = '⚠️';

    toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
