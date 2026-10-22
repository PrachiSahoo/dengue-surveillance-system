"""
Benchmarking Zero-Shot Time-Series Foundation Models vs Supervised LSTM Baselines
for Indian NCDC Dengue Outbreak Forecasting (2015–2025)

Sri Sri University — Faculty of Engineering & Technology
School of AI & Data Science (Academic Session 2026–2027)
Researcher: Prachi Sahoo
"""

import os
import argparse
import random
import warnings
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm

warnings.filterwarnings("ignore")

# -----------------------------------------------------------------------------
# 0. Global Constants & Configuration
# -----------------------------------------------------------------------------
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)

QUANTILE_LEVELS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
HORIZONS = [1, 2, 4, 8]
CONTEXT_LEN = 52
D_HIDDEN = 64

TRAIN_END = "2022-12-31"
VAL_END = "2023-12-31"

INDIAN_STATES_UTS = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir",
    "Ladakh", "Lakshadweep", "Puducherry"
]

# -----------------------------------------------------------------------------
# 1. Data Ingestion & Synthetic Generator (Section 1A & 1B)
# -----------------------------------------------------------------------------
def load_real_data(path: str) -> pd.DataFrame:
    """Loads consolidated NCDC/IDSP weekly dengue dataset from CSV."""
    df = pd.read_csv(path, parse_dates=["week_start"])
    required_cols = {"state", "week_start", "cases"}
    assert required_cols.issubset(df.columns), f"CSV must contain columns: {required_cols}"
    df = df.sort_values(["state", "week_start"]).reset_index(drop=True)
    return df

def generate_synthetic_idsp(
    start: str = "2015-01-04",
    end: str = "2025-12-28",
    seed: int = SEED
) -> pd.DataFrame:
    """
    Generates realistic synthetic NCDC/IDSP weekly dengue surveillance data:
    - Monsoon-driven non-linear surges (June-November seasonal peaks)
    - High zero-inflation during dry/winter months
    - Administrative batch-dump artifacts (reporting spikes)
    - Random missing weeks for NIL-reporting testing
    - All 36 States/UTs over the 2015-2025 study period (decade spanning)
    """
    rng = np.random.default_rng(seed)
    weeks = pd.date_range(start=start, end=end, freq="W-SUN")
    records = []

    for state in INDIAN_STATES_UTS:
        base_burden = rng.gamma(shape=2.0, scale=rng.uniform(4, 45))
        monsoon_peak_week = rng.integers(26, 42)      # ~Jul to late-Oct
        monsoon_width = rng.uniform(5, 10)
        yearly_trend = rng.uniform(-0.02, 0.05)       # Long-term drift
        reporting_dropout_p = rng.uniform(0.01, 0.06) # Missing reporting rate
        zero_inflation_p = rng.uniform(0.15, 0.50)    # Non-monsoon zero rate

        for i, wk in enumerate(weeks):
            year_frac = i / 52.0
            week_of_year = wk.isocalendar().week
            seasonal = np.exp(-0.5 * ((week_of_year - monsoon_peak_week) / monsoon_width) ** 2)
            trend = (1 + yearly_trend) ** year_frac
            lam = base_burden * seasonal * trend * rng.uniform(0.8, 1.2)

            if rng.random() < zero_inflation_p * (1.0 - seasonal):
                cases = 0.0
            else:
                cases = float(rng.poisson(max(lam, 0.01)))

            # Administrative batch-dump reporting spike
            if rng.random() < 0.015:
                cases += float(rng.poisson(lam * rng.uniform(2.5, 6.0)))

            # Missing week report
            if rng.random() < reporting_dropout_p:
                cases = np.nan

            records.append({"state": state, "week_start": wk, "cases": cases})

    df = pd.DataFrame(records)
    return df

# -----------------------------------------------------------------------------
# 2. Preprocessing Pipeline
# -----------------------------------------------------------------------------
def impute_nil_reporting(s: pd.Series, short_gap: int = 2) -> pd.Series:
    """
    Imputes missing weeks per IDSP guidelines:
    - Short gaps (<= short_gap weeks) imputed as 0 (NIL report)
    - Long gaps linearly interpolated to prevent false zero spikes in outbreaks
    """
    s = s.copy()
    is_na = s.isna()
    if not is_na.any():
        return s

    gap_id = (is_na != is_na.shift()).cumsum()
    for _, grp in s.groupby(gap_id):
        if is_na.loc[grp.index].all():
            if len(grp) <= short_gap:
                s.loc[grp.index] = 0.0

    s = s.interpolate(method="linear", limit_direction="both")
    return s.fillna(0.0)

