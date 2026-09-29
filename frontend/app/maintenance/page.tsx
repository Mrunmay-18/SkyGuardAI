// app/maintenance/page.tsx
"use client";

import { useEffect, useState } from "react";
import {
  Wrench,
  Check,
  AlertTriangle,
  AlertCircle,
  Activity,
  Thermometer,
  Droplet,
  Gauge,
  Zap,
  CheckCircle2,
  Filter,
  Layers,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getAlerts, getStations, type Alert, type Station } from "@/lib/api";

type FilterType = "All" | "P1" | "P2" | "P3" | "Acknowledged";

const PRIORITY_STYLES: Record<string, { bg: string; text: string; border: string; label: string }> = {
  P1: { bg: "bg-rose-100 text-rose-800 border-rose-300", text: "text-rose-800", border: "#EF4444", label: "Critical" },
  P2: { bg: "bg-amber-100 text-amber-800 border-amber-300", text: "text-amber-800", border: "#F59E0B", label: "High" },
  P3: { bg: "bg-sky-100 text-sky-800 border-sky-300", text: "text-sky-800", border: "#3B82F6", label: "Routine" },
};

// Map anomaly type → which sensor to inspect
function sensorIcon(anomalyType: string) {
  const t = anomalyType.toLowerCase();
  if (t.includes("temperature") || t.includes("frozen")) {
    return <Thermometer size={14} className="text-rose-500" />;
  }
  if (t.includes("humidity") || t.includes("multivariate")) {
    return <Droplet size={14} className="text-emerald-500" />;
  }
  if (t.includes("pressure")) {
    return <Gauge size={14} className="text-blue-500" />;
  }
  if (t.includes("power") || t.includes("collapse")) {
    return <Zap size={14} className="text-amber-500" />;
  }
  return <Activity size={14} className="text-stone-500" />;
}

function maintenanceAction(alert: Alert): string {
  const t = alert.anomaly_type.toLowerCase();
  if (t.includes("frozen")) return "Inspect sensor for stuck value";
  if (t.includes("power") || t.includes("collapse")) return "Check power + connectivity";
  if (t.includes("drift")) return "Recalibrate sensor";
  if (t.includes("spike")) return "Inspect for stuck/frozen value";
  if (t.includes("drop")) return "Inspect sensor reading";
  if (t.includes("multivariate")) return "Check sensor calibration";
  return alert.maintenance_recommendation || "Review manually";
}

