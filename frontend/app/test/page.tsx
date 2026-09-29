// app/test/page.tsx
"use client";

import { useEffect, useState } from "react";
import {
  FlaskConical,
  Zap,
  ArrowRight,
  AlertTriangle,
  CheckCircle,
  Loader2,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  getStations,
  getFaultTypes,
  injectFault,
  type Station,
  type FaultTypesResponse,
  type InjectionResult,
} from "@/lib/api";

const PRIORITY_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  P1: { bg: "#FEE2E2", text: "#991B1B", label: "Critical" },
  P2: { bg: "#FEF3C7", text: "#92400E", label: "High" },
  P3: { bg: "#DBEAFE", text: "#1E40AF", label: "Routine" },
};

function humanizeFault(s: string) {
  return s
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export default function TestPage() {
  const [stations, setStations] = useState<Station[]>([]);
  const [faultInfo, setFaultInfo] = useState<FaultTypesResponse>({
    fault_types: [],
    default_magnitudes: {},
  });
  const [stationId, setStationId] = useState("");
  const [faultType, setFaultType] = useState("");
  const [magnitude, setMagnitude] = useState(15);
  const [result, setResult] = useState<InjectionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      const [st, ft] = await Promise.all([getStations(), getFaultTypes()]);
      setStations(st);
      setFaultInfo(ft);
      if (st.length > 0) setStationId(st[0].station_id);
      if (ft.fault_types.length > 0) {
        setFaultType(ft.fault_types[0]);
        setMagnitude(ft.default_magnitudes[ft.fault_types[0]] ?? 15);
      }
    }
    load();
  }, []);

  // Update magnitude default when fault type changes
  useEffect(() => {
    if (faultType && faultInfo.default_magnitudes[faultType] !== undefined) {
      setMagnitude(faultInfo.default_magnitudes[faultType]);
    }
  }, [faultType, faultInfo]);

  async function runInjection() {
    if (!stationId || !faultType) return;
    setLoading(true);
    setError(null);
    setResult(null);
    const res = await injectFault(stationId, faultType, magnitude);
    if (res) {
      setResult(res);
    } else {
      setError("Injection failed. Check the API server is running.");
    }
    setLoading(false);
  }

  const stationName =
    stations.find((s) => s.station_id === stationId)?.station_name || stationId;

  return (
    <div className="space-y-8 fade-in">
      {/* Page header */}
      <div>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-teal-500 to-teal-700 flex items-center justify-center">
            <FlaskConical size={22} className="text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900 tracking-tight">
              Fault Injection Lab
            </h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Test SkyGuard AI with a synthetic sensor fault
            </p>
          </div>
        </div>
      </div>

      {/* Control panel */}
      <Card className="p-6 card-soft">
        <h2 className="text-sm font-semibold text-gray-800 mb-4">
          Configure Injection
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Station dropdown */}
          <div>
            <label className="text-xs font-medium text-gray-600 mb-1.5 block">
              Station
            </label>
            <select
              value={stationId}
              onChange={(e) => setStationId(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm bg-white focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
            >
              {stations.map((s) => (
                <option key={s.station_id} value={s.station_id}>
                  {s.station_name} ({s.station_id})
                </option>
              ))}
            </select>
          </div>

          {/* Fault type dropdown */}
          <div>
            <label className="text-xs font-medium text-gray-600 mb-1.5 block">
              Fault Type
            </label>
            <select
              value={faultType}
              onChange={(e) => setFaultType(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm bg-white focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
            >
              {faultInfo.fault_types.map((ft) => (
                <option key={ft} value={ft}>
                  {humanizeFault(ft)}
                </option>
              ))}
            </select>
          </div>

          {/* Magnitude slider */}
          <div>
            <label className="text-xs font-medium text-gray-600 mb-1.5 block">
              Magnitude:{" "}
              <span className="font-mono font-semibold text-teal-700">
                {magnitude}
              </span>
            </label>
            <input
              type="range"
              min={1}
              max={40}
              value={magnitude}
              onChange={(e) => setMagnitude(Number(e.target.value))}
              className="w-full accent-teal-600"
            />
          </div>
        </div>

        <div className="mt-6 flex items-center gap-3">
          <Button
            onClick={runInjection}
            disabled={loading || !stationId || !faultType}
            className="bg-teal-600 hover:bg-teal-700 text-white"
          >
            {loading ? (
              <>
                <Loader2 size={16} className="mr-2 animate-spin" />
                Running detection…
              </>
            ) : (
              <>
                <Zap size={16} className="mr-2" />
                Inject & Detect
              </>
            )}
          </Button>

          {error && (
            <span className="text-sm text-red-600 flex items-center gap-1">
              <AlertTriangle size={14} />
              {error}
            </span>
          )}
        </div>
      </Card>

      {/* Empty state */}
      {!result && !loading && (
        <Card className="p-12 text-center card-soft">
          <FlaskConical
            size={40}
            className="mx-auto text-gray-300 mb-3"
          />
          <p className="text-sm text-gray-500">
            Select a station and fault type above, then click Inject & Detect.
          </p>
        </Card>
      )}

      {/* Result */}
      {result && (
        <div className="space-y-6 fade-in">
          {/* Original vs Modified reading */}
          <Card className="p-6 card-soft">
            <h2 className="text-sm font-semibold text-gray-800 mb-4">
              Reading Change — {stationName}
            </h2>
            <div className="grid grid-cols-3 gap-4">
              {[
                {
                  label: "Temperature",
                  unit: "°C",
                  orig: result.original_reading.temperature,
                  mod: result.modified_reading.temperature,
                },
                {
                  label: "Pressure",
                  unit: "hPa",
                  orig: result.original_reading.pressure,
                  mod: result.modified_reading.pressure,
                },
                {
                  label: "Humidity",
                  unit: "%",
                  orig: result.original_reading.humidity,
                  mod: result.modified_reading.humidity,
                },
              ].map((p) => {
                const delta = p.mod - p.orig;
                const changed = Math.abs(delta) > 0.01;
                return (
                  <div
                    key={p.label}
                    className="border border-gray-200 rounded-lg p-4"
                  >
                    <p className="text-xs text-gray-500 mb-2">{p.label}</p>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-500 line-through">
                        {p.orig.toFixed(1)}
                      </span>
                      <ArrowRight size={14} className="text-gray-400" />
                      <span
                        className={`text-base font-bold ${
                          changed ? "text-red-600" : "text-gray-900"
                        }`}
                      >
                        {p.mod.toFixed(1)} {p.unit}
                      </span>
                    </div>
                    {changed && (
                      <p className="text-xs text-red-600 mt-1 font-medium">
                        {delta > 0 ? "+" : ""}
                        {delta.toFixed(1)}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </Card>

          {/* Detection result */}
          <Card className="p-6 card-soft border-l-4 border-l-red-500">
            <div className="flex items-start justify-between mb-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <CheckCircle size={18} className="text-red-600" />
                  <span className="text-xs font-bold text-red-700 uppercase tracking-wider">
                    Anomaly Detected
                  </span>
                </div>
                <h3 className="text-xl font-bold text-gray-900">
                  {result.alert.anomaly_type}
                </h3>
                <p className="text-xs text-gray-500 mt-1">
                  {result.alert.timestamp}
                </p>
              </div>
              {result.alert.priority && PRIORITY_STYLES[result.alert.priority] && (
                <span
                  className="px-3 py-1.5 rounded-full text-xs font-semibold"
                  style={{
                    backgroundColor:
                      PRIORITY_STYLES[result.alert.priority].bg,
                    color: PRIORITY_STYLES[result.alert.priority].text,
                  }}
                >
                  {PRIORITY_STYLES[result.alert.priority].label} (
                  {result.alert.priority})
                </span>
              )}
            </div>

            <div className="flex items-center gap-6 text-sm mb-4">
              <span className="text-gray-600">
                Confidence:{" "}
                <b className="text-gray-900">{result.alert.confidence}</b>
              </span>
              <span className="text-gray-600">
                Trust:{" "}
                <b className="text-gray-900">{result.alert.trust_score}</b>
              </span>
              <span className="text-gray-600">
                Severity:{" "}
                <b className="text-gray-900">{result.alert.severity}</b>
              </span>
            </div>

            <Separator className="my-4" />

            <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
              Physical Reasoning
            </h4>
            <p className="text-sm text-gray-700 leading-relaxed mb-4">
              {result.alert.physical_reasoning}
            </p>

            <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
              Evidence
            </h4>
            <div className="flex flex-wrap gap-2 mb-3">
              {Object.entries(result.alert.evidence_breakdown || {})
                .filter(([, d]: any) => d?.fired)
                .map(([source]) => (
                  <span
                    key={source}
                    className="px-2.5 py-1 rounded-full text-xs font-medium bg-teal-50 text-teal-700 border border-teal-200"
                  >
                    {source}
                  </span>
                ))}
            </div>
            <p className="text-xs text-gray-600 mb-4">
              {result.alert.decision_basis}
            </p>

            <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
              Physics Coupling Check
            </h4>
            <p className="text-sm text-gray-700 leading-relaxed mb-4">
              {result.alert.multivariate_analysis?.reason ||
                "Not available"}
            </p>

            <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
              Verdict
            </h4>
            <p className="text-sm text-gray-700 leading-relaxed mb-4">
              {result.alert.weather_verdict_reason}
            </p>

            <div className="bg-teal-50 border border-teal-200 rounded-lg p-4">
              <h4 className="text-xs font-bold text-teal-800 uppercase tracking-wider mb-2">
                Recommended Action
              </h4>
              <p className="text-sm text-teal-900 font-medium">
                {result.alert.maintenance_recommendation}
              </p>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}