def rolling_median_smooth(s: pd.Series, window: int = 3) -> pd.Series:
    """
    Applies a rolling 3-week median filter to remove administrative batch-dump artifacts
    while preserving true epidemic trajectory.
    """
    med = s.rolling(window=window, center=True, min_periods=1).median()
    resid = (s - med).abs()
    thresh = resid.quantile(0.97) if resid.notna().any() else np.inf
    cleaned = s.where(resid <= thresh, med)
    return cleaned

def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """Applies NIL imputation and outlier smoothing across all states."""
    out = []
    for state, g in df.groupby("state"):
        g = g.sort_values("week_start").copy()
        g["cases"] = impute_nil_reporting(g["cases"])
        g["cases"] = rolling_median_smooth(g["cases"])
        g["cases"] = g["cases"].clip(lower=0).round().astype(float)
        out.append(g)
    return pd.concat(out, ignore_index=True)

# -----------------------------------------------------------------------------
# 3. Evaluation Metrics: MASE, WQL, PPE, and Peak Timing Error
# -----------------------------------------------------------------------------
def mase(y_true: np.ndarray, y_pred: np.ndarray, y_train_history: np.ndarray, season_length: int = 52) -> float:
    """
    Mean Absolute Scaled Error (Hyndman & Koehler, 2006).
    Compares against a seasonal naive baseline (52-week lag).
    """
    y_true, y_pred, y_train_history = map(np.asarray, (y_true, y_pred, y_train_history))
    if len(y_train_history) <= season_length:
        naive_errors = np.abs(np.diff(y_train_history))
    else:
        naive_errors = np.abs(y_train_history[season_length:] - y_train_history[:-season_length])

    scale = float(naive_errors.mean()) if len(naive_errors) > 0 and float(naive_errors.mean()) > 1e-4 else 1.0
    mae = float(np.mean(np.abs(y_true - y_pred)))
    return mae / scale

def wql(y_true: np.ndarray, quantile_preds: Dict[float, np.ndarray], baseline_scale: float = 1.0) -> float:
    """
    Weighted Quantile Loss (Gneiting & Raftery, 2007).
    Proper scoring rule across all quantile predictions.
    Safely regularized for zero-inflated epidemiological series.
    """
    y_true = np.asarray(y_true)
    total_loss = 0.0
    num_quantiles = len(quantile_preds)

    for q, preds in quantile_preds.items():
        preds = np.asarray(preds)
        diff = y_true - preds
        loss = np.maximum(q * diff, (q - 1.0) * diff)
        total_loss += 2.0 * float(np.sum(loss))

    sum_y = float(np.sum(np.abs(y_true)))
    denom = num_quantiles * max(sum_y, len(y_true) * max(baseline_scale, 1.0))
    return float(total_loss / denom)

def ppe(y_true: np.ndarray, y_pred: np.ndarray) -> Tuple[float, float, int]:
    """
    Peak Prediction Error metrics for epidemiological outbreak spikes:
    - Absolute Peak Error: |max(y_true) - max(y_pred)|
    - Relative Peak Error (%): |max(y_true) - max(y_pred)| / max(max(y_true), 1.0)
    - Peak Timing Error: |argmax(y_true) - argmax(y_pred)| (in weeks)
    """
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    true_max = float(np.max(y_true)) if len(y_true) > 0 else 0.0
    pred_max = float(np.max(y_pred)) if len(y_pred) > 0 else 0.0
    abs_ppe = abs(true_max - pred_max)
    rel_ppe = abs_ppe / max(true_max, 1.0)

    true_peak_idx = int(np.argmax(y_true)) if len(y_true) > 0 else 0
    pred_peak_idx = int(np.argmax(y_pred)) if len(y_pred) > 0 else 0
    timing_err = abs(true_peak_idx - pred_peak_idx)

    return abs_ppe, rel_ppe, timing_err

