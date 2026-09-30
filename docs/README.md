# 🛰️ SkyGuard AI — Full Documentation

**Intelligent Real-Time Anomaly Detection System for Temperature, Pressure, and Humidity Sensors in Automatic Weather Stations (AWS)**

- **Problem Statement ID:** 26073
- **Organization:** Ministry of Earth Sciences / India Meteorological Department
- **Category:** Software
- **Theme:** Disaster Management

---

## Live Demo

- **Frontend:** https://sky-guard-ai-gules.vercel.app
- **Backend API:** https://skyguardai-production.up.railway.app
- **API Docs:** https://skyguardai-production.up.railway.app/docs
- **Repository:** https://github.com/Mrunmay-18/SkyGuardAI

### What's Live

- **Dashboard** — Real-time metrics, alerts, charts, map
- **Reality Check** — Sensor fault vs genuine weather event comparison
- **Test AI Lab** — Interactive fault injection with live detection
- **Maintenance Queue** — Prioritized work orders with acknowledge
- **AWS Network** — Station table with filters
- **Parameters** — Live charts with station filter

*Frontend works even if backend is down — cached fallback data ships with the app.*

---

## Overview

Automatic Weather Stations (AWS) continuously monitor atmospheric parameters and feed data into weather forecasting, climate monitoring, disaster management, aviation, and agriculture. However, AWS observations often contain anomalies caused by sensor malfunction, communication failures, calibration drift, power fluctuations, harsh environmental conditions, and data corruption.

**SkyGuard AI** is an AI/ML-based intelligent anomaly detection system that identifies abnormal, inconsistent, or faulty AWS observations in real time using only three parameters: **Temperature (°C)**, **Atmospheric Pressure (hPa)**, and **Relative Humidity (%)**.

Unlike traditional threshold-based quality control, SkyGuard AI uses **multi-source evidence fusion** — combining Isolation Forest, rule-based QC, spatial consistency, temporal detection, and rule-based classification — to distinguish genuine meteorological events from sensor/data anomalies while minimizing false alarms.

SkyGuard also provides **self-healing corrected values** for detected anomalies, addressing the PS grand challenge of a *"self-aware and self-healing weather observation network."*

---

## Highlights

- **Expanded evaluation** — 2,289 injected anomalies across 7 fault types
- **Fusion-based detection** — 5 evidence sources with counter-evidence suppression
- **Reality Check demo** — side-by-side sensor fault vs genuine weather comparison
- **Test AI Lab** — interactive fault injection with live detection (sub-second response)
- **Maintenance Queue** — P1/P2/P3 prioritized work orders with acknowledge buttons
- **Self-healing** — corrected values via neighbor median imputation
- **Offline fallback** — frontend remains functional when backend is unreachable
- **Reproducible results** — both evaluation sets reproducible via documented commands

---

## API Endpoints

The backend exposes 9 REST endpoints:

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Service health check |
| GET | `/api/alerts` | All detected alerts |
| GET | `/api/alerts/{station_id}` | Alerts for a specific station |
| GET | `/api/stations` | Station metadata |
| GET | `/api/observations` | Full observations feed |
| GET | `/api/observations/{station_id}` | Observations per station |
| GET | `/api/injection-fault-types` | Available fault types for demo |
| POST | `/api/inject` | Inject synthetic fault |
| GET | `/api/reality-check` | Two contrasting scenarios |

**Interactive API docs:** https://skyguardai-production.up.railway.app/docs

---

## Architecture

```
┌──────────────────────────────────────────────┐
│ Raw AWS Observations                         │
│ (temperature, pressure, humidity)            │
└──────────────────┬───────────────────────────┘
                   │
┌──────────────────▼───────────────────────────┐
│ Feature Engineering                          │
│ (raw + per-station deltas)                   │
└──────────────────┬───────────────────────────┘
                   │
       ┌───────────┼───────────┐
       │           │           │
       ▼           ▼           ▼
┌───────────┐ ┌─────────┐ ┌───────────┐
│ Isolation │ │ Rule-   │ │ Spatial   │
│ Forest    │ │ Based   │ │ Consis-   │
│ (unsuper- │ │ QC      │ │ tency     │
│ vised)    │ │         │ │ (z-score) │
└─────┬─────┘ └────┬────┘ └─────┬─────┘
      │            │            │
      │            │      ┌─────▼──────┐
      │            │      │ Temporal   │
      │            │      │ Detector   │
      │            │      │ (rolling z)│
      │            │      └─────┬──────┘
      │            │            │
      └────────────┼────────────┘
                   │
┌──────────────────▼───────────────────────────┐
│ Evidence Fusion                              │
│ (weighted combination, counter-evidence)     │
└──────────────────┬───────────────────────────┘
                   │
┌──────────────────▼───────────────────────────┐
│ Anomaly Classification                       │
│ (Spike / Drop / Frozen / Drift / Comm / etc) │
└──────────────────┬───────────────────────────┘
                   │
┌──────────────────▼───────────────────────────┐
│ Confidence + Severity                        │
└──────────────────┬───────────────────────────┘
                   │
┌──────────────────▼───────────────────────────┐
│ Explanation + Sensor Health + Corrected      │
│ Values (self-healing) + Maintenance          │
└──────────────────┬───────────────────────────┘
                   │
┌──────────────────▼───────────────────────────┐
│ outputs/alerts.json                          │
└──────────────────────────────────────────────┘
```

