// components/dashboard/MetricsCard.tsx
"use client";

import { useState } from "react";
import { Info, ChevronDown, ChevronUp, Shield } from "lucide-react";
import { Card } from "@/components/ui/card";

// Values from evaluation/evaluate.py output.
// Update these when you re-train or re-evaluate the pipeline.
const METRICS = {
  precision: 0.78,
  recall: 0.05,
  f1: 0.09,
  falseAlarmRate: 0.0001,
  confidenceCalibration: 0.86,
  totalAlerts: 9,
  truePositives: 7,
  falsePositives: 2,
  driftAnomalies: 96,
  totalAnomalies: 140,
};

export default function MetricsCard() {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card className="card-soft overflow-hidden">
      {/* Header */}
      <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield size={16} className="text-teal-600" />
          <h3 className="text-sm font-semibold text-gray-800">
            Performance Metrics
          </h3>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-teal-600 hover:text-teal-700 flex items-center gap-1 font-medium"
        >
          <Info size={12} />
          Methodology
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
      </div>

      {/* Metrics grid */}
      <div className="px-5 py-4 grid grid-cols-2 md:grid-cols-4 gap-4">
        <div>
          <p className="text-xs text-gray-500 mb-1">Precision</p>
          <p className="text-xl font-bold text-gray-900">
            {METRICS.precision.toFixed(2)}
          </p>
          <p className="text-xs text-teal-600 mt-0.5">
            {METRICS.truePositives} of {METRICS.totalAlerts} alerts correct
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">Recall</p>
          <p className="text-xl font-bold text-gray-900">
            {METRICS.recall.toFixed(2)}
          </p>
          <p className="text-xs text-amber-600 mt-0.5">
            Precision-first design
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">F1 Score</p>
          <p className="text-xl font-bold text-gray-900">
            {METRICS.f1.toFixed(2)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">False Alarm Rate</p>
          <p className="text-xl font-bold text-teal-700">
            {METRICS.falseAlarmRate.toFixed(4)}
          </p>
          <p className="text-xs text-teal-600 mt-0.5">
            Very low (0.01%)
          </p>
        </div>
      </div>

      {/* Context line — always visible */}
      <div className="px-5 py-3 bg-amber-50 border-t border-amber-100 text-xs text-amber-800 leading-relaxed">
        <b>Precision-first design:</b> SkyGuard fires an alert only when
        multiple detectors corroborate. The {METRICS.driftAnomalies} of{" "}
        {METRICS.totalAnomalies} drift anomalies require multi-week baseline
        tracking — a separate detection paradigm planned as future work.
      </div>

      {/* Expanded methodology */}
      {expanded && (
        <div className="px-5 py-4 border-t border-gray-100 bg-gray-50 text-xs space-y-3 fade-in">
          <div>
            <p className="font-semibold text-gray-700 mb-1">
              Confidence Calibration
            </p>
            <p className="text-gray-600">
              When the system reports High confidence (80–100), it is correct{" "}
              <b className="text-teal-700">
                {(METRICS.confidenceCalibration * 100).toFixed(0)}%
              </b>{" "}
              of the time in our test set — the confidence score is
              calibrated and meaningful.
            </p>
          </div>

          <div>
            <p className="font-semibold text-gray-700 mb-1">
              Evaluation methodology
            </p>
            <p className="text-gray-600">
              Evaluated on 14,388 observations with 140 injected anomalies
              across 6 fault types. Precision, recall, and F1 are computed on
              the fused pipeline output — not on Isolation Forest alone —
              which is the system users would actually deploy.
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}