# -----------------------------------------------------------------------------
# 4. Chronos-Bolt Zero-Shot Forecasting Pipeline
# -----------------------------------------------------------------------------
class ChronosModelWrapper:
    """Wrapper supporting ChronosBoltPipeline and BaseChronosPipeline."""
    def __init__(self, model_id: str = "amazon/chronos-bolt-base", device: str = "cpu"):
        self.model_id = model_id
        self.device = device
        self.pipeline = None
        self._load_pipeline()

    def _load_pipeline(self):
        print(f"Loading Chronos model '{self.model_id}' on {self.device}...")
        try:
            from chronos import ChronosBoltPipeline
            self.pipeline = ChronosBoltPipeline.from_pretrained(
                self.model_id,
                device_map=self.device,
                torch_dtype=torch.bfloat16 if self.device == "cuda" else torch.float32,
            )
        except Exception as e1:
            try:
                from chronos import BaseChronosPipeline
                self.pipeline = BaseChronosPipeline.from_pretrained(
                    self.model_id,
                    device_map=self.device,
                    torch_dtype=torch.float32,
                )
            except Exception as e2:
                raise RuntimeError(f"Could not load Chronos pipeline: {e1} | {e2}")

    def predict(
        self,
        context: np.ndarray,
        horizon: int,
        quantiles: List[float] = QUANTILE_LEVELS
    ) -> Tuple[np.ndarray, Dict[float, np.ndarray]]:

        print("\n" + "=" * 60)
        print("CHRONOS PREDICTION DEBUG")
        print("=" * 60)

        # ---------------------------------------------------------
        # Step 1: Convert context into a PyTorch tensor
        # ---------------------------------------------------------
        if isinstance(context, np.ndarray):
            ctx_tensor = torch.tensor(context, dtype=torch.float32)
        else:
            ctx_tensor = torch.as_tensor(context, dtype=torch.float32)

        # Chronos expects a batch dimension.
        # Example:
        # [52] -> [1, 52]
        if ctx_tensor.ndim == 1:
            ctx_tensor = ctx_tensor.unsqueeze(0)

        print(f"Context shape: {tuple(ctx_tensor.shape)}")
        print(f"Forecast horizon: {horizon}")
        print(f"Quantile levels: {quantiles}")
        print(f"Pipeline type: {type(self.pipeline).__name__}")

        # ---------------------------------------------------------
        # Step 2: Check that the context is valid
        # ---------------------------------------------------------
        if ctx_tensor.numel() == 0:
            raise ValueError("Chronos received an empty context.")

        if torch.isnan(ctx_tensor).any():
            raise ValueError("Chronos context contains NaN values.")

        if torch.isinf(ctx_tensor).any():
            raise ValueError("Chronos context contains infinite values.")

        print(
            f"Context range: "
            f"min={ctx_tensor.min().item():.4f}, "
            f"max={ctx_tensor.max().item():.4f}"
        )

        # ---------------------------------------------------------
        # Step 3: Use Chronos predict_quantiles()
        # ---------------------------------------------------------
        if hasattr(self.pipeline, "predict_quantiles"):

            print("\nCalling Chronos predict_quantiles()...")

            try:
                try:
                    result = self.pipeline.predict_quantiles(
                        inputs=ctx_tensor,
                        prediction_length=horizon,
                        quantile_levels=quantiles,
                    )
                except TypeError:
                    try:
                        result = self.pipeline.predict_quantiles(
                            context=ctx_tensor,
                            prediction_length=horizon,
                            quantile_levels=quantiles,
                        )
                    except TypeError:
                        result = self.pipeline.predict_quantiles(
                            ctx_tensor,
                            prediction_length=horizon,
                            quantile_levels=quantiles,
                        )

                print("predict_quantiles() completed successfully.")
                print(f"Returned object type: {type(result)}")

            except Exception as e:
                print("\nChronos predict_quantiles() FAILED.")
                print(f"Error type: {type(e).__name__}")
                print(f"Error message: {e}")

                raise RuntimeError(
                    "\nChronos prediction failed.\n"
                    "The original error is shown above.\n"
                    "This error was previously being hidden by "
                    "`except Exception: pass`."
                ) from e

            # -----------------------------------------------------
            # Step 4: Extract quantiles and mean
            # -----------------------------------------------------
            if isinstance(result, tuple):
                quantile_output, mean_output = result

                print(
                    f"Quantile output type: {type(quantile_output)}"
                )
                print(
                    f"Mean output type: {type(mean_output)}"
                )

            else:
                quantile_output = result
                mean_output = None

                print("Chronos returned only quantile output.")

            # -----------------------------------------------------
            # Step 5: Convert output to tensor if necessary
            # -----------------------------------------------------
            if isinstance(quantile_output, np.ndarray):
                quantile_output = torch.from_numpy(quantile_output)

            elif isinstance(quantile_output, list):
                quantile_output = torch.tensor(
                    np.asarray(quantile_output),
                    dtype=torch.float32
                )

            if mean_output is not None:

                if isinstance(mean_output, np.ndarray):
                    mean_output = torch.from_numpy(mean_output)

                elif isinstance(mean_output, list):
                    mean_output = torch.tensor(
                        np.asarray(mean_output),
                        dtype=torch.float32
                    )

            print(
                f"Quantile output shape: "
                f"{tuple(quantile_output.shape)}"
            )

            if mean_output is not None:
                print(
                    f"Mean output shape: "
                    f"{tuple(mean_output.shape)}"
                )

            # -----------------------------------------------------
            # Step 6: Make sure quantile output is 3-dimensional
            # -----------------------------------------------------
            if quantile_output.ndim != 3:

                raise RuntimeError(
                    "Unexpected Chronos quantile output shape: "
                    f"{tuple(quantile_output.shape)}. "
                    "Expected a 3-dimensional tensor."
                )

            # -----------------------------------------------------
            # Step 7: Chronos-Bolt normally returns:
            #
            # [batch_size, prediction_length, num_quantiles]
            #
            # Example:
            # [1, 8, 9]
            #
            # -----------------------------------------------------
            if (
                quantile_output.shape[0] == ctx_tensor.shape[0]
                and quantile_output.shape[1] == horizon
                and quantile_output.shape[2] == len(quantiles)
            ):

                print(
                    "Detected format: "
                    "[batch, horizon, quantiles]"
                )

                q_preds = {}

                for i, q in enumerate(quantiles):
                    q_preds[q] = (
                        quantile_output[0, :, i]
                        .detach()
                        .cpu()
                        .numpy()
                    )

            # -----------------------------------------------------
            # Step 8: Handle alternative format:
            #
            # [batch_size, num_quantiles, prediction_length]
            #
            # -----------------------------------------------------
            elif (
                quantile_output.shape[0] == ctx_tensor.shape[0]
                and quantile_output.shape[1] == len(quantiles)
                and quantile_output.shape[2] == horizon
            ):

                print(
                    "Detected format: "
                    "[batch, quantiles, horizon]"
                )

                q_preds = {}

                for i, q in enumerate(quantiles):
                    q_preds[q] = (
                        quantile_output[0, i, :]
                        .detach()
                        .cpu()
                        .numpy()
                    )

            else:

                raise RuntimeError(
                    "Chronos returned an unexpected tensor shape.\n"
                    f"Shape received: {tuple(quantile_output.shape)}\n"
                    f"Expected either:\n"
                    f"  [batch, horizon, quantiles] = "
                    f"[{ctx_tensor.shape[0]}, {horizon}, "
                    f"{len(quantiles)}]\n"
                    f"or:\n"
                    f"  [batch, quantiles, horizon] = "
                    f"[{ctx_tensor.shape[0]}, {len(quantiles)}, "
                    f"{horizon}]"
                )

            # -----------------------------------------------------
            # Step 9: Get point forecast
            #
            # Prefer Chronos mean if available.
            # Otherwise use the 0.5 quantile (median).
            # -----------------------------------------------------
            if mean_output is not None:

                mean_array = (
                    mean_output.detach()
                    .cpu()
                    .numpy()
                )

                point_pred = np.squeeze(mean_array)

                print("Using Chronos mean as point forecast.")

            elif 0.5 in q_preds:

                point_pred = q_preds[0.5]

                print(
                    "Chronos mean unavailable. "
                    "Using 0.5 quantile as point forecast."
                )

            else:

                middle_index = len(quantiles) // 2

                point_pred = q_preds[
                    quantiles[middle_index]
                ]

                print(
                    "0.5 quantile unavailable. "
                    "Using middle quantile as point forecast."
                )

            # -----------------------------------------------------
            # Step 10: Force correct shape
            # -----------------------------------------------------
            point_pred = np.asarray(point_pred).reshape(-1)

            for q in q_preds:
                q_preds[q] = np.asarray(
                    q_preds[q]
                ).reshape(-1)

            # -----------------------------------------------------
            # Step 11: Verify final forecast length
            # -----------------------------------------------------
            if len(point_pred) != horizon:

                raise RuntimeError(
                    "Point forecast has the wrong length.\n"
                    f"Expected: {horizon}\n"
                    f"Received: {len(point_pred)}"
                )

            for q, values in q_preds.items():

                if len(values) != horizon:

                    raise RuntimeError(
                        f"Quantile {q} has the wrong length.\n"
                        f"Expected: {horizon}\n"
                        f"Received: {len(values)}"
                    )

            # -----------------------------------------------------
            # Step 12: Print final forecast
            # -----------------------------------------------------
            print("\nChronos prediction successful.")
            print(f"Point forecast shape: {point_pred.shape}")

            print("\nPoint forecast:")
            print(point_pred)

            print("\nQuantile forecasts:")

            for q in quantiles:
                print(
                    f"  q={q}: "
                    f"{q_preds[q]}"
                )

            print("=" * 60 + "\n")

            return point_pred, q_preds

        # ---------------------------------------------------------
        # Fallback if predict_quantiles() does not exist
        # ---------------------------------------------------------
        print(
            "\nWARNING: This Chronos pipeline does not have "
            "`predict_quantiles()`."
        )

        print("Trying standard pipeline.predict() instead...")

        try:
            try:
                preds = self.pipeline.predict(
                    inputs=ctx_tensor,
                    prediction_length=horizon
                )
            except TypeError:
                try:
                    preds = self.pipeline.predict(
                        context=ctx_tensor,
                        prediction_length=horizon
                    )
                except TypeError:
                    preds = self.pipeline.predict(
                        ctx_tensor,
                        prediction_length=horizon
                    )

        except Exception as e:

            raise RuntimeError(
                "Chronos standard predict() also failed.\n"
                f"Error: {e}"
            ) from e

        print(
            f"Standard prediction output shape: "
            f"{tuple(preds.shape)}"
        )

        # ---------------------------------------------------------
        # Handle standard Chronos output
        # ---------------------------------------------------------
        if preds.ndim == 3:

            # [batch, quantiles, horizon]
            if (
                preds.shape[0] == ctx_tensor.shape[0]
                and preds.shape[1] == len(quantiles)
                and preds.shape[2] == horizon
            ):

                q_preds = {
                    q: preds[0, i, :]
                    .detach()
                    .cpu()
                    .numpy()
                    for i, q in enumerate(quantiles)
                }

                point_pred = q_preds.get(
                    0.5,
                    q_preds[quantiles[len(quantiles) // 2]]
                )

            # [batch, horizon, quantiles]
            elif (
                preds.shape[0] == ctx_tensor.shape[0]
                and preds.shape[1] == horizon
                and preds.shape[2] == len(quantiles)
            ):

                q_preds = {
                    q: preds[0, :, i]
                    .detach()
                    .cpu()
                    .numpy()
                    for i, q in enumerate(quantiles)
                }

                point_pred = q_preds.get(
                    0.5,
                    q_preds[quantiles[len(quantiles) // 2]]
                )

            else:

                raise RuntimeError(
                    "Unexpected standard Chronos prediction shape: "
                    f"{tuple(preds.shape)}"
                )

        else:

            point_pred = (
                np.asarray(
                    preds.detach()
                    .cpu()
                    .numpy()
                )
                .reshape(-1)
            )

            q_preds = {
                q: point_pred.copy()
                for q in quantiles
            }

        # ---------------------------------------------------------
        # Final shape check
        # ---------------------------------------------------------
        point_pred = np.asarray(point_pred).reshape(-1)

        if len(point_pred) != horizon:

            raise RuntimeError(
                "Fallback point forecast has wrong length. "
                f"Expected {horizon}, got {len(point_pred)}"
            )

        print("\nFallback Chronos prediction successful.")
        print(f"Point forecast: {point_pred}")

        return point_pred, q_preds

# -----------------------------------------------------------------------------
# 5. Supervised Stacked Quantile LSTM Baseline (dh = 64, 2 layers, Pinball Loss)
# -----------------------------------------------------------------------------
class WindowDataset(Dataset):
    def __init__(self, series: np.ndarray, context_len: int = CONTEXT_LEN, horizon: int = 1, scale_factor: float = 1.0):
        self.X, self.y = [], []
        scaled = np.log1p(series) / (scale_factor + 1e-6)
        for i in range(len(scaled) - context_len - horizon + 1):
            self.X.append(scaled[i:i + context_len])
            self.y.append(scaled[i + context_len:i + context_len + horizon])
        self.X = np.array(self.X, dtype=np.float32)
        self.y = np.array(self.y, dtype=np.float32)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

class StackedQuantileLSTM(nn.Module):
    def __init__(self, hidden_dim: int = D_HIDDEN, horizon: int = 1, quantiles: List[float] = QUANTILE_LEVELS):
        super().__init__()
        self.quantiles = quantiles
        self.horizon = horizon
        self.lstm1 = nn.LSTM(input_size=1, hidden_size=hidden_dim, batch_first=True)
        self.lstm2 = nn.LSTM(input_size=hidden_dim, hidden_size=hidden_dim, batch_first=True)
        self.head = nn.Linear(hidden_dim, horizon * len(quantiles))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [Batch, Time] -> [Batch, Time, 1]
        x = x.unsqueeze(-1)
        out, _ = self.lstm1(x)
        out, _ = self.lstm2(out)
        last_hidden = out[:, -1, :]  # [Batch, Hidden]
        preds = self.head(last_hidden)  # [Batch, Horizon * NumQuantiles]
        return preds.view(-1, self.horizon, len(self.quantiles))

def pinball_loss_fn(preds: torch.Tensor, targets: torch.Tensor, quantiles: List[float] = QUANTILE_LEVELS) -> torch.Tensor:
    # preds: [B, H, Q], targets: [B, H]
    losses = []
    for i, q in enumerate(quantiles):
        diff = targets - preds[:, :, i]
        losses.append(torch.maximum(q * diff, (q - 1.0) * diff))
    return torch.mean(torch.stack(losses))

def train_quantile_lstm(
    train_series: np.ndarray,
    val_series: np.ndarray,
    horizon: int,
    device: str = "cpu",
    epochs: int = 20,
    batch_size: int = 32,
    lr: float = 1e-3,
) -> Tuple[Optional[nn.Module], float]:
    """Trains a 2-layer Stacked Quantile LSTM on log1p normalized state series."""
    scale_factor = float(np.log1p(train_series).std() + 1e-6)
    train_ds = WindowDataset(train_series, CONTEXT_LEN, horizon, scale_factor)
    val_concat = np.concatenate([train_series[-CONTEXT_LEN:], val_series])
    val_ds = WindowDataset(val_concat, CONTEXT_LEN, horizon, scale_factor)

    if len(train_ds) < 4:
        return None, scale_factor

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    model = StackedQuantileLSTM(hidden_dim=D_HIDDEN, horizon=horizon, quantiles=QUANTILE_LEVELS).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    best_loss = float("inf")
    best_weights = None
    patience, bad_epochs = 5, 0

    for _ in range(epochs):
        model.train()
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            preds = model(xb)
            loss = pinball_loss_fn(preds, yb)
            loss.backward()
            optimizer.step()

        model.eval()
        val_losses = []
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(device), yb.to(device)
                preds = model(xb)
                val_losses.append(pinball_loss_fn(preds, yb).item())

        avg_val_loss = float(np.mean(val_losses)) if val_losses else float("inf")
        if avg_val_loss < best_loss:
            best_loss = avg_val_loss
            best_weights = {k: v.clone() for k, v in model.state_dict().items()}
            bad_epochs = 0
        else:
            bad_epochs += 1
            if bad_epochs >= patience:
                break

    if best_weights is not None:
        model.load_state_dict(best_weights)

    return model, scale_factor

# -----------------------------------------------------------------------------
# 6. Failure Diagnostics & Deployment Synthesis
# -----------------------------------------------------------------------------
def compute_quantization_score(preds: np.ndarray) -> float:
    """Evaluates prediction granularity / token discretization sparsity."""
    if len(preds) == 0:
        return np.nan
    return float(len(np.unique(np.round(preds, 2))) / len(preds))

def synthesize_deployment_guidelines(results_df: pd.DataFrame, margin_threshold: float = 0.10) -> pd.DataFrame:
    """Synthesizes deployment guidelines for state health departments."""
    rows = []
    for horizon in sorted(results_df["horizon"].unique()):
        sub = results_df[results_df.horizon == horizon]
        chronos_mase = sub[sub.model == "Chronos-Bolt"]["MASE"].mean()
        lstm_mase = sub[sub.model == "Stacked-LSTM"]["MASE"].mean()
        chronos_wql = sub[sub.model == "Chronos-Bolt"]["WQL"].mean()
        lstm_wql = sub[sub.model == "Stacked-LSTM"]["WQL"].mean()

        rel_mase_diff = (chronos_mase - lstm_mase) / (lstm_mase + 1e-6)

        if rel_mase_diff <= -margin_threshold:
            recommendation = "Chronos-Bolt zero-shot preferred (Higher accuracy, zero local training cost)"
        elif rel_mase_diff >= margin_threshold:
            recommendation = "Local Quantile LSTM recommended (Foundation model underperforms on extreme sparsity)"
        else:
            recommendation = "Comparable accuracy — Chronos-Bolt viable for immediate deployment"

        rows.append({
            "horizon_weeks": horizon,
            "Chronos-Bolt MASE": round(chronos_mase, 3),
            "Stacked-LSTM MASE": round(lstm_mase, 3),
            "Chronos-Bolt WQL": round(chronos_wql, 3),
            "Stacked-LSTM WQL": round(lstm_wql, 3),
            "Relative MASE Gap (%)": f"{rel_mase_diff * 100:+.1f}%",
            "Deployment Guideline": recommendation,
        })
    return pd.DataFrame(rows)

# -----------------------------------------------------------------------------
# 7. Main Benchmark Execution
# -----------------------------------------------------------------------------
def run_benchmark(
    chronos_model_id: str = "amazon/chronos-bolt-mini",
    states_count: Optional[int] = None,
    n_origins: int = 6,
    epochs: int = 15,
    device: str = "cpu",
    output_dir: str = "output",
    data_path: Optional[str] = None,
):
    os.makedirs(output_dir, exist_ok=True)
    print("=" * 80)
    print("SRI SRI UNIVERSITY — B.TECH FINAL YEAR RESEARCH BENCHMARK")
    print("Chronos-Bolt Foundation Model vs Supervised Stacked Quantile LSTM Baseline")
    print(f"Device: {device} | Model: {chronos_model_id} | Epochs: {epochs}")
    print("=" * 80)

    # 1. Load Data
    if data_path and os.path.exists(data_path):
        print(f"Loading real NCDC dataset from: {data_path}")
        raw_df = load_real_data(data_path)
    else:
        print("Generating synthetic IDSP surveillance dataset (2015–2025, 36 states/UTs)...")
        raw_df = generate_synthetic_idsp()

    # 2. Preprocess
    print("Applying IDSP NIL-reporting imputation & 3-week rolling median smoothing...")
    clean_df = preprocess(raw_df)

    train_df = clean_df[clean_df.week_start <= TRAIN_END]
    val_df = clean_df[(clean_df.week_start > TRAIN_END) & (clean_df.week_start <= VAL_END)]
    test_df = clean_df[clean_df.week_start > VAL_END]

    print(f"Dataset Split: Train ({train_df.week_start.nunique()} wks) | "
          f"Val ({val_df.week_start.nunique()} wks) | Test ({test_df.week_start.nunique()} wks)")

    # 3. Load Foundation Model
    chronos_wrapper = ChronosModelWrapper(model_id=chronos_model_id, device=device)

    # 4. Evaluation Loop
    states = clean_df.state.unique().tolist()
    if states_count and states_count < len(states):
        states = states[:states_count]

    results = []
    print(f"\nRunning benchmark across {len(states)} states/UTs at horizons {HORIZONS}...")

    for state in tqdm(states, desc="Evaluating States"):
        s_train = train_df[train_df.state == state].sort_values("week_start")["cases"].values
        s_val = val_df[val_df.state == state].sort_values("week_start")["cases"].values
        s_test = test_df[test_df.state == state].sort_values("week_start")["cases"].values
        full_history_pre_test = np.concatenate([s_train, s_val])

        if len(s_test) < max(HORIZONS) + n_origins:
            continue

        for horizon in HORIZONS:
            lstm_model, scale_factor = train_quantile_lstm(
                s_train, s_val, horizon=horizon, device=device, epochs=epochs
            )
            if lstm_model is None:
                continue
            lstm_model.eval()

            origins = np.linspace(0, len(s_test) - horizon - 1, n_origins).astype(int)
            for origin in origins:
                context = np.concatenate([full_history_pre_test, s_test[:origin]])[-CONTEXT_LEN:]
                y_true = s_test[origin:origin + horizon]
                if len(y_true) < horizon:
                    continue

                # --- Chronos-Bolt zero-shot ---
                c_point, c_quant = chronos_wrapper.predict(context, horizon)
                c_mase = mase(y_true, c_point, full_history_pre_test)
                c_wql = wql(y_true, c_quant)
                c_abs_ppe, c_rel_ppe, c_timing = ppe(y_true, c_point)

                # --- Supervised Quantile LSTM ---
                with torch.no_grad():
                    scaled_ctx = (np.log1p(context) / scale_factor).astype(np.float32)
                    xb = torch.tensor(scaled_ctx).unsqueeze(0).to(device)
                    scaled_preds = lstm_model(xb)[0].cpu().numpy()  # [H, Q]
                    # Inverse scale
                    unscaled_preds = np.expm1(scaled_preds * scale_factor).clip(min=0.0)

                l_quant = {q: unscaled_preds[:, i] for i, q in enumerate(QUANTILE_LEVELS)}
                l_point = unscaled_preds[:, QUANTILE_LEVELS.index(0.5)]
                l_mase = mase(y_true, l_point, full_history_pre_test)
                l_wql = wql(y_true, l_quant)
                l_abs_ppe, l_rel_ppe, l_timing = ppe(y_true, l_point)

                results.append({
                    "state": state, "horizon": horizon, "origin": origin, "model": "Chronos-Bolt",
                    "MASE": c_mase, "WQL": c_wql, "PPE_Abs": c_abs_ppe, "PPE_Rel": c_rel_ppe, "Timing_Err": c_timing
                })
                results.append({
                    "state": state, "horizon": horizon, "origin": origin, "model": "Stacked-LSTM",
                    "MASE": l_mase, "WQL": l_wql, "PPE_Abs": l_abs_ppe, "PPE_Rel": l_rel_ppe, "Timing_Err": l_timing
                })

    results_df = pd.DataFrame(results)
    results_path = os.path.join(output_dir, "benchmark_results.csv")
    results_df.to_csv(results_path, index=False)
    print(f"\n[Saved] Detailed results saved to: {results_path}")

    # Summary
    summary = results_df.groupby(["model", "horizon"])[["MASE", "WQL", "PPE_Abs", "PPE_Rel", "Timing_Err"]].mean().reset_index()
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY (Averaged across rolling test origins):")
    print("=" * 60)
    print(summary.to_string(index=False))

    # Guidelines
    guidelines_df = synthesize_deployment_guidelines(results_df)
    guidelines_path = os.path.join(output_dir, "deployment_guidelines.csv")
    guidelines_df.to_csv(guidelines_path, index=False)
    print("\n" + "=" * 60)
    print("DEPLOYMENT GUIDELINES (Objective 4):")
    print("=" * 60)
    print(guidelines_df.to_string(index=False))

    # Plots
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    for ax, metric in zip(axes, ["MASE", "WQL", "PPE_Abs"]):
        sns.lineplot(data=summary, x="horizon", y=metric, hue="model", marker="o", ax=ax)
        ax.set_title(f"{metric} vs Forecast Horizon (Weeks)")
        ax.set_xlabel("Horizon (Weeks)")
    plt.tight_layout()
    plot_path = os.path.join(output_dir, "benchmark_metrics_plot.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f"[Saved] Metrics plot saved to: {plot_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Dengue Outbreak Forecasting Benchmark")
    parser.add_argument("--model", type=str, default="amazon/chronos-bolt-mini", help="Chronos model name or path")
    parser.add_argument("--states", type=int, default=None, help="Number of states to evaluate (default: all 36)")
    parser.add_argument("--origins", type=int, default=4, help="Number of rolling test origins per horizon")
    parser.add_argument("--epochs", type=int, default=15, help="LSTM training epochs per state")
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--output-dir", type=str, default="benchmark_output")
    parser.add_argument("--data-path", type=str, default=None, help="Path to real NCDC CSV file")
    args = parser.parse_args()

    run_benchmark(
        chronos_model_id=args.model,
        states_count=args.states,
        n_origins=args.origins,
        epochs=args.epochs,
        device=args.device,
        output_dir=args.output_dir,
        data_path=args.data_path,
    )
