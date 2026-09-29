// components/dashboard/MetricsCard.tsx
"use client";

import { useState } from "react";
import {
  Info,
  ChevronDown,
  ChevronUp,
  Shield,
  TrendingUp,
  Target,
  BarChart3,
  CheckCircle2,
  Sparkles,
} from "lucide-react";
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
      <div className="px-5 py-3.5 border-b border-stone-200/80 bg-gradient-to-r from-stone-50/80 via-white to-stone-50/40 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-teal-50 border border-teal-200/60 flex items-center justify-center text-teal-700">
            <Shield size={15} />
          </div>
          <h3 className="text-sm font-semibold text-stone-900 tracking-tight">
            Performance Metrics
          </h3>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-teal-700 hover:text-teal-800 bg-teal-50/80 hover:bg-teal-100/80 px-2.5 py-1 rounded-full border border-teal-200/60 transition-colors flex items-center gap-1.5 font-medium cursor-pointer"
        >
          <Info size={12} />
          Methodology
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
      </div>

      {/* Metrics grid: each metric in its own soft-tinted box with colored left border */}
      <div className="p-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Precision: Teal */}
        <div className="bg-teal-50/50 hover:bg-teal-50/80 transition-all rounded-xl p-4 border border-teal-100/80 border-l-4 border-l-teal-600 shadow-2xs">
          <div className="flex items-center justify-between gap-1 mb-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-teal-800">
              Precision
            </span>
            <TrendingUp size={14} className="text-teal-600" />
          </div>
          <p className="text-2xl font-bold text-stone-900 tracking-tight">
            {METRICS.precision.toFixed(2)}
          </p>
          <p className="text-xs text-teal-700 font-medium mt-1">
            {METRICS.truePositives} of {METRICS.totalAlerts} alerts correct
          </p>
        </div>

        {/* Recall: Amber */}
        <div className="bg-amber-50/50 hover:bg-amber-50/80 transition-all rounded-xl p-4 border border-amber-100/80 border-l-4 border-l-amber-500 shadow-2xs">
          <div className="flex items-center justify-between gap-1 mb-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-amber-800">
              Recall
            </span>
            <Target size={14} className="text-amber-600" />
          </div>
          <p className="text-2xl font-bold text-stone-900 tracking-tight">
            {METRICS.recall.toFixed(2)}
          </p>
          <p className="text-xs text-amber-700 font-medium mt-1">
            Precision-first design
          </p>
        </div>

        {/* F1 Score: Slate */}
        <div className="bg-slate-50/80 hover:bg-slate-100/60 transition-all rounded-xl p-4 border border-slate-200/80 border-l-4 border-l-slate-500 shadow-2xs">
          <div className="flex items-center justify-between gap-1 mb-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-700">
              F1 Score
            </span>
            <BarChart3 size={14} className="text-slate-500" />
          </div>
          <p className="text-2xl font-bold text-stone-900 tracking-tight">
            {METRICS.f1.toFixed(2)}
          </p>
          <p className="text-xs text-slate-500 font-medium mt-1">
            Harmonic balance
          </p>
        </div>

        {/* False Alarm Rate: Green */}
        <div className="bg-emerald-50/50 hover:bg-emerald-50/80 transition-all rounded-xl p-4 border border-emerald-100/80 border-l-4 border-l-emerald-600 shadow-2xs">
          <div className="flex items-center justify-between gap-1 mb-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-800">
              False Alarm Rate
            </span>
            <CheckCircle2 size={14} className="text-emerald-600" />
          </div>
          <p className="text-2xl font-bold text-stone-900 tracking-tight">
            {METRICS.falseAlarmRate.toFixed(4)}
          </p>
          <p className="text-xs text-emerald-700 font-medium mt-1">
            Very low (0.01%)
          </p>
        </div>
      </div>

      {/* Context line — always visible */}
      <div className="px-5 py-3.5 bg-gradient-to-r from-amber-50/90 via-amber-50/40 to-transparent border-t border-amber-200/60 text-xs text-amber-900 leading-relaxed flex items-start gap-2.5">
        <Sparkles size={15} className="text-amber-600 shrink-0 mt-0.5" />
        <div>
          <span className="font-bold text-amber-950">Precision-first design: </span>
          SkyGuard fires an alert only when multiple detectors corroborate. The{" "}
          {METRICS.driftAnomalies} of {METRICS.totalAnomalies} drift anomalies
          require multi-week baseline tracking — a separate detection paradigm
          planned as future work.
        </div>
      </div>

      {/* Expanded methodology */}
      {expanded && (
        <div className="px-5 py-4 border-t border-stone-200/80 bg-stone-50/60 text-xs space-y-3 animate-fade-in">
          <div className="bg-white p-3.5 rounded-lg border border-stone-200/70 shadow-2xs">
            <p className="font-semibold text-stone-800 mb-1">
              Confidence Calibration
            </p>
            <p className="text-stone-600 leading-relaxed">
              When the system reports High confidence (80–100), it is correct{" "}
              <b className="text-teal-700">
                {(METRICS.confidenceCalibration * 100).toFixed(0)}%
              </b>{" "}
              of the time in our test set — the confidence score is calibrated and
              meaningful.
            </p>
          </div>

          <div className="bg-white p-3.5 rounded-lg border border-stone-200/70 shadow-2xs">
            <p className="font-semibold text-stone-800 mb-1">
              Evaluation Methodology
            </p>
            <p className="text-stone-600 leading-relaxed">
              Evaluated on 14,388 observations with 140 injected anomalies across
              6 fault types. Precision, recall, and F1 are computed on the fused
              pipeline output — not on Isolation Forest alone — which is the
              system users would actually deploy.
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}