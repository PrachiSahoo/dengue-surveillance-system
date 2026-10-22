"""
Real-Time Epidemiological Surveillance & Dengue Outbreak Forecasting Engine

Sri Sri University — Faculty of Engineering & Technology
School of AI & Data Science (Academic Session 2026–2027)
Lead Researcher: Prachi Sahoo

Features:
1. Real-Time Surveillance Ingestion (CSV / Live streams)
2. State-Wise Epidemic Metrics:
   - Current Burden & 4-Week Velocity (% Growth)
   - Estimated Effective Reproduction Ratio (Rt) proxy
   - Anomaly / Surge Early Warning Alerts (Normal / Elevated / High Outbreak)
3. Multi-Horizon Zero-Shot Probabilistic Forecasting (Chronos-Bolt + Stacked Quantile LSTM)
4. Comprehensive Visual Diagnostics & Dashboard Generation
"""

import os
import argparse
import warnings
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import torch
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")

from run_benchmark import (
    INDIAN_STATES_UTS,
    CONTEXT_LEN,
    QUANTILE_LEVELS,
    ChronosModelWrapper,
    preprocess,
    impute_nil_reporting,
    rolling_median_smooth,
    train_quantile_lstm,
)

def compute_effective_reproduction_number(cases: np.ndarray, serial_interval_weeks: int = 2) -> float:
    """
    Computes a simplified proxy for the Effective Reproduction Number (R_t)
    based on the ratio of recent incident cases to the generation interval history.
    R_t > 1.0 indicates expanding epidemic transmission.
    """
    if len(cases) < serial_interval_weeks * 2:
        return 1.0
    recent_mean = float(np.mean(cases[-serial_interval_weeks:]))
    prior_mean = float(np.mean(cases[-2 * serial_interval_weeks : -serial_interval_weeks]))
    if prior_mean < 1.0:
        return 1.0 if recent_mean < 1.0 else min(recent_mean / 1.0, 3.5)
    return float(np.clip(recent_mean / prior_mean, 0.1, 5.0))

def compute_outbreak_risk_score(current_cases: float, hist_p75: float, hist_p95: float, rt: float) -> Tuple[str, str]:
    """
    Classifies the current state outbreak alert level into:
    - GREEN (Normal baseline)
    - YELLOW (Moderate Surge / Watch)
    - RED (Active Epidemic Outbreak Surge)
    """
    if current_cases >= hist_p95 or (current_cases >= hist_p75 and rt > 1.3):
        return "HIGH OUTBREAK SURGE", "#d62728"
    elif current_cases >= hist_p75 or rt > 1.15:
        return "ELEVATED TRANSMISSION", "#ff7f0e"
    else:
        return "STABLE BASELINE", "#2ca02c"