export default function MaintenancePage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [stations, setStations] = useState<Station[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterType>("All");
  const [acknowledged, setAcknowledged] = useState<Set<string>>(new Set());

  useEffect(() => {
    async function load() {
      const [al, st] = await Promise.all([getAlerts(), getStations()]);
      setAlerts(al);
      setStations(st);
      setLoading(false);
    }
    load();
  }, []);

  function toggleAck(key: string) {
    const next = new Set(acknowledged);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setAcknowledged(next);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 text-sm text-stone-500 py-16">
        <Activity size={18} className="text-teal-600 animate-spin" />
        Loading maintenance queue…
      </div>
    );
  }

  // Sort by priority (P1 first), then by severity
  const sorted = [...alerts].sort((a, b) => {
    const order: Record<string, number> = { P1: 1, P2: 2, P3: 3 };
    return (order[a.priority] || 99) - (order[b.priority] || 99);
  });

  const filtered = sorted.filter((a) => {
    const key = `${a.station_id}-${a.timestamp}`;
    if (filter === "Acknowledged") return acknowledged.has(key);
    if (filter === "All") return true;
    return a.priority === filter;
  });

  const counts = {
    All: sorted.length,
    P1: sorted.filter((a) => a.priority === "P1").length,
    P2: sorted.filter((a) => a.priority === "P2").length,
    P3: sorted.filter((a) => a.priority === "P3").length,
    Acknowledged: acknowledged.size,
  };

  return (
    <div className="space-y-7 fade-in">
      {/* Page header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-600 to-amber-800 flex items-center justify-center text-white shadow-soft">
          <Wrench size={20} />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-stone-900 tracking-tight">
            Maintenance Queue
          </h1>
          <p className="text-sm text-stone-500 mt-0.5 font-medium">
            Prioritized automated work orders & sensor remediation tasks
          </p>
        </div>
      </div>

      {/* Summary cards with icons + gradient backgrounds */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Work Orders */}
        <Card className="p-4.5 card-soft rounded-2xl bg-gradient-to-br from-slate-50 via-white to-stone-50 border border-stone-200/80 shadow-soft">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-stone-500">
              Total Work Orders
            </span>
            <div className="w-8 h-8 rounded-lg bg-stone-100 flex items-center justify-center text-stone-600 shadow-2xs">
              <Layers size={16} />
            </div>
          </div>
          <p className="text-3xl font-bold text-stone-900 tracking-tight">
            {counts.All}
          </p>
          <p className="text-xs text-stone-400 mt-1">Pending triage & inspection</p>
        </Card>

        {/* Critical (P1) */}
        <Card className="p-4.5 card-soft rounded-2xl bg-gradient-to-br from-rose-50/80 via-white to-rose-50/30 border border-rose-200/80 border-l-4 border-l-rose-500 shadow-soft">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-rose-800">
              Critical (P1)
            </span>
            <div className="w-8 h-8 rounded-lg bg-rose-100 text-rose-700 flex items-center justify-center shadow-2xs">
              <AlertTriangle size={16} />
            </div>
          </div>
          <p className="text-3xl font-bold text-rose-700 tracking-tight">
            {counts.P1}
          </p>
          <p className="text-xs text-rose-600 mt-1 font-medium">Urgent dispatch required</p>
        </Card>

        {/* High (P2) */}
        <Card className="p-4.5 card-soft rounded-2xl bg-gradient-to-br from-amber-50/80 via-white to-amber-50/30 border border-amber-200/80 border-l-4 border-l-amber-500 shadow-soft">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-amber-800">
              High (P2)
            </span>
            <div className="w-8 h-8 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center shadow-2xs">
              <AlertCircle size={16} />
            </div>
          </div>
          <p className="text-3xl font-bold text-amber-700 tracking-tight">
            {counts.P2}
          </p>
          <p className="text-xs text-amber-600 mt-1 font-medium">Monitoring & calibrate</p>
        </Card>

        {/* Acknowledged */}
        <Card className="p-4.5 card-soft rounded-2xl bg-gradient-to-br from-emerald-50/80 via-white to-emerald-50/30 border border-emerald-200/80 border-l-4 border-l-emerald-500 shadow-soft">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-800">
              Acknowledged
            </span>
            <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center shadow-2xs">
              <CheckCircle2 size={16} />
            </div>
          </div>
          <p className="text-3xl font-bold text-emerald-700 tracking-tight">
            {counts.Acknowledged}/{counts.All}
          </p>
          <p className="text-xs text-emerald-600 mt-1 font-medium">Operator review status</p>
        </Card>
      </div>

      {/* Filter buttons styled as toggle pills */}
      <Card className="p-3.5 card-soft rounded-2xl border border-stone-200/80 shadow-soft bg-white">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold text-stone-700 uppercase tracking-wider mr-2 flex items-center gap-1.5">
            <Filter size={13} className="text-teal-600" />
            Filter Queue:
          </span>
          {(["All", "P1", "P2", "P3", "Acknowledged"] as FilterType[]).map(
            (f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3.5 py-1.5 text-xs rounded-full border transition-all duration-150 font-medium cursor-pointer ${
                  filter === f
                    ? "bg-teal-700 text-white border-teal-700 shadow-xs ring-1 ring-teal-700/20 font-semibold"
                    : "bg-white text-stone-600 border-stone-200 hover:border-teal-400 hover:text-stone-900"
                }`}
              >
                {f} ({counts[f]})
              </button>
            )
          )}
        </div>
      </Card>

      {/* Work orders table: Striped rows + Hover highlight + Prominent priority pills */}
      <Card className="overflow-hidden card-soft rounded-2xl border border-stone-200/80 shadow-soft bg-white">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gradient-to-r from-stone-50 to-stone-100/70 border-b border-stone-200">
              <tr className="text-left text-[11px] font-bold text-stone-600 uppercase tracking-wider">
                <th className="px-4 py-3.5">Priority</th>
                <th className="px-4 py-3.5">Station</th>
                <th className="px-4 py-3.5">Sensor Issue</th>
                <th className="px-4 py-3.5">Physical Diagnostics</th>
                <th className="px-4 py-3.5">Recommended Action</th>
                <th className="px-4 py-3.5">Detected</th>
                <th className="px-4 py-3.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {filtered.map((alert, i) => {
                const key = `${alert.station_id}-${alert.timestamp}`;
                const isAck = acknowledged.has(key);
                const pri = PRIORITY_STYLES[alert.priority] || PRIORITY_STYLES.P3;
                const stationName =
                  stations.find((s) => s.station_id === alert.station_id)
                    ?.station_name || alert.station_id;

                return (
                  <tr
                    key={i}
                    className={`transition-colors even:bg-stone-50/40 odd:bg-white hover:bg-teal-50/50 ${
                      isAck ? "opacity-60 bg-stone-50/80" : ""
                    }`}
                  >
                    {/* Prominent priority pill */}
                    <td className="px-4 py-3.5">
                      <span
                        className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border shadow-2xs whitespace-nowrap ${pri.bg}`}
                      >
                        {alert.priority === "P1" && (
                          <AlertTriangle size={12} className="shrink-0" />
                        )}
                        {pri.label} ({alert.priority})
                      </span>
                    </td>

                    <td className="px-4 py-3.5">
                      <p className="font-bold text-stone-900">
                        {stationName}
                      </p>
                      <p className="text-[11px] text-stone-400 font-mono">
                        {alert.station_id}
                      </p>
                    </td>

                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-md bg-stone-100 flex items-center justify-center shrink-0">
                          {sensorIcon(alert.anomaly_type)}
                        </div>
                        <span className="text-xs text-stone-800 font-semibold">
                          {alert.anomaly_type}
                        </span>
                      </div>
                    </td>

                    <td className="px-4 py-3.5 text-xs text-stone-600 max-w-xs leading-relaxed">
                      {alert.physical_reasoning?.slice(0, 85)}
                      {alert.physical_reasoning?.length > 85 ? "…" : ""}
                    </td>

                    <td className="px-4 py-3.5 text-xs font-medium text-teal-900 max-w-xs">
                      <span className="bg-teal-50/80 border border-teal-100 px-2 py-1 rounded-lg block">
                        {maintenanceAction(alert)}
                      </span>
                    </td>

                    <td className="px-4 py-3.5 text-xs text-stone-400 whitespace-nowrap font-mono">
                      {alert.timestamp}
                    </td>

                    <td className="px-4 py-3.5 text-right">
                      <Button
                        size="sm"
                        variant={isAck ? "default" : "outline"}
                        onClick={() => toggleAck(key)}
                        className={`cursor-pointer rounded-lg text-xs font-semibold shadow-2xs transition-all ${
                          isAck
                            ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                            : "border-stone-200 hover:bg-stone-50 hover:text-stone-900"
                        }`}
                      >
                        {isAck ? (
                          <>
                            <Check size={13} className="mr-1" />
                            Resolved
                          </>
                        ) : (
                          "Acknowledge"
                        )}
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {filtered.length === 0 && (
          <div className="text-center py-16 text-sm text-stone-500 bg-white">
            <CheckCircle2 size={32} className="mx-auto text-emerald-500 mb-2 opacity-80" />
            <p className="font-semibold text-stone-800">
              {filter === "Acknowledged"
                ? "No acknowledged work orders yet"
                : "No work orders matching this filter"}
            </p>
            <p className="text-xs text-stone-400 mt-1">
              Select another filter tier above to view tasks
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}