---

## Installation

Requires **Python 3.11+**.

```bash
pip install -r requirements.txt
```

---

## How to Run

### 1. Train the Isolation Forest model

```bash
python src/ml_detector.py
```

Trains on `data/normal_aws_data.csv` (normal only), predicts on `data/test_injected_aws.csv`, and saves `models/isolation_forest.pkl` and `data/isolation_forest_predictions.csv`.

**Example output:**
```
[train] Normal rows loaded      : 14400
[train] IsolationForest fitted. n_estimators=200, contamination=0.02
[predict] Test rows loaded       : 14388
[save] Predictions saved to: data/isolation_forest_predictions.csv
```

### 2. Run the full pipeline → generate alerts

```bash
python src/backend_output.py
```

Reads all evidence sources, runs fusion + classification + scoring + explanation + sensor health + corrected values, and writes `outputs/alerts.json`.

**Example output:**
```
[save] Fused predictions saved to data/fused_predictions.csv (14388 rows)
Total anomalies: 8
Saved to: outputs\alerts.json
```

### 3. Evaluate against ground truth

```bash
python evaluation/evaluate.py
```

Prints precision, recall, F1, confusion matrix, and per-anomaly-type detection rate. Saves results to `results/`.

### 4. Real-time replay simulator

```bash
python src/realtime_simulator.py --no-wait
```

Replays historical AWS readings sequentially, with alerts highlighted.

Options:
```bash
python src/realtime_simulator.py               # 1.0s delay, windowed around alerts
python src/realtime_simulator.py --delay 0.5   # faster
python src/realtime_simulator.py --full        # replay all rows
python src/realtime_simulator.py --limit 500   # first 500 rows only
```

### 5. Backend API (FastAPI)

```bash
python api.py
```

Runs on `http://localhost:8000`. Swagger UI at `http://localhost:8000/docs`.

### 6. Next.js frontend (React)

```bash
cd frontend
npm install
npm run dev
```

Opens in browser at `http://localhost:3000`. Requires the backend API to be running.

### 7. Streamlit dashboard (alternative)

```bash
python -m streamlit run app.py
```

Opens in browser at `http://localhost:8501`.

### 8. Generate expanded evaluation set

```bash
python injector_expanded.py
```

Creates `data/test_expanded_aws.csv` with 2,289 injected anomalies across 7 fault types.

---

## Detection Pipeline (12 Stages)

1. **Feature Engineering** — per-station raw values + deltas
2. **Isolation Forest** — unsupervised baseline (contamination=0.02)
3. **Rule-Based QC** — range, temporal, persistence, internal consistency, missing data
4. **Spatial Consistency** — station-normalized z-scores vs neighbours; isolated vs common event
5. **Temporal Detector** — rolling z-scores over 3 windows
6. **Evidence Fusion** — weighted combination with counter-evidence
7. **Anomaly Classification** — spike, drop, frozen, drift, communication failure, power failure, multivariate inconsistency, genuine weather event
8. **Confidence + Severity** — 0–100 confidence, Low/Medium/High/Critical severity
9. **Explainability** — human-readable reasons per alert
10. **Sensor Health** — Healthy / Watch / At Risk (per station, based on 24h history)
11. **Corrected Values (Self-Healing)** — imputed reading from neighboring stations
12. **Backend Output** — one JSON object per alert

---

## Output Format

`outputs/alerts.json` contains a list of alert objects:

```json
{
  "station_id": "AWS_02",
  "timestamp": "2026-01-06 01:45:00",
  "temperature": 5.61,
  "pressure": 1011.77,
  "humidity": 75.57,
  "status": "anomaly",
  "anomaly_type": "Temperature Drop",
  "confidence": 83,
  "severity": "High",
  "priority": "P1",
  "trust_score": 61,
  "reasons": [
    "Isolation Forest flagged this observation as anomalous (score=-0.008).",
    "QC temporal check flagged a large temperature change (d=-7.02).",
    "QC internal consistency check flagged an inconsistent reading (isolated temperature shift (dT=-7.02)).",
    "Temporal detector flagged a sudden temperature change (temporal_z_4=17.69)."
  ],
  "physical_reasoning": "Temperature dropped by 7.0°C within one interval while pressure and humidity did not show a corresponding change.",
  "weather_verdict_reason": "Temperature change is not coupled with humidity change — inconsistent with a physical weather event.",
  "sensor_health": "healthy",
  "maintenance_recommendation": "Inspect the affected station/sensor.",
  "corrected_temperature": 17.73,
  "corrected_pressure": 1012.48,
  "corrected_humidity": 69.49,
  "correction_confidence": 77,
  "correction_basis": "median of 2 neighbouring station(s) (AWS_01, AWS_05)"
}
```

---

## Self-Healing — Corrected Values

When an anomaly is detected at a station, SkyGuard computes a suggested corrected reading using the median of neighboring stations' readings at the same timestamp. This addresses the PS's "self-healing network" grand challenge.

- `corrected_temperature` / `corrected_pressure` / `corrected_humidity` — imputed values
- `correction_confidence` (0–100) — higher when neighbors agree tightly
- `correction_basis` — which neighbors were used

**Design principle:** corrected values are advisory, not authoritative. The original reading is preserved; the corrected value is a suggested replacement for manual review.

---

## Results

SkyGuard was evaluated on two test sets to demonstrate robustness.

### Original test set (140 injected anomalies)

| Metric | Value |
|---|---|
| Alerts emitted | 8 |
| True positives | 7 |
| False positives | 1 |
| Precision | 0.875 |
| Recall | 0.050 |
| F1 | 0.095 |
| False alarm rate | 0.0001 |
| Confidence calibration (high) | 86% |

### Expanded test set (2,289 injected anomalies, 7 fault types)

| Metric | Value |
|---|---|
| Precision | 0.912 |
| Recall | 0.104 |
| F1 | 0.187 |
| Test anomalies | 2,289 |
| False alarm rate | 0.0019 |
| Confidence calibration (high) | 92.3% |

### Per-type detection (expanded test set)

| Anomaly type | Injected | Detected | Rate |
|---|---|---|---|
| Temperature spike | 23 | 22 | 95.7% |
| Power failure | 44 | 44 | 100% |
| Temperature drop | 23 | 10 | 43.5% |
| Multivariate inconsistency | 240 | 76 | 31.7% |
| Missing data | 280 | 61 | 21.8% |
| Frozen sensor | 719 | 26 | 3.6% |
| Calibration drift | 960 | 0 | 0% (future work) |

### Per-station detection (expanded test set)

| Station | Alerts | Precision | Recall |
|---|---|---|---|
| AWS_01 | 50 | 0.84 | 0.09 |
| AWS_02 | 49 | 0.90 | 0.10 |
| AWS_03 | 55 | 0.87 | 0.11 |
| AWS_04 | 67 | 0.97 | 0.14 |
| AWS_05 | 41 | 0.98 | 0.09 |

### Confidence calibration (expanded test set)

| Bucket | Alerts | Correct | Accuracy |
|---|---|---|---|
| High (80–100) | 220 | 203 | 92.3% |
| Medium (50–79) | 39 | 35 | 89.7% |
| Low (0–49) | 3 | 1 | 33.3% (small sample) |

### Design choice — precision over recall

SkyGuard prioritizes precision over recall by design. It fires alerts only when multiple evidence sources corroborate. This yields **91% precision on the expanded test set with 262 actionable alerts** — instead of thousands of noisy alerts.

### Stratified Recall

Overall recall of 0.104 is dominated by out-of-scope categories:

| Scope | Recall | Counts |
|---|---|---|
| All anomalies | 0.104 | 239 / 2,289 |
| Excluding calibration drift | 0.180 | 239 / 1,329 |
| Excluding drift + frozen sensor | 0.349 | 213 / 610 |
| Temperature spikes only | 0.957 | 22 / 23 |
| Power failures only | 1.000 | 44 / 44 |

**Interpretation:** Calibration drift (960 injections, 0 detected) is documented as out of scope — point-wise detectors cannot catch slow drift. Frozen sensor (719 injections, 26 detected) is under-tuned for the 24-row injection blocks used in this benchmark; the persistence rule fires, but fusion does not always promote sustained frozen runs to alerts. On the anomaly types SkyGuard is designed for (spikes, power failures), recall is near-perfect.