def analyze_realtime_surveillance(
    df: pd.DataFrame,
    chronos_model_id: str = "amazon/chronos-bolt-mini",
    target_state: str = "Kerala",
    forecast_horizon: int = 8,
    output_dir: str = "realtime_reports",
    device: str = "cpu",
):
    os.makedirs(output_dir, exist_ok=True)
    print("=" * 85)
    print(f"REAL-TIME EPIDEMIOLOGICAL SURVEILLANCE & EARLY WARNING ANALYSIS")
    print(f"Target State: {target_state} | Forecast Horizon: {forecast_horizon} Weeks | Model: {chronos_model_id}")
    print("=" * 85)

    # 1. Clean and filter state series
    clean_df = preprocess(df)
    state_df = clean_df[clean_df.state == target_state].sort_values("week_start").reset_index(drop=True)
    if len(state_df) < CONTEXT_LEN:
        raise ValueError(f"Insufficient historical data for {target_state}. Requires at least {CONTEXT_LEN} weeks.")

    cases = state_df["cases"].values
    weeks = pd.to_datetime(state_df["week_start"]).dt.date.values

    latest_week = weeks[-1]
    latest_cases = cases[-1]
    prev_4wk_mean = np.mean(cases[-5:-1]) if len(cases) >= 5 else latest_cases
    growth_rate = ((latest_cases - prev_4wk_mean) / (prev_4wk_mean + 1e-6)) * 100.0

    # Historical quantiles (for alert thresholds)
    p75 = np.percentile(cases[:-4], 75)
    p95 = np.percentile(cases[:-4], 95)
    rt_proxy = compute_effective_reproduction_number(cases)
    status_label, status_color = compute_outbreak_risk_score(latest_cases, p75, p95, rt_proxy)

    print(f"\n--- [LATEST SURVEILLANCE REPORT: {latest_week}] ---")
    print(f"Current Reported Cases:   {latest_cases:.0f} cases")
    print(f"4-Week Baseline Mean:     {prev_4wk_mean:.1f} cases")
    print(f"4-Week Momentum Growth:   {growth_rate:+.1f}%")
    print(f"Estimated Reprod. No (Rt): {rt_proxy:.2f} {'(EXPANDING)' if rt_proxy > 1.0 else '(CONTAINED)'}")
    print(f"Outbreak Alert Status:    {status_label}")

    # 2. Compute Multi-State Real-Time Summary Table
    state_summaries = []
    for st in clean_df.state.unique():
        s_data = clean_df[clean_df.state == st].sort_values("week_start")["cases"].values
        if len(s_data) < 20:
            continue
        c_now = s_data[-1]
        c_p75 = np.percentile(s_data[:-4], 75)
        c_p95 = np.percentile(s_data[:-4], 95)
        st_rt = compute_effective_reproduction_number(s_data)
        st_status, _ = compute_outbreak_risk_score(c_now, c_p75, c_p95, st_rt)
        state_summaries.append({
            "State/UT": st,
            "Latest Week Cases": int(c_now),
            "Estimated Rt": round(st_rt, 2),
            "75th Pctile Threshold": int(c_p75),
            "95th Pctile Threshold": int(c_p95),
            "Epidemic Alert Level": st_status,
        })

    summary_df = pd.DataFrame(state_summaries).sort_values("Latest Week Cases", ascending=False)
    summary_path = os.path.join(output_dir, "realtime_state_alerts.csv")
    summary_df.to_csv(summary_path, index=False)
    print(f"\n[Saved] State-wide real-time alert summary: {summary_path}")

    # 3. Generate Real-Time Forecasts
    print(f"\nGenerating real-time {forecast_horizon}-week forecasts for {target_state}...")
    context = cases[-CONTEXT_LEN:]

    # Chronos-Bolt zero-shot forecast
    chronos = ChronosModelWrapper(model_id=chronos_model_id, device=device)
    c_point, c_quant = chronos.predict(context, horizon=forecast_horizon)

    # Supervised LSTM forecast
    lstm_model, scale_factor = train_quantile_lstm(cases[:-12], cases[-12:], horizon=forecast_horizon, device=device, epochs=15)
    if lstm_model is not None:
        with torch.no_grad():
            scaled_ctx = (np.log1p(context) / scale_factor).astype(np.float32)
            xb = torch.tensor(scaled_ctx).unsqueeze(0).to(device)
            lstm_preds = lstm_model(xb)[0].cpu().numpy()
            l_unscaled = np.expm1(lstm_preds * scale_factor).clip(min=0.0)
            l_point = l_unscaled[:, QUANTILE_LEVELS.index(0.5)]
            l_p10 = l_unscaled[:, QUANTILE_LEVELS.index(0.1)]
            l_p90 = l_unscaled[:, QUANTILE_LEVELS.index(0.9)]
    else:
        l_point, l_p10, l_p90 = c_point, c_quant[0.1], c_quant[0.9]

    # 4. Generate Comprehensive Real-Time Dashboard Plot
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.2, 1.0])

    # Top Plot: Time-Series with Zero-Shot Uncertainty Forecast
    ax0 = fig.add_subplot(gs[0, :])
    hist_x = np.arange(-CONTEXT_LEN, 0)
    future_x = np.arange(1, forecast_horizon + 1)

    ax0.plot(hist_x, context, color="#1f77b4", lw=2.2, label=f"Historical Surveillance ({target_state})")
    ax0.axhline(p75, color="#ff7f0e", ls=":", lw=1.5, label=f"75th Percentile Alert ({p75:.0f} cases)")
    ax0.axhline(p95, color="#d62728", ls="--", lw=1.5, label=f"95th Percentile Epidemic Surge ({p95:.0f} cases)")

    # Chronos-Bolt Ribbon
    ax0.plot(future_x, c_point, color="#2ca02c", marker="o", lw=2.5, label="Chronos-Bolt Median (p50)")
    ax0.fill_between(future_x, c_quant[0.1], c_quant[0.9], color="#2ca02c", alpha=0.25, label="Chronos-Bolt 80% CI (p10–p90)")

    # LSTM Line
    ax0.plot(future_x, l_point, color="#9467bd", marker="s", ls="--", lw=2.0, label="Stacked LSTM Median (p50)")

    ax0.axvline(0, color="gray", ls="-", lw=1.0)
    ax0.set_title(f"Real-Time Dengue Outbreak Surveillance & {forecast_horizon}-Week Forward Forecast — {target_state} [{status_label}]",
                  fontsize=14, fontweight="bold", color=status_color if status_color != "#2ca02c" else "black")
    ax0.set_xlabel("Weeks (Relative to Current Surveillance Origin)")
    ax0.set_ylabel("Weekly Dengue Cases")
    ax0.legend(loc="upper left")

    # Bottom Left: Top 10 High-Burden States Real-Time Alert
    ax1 = fig.add_subplot(gs[1, 0])
    top10 = summary_df.head(10)
    colors = [
        "#d62728" if x == "HIGH OUTBREAK SURGE" else "#ff7f0e" if x == "ELEVATED TRANSMISSION" else "#2ca02c"
        for x in top10["Epidemic Alert Level"]
    ]
    ax1.barh(top10["State/UT"][::-1], top10["Latest Week Cases"][::-1], color=colors[::-1])
    ax1.set_title("Current Weekly Cases across Top States", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Weekly Reported Cases")

    # Bottom Right: Estimated Rt Across States
    ax2 = fig.add_subplot(gs[1, 1])
    top_rt = summary_df.sort_values("Estimated Rt", ascending=False).head(10)
    ax2.barh(top_rt["State/UT"][::-1], top_rt["Estimated Rt"][::-1], color="#3b528b")
    ax2.axvline(1.0, color="red", ls="--", label="Rt = 1.0 (Epidemic Growth Threshold)")
    ax2.set_title("Top 10 States by Epidemic Growth Velocity (Estimated Rt)", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Effective Reproduction Ratio (Rt)")
    ax2.legend()

    plt.tight_layout()
    dashboard_path = os.path.join(output_dir, f"realtime_dashboard_{target_state.replace(' ', '_')}.png")
    plt.savefig(dashboard_path, dpi=300)
    plt.close()

    print(f"\n[Dashboard Generated] Saved to: {dashboard_path}")
    print("\n--- Real-Time Analysis Complete ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Real-Time Dengue Surveillance & Forecasting Engine")
    parser.add_argument("--data-path", type=str, default="ncdc_dengue_weekly.csv", help="Path to NCDC CSV")
    parser.add_argument("--state", type=str, default="Kerala", help="Target State for detailed dashboard")
    parser.add_argument("--horizon", type=int, default=8, help="Forecast horizon (weeks)")
    parser.add_argument("--model", type=str, default="amazon/chronos-bolt-mini", help="Chronos model ID")
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--output-dir", type=str, default="realtime_reports")
    args = parser.parse_args()

    if not os.path.exists(args.data_path):
        from extract_ncdc_dataset import compile_ncdc_surveillance_matrix
        print(f"Dataset '{args.data_path}' not found. Compiling standardized NCDC surveillance matrix...")
        compile_ncdc_surveillance_matrix(output_csv=args.data_path)

    surveillance_df = pd.read_csv(args.data_path, parse_dates=["week_start"])
    analyze_realtime_surveillance(
        df=surveillance_df,
        chronos_model_id=args.model,
        target_state=args.state,
        forecast_horizon=args.horizon,
        output_dir=args.output_dir,
        device=args.device
    )
