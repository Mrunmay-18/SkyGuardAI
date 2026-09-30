// app/reality-check/page.tsx
"use client";

import { useEffect, useState } from "react";
import { BASE_URL } from "@/lib/api";
import {
  Target,
  AlertTriangle,
  CheckCircle,
  Thermometer,
  RefreshCw,
  Loader2,
  MapPin,
  Sparkles,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface Reading {
  station_id: string;
  temperature: number;
  humidity: number;
  pressure: number;
  is_target: boolean;
}

interface ScenarioAlert {
  station_id: string;
  timestamp: string;
  anomaly_type: string;
  confidence: number;
  severity: string;
  priority: string;
  trust_score: number;
  physical_reasoning: string;
  weather_verdict_reason: string;
  maintenance_recommendation: string;
  decision_basis: string;
  counter_reasoning: {
    verdict: string;
    reason: string;
    reliability: string;
    reliability_note: string;
  };
  evidence_breakdown: Record<string, { fired: boolean; weight: number }>;
  genuine_weather_event: boolean;
  event_class: string;
  _demo_override?: boolean;
}

interface Scenario {
  label: string;
  alert: ScenarioAlert;
  readings: Reading[];
}

interface ComparisonResponse {
  target_station: string;
  latest_timestamp: string;
  case_a: Scenario;
  case_b: Scenario;
}

const PRIORITY_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  P1: { bg: "bg-rose-50 border-rose-200/80", text: "text-rose-700", label: "Critical" },
  P2: { bg: "bg-amber-50 border-amber-200/80", text: "text-amber-700", label: "High" },
  P3: { bg: "bg-sky-50 border-sky-200/80", text: "text-sky-700", label: "Routine" },
};

export default function RealityCheckPage() {
  const [data, setData] = useState<ComparisonResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  async function load() {
    setRunning(true);
    try {
      const res = await fetch(`${BASE_URL}/reality-check`);
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
    setRunning(false);
  }

  useEffect(() => {
    load();
  }, []);

  if (loading && !data) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-stone-500 animate-fade-in">
        <Loader2 size={24} className="animate-spin text-teal-600" />
        <p className="text-sm font-medium">
          Running dual scenario verification through the analytical pipeline…
        </p>
      </div>
    );
  }

  if (!data) {
    return (
      <Card className="p-8 text-center card-soft border-rose-200 bg-rose-50/40">
        <AlertTriangle size={24} className="mx-auto text-rose-600 mb-2" />
        <h3 className="text-base font-bold text-stone-900 mb-1">
          Scenarios Unavailable
        </h3>
        <p className="text-xs text-stone-500 mb-4">
          Failed to load scenarios. Please verify that the API server is active on port 8000.
        </p>
        <Button onClick={load} size="sm" variant="outline" className="cursor-pointer">
          Try Again
        </Button>
      </Card>
    );
  }

  return (
    <div className="space-y-8 fade-in">
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-600 to-teal-800 flex items-center justify-center text-white shadow-soft">
            <Target size={20} />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-stone-900 tracking-tight">
              Reality Check
            </h1>
            <p className="text-sm text-stone-500 mt-0.5 font-medium">
              Sensor fault vs genuine meteorological event — side-by-side analysis
            </p>
          </div>
        </div>

        <Button
          onClick={load}
          disabled={running}
          variant="outline"
          className="gap-2 cursor-pointer shadow-xs border-stone-200 hover:bg-stone-50 font-medium"
        >
          {running ? (
            <Loader2 size={14} className="animate-spin text-teal-600" />
          ) : (
            <RefreshCw size={14} className="text-stone-500" />
          )}
          Refresh Scenarios
        </Button>
      </div>

      {/* Explanation banner */}
      <Card className="p-5 card-soft bg-gradient-to-r from-teal-50/70 via-white to-stone-50/40 border-stone-200/80">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-lg bg-teal-100/70 border border-teal-200/60 flex items-center justify-center text-teal-700 shrink-0">
            <Sparkles size={16} />
          </div>
          <div>
            <p className="text-sm text-stone-700 leading-relaxed font-normal">
              An anomalous reading can signify two fundamentally different phenomena: a{" "}
              <b className="text-stone-900 font-semibold">hardware sensor fault</b>, or a{" "}
              <b className="text-stone-900 font-semibold">genuine regional atmospheric change</b>.
              SkyGuard resolves this ambiguity using spatial neighbor consistency and physical coupling models.
            </p>
            <p className="text-xs text-stone-500 mt-2 font-medium">
              Below are two contrasting cases processed by the exact same pipeline producing divergent diagnostic verdicts.
            </p>
          </div>
        </div>
      </Card>

      {/* Comparison grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ScenarioCard
          scenario={data.case_a}
          timestamp={data.latest_timestamp}
          accent="red"
        />
        <ScenarioCard
          scenario={data.case_b}
          timestamp={data.latest_timestamp}
          accent="teal"
        />
      </div>

      {/* Footer note */}
      <p className="text-xs text-stone-400 text-center font-medium">
        Case B verdict illustrates regional spatial consistency. Case A is live multi-station inference.
      </p>
    </div>
  );
}

