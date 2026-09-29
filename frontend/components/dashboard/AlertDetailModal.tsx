// components/dashboard/AlertDetailModal.tsx
"use client";

import {
  X,
  Thermometer,
  Droplet,
  Gauge,
  AlertTriangle,
  Activity,
  Wrench,
  Shield,
  BarChart3,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { Alert } from "@/lib/api";

interface AlertDetailModalProps {
  alert: Alert | null;
  onClose: () => void;
}

const PRIORITY_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  P1: { bg: "#FEE2E2", text: "#991B1B", label: "Critical" },
  P2: { bg: "#FEF3C7", text: "#92400E", label: "High" },
  P3: { bg: "#DBEAFE", text: "#1E40AF", label: "Routine" },
};

const SOURCE_COLORS: Record<string, string> = {
  ml_if: "#8B5CF6",
  qc_any: "#3B82F6",
  temporal: "#F59E0B",
  spatial: "#10B981",
};

const SOURCE_LABELS: Record<string, string> = {
  ml_if: "Isolation Forest (ML)",
  qc_any: "Rule-Based QC",
  temporal: "Temporal Detector",
  spatial: "Spatial Consistency",
};

export default function AlertDetailModal({
  alert,
  onClose,
}: AlertDetailModalProps) {
  if (!alert) return null;

  const pri = PRIORITY_STYLES[alert.priority] || PRIORITY_STYLES.P3;
  const evidence = alert.evidence_breakdown || {};

  // Build feature importance list
  const featureImportance = Object.entries(evidence)
    .map(([source, data]: [string, any]) => {
      const weight = typeof data?.weight === "number" ? data.weight : 1.0;
      const fired = data?.fired === true;
      return {
        source,
        label: SOURCE_LABELS[source] || source,
        color: SOURCE_COLORS[source] || "#64748B",
        weight,
        fired,
        contribution: fired ? weight : 0,
      };
    })
    .sort((a, b) => b.contribution - a.contribution);

  const maxContribution = Math.max(
    ...featureImportance.map((f) => f.contribution),
    0.01
  );

  const firedSources = featureImportance
    .filter((f) => f.fired)
    .map((f) => f.source);

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4 fade-in"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg max-w-3xl w-full max-h-[90vh] overflow-y-auto shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-start justify-between z-10">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h3 className="text-lg font-bold text-gray-900">
                {alert.station_id}
              </h3>
              <span
                className="px-2.5 py-1 rounded-full text-xs font-semibold"
                style={{ backgroundColor: pri.bg, color: pri.text }}
              >
                {pri.label} ({alert.priority})
              </span>
            </div>
            <p className="text-sm text-gray-500">
              {alert.anomaly_type} • {alert.timestamp}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700 transition-colors"
          >
            <X size={22} />
          </button>
        </div>

        <div className="px-6 py-5 space-y-6">
          {/* Observed vs Corrected */}
          <div>
            <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">
              Observation
            </h4>
            <div className="grid grid-cols-3 gap-4">
              <div className="border border-gray-200 rounded-lg p-3">
                <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1">
                  <Thermometer size={12} className="text-red-500" />
                  Temperature
                </div>
                <p className="text-sm font-semibold text-gray-900">
                  {alert.temperature?.toFixed(1) ?? "—"}°C
                </p>
                {alert.corrected_temperature != null && (
                  <p className="text-xs text-teal-600 mt-1">
                    Corrected: {alert.corrected_temperature.toFixed(1)}°C
                  </p>
                )}
              </div>
              <div className="border border-gray-200 rounded-lg p-3">
                <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1">
                  <Droplet size={12} className="text-green-500" />
                  Humidity
                </div>
                <p className="text-sm font-semibold text-gray-900">
                  {alert.humidity?.toFixed(0) ?? "—"}%
                </p>
                {alert.corrected_humidity != null && (
                  <p className="text-xs text-teal-600 mt-1">
                    Corrected: {alert.corrected_humidity.toFixed(0)}%
                  </p>
                )}
              </div>
              <div className="border border-gray-200 rounded-lg p-3">
                <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1">
                  <Gauge size={12} className="text-blue-500" />
                  Pressure
                </div>
                <p className="text-sm font-semibold text-gray-900">
                  {alert.pressure?.toFixed(0) ?? "—"} hPa
                </p>
                {alert.corrected_pressure != null && (
                  <p className="text-xs text-teal-600 mt-1">
                    Corrected: {alert.corrected_pressure.toFixed(0)} hPa
                  </p>
                )}
              </div>
            </div>
          </div>

          <Separator />

          {/* FEATURE IMPORTANCE CHART */}
          <div>
            <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <BarChart3 size={13} />
              Detector Contribution
            </h4>
            <div className="space-y-2.5">
              {featureImportance.map((f) => {
                const pct = (f.contribution / maxContribution) * 100;
                return (
                  <div key={f.source}>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span
                        className={`font-medium ${
                          f.fired ? "text-gray-800" : "text-gray-400"
                        }`}
                      >
                        {f.label}
                      </span>
                      <span
                        className={`font-mono ${
                          f.fired ? "text-gray-700" : "text-gray-400"
                        }`}
                      >
                        {f.fired
                          ? `weight ${f.weight.toFixed(1)}`
                          : "not fired"}
                      </span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${pct}%`,
                          backgroundColor: f.fired ? f.color : "#E5E7EB",
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="text-xs text-gray-500 mt-3">
              {alert.decision_basis}
            </p>
          </div>

          <Separator />

          {/* Physical reasoning */}
          <div>
            <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Activity size={13} />
              Physical Reasoning
            </h4>
            <p className="text-sm text-gray-700 leading-relaxed">
              {alert.physical_reasoning}
            </p>
          </div>

          <Separator />

          {/* Evidence tags */}
          <div>
            <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">
              Evidence
            </h4>
            <div className="flex flex-wrap gap-2">
              {firedSources.map((s) => (
                <span
                  key={s}
                  className="px-2.5 py-1 rounded-full text-xs font-medium bg-teal-50 text-teal-700 border border-teal-200"
                >
                  {SOURCE_LABELS[s] || s}
                </span>
              ))}
            </div>
            <div className="flex items-center gap-4 mt-3 text-xs text-gray-600">
              <span>
                Confidence: <b className="text-gray-900">{alert.confidence}</b>
              </span>
              <span>
                Trust: <b className="text-gray-900">{alert.trust_score}</b>
              </span>
              <span>
                Severity: <b className="text-gray-900">{alert.severity}</b>
              </span>
            </div>
          </div>

          <Separator />

          {/* Physics coupling */}
          <div>
            <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <AlertTriangle size={13} />
              Physics Coupling Check
            </h4>
            <p className="text-sm text-gray-700 leading-relaxed">
              {alert.multivariate_analysis?.reason || "Not available"}
            </p>
          </div>

          <Separator />

          {/* Verdict */}
          <div>
            <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Shield size={13} />
              Verdict
            </h4>
            <p className="text-sm text-gray-700 leading-relaxed mb-2">
              {alert.weather_verdict_reason}
            </p>
            <p className="text-xs text-gray-500">
              {alert.counter_reasoning?.reason}
            </p>
          </div>

          <Separator />

          {/* Recommended action */}
          <div className="bg-teal-50 border border-teal-200 rounded-lg p-4">
            <h4 className="text-xs font-bold text-teal-800 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Wrench size={13} />
              Recommended Action
            </h4>
            <p className="text-sm text-teal-900 font-medium">
              {alert.maintenance_recommendation}
            </p>
            <p className="text-xs text-teal-700 mt-2">
              {alert.defensibility?.operator_action}
            </p>
          </div>

          {/* Known limitations */}
          {alert.defensibility?.known_limitations?.length > 0 && (
            <div className="text-xs text-gray-500 italic border-t border-gray-100 pt-3">
              <b className="text-gray-600">Known limitations: </b>
              {alert.defensibility.known_limitations.join(" • ")}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}