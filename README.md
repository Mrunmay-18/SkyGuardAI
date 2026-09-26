# 🛰️ SkyGuard AI

**AI/ML-Based Intelligent Anomaly Detection for Automatic Weather Stations**

**Problem Statement ID:** 26073  
**Organization:** Ministry of Earth Sciences / India Meteorological Department  
**Theme:** Disaster Management

---

## Overview

SkyGuard AI detects anomalies in AWS temperature, pressure, and humidity data using **multi-source evidence fusion** — combining Isolation Forest, rule-based QC, spatial consistency, temporal detection, and rule-based classification. It distinguishes genuine meteorological events from sensor faults and provides **self-healing corrected values** for detected anomalies.

## Key Results

| Metric | Value |
|---|---|
| Alerts emitted | 10 |
| Precision | **0.70** |
| False positives | 3 |
| True positives | 7 |
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

# 4. Real-time replay
python src/realtime_simulator.py --no-wait

# 5. Launch dashboard
python -m streamlit run app.py