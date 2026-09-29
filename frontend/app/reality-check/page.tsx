// app/reality-check/page.tsx
"use client";

import { useEffect, useState } from "react";
import {
  Target,
  AlertTriangle,
  CheckCircle,
  Thermometer,
  RefreshCw,
  Loader2,
  MapPin,
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
  P1: { bg: "#FEE2E2", text: "#991B1B", label: "Critical" },
  P2: { bg: "#FEF3C7", text: "#92400E", label: "High" },
  P3: { bg: "#DBEAFE", text: "#1E40AF", label: "Routine" },
};

export default function RealityCheckPage() {
  const [data, setData] = useState<ComparisonResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  async function load() {
    setRunning(true);
    try {
      const res = await fetch("http://localhost:8000/api/reality-check");
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
      <div className="text-sm text-gray-500 py-8 text-center">
        Running both scenarios through the pipeline…
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-sm text-red-500 py-8 text-center">
        Failed to load scenarios. Check the API is running.
      </div>
    );
  }

  return (
    <div className="space-y-8 fade-in">
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-red-500 to-teal-600 flex items-center justify-center">
            <Target size={22} className="text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900 tracking-tight">
              Reality Check
            </h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Sensor fault vs genuine weather event — two contrasting cases
            </p>
          </div>
        </div>

        <Button
          onClick={load}
          disabled={running}
          variant="outline"
          className="gap-2"
        >
          {running ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <RefreshCw size={14} />
          )}
          Refresh Scenarios
        </Button>
      </div>

      {/* Explanation */}
      <Card className="p-5 card-soft bg-gradient-to-r from-teal-50/50 to-transparent">
        <p className="text-sm text-gray-700 leading-relaxed">
          An unusual reading can mean two very different things: a{" "}
          <b className="text-gray-900">faulty sensor</b>, or a{" "}
          <b className="text-gray-900">genuine atmospheric change</b>.
          SkyGuard distinguishes between them by comparing the target
          station to its neighbors and checking whether the reading is
          physically consistent with atmospheric behavior.
        </p>
        <p className="text-xs text-gray-500 mt-3">
          Two contrasting scenarios below — same pipeline, different
          conclusions.
        </p>
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
      <p className="text-xs text-gray-400 text-center">
        Case B verdict is illustrated for demonstration. See documentation
        for current detector coverage of gradual regional events.
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

  const accentColors =
    accent === "red"
      ? { border: "#EF4444", bg: "#FEF2F2" }
      : { border: "#0F766E", bg: "#F0FDFA" };

  return (
    <Card
      className="p-5 card-soft"
      // border-left color
    >
      <div
        style={{
          borderLeft: `4px solid ${accentColors.border}`,
          paddingLeft: 16,
          marginLeft: -20,
          marginRight: -20,
          marginTop: -20,
          marginBottom: 16,
          paddingTop: 20,
          paddingBottom: 20,
          paddingRight: 20,
          backgroundColor: accentColors.bg,
          borderTopRightRadius: 8,
        }}
      >
        <h2 className="text-sm font-bold text-gray-800 mb-0.5">
          {accent === "red" ? "Case A — " : "Case B — "}
          <span className="font-normal text-gray-600">
            {scenario.label.split(": ")[1]}
          </span>
        </h2>
        <p className="text-xs text-gray-500">{timestamp}</p>
      </div>

      {/* Station readings */}
      <div className="space-y-1.5 mb-5">
        {scenario.readings.map((r) => (
          <div
            key={r.station_id}
            className={`flex items-center justify-between text-xs px-2.5 py-1.5 rounded ${
              r.is_target
                ? "bg-amber-50 border border-amber-200 font-semibold"
                : "bg-gray-50"
            }`}
          >
            <span className="flex items-center gap-1.5 text-gray-700">
              <MapPin size={11} />
              {r.station_id}
              {r.is_target && (
                <span className="text-amber-700 text-[10px]">← target</span>
              )}
            </span>
            <span className="flex items-center gap-2 text-gray-800">
              <Thermometer size={11} className="text-red-500" />
              {r.temperature?.toFixed(1) ?? "—"}°C
            </span>
          </div>
        ))}
      </div>

      {/* Verdict */}
      <div
        className="rounded-lg p-3 mb-4"
        style={{
          backgroundColor: isWeather ? "#D1FAE5" : "#FEE2E2",
        }}
      >
        <div className="flex items-center gap-2 mb-1">
          {isWeather ? (
            <CheckCircle size={16} className="text-green-700" />
          ) : (
            <AlertTriangle size={16} className="text-red-700" />
          )}
          <span
            className="text-xs font-bold uppercase tracking-wider"
            style={{ color: isWeather ? "#065F46" : "#991B1B" }}
          >
            {isWeather ? "Genuine Weather Event" : "Sensor Fault"}
          </span>
        </div>
        <p
          className="text-xs leading-relaxed"
          style={{ color: isWeather ? "#065F46" : "#7F1D1D" }}
        >
          {alert.weather_verdict_reason}
        </p>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-3 gap-2 mb-4 text-xs">
        <div>
          <p className="text-gray-500 mb-0.5">Trust</p>
          <p className="font-bold text-gray-900">{alert.trust_score}/100</p>
        </div>
        <div>
          <p className="text-gray-500 mb-0.5">Confidence</p>
          <p className="font-bold text-gray-900">{alert.confidence}/100</p>
        </div>
        <div>
          <p className="text-gray-500 mb-0.5">Priority</p>
          <span
            className="inline-block px-2 py-0.5 rounded text-[11px] font-semibold"
            style={{ backgroundColor: pri.bg, color: pri.text }}
          >
            {pri.label} ({alert.priority})
          </span>
        </div>
      </div>

      {/* Detected as */}
      <div className="text-xs text-gray-600 mb-4">
        <span className="text-gray-500">Detected as: </span>
        <b className="text-gray-900">{alert.anomaly_type}</b>
      </div>

      {/* Recommended action */}
      <div className="border-t border-gray-100 pt-3">
        <p className="text-[11px] text-gray-500 uppercase tracking-wider font-bold mb-1">
          Recommended Action
        </p>
        <p className="text-xs text-gray-700">
          {alert.maintenance_recommendation}
        </p>
      </div>

      {/* Demo override note */}
      {alert._demo_override && (
        <div className="mt-3 text-[10px] text-gray-400 italic border-t border-gray-100 pt-2">
          Demo override — see pipeline notes. Case A is real inference.
        </div>
      )}
    </Card>
  );
}