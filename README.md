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

## Key Results

| Metric | Value |
|---|---|
| Alerts emitted | 9 |
| **Precision** | **0.78** |
| False positives | 2 |
| True positives | 7 |
| False alarm rate | 0.0001 |
| Confidence calibration (high) | 86% |
| Self-healing coverage | 100% of alerts |

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
Frontend opens at http://localhost:3000.
Backend API at http://localhost:8000.

Documentation
📖 Full documentation → — architecture, 12-stage pipeline, output format, results, 5 use cases, limitations, and future work.

Project Structure
text
SkyGuard AI/
├── api.py                  # FastAPI backend (Railway)
├── app.py                  # Streamlit dashboard (fallback)
├── frontend/               # Next.js dashboard (Vercel)
├── data/                   # Synthetic AWS observations
├── models/                 # Trained Isolation Forest
├── outputs/alerts.json     # 9 detected alerts
├── results/                # Evaluation metrics
└── src/                    # 12-file detection pipeline
Design Philosophy
No ground-truth labels used in training or inference

Multi-source evidence fusion — not just a single model

Precision over recall — 9 clean, actionable alerts beat 3,000 noisy ones

Rule-based explanations — transparent and auditable

Honest disclaimers — prototype heuristics, not WMO standards

SkyGuard AI is a prototype. Thresholds are operational heuristics. Do not use for operational decisions without domain calibration.