---

## Reproducing Both Evaluations

### Original set (140 anomalies, 8 alerts)

```bash
python evaluation/evaluate.py --predictions data/fused_predictions.csv --labels data/test_injected_aws.csv
```

**Result:** precision 0.875, recall 0.050, F1 0.095.

### Expanded set (2,289 anomalies, 262 alerts)

```cmd
:: 1. Back up original test file
copy data\test_injected_aws.csv data\test_injected_aws_ORIGINAL.csv

:: 2. Swap in expanded test set
copy data\test_expanded_aws.csv data\test_injected_aws.csv

:: 3. Regenerate IF predictions on expanded data
python src\ml_detector.py

:: 4. Run fusion pipeline
python src\backend_output.py

:: 5. Save expanded outputs
copy data\fused_predictions.csv data\predictions_expanded_full.csv
copy outputs\alerts.json outputs\alerts_expanded.json

:: 6. Restore original test file and regenerate original predictions
copy data\test_injected_aws_ORIGINAL.csv data\test_injected_aws.csv
python src\ml_detector.py
python src\backend_output.py

:: 7. Evaluate expanded
python evaluation\evaluate.py --predictions data\predictions_expanded_full.csv --labels data\test_expanded_aws.csv
```

**Result:** precision 0.912, recall 0.104, F1 0.187.

**Note:** Steps 3 and 6 are essential — `ml_detector.py` must be re-run after swapping `test_injected_aws.csv`, because the Isolation Forest predictions file reflects the last test set processed.

---
## Performance

Measured end-to-end on the full expanded test set (14,388 readings):

| Metric | Value |
|---|---|
| Total pipeline time | 8.18 s |
| Readings processed | 14,388 |
| **Per-reading latency** | **0.57 ms** |
| **Throughput** | **~1,760 readings/sec** |
| India AWS network load | ~1.11 readings/sec |
| **Headroom** | **~1,580×** |

**Interpretation:** The full pipeline — feature engineering, rule-based QC, spatial consistency, temporal detection, Isolation Forest inference, evidence fusion, classification, scoring, explanation, sensor health, and self-healing — processes one reading in under 1 millisecond. A single commodity instance can serve India's entire ~1,000-station AWS network with roughly three orders of magnitude of headroom.

**Measurement method:** `Measure-Command { python src\backend_output.py }` on a single-core-equivalent instance against `data/test_injected_aws.csv`. This measures end-to-end wall-clock time from CSV load to alerts written to disk — a conservative upper bound on the incremental per-reading cost in a streaming deployment, since it includes one-time startup and file I/O.

## Use Cases

### 1. Aviation weather safety

AWS anomalies at airports can cause incorrect wind, visibility, or icing forecasts. SkyGuard flags sensor faults in real time, allowing ground crews to switch to backup instruments before a critical takeoff or landing.

### 2. Agricultural advisories

Farmers rely on temperature and humidity forecasts for irrigation, frost protection, and pest management. A drifting temperature sensor can trigger wrong frost alerts or miss heat-stress warnings. SkyGuard identifies faulty stations and routes advisories to nearest reliable neighbors.

### 3. Disaster management

During cyclones and heatwaves, timely ground observations feed evacuation and resource-allocation decisions. Erroneous readings during a crisis can cause misdirected response. SkyGuard's spatial consistency check distinguishes isolated sensor faults from regional weather events.

### 4. Climate research

Long-term climate records depend on data integrity across decades. Sensor drift, once embedded in archives, is hard to remove. SkyGuard's per-station health tracking helps data managers flag stations for calibration before systematic bias accumulates.

### 5. Renewable energy forecasting

Solar and wind forecasts use AWS temperature, pressure, and humidity as inputs. Faulty readings degrade renewable generation predictions. SkyGuard's real-time alerts let grid operators fall back to neighboring stations during sensor outages.

---

## Limitations (honest)

- **Synthetic dataset** — the current prototype is validated on injected synthetic anomalies, not real IMD AWS data.
- **Low recall on calibration drift** — point-wise detectors cannot catch slow drift. Documented, not hidden.
- **Prototype thresholds** — all numeric thresholds are heuristics, not WMO or any other official standard.
- **No edge deployment** — runs on a workstation or server. ESP32 deployment is future work.
- **No SHAP/LIME** — rule-based reasons used instead. SHAP planned.
- **Sensor health shows "healthy" for single alerts** — because health is a 24-hour per-station status, not per-alert.

---

## Calibration Drift — Investigation & Findings

A dedicated gradual-drift detector was implemented as a sixth evidence source in the SkyGuard architecture (available on the `drift-experiment` branch, `src/drift_detector.py`), using:

