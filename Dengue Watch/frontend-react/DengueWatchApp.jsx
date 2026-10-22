import React, { useState, useEffect, useCallback, useMemo } from 'react';

/**
 * DengueWatch React 18+ Enterprise Dashboard Component
 * Demonstrates modern React state hooks, real-time API integrations,
 * predictive sandbox controls, and responsive UI rendering.
 */
export default function DengueWatchDashboard() {
  // State Management
  const [alerts, setAlerts] = useState([]);
  const [summary, setSummary] = useState(null);
  const [selectedState, setSelectedState] = useState('Kerala');
  const [selectedHorizon, setSelectedHorizon] = useState(4);
  const [selectedModel, setSelectedModel] = useState('Chronos-Bolt');
  const [forecast, setForecast] = useState(null);
  const [agentAdvisory, setAgentAdvisory] = useState(null);
  const [agentQuery, setAgentQuery] = useState('');
  const [agentChatLog, setAgentChatLog] = useState([]);
  const [loadingForecast, setLoadingForecast] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');

  // Fetch National Alerts on Mount
  useEffect(() => {
    fetchAlerts();
    fetchSummary();
  }, []);

  const fetchAlerts = async () => {
    try {
      const res = await fetch('/api/alerts');
      const data = await res.json();
      setAlerts(data);
    } catch (err) {
      console.error('Failed to load alerts:', err);
    }
  };

  const fetchSummary = async () => {
    try {
      const res = await fetch('/api/alerts/summary');
      const data = await res.json();
      setSummary(data);
    } catch (err) {
      console.error('Failed to load summary:', err);
    }
  };

  // Run Probabilistic Forecast Simulation
  const handleRunForecast = useCallback(async () => {
    setLoadingForecast(true);
    try {
      const res = await fetch('/api/forecast/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          state: selectedState,
          horizon: selectedHorizon,
          model: selectedModel
        })
      });
      const data = await res.json();
      setForecast(data);

      // Auto-fetch Agentic AI Public Health Advisory
      const agentRes = await fetch('/api/agent/advise', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state: selectedState })
      });
      const agentData = await agentRes.json();
      setAgentAdvisory(agentData);
    } catch (err) {
      console.error('Forecast failed:', err);
    } finally {
      setLoadingForecast(false);
    }
  }, [selectedState, selectedHorizon, selectedModel]);

  // Handle Agentic Copilot Chat
  const handleSendAgentQuery = async (e) => {
    e.preventDefault();
    if (!agentQuery.trim()) return;

    const userMsg = agentQuery;
    setAgentQuery('');
    setAgentChatLog(prev => [...prev, { sender: 'user', text: userMsg }]);

    try {
      const res = await fetch('/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMsg, state: selectedState })
      });
      const data = await res.json();
      setAgentChatLog(prev => [...prev, { sender: 'agent', text: data.response }]);
    } catch (err) {
      setAgentChatLog(prev => [...prev, { sender: 'agent', text: 'Service temporarily unavailable.' }]);
    }
  };

  // Memoized Alert Calculations
  const highAlertCount = useMemo(() => {
    return alerts.filter(a => a['Epidemic Alert Level'] === 'HIGH OUTBREAK SURGE').length;
  }, [alerts]);

  return (
    <div className="denguewatch-react-root" style={{ background: '#0a0e17', color: '#f8fafc', minHeight: '100vh', padding: '2rem' }}>
      {/* Header */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0 }}>
            🦟 DengueWatch <span style={{ fontSize: '0.8rem', background: 'rgba(56,189,248,0.2)', color: '#38bdf8', padding: '3px 8px', borderRadius: '4px' }}>React 18 + AI</span>
          </h1>
          <p style={{ color: '#94a3b8', margin: '0.25rem 0 0' }}>End-to-End Epidemiological Intelligence & Foundation Model Forecasting</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button onClick={() => setActiveTab('overview')} style={{ padding: '0.5rem 1rem', background: activeTab === 'overview' ? '#0284c7' : '#1e293b', border: 'none', color: '#fff', borderRadius: '6px', cursor: 'pointer' }}>
            📊 Overview
          </button>
          <button onClick={() => setActiveTab('sandbox')} style={{ padding: '0.5rem 1rem', background: activeTab === 'sandbox' ? '#0284c7' : '#1e293b', border: 'none', color: '#fff', borderRadius: '6px', cursor: 'pointer' }}>
            🔮 AI Forecasting & Agent
          </button>
        </div>
      </header>

      {/* KPI Banner */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <div style={{ background: '#121826', padding: '1.25rem', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.08)' }}>
          <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>High Epidemic Surge</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#f87171' }}>{highAlertCount}</div>
        </div>
        <div style={{ background: '#121826', padding: '1.25rem', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.08)' }}>
          <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>National Avg Rt</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#34d399' }}>{summary?.national_avg_rt || '1.05'}</div>
        </div>
        <div style={{ background: '#121826', padding: '1.25rem', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.08)' }}>
          <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>10-Yr Surveillance Volume</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#38bdf8' }}>20,664</div>
        </div>
        <div style={{ background: '#121826', padding: '1.25rem', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.08)' }}>
          <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>Zero-Shot Lead (h=8)</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#c084fc' }}>+31.1% MASE</div>
        </div>
      </div>

      {/* Main Tab Views */}
      {activeTab === 'overview' ? (
        <div style={{ background: '#121826', padding: '1.5rem', borderRadius: '14px', border: '1px solid rgba(255,255,255,0.08)' }}>
          <h3 style={{ margin: '0 0 1rem' }}>Active State Outbreak Surveillance Table</h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94a3b8' }}>
                  <th style={{ padding: '0.75rem' }}>State/UT</th>
                  <th>Latest Cases</th>
                  <th>Estimated Rt</th>
                  <th>Alert Level</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {alerts.slice(0, 15).map((row, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                    <td style={{ padding: '0.75rem', fontWeight: 600 }}>{row.state}</td>
                    <td>{row['Latest Week Cases']}</td>
                    <td style={{ color: row['Estimated Rt'] > 1.0 ? '#f87171' : '#34d399' }}>{row['Estimated Rt']}</td>
                    <td>
                      <span style={{
                        padding: '3px 8px', borderRadius: '12px', fontSize: '0.7rem', fontWeight: 700,
                        background: row['Epidemic Alert Level'].includes('HIGH') ? 'rgba(239,68,68,0.2)' :
                          row['Epidemic Alert Level'].includes('ELEVATED') ? 'rgba(245,158,11,0.2)' : 'rgba(16,185,129,0.2)',
                        color: row['Epidemic Alert Level'].includes('HIGH') ? '#f87171' :
                          row['Epidemic Alert Level'].includes('ELEVATED') ? '#fbbf24' : '#34d399'
                      }}>
                        {row['Epidemic Alert Level']}
                      </span>
                    </td>
                    <td>
                      <button onClick={() => { setSelectedState(row.state); setActiveTab('sandbox'); }} style={{ background: 'transparent', border: '1px solid #38bdf8', color: '#38bdf8', borderRadius: '4px', padding: '2px 8px', cursor: 'pointer' }}>
                        Simulate 🔮
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div>
          {/* Controls */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', background: '#121826', padding: '1.25rem', borderRadius: '14px', border: '1px solid rgba(255,255,255,0.08)', marginBottom: '1.5rem', alignItems: 'end' }}>
            <div>
              <label style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'block', marginBottom: '0.4rem' }}>Target State</label>
              <select value={selectedState} onChange={e => setSelectedState(e.target.value)} style={{ width: '100%', background: '#0f172a', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', padding: '0.5rem', borderRadius: '6px' }}>
                {alerts.map(a => <option key={a.state} value={a.state}>{a.state}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'block', marginBottom: '0.4rem' }}>Horizon (Weeks)</label>
              <div style={{ display: 'flex', gap: '0.25rem' }}>
                {[1, 2, 4, 8].map(h => (
                  <button key={h} onClick={() => setSelectedHorizon(h)} style={{ flex: 1, padding: '0.5rem', background: selectedHorizon === h ? '#0284c7' : '#0f172a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', borderRadius: '4px', cursor: 'pointer' }}>
                    {h}W
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'block', marginBottom: '0.4rem' }}>Model Architecture</label>
              <select value={selectedModel} onChange={e => setSelectedModel(e.target.value)} style={{ width: '100%', background: '#0f172a', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', padding: '0.5rem', borderRadius: '6px' }}>
                <option value="Chronos-Bolt">Chronos-Bolt (Zero-Shot TSFM)</option>
                <option value="Stacked-LSTM">Stacked Quantile LSTM</option>
                <option value="Ensemble-Hybrid">Ensemble Hybrid</option>
              </select>
            </div>
            <div>
              <button onClick={handleRunForecast} disabled={loadingForecast} style={{ width: '100%', padding: '0.6rem', background: 'linear-gradient(135deg, #0284c7, #06b6d4)', border: 'none', color: '#fff', fontWeight: 600, borderRadius: '6px', cursor: 'pointer' }}>
                {loadingForecast ? 'Computing...' : '⚡ Generate Forecast'}
              </button>
            </div>
          </div>

          {/* Forecast & Agentic AI Split View */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
            {/* Trajectory */}
            <div style={{ background: '#121826', padding: '1.25rem', borderRadius: '14px', border: '1px solid rgba(255,255,255,0.08)' }}>
              <h3 style={{ margin: '0 0 1rem' }}>Multi-Horizon Quantile Trajectory</h3>
              {forecast ? (
                <div>
                  <div style={{ padding: '0.75rem', borderRadius: '8px', background: 'rgba(56,189,248,0.1)', border: '1px solid rgba(56,189,248,0.3)', marginBottom: '1rem' }}>
                    <strong>{forecast.risk_evaluation.projected_alert}</strong>
                    <div style={{ fontSize: '0.8rem', color: '#cbd5e1' }}>{forecast.risk_evaluation.recommendation}</div>
                  </div>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                    <thead>
                      <tr style={{ color: '#94a3b8', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                        <th style={{ padding: '0.5rem' }}>Step</th>
                        <th>Target Week</th>
                        <th>p10 (Lower)</th>
                        <th>p50 (Median)</th>
                        <th>p90 (Upper)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {forecast.forecast_points.map((pt, i) => (
                        <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                          <td style={{ padding: '0.5rem' }}>+{pt.step} Wk</td>
                          <td>{pt.week_start}</td>
                          <td style={{ color: '#94a3b8' }}>{pt.p10}</td>
                          <td style={{ fontWeight: 700, color: '#38bdf8' }}>{pt.p50}</td>
                          <td style={{ color: '#f87171' }}>{pt.p90}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div style={{ color: '#94a3b8', textAlign: 'center', padding: '3rem 0' }}>Click "Generate Forecast" to trigger prediction.</div>
              )}
            </div>

            {/* Agentic Copilot */}
            <div style={{ background: '#121826', padding: '1.25rem', borderRadius: '14px', border: '1px solid rgba(255,255,255,0.08)' }}>
              <h3 style={{ margin: '0 0 0.5rem' }}>🤖 Agentic Public Health Copilot</h3>
              <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '0 0 1rem' }}>Autonomous multi-agent protocol generating clinical resource and vector plans</p>

              {agentAdvisory && (
                <div style={{ background: '#070a12', padding: '0.85rem', borderRadius: '8px', fontSize: '0.8rem', marginBottom: '1rem', border: '1px solid rgba(255,255,255,0.08)' }}>
                  <div style={{ color: '#38bdf8', fontWeight: 600, marginBottom: '0.3rem' }}>
                    {agentAdvisory.risk_stratification.severity_tier}
                  </div>
                  <div>• Hospital Admissions: ~{agentAdvisory.clinical_logistics_plan.projected_peak_weekly_admissions} beds</div>
                  <div>• ICU Beds Target: {agentAdvisory.clinical_logistics_plan.recommended_reserved_icu_beds} beds</div>
                  <div>• Platelets Standby: {agentAdvisory.clinical_logistics_plan.platelet_concentrate_standby_units} units</div>
                </div>
              )}

              {/* Chat Log */}
              <div style={{ height: '180px', overflowY: 'auto', background: '#0a0e17', padding: '0.75rem', borderRadius: '8px', fontSize: '0.8rem', marginBottom: '0.75rem' }}>
                {agentChatLog.length === 0 ? (
                  <div style={{ color: '#64748b', textAlign: 'center', paddingTop: '2.5rem' }}>Ask questions about Rt, vector directives, or foundation models.</div>
                ) : (
                  agentChatLog.map((m, idx) => (
                    <div key={idx} style={{ marginBottom: '0.5rem', textAlign: m.sender === 'user' ? 'right' : 'left' }}>
                      <span style={{ display: 'inline-block', padding: '0.35rem 0.65rem', borderRadius: '6px', background: m.sender === 'user' ? '#0284c7' : '#1e293b', color: '#fff' }}>
                        {m.text}
                      </span>
                    </div>
                  ))
                )}
              </div>

              {/* Chat Input */}
              <form onSubmit={handleSendAgentQuery} style={{ display: 'flex', gap: '0.5rem' }}>
                <input
                  type="text"
                  value={agentQuery}
                  onChange={e => setAgentQuery(e.target.value)}
                  placeholder="e.g. What is the hospital bed plan?"
                  style={{ flex: 1, background: '#0f172a', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', padding: '0.5rem', borderRadius: '6px', fontSize: '0.82rem' }}
                />
                <button type="submit" style={{ padding: '0.5rem 1rem', background: '#06b6d4', border: 'none', color: '#fff', borderRadius: '6px', cursor: 'pointer', fontWeight: 600 }}>
                  Ask
                </button>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
