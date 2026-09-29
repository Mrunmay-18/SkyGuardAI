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
  Radio,
  Sliders,
  Sparkles,
  Layers,
  Thermometer,
  Gauge,
  Droplet,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
  P1: { bg: "bg-rose-50 border-rose-200/80", text: "text-rose-700", label: "Critical" },
  P2: { bg: "bg-amber-50 border-amber-200/80", text: "text-amber-700", label: "High" },
  P3: { bg: "bg-sky-50 border-sky-200/80", text: "text-sky-700", label: "Routine" },
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
      setError("Injection failed. Check that the API server is running on port 8000.");
    }
    setLoading(false);
  }

  const stationName =
    stations.find((s) => s.station_id === stationId)?.station_name || stationId;

  return (
    <div className="space-y-8 fade-in">
      {/* Page header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-600 to-teal-800 flex items-center justify-center text-white shadow-soft">
          <FlaskConical size={20} />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-stone-900 tracking-tight">
            Fault Injection Lab
          </h1>
          <p className="text-sm text-stone-500 mt-0.5 font-medium">
            Test SkyGuard AI in real-time with synthetic sensor fault injections
          </p>
        </div>
      </div>

      {/* Control panel with visual grouping (Station / Fault / Magnitude) */}
      <Card className="p-6 card-soft rounded-2xl border border-stone-200/80 shadow-soft bg-white">
        <div className="flex items-center justify-between mb-5 pb-3 border-b border-stone-100">
          <div className="flex items-center gap-2">
            <Sliders size={16} className="text-teal-700" />
            <h2 className="text-sm font-bold text-stone-900 tracking-tight">
              Injection Control Configuration
            </h2>
          </div>
          <span className="text-[10px] font-semibold text-teal-800 bg-teal-50 border border-teal-200/70 px-2.5 py-0.5 rounded-full">
            Real-Time Simulator
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Group 1: Station Selection */}
          <div className="p-4 rounded-xl bg-stone-50/70 border border-stone-200/70 space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-stone-600">
              <Radio size={13} className="text-teal-600" />
              <span>Target Station</span>
            </div>
            <select
              value={stationId}
              onChange={(e) => setStationId(e.target.value)}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white text-stone-800 font-medium focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20 shadow-2xs transition-all cursor-pointer"
            >
              {stations.map((s) => (
                <option key={s.station_id} value={s.station_id}>
                  {s.station_name} ({s.station_id})
                </option>
              ))}
            </select>
            <p className="text-[11px] text-stone-400">
              Station undergoing simulated telemetry failure
            </p>
          </div>

          {/* Group 2: Fault Type */}
          <div className="p-4 rounded-xl bg-stone-50/70 border border-stone-200/70 space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-stone-600">
              <Layers size={13} className="text-teal-600" />
              <span>Fault Signature</span>
            </div>
            <select
              value={faultType}
              onChange={(e) => setFaultType(e.target.value)}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white text-stone-800 font-medium focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20 shadow-2xs transition-all cursor-pointer"
            >
              {faultInfo.fault_types.map((ft) => (
                <option key={ft} value={ft}>
                  {humanizeFault(ft)}
                </option>
              ))}
            </select>
            <p className="text-[11px] text-stone-400">
              Select perturbation type injected into sensors
            </p>
          </div>

          {/* Group 3: Magnitude Slider */}
          <div className="p-4 rounded-xl bg-stone-50/70 border border-stone-200/70 space-y-2">
            <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-stone-600">
              <div className="flex items-center gap-1.5">
                <Sparkles size={13} className="text-teal-600" />
                <span>Magnitude</span>
              </div>
              <span className="font-mono font-bold text-teal-800 bg-teal-50 px-2 py-0.5 rounded border border-teal-200/80">
                ±{magnitude}
              </span>
            </div>
            <div className="pt-2">
              <input
                type="range"
                min={1}
                max={40}
                value={magnitude}
                onChange={(e) => setMagnitude(Number(e.target.value))}
                className="w-full accent-teal-700 cursor-pointer"
              />
            </div>
            <div className="flex justify-between text-[10px] text-stone-400 font-mono">
              <span>Mild (1)</span>
              <span>Default ({faultInfo.default_magnitudes[faultType] ?? 15})</span>
              <span>Severe (40)</span>
            </div>
          </div>
        </div>

        {/* Action Button: Gradient Teal, Larger, With Icon */}
        <div className="mt-6 flex flex-wrap items-center gap-4 pt-4 border-t border-stone-100">
          <Button
            onClick={runInjection}
            disabled={loading || !stationId || !faultType}
            className="h-11 px-6 rounded-xl bg-gradient-to-r from-teal-600 to-teal-800 hover:from-teal-700 hover:to-teal-900 text-white font-semibold text-sm shadow-soft cursor-pointer transition-all hover:shadow-md"
          >
            {loading ? (
              <>
                <Loader2 size={16} className="mr-2 animate-spin" />
                Simulating Pipeline Detection…
              </>
            ) : (
              <>
                <Zap size={16} className="mr-2 text-teal-200" />
                Inject Fault & Run Detection
              </>
            )}
          </Button>

          {error && (
            <span className="text-xs text-rose-600 font-medium flex items-center gap-1.5 bg-rose-50 border border-rose-200 px-3 py-2 rounded-lg">
              <AlertTriangle size={14} />
              {error}
            </span>
          )}
        </div>
      </Card>

      {/* Empty state */}
      {!result && !loading && (
        <Card className="p-12 text-center card-soft rounded-2xl border border-stone-200/80 bg-gradient-to-b from-white to-stone-50/50">
          <div className="w-14 h-14 rounded-2xl bg-teal-50 border border-teal-200/70 mx-auto flex items-center justify-center text-teal-600 mb-3 shadow-2xs">
            <FlaskConical size={26} />
          </div>
          <h3 className="text-base font-bold text-stone-900 mb-1">
            Ready to Simulate
          </h3>
          <p className="text-xs text-stone-500 max-w-sm mx-auto leading-relaxed">
            Configure the station and anomaly pattern above, then trigger detection to trace how the ensemble corroborates or rejects the signal.
          </p>
        </Card>
      )}

      {/* Result Panel: Animated Fade-in */}
      {result && (
        <div className="space-y-6 animate-fade-in">
          {/* Reading change with animated arrow */}
          <Card className="p-5 card-soft rounded-2xl border border-stone-200/80 shadow-soft bg-white">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-stone-900 tracking-tight">
                Reading Perturbation — {stationName}
              </h2>
              <span className="text-[10px] font-semibold text-stone-500 bg-stone-100 px-2 py-0.5 rounded-full">
                Pre vs Post Injection
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                {
                  label: "Temperature",
                  unit: "°C",
                  orig: result.original_reading.temperature,
                  mod: result.modified_reading.temperature,
                  Icon: Thermometer,
                  iconColor: "text-rose-500",
                },
                {
                  label: "Pressure",
                  unit: "hPa",
                  orig: result.original_reading.pressure,
                  mod: result.modified_reading.pressure,
                  Icon: Gauge,
                  iconColor: "text-blue-500",
                },
                {
                  label: "Humidity",
                  unit: "%",
                  orig: result.original_reading.humidity,
                  mod: result.modified_reading.humidity,
                  Icon: Droplet,
                  iconColor: "text-emerald-500",
                },
              ].map((p) => {
                const delta = p.mod - p.orig;
                const changed = Math.abs(delta) > 0.01;
                const Icon = p.Icon;

                return (
                  <div
                    key={p.label}
                    className={`rounded-xl p-4 border transition-all ${
                      changed
                        ? "bg-rose-50/30 border-rose-200/90 shadow-2xs"
                        : "bg-stone-50/60 border-stone-200/70"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-stone-600">
                        <Icon size={13} className={p.iconColor} />
                        <span>{p.label}</span>
                      </div>
                      {changed && (
                        <span className="text-[10px] font-bold text-rose-700 bg-rose-100/80 border border-rose-200 px-1.5 py-0.2 rounded-full">
                          {delta > 0 ? "+" : ""}
                          {delta.toFixed(1)} {p.unit}
                        </span>
                      )}
                    </div>

                    {/* Animated arrow between original and modified */}
                    <div className="flex items-center justify-between gap-2 pt-1 font-mono">
                      <span className="text-xs text-stone-400 line-through">
                        {p.orig.toFixed(1)} {p.unit}
                      </span>
                      <div className="w-7 h-7 rounded-full bg-white border border-stone-200 flex items-center justify-center shrink-0 shadow-2xs">
                        <ArrowRight
                          size={14}
                          className={changed ? "text-rose-600 animate-pulse" : "text-stone-400"}
                        />
                      </div>
                      <span
                        className={`text-sm font-bold ${
                          changed ? "text-rose-700" : "text-stone-800"
                        }`}
                      >
                        {p.mod.toFixed(1)} {p.unit}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* Detection Result Card */}
          <Card className="p-6 card-soft rounded-2xl border-l-4 border-l-rose-500 border-stone-200/80 shadow-soft bg-white">
            <div className="flex items-start justify-between mb-4">
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <CheckCircle size={18} className="text-rose-600" />
                  <span className="text-xs font-bold text-rose-700 uppercase tracking-wider">
                    Anomaly Successfully Intercepted
                  </span>
                </div>
                <h3 className="text-xl font-bold text-stone-900 tracking-tight">
                  {result.alert.anomaly_type}
                </h3>
                <p className="text-xs text-stone-500 mt-0.5 font-medium">
                  Timestamp: {result.alert.timestamp}
                </p>
              </div>

              {result.alert.priority && PRIORITY_STYLES[result.alert.priority] && (
                <span
                  className={`px-3 py-1 rounded-full text-xs font-bold border ${
                    PRIORITY_STYLES[result.alert.priority].bg
                  } ${PRIORITY_STYLES[result.alert.priority].text}`}
                >
                  {PRIORITY_STYLES[result.alert.priority].label} ({result.alert.priority})
                </span>
              )}
            </div>

            {/* Chips */}
            <div className="flex flex-wrap items-center gap-3 mb-4">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-teal-50 text-teal-800 border border-teal-200/80">
                Confidence: <b className="font-bold">{result.alert.confidence}%</b>
              </span>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200/80">
                Trust Score: <b className="font-bold">{result.alert.trust_score}/100</b>
              </span>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-stone-100 text-stone-700 border border-stone-200">
                Severity: <b className="font-bold">{result.alert.severity}</b>
              </span>
            </div>

            <Separator className="my-4" />

            <div className="space-y-4">
              <div>
                <h4 className="text-xs font-bold text-stone-500 uppercase tracking-wider mb-1.5">
                  Physical Reasoning & Verification
                </h4>
                <p className="text-xs text-stone-700 leading-relaxed bg-stone-50/70 p-3 rounded-xl border border-stone-200/60 font-medium">
                  {result.alert.physical_reasoning}
                </p>
              </div>

              <div>
                <h4 className="text-xs font-bold text-stone-500 uppercase tracking-wider mb-2">
                  Corroborating Evidence Sources
                </h4>
                <div className="flex flex-wrap gap-2 mb-2">
                  {Object.entries(result.alert.evidence_breakdown || {})
                    .filter(([, d]: any) => d?.fired)
                    .map(([source]) => (
                      <span
                        key={source}
                        className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-teal-50 text-teal-800 border border-teal-200/70 shadow-2xs"
                      >
                        ✓ {source}
                      </span>
                    ))}
                </div>
                <p className="text-xs text-stone-500 leading-relaxed">
                  {result.alert.decision_basis}
                </p>
              </div>

              <div>
                <h4 className="text-xs font-bold text-stone-500 uppercase tracking-wider mb-1.5">
                  Weather Correlation Verdict
                </h4>
                <p className="text-xs text-stone-700 leading-relaxed bg-emerald-50/40 p-3 rounded-xl border border-emerald-200/60 font-medium">
                  {result.alert.weather_verdict_reason}
                </p>
              </div>

              {/* Maintenance recommendation */}
              <div className="bg-gradient-to-r from-teal-50 to-teal-100/40 border border-teal-200/90 rounded-xl p-4">
                <h4 className="text-xs font-bold text-teal-800 uppercase tracking-wider mb-1">
                  Automated Maintenance Protocol
                </h4>
                <p className="text-xs text-teal-950 font-medium leading-relaxed">
                  {result.alert.maintenance_recommendation}
                </p>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}