- Rolling 7-day baseline comparison
- Linear regression slope test on the recent window
- Persistence requirement (12 consecutive readings)
- Parameter-specific physical validity checks

**Validation finding:**
The synthetic benchmark injects calibration drift as a 24-hour linear ramp (+4.0°C over 96 observations, ~0.04°C per reading). This rate is 5–10x smaller than natural 15-minute temperature variation (~0.2–0.5°C per reading). No window configuration detected the injected drift without also flagging normal diurnal temperature cycles.

**Outcome:**
The drift detector is retained as an independent evidence source in the architecture but is NOT integrated into the live fusion pipeline on this benchmark, because it produces false positives on natural temperature variation without reliably detecting the injected drift.

**Future work:**
Reliable calibration-drift validation requires multi-week historical data or synthetic drift scenarios extending over 7–14 days. Real-world calibration drift occurs over weeks to months — the current 24-hour injection timescale is too short to distinguish from natural diurnal variation.

---

## Future Work

- **Calibration drift detector** — implemented (`drift-experiment` branch); needs multi-week validation data
- **Edge AI on ESP32** — quantized model, low-power inference
- **SHAP/LIME** — additional explainability layer
- **Real IMD AWS data integration** — validate against production observations
- **Multi-region scaling** — partition by climatological zone
- **Frozen sensor fusion tuning** — persistence rule fires, but fusion does not always promote sustained frozen runs to alerts

---

## File Structure

```
SkyGuard AI/
├── api.py                         # FastAPI backend (deployed on Railway)
├── app.py                         # Streamlit dashboard (local fallback)
├── injector_expanded.py           # generates expanded eval set (2,289 anomalies)
├── requirements.txt
├── README.md
├── docs/
│   └── README.md                  # this file
├── frontend/                      # Next.js dashboard (deployed on Vercel)
│   ├── app/                       # 7 pages: dashboard, network, parameters,
│   │                              # reality-check, test, maintenance, stations
│   ├── components/                # dashboard + UI components
│   ├── lib/api.ts                 # typed API client with fallback
│   └── public/fallback/           # offline cached data
├── data/
│   ├── normal_aws_data.csv
│   ├── test_injected_aws.csv
│   ├── test_expanded_aws.csv      # 2,289 anomalies
│   ├── predictions_expanded_full.csv  # full-column expanded predictions
│   ├── station_metadata.csv
│   └── isolation_forest_predictions.csv
├── models/
│   └── isolation_forest.pkl
├── outputs/
│   ├── alerts.json                # 8 alerts (original test set)
│   └── alerts_expanded.json       # 262 alerts (expanded test set)
├── results/
│   ├── evaluation_metrics.csv
│   ├── evaluation_summary.txt
│   ├── evaluation_summary_original.txt
│   ├── evaluation_metrics_expanded.csv
│   └── evaluation_summary_expanded.txt
└── src/
    ├── feature_engineering.py
    ├── ml_detector.py
    ├── qc_rules.py
    ├── spatial_analysis.py
    ├── temporal_detector.py
    ├── evidence_fusion.py
    ├── anomaly_classifier.py
    ├── scoring.py
    ├── explainer.py
    ├── sensor_health.py
    ├── backend_output.py
    ├── realtime_simulator.py
    ├── inject_demo.py             # fault injection (full pipeline)
    └── inject_demo_fast.py        # fault injection (cached baseline)
```

---

## PS Compliance Checklist

| PS Requirement | Status |
|---|---|
| Detect anomalies in real-time | ✅ |
| Identify sensor faults, spikes, frozen values, communication errors | ✅ |
| Learn normal temporal patterns | ✅ |
| Multivariate consistency (T/P/H) | ✅ |
| Confidence scores | ✅ |
| Explainable reasoning | ✅ (rule-based) |
| Root-cause classification | ✅ |
| Real-time anomaly alerts | ✅ |
| Severity scores | ✅ |
| Sensor health status | ✅ |
| Visualization dashboard | ✅ |
| Corrected / imputed values | ✅ |
| Document explaining use cases | ✅ (this file) |
| Fully executable code with example usage | ✅ |

---

## Design Philosophy

- **No ground-truth labels used in training or inference.** Labels are used only for evaluation.
- **Multi-source evidence fusion** rather than a single model.
- **Rule-based explanations** — transparent and auditable.
- **Precision over recall** — 262 alerts with 91% precision beats thousands of noisy alerts.
- **Config-driven thresholds** — no magic numbers; all in dataclasses.
- **Honest disclaimers** — prototype heuristics, not WMO standards.