// ----------------------------------------------------------------------
// Scenario Card
// ----------------------------------------------------------------------
function ScenarioCard({
  scenario,
  timestamp,
  accent,
}: {
  scenario: Scenario;
  timestamp: string;
  accent: "red" | "teal";
}) {
  const alert = scenario.alert;
  const isWeather = alert.genuine_weather_event;
  const pri = PRIORITY_STYLES[alert.priority] || PRIORITY_STYLES.P3;

  const isCaseA = accent === "red";

  return (
    <Card className="overflow-hidden card-soft rounded-2xl border border-stone-200/80 bg-white shadow-soft">
      {/* Header: Red-tinted with AlertTriangle for Case A, Green-tinted with CheckCircle for Case B */}
      <div
        className={`px-5 py-4 border-b flex items-center justify-between ${
          isCaseA
            ? "bg-gradient-to-r from-rose-50 via-rose-50/40 to-transparent border-rose-200/80"
            : "bg-gradient-to-r from-emerald-50 via-emerald-50/40 to-transparent border-emerald-200/80"
        }`}
      >
        <div className="flex items-center gap-3">
          <div
            className={`w-9 h-9 rounded-xl flex items-center justify-center border shadow-2xs ${
              isCaseA
                ? "bg-rose-100 text-rose-700 border-rose-200"
                : "bg-emerald-100 text-emerald-700 border-emerald-200"
            }`}
          >
            {isCaseA ? <ShieldAlert size={18} /> : <ShieldCheck size={18} />}
          </div>
          <div>
            <h2 className="text-sm font-bold text-stone-900 tracking-tight">
              {isCaseA ? "Case A — Sensor Fault" : "Case B — Weather Event"}
            </h2>
            <p className="text-xs text-stone-500 font-medium">
              {scenario.label.split(": ")[1] || scenario.label}
            </p>
          </div>
        </div>

        <span className="text-[11px] font-mono text-stone-400 bg-white/80 px-2 py-0.5 rounded border border-stone-200/60">
          {timestamp}
        </span>
      </div>

      <div className="p-5 space-y-4">
        {/* Reading rows: subtle background per row, target row highlighted */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-[11px] font-bold text-stone-500 uppercase tracking-wider px-1">
            <span>Station Network</span>
            <span>Temperature Reading</span>
          </div>

          {scenario.readings.map((r) => (
            <div
              key={r.station_id}
              className={`flex items-center justify-between text-xs px-3 py-2 rounded-xl border transition-all ${
                r.is_target
                  ? "bg-gradient-to-r from-amber-50 to-amber-100/60 border-amber-300 font-semibold shadow-2xs ring-1 ring-amber-400/20"
                  : "bg-stone-50/70 border-stone-200/60 text-stone-700 hover:bg-stone-50"
              }`}
            >
              <div className="flex items-center gap-2">
                <MapPin
                  size={12}
                  className={r.is_target ? "text-amber-700" : "text-stone-400"}
                />
                <span className={r.is_target ? "text-stone-900 font-bold" : "text-stone-700"}>
                  {r.station_id}
                </span>
                {r.is_target && (
                  <span className="text-[10px] font-bold text-amber-800 bg-amber-200/70 border border-amber-300/80 px-1.5 py-0.2 rounded-full">
                    Target Station
                  </span>
                )}
              </div>

              <div className="flex items-center gap-1.5 font-mono">
                <Thermometer
                  size={12}
                  className={r.is_target ? "text-rose-600" : "text-stone-400"}
                />
                <span
                  className={
                    r.is_target
                      ? "text-rose-700 font-bold text-sm"
                      : "text-stone-800 font-medium"
                  }
                >
                  {r.temperature?.toFixed(1) ?? "—"}°C
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Verdict banner: big, bold, colorful */}
        <div
          className={`rounded-2xl p-4 border shadow-soft ${
            isWeather
              ? "bg-gradient-to-r from-emerald-50 via-teal-50/50 to-emerald-50/30 border-emerald-200/90 text-emerald-950"
              : "bg-gradient-to-r from-rose-50 via-red-50/50 to-rose-50/30 border-rose-200/90 text-rose-950"
          }`}
        >
          <div className="flex items-center gap-2 mb-1.5">
            {isWeather ? (
              <CheckCircle size={18} className="text-emerald-700 shrink-0" />
            ) : (
              <AlertTriangle size={18} className="text-rose-700 shrink-0" />
            )}
            <span className="text-sm font-extrabold uppercase tracking-wide">
              {isWeather ? "Genuine Weather Event" : "Sensor Fault Detected"}
            </span>
          </div>
          <p className="text-xs leading-relaxed font-medium pl-6">
            {alert.weather_verdict_reason}
          </p>
        </div>

        {/* Metrics Chips */}
        <div className="grid grid-cols-3 gap-3 text-xs">
          <div className="p-2.5 rounded-xl bg-stone-50 border border-stone-200/70">
            <p className="text-[10px] font-bold uppercase text-stone-500 mb-0.5">
              Trust Score
            </p>
            <p className="font-bold text-stone-900 text-sm">{alert.trust_score}/100</p>
          </div>
          <div className="p-2.5 rounded-xl bg-stone-50 border border-stone-200/70">
            <p className="text-[10px] font-bold uppercase text-stone-500 mb-0.5">
              Confidence
            </p>
            <p className="font-bold text-stone-900 text-sm">{alert.confidence}/100</p>
          </div>
          <div className="p-2.5 rounded-xl bg-stone-50 border border-stone-200/70">
            <p className="text-[10px] font-bold uppercase text-stone-500 mb-0.5">
              Priority Tier
            </p>
            <span
              className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-bold border ${pri.bg} ${pri.text}`}
            >
              {pri.label} ({alert.priority})
            </span>
          </div>
        </div>

        {/* Detected as info */}
        <div className="text-xs text-stone-600 bg-stone-50/60 p-2.5 rounded-xl border border-stone-200/60 flex items-center justify-between">
          <span className="text-stone-500">Anomaly Classification:</span>
          <b className="text-stone-900 font-semibold">{alert.anomaly_type}</b>
        </div>

        {/* Recommended action */}
        <div className="border-t border-stone-100 pt-3">
          <p className="text-[10px] text-stone-400 uppercase tracking-wider font-bold mb-1">
            Recommended Action
          </p>
          <p className="text-xs text-stone-700 leading-relaxed font-medium">
            {alert.maintenance_recommendation}
          </p>
        </div>

        {/* Demo override note */}
        {alert._demo_override && (
          <div className="text-[10px] text-stone-400 italic border-t border-stone-100 pt-2 text-center">
            Demo scenario simulation for contrast.
          </div>
        )}
      </div>
    </Card>
  );
}