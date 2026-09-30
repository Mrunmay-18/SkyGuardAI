# 🛰️ SkyGuard AI

**AI/ML-Based Intelligent Anomaly Detection for Automatic Weather Stations**

**Problem Statement ID:** 26073  
**Organization:** Ministry of Earth Sciences / India Meteorological Department  
**Theme:** Disaster Management

---

## Live Demo

| Component | URL |
|---|---|
| **Frontend** | https://sky-guard-ai-gules.vercel.app |
| **Backend API** | https://skyguardai-production.up.railway.app |
| **API Docs** | https://skyguardai-production.up.railway.app/docs |
| **Repository** | https://github.com/Mrunmay-18/SkyGuardAI |

---

## Overview

SkyGuard AI detects anomalies in AWS temperature, pressure, and humidity data using **multi-source evidence fusion** — combining Isolation Forest, rule-based QC, spatial consistency, temporal detection, and rule-based classification. It distinguishes genuine meteorological events from sensor faults and provides **self-healing corrected values** for detected anomalies.

---

## Key Results

### Original test set (140 injected anomalies)

| Metric | Value |
|---|---|
| Alerts emitted | 8 |
| **Precision** | **0.875** |
| **Recall** | **0.050** |
| **F1** | **0.095** |
| False alarm rate | 0.0001 |

### Expanded test set (2,289 injected anomalies, 7 fault types)

| Metric | Value |
|---|---|
| **Precision** | **0.912** |
| **Recall** | **0.104** |
| **F1** | **0.187** |
| False alarm rate | 0.0019 |
| Confidence calibration (high) | **92.3%** |

### Stratified recall (expanded test set)

| Scope | Recall |
|---|---|
| All anomalies | 0.104 |
| Excluding calibration drift | 0.180 |
| Excluding drift + frozen sensor | 0.349 |
| Temperature spikes only | **0.957** |
| Power failures only | **1.000** |
### Performance

| Metric | Value |
|---|---|
| Per-reading latency | **0.57 ms** |
| Throughput | **~1,760 readings/sec** |
| India AWS network load | ~1.11 readings/sec |
| **Headroom** | **~1,580×** |

A single instance handles the full ~1,000-station AWS network with substantial margin.

Calibration drift (960 injections, 0 detected) is documented as future work — point-wise detectors cannot catch slow drift. Frozen sensor is under-tuned for the benchmark's 24-row injection blocks. On the anomaly types SkyGuard is designed for, recall is near-perfect.

### Detection highlights (expanded test set)

- Temperature spike: **95.7%**
- Power failure: **100%**
- Temperature drop: 43.5%
- Multivariate inconsistency: 31.7%
- Missing data: 21.8%
- Frozen sensor: 3.6%
- Calibration drift: 0% (documented as future work)

---

## Quick Start

```bash
pip install -r requirements.txt

# 1. Train Isolation Forest model
python src/ml_detector.py

# 2. Run full pipeline → generate alerts
python src/backend_output.py

# 3. Evaluate against ground truth
python evaluation/evaluate.py

# 4. Start backend API
python api.py

# 5. Start frontend (new terminal)
cd frontend
npm install
npm run dev
```

Frontend opens at http://localhost:3000.  
Backend API at http://localhost:8000.

---

## Documentation

📖 **[Full documentation →](./docs/README.md)** — architecture, 12-stage pipeline, output format, results, stratified recall, reproducibility commands, 5 use cases, limitations, and future work.

---

## Project Structure

```
SkyGuard AI/
├── api.py                       # FastAPI backend (Railway)
├── app.py                       # Streamlit dashboard (fallback)
├── injector_expanded.py         # generates expanded eval set (2,289 anomalies)
├── requirements.txt
├── README.md                    # this file
├── docs/
│   └── README.md                # full documentation
├── frontend/                    # Next.js dashboard (Vercel)
│   ├── app/                     # 7 pages
│   ├── components/              # dashboard + UI components
│   └── lib/api.ts               # typed API client with fallback
├── data/
│   ├── normal_aws_data.csv
│   ├── test_injected_aws.csv
│   ├── test_expanded_aws.csv    # 2,289 anomalies
│   ├── predictions_expanded_full.csv
│   ├── station_metadata.csv
│   └── isolation_forest_predictions.csv
├── models/
│   └── isolation_forest.pkl
├── outputs/
│   ├── alerts.json              # 8 alerts (original)
│   └── alerts_expanded.json     # 262 alerts (expanded)
├── results/
│   ├── evaluation_summary.txt
│   ├── evaluation_summary_original.txt
│   ├── evaluation_metrics.csv
│   ├── evaluation_summary_expanded.txt
│   └── evaluation_metrics_expanded.csv
└── src/                         # 14-file detection pipeline
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
    ├── inject_demo.py
    └── inject_demo_fast.py
```

---

## Design Philosophy

- **No ground-truth labels used in training or inference** — labels are used only for evaluation.
- **Multi-source evidence fusion** rather than a single model.
- **Precision over recall** — 262 alerts with 91% precision beats thousands of noisy alerts; stratified recall reported honestly.
- **Rule-based explanations** — transparent and auditable.
- **Config-driven thresholds** — no magic numbers; all in dataclasses.
- **Honest disclaimers** — prototype heuristics, not WMO standards.

---

## Limitations

- Synthetic dataset — not yet validated on real IMD AWS data.
- Calibration drift (0% detected) — documented as future work; requires multi-week baseline tracking.
- Frozen sensor (3.6% detected) — under-tuned for the 24-row injection blocks; persistence rule fires but fusion does not always promote sustained runs to alerts.
- Prototype thresholds — operational heuristics, not WMO standards.
- No edge deployment — ESP32 planned as future work.
- No SHAP/LIME — rule-based explanations used instead; SHAP planned.

---

> ⚠️ SkyGuard AI is a prototype. Thresholds are operational heuristics. Do not use for operational decisions without domain calibration.