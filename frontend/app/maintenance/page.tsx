// app/maintenance/page.tsx
"use client";

import { useEffect, useState } from "react";
import {
  Wrench,
  Check,
  AlertTriangle,
  Activity,
  Thermometer,
  Droplet,
  Gauge,
  Zap,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getAlerts, getStations, type Alert, type Station } from "@/lib/api";

type FilterType = "All" | "P1" | "P2" | "P3" | "Acknowledged";

const PRIORITY_STYLES: Record<string, { bg: string; text: string; border: string; label: string }> = {
  P1: { bg: "#FEE2E2", text: "#991B1B", border: "#EF4444", label: "Critical" },
  P2: { bg: "#FEF3C7", text: "#92400E", border: "#F59E0B", label: "High" },
  P3: { bg: "#DBEAFE", text: "#1E40AF", border: "#3B82F6", label: "Routine" },
};

// Map anomaly type → which sensor to inspect
function sensorIcon(anomalyType: string) {
  const t = anomalyType.toLowerCase();
  if (t.includes("temperature") || t.includes("frozen")) {
    return <Thermometer size={14} className="text-red-500" />;
  }
  if (t.includes("humidity") || t.includes("multivariate")) {
    return <Droplet size={14} className="text-green-500" />;
  }
  if (t.includes("pressure")) {
    return <Gauge size={14} className="text-blue-500" />;
  }
  if (t.includes("power") || t.includes("collapse")) {
    return <Zap size={14} className="text-amber-500" />;
  }
  return <Activity size={14} className="text-gray-500" />;
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
      <div className="text-sm text-gray-500 py-8 text-center">
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
    <div className="space-y-6 fade-in">
      {/* Page header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center">
          <Wrench size={22} className="text-white" />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-gray-900 tracking-tight">
            Maintenance Queue
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Prioritized work orders from current alerts
          </p>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4 card-soft">
          <p className="text-xs text-gray-500 mb-1">Total Work Orders</p>
          <p className="text-2xl font-bold text-gray-900">{counts.All}</p>
        </Card>
        <Card className="p-4 card-soft border-l-4 border-l-red-500">
          <p className="text-xs text-gray-500 mb-1">Critical (P1)</p>
          <p className="text-2xl font-bold text-red-700">{counts.P1}</p>
        </Card>
        <Card className="p-4 card-soft border-l-4 border-l-amber-500">
          <p className="text-xs text-gray-500 mb-1">High (P2)</p>
          <p className="text-2xl font-bold text-amber-700">{counts.P2}</p>
        </Card>
        <Card className="p-4 card-soft">
          <p className="text-xs text-gray-500 mb-1">Acknowledged</p>
          <p className="text-2xl font-bold text-green-700">
            {counts.Acknowledged}/{counts.All}
          </p>
        </Card>
      </div>

      {/* Filter buttons */}
      <Card className="p-4 card-soft">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-gray-600 mr-2">
            Filter:
          </span>
          {(["All", "P1", "P2", "P3", "Acknowledged"] as FilterType[]).map(
            (f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3.5 py-1.5 text-xs rounded-full border transition-all duration-150 font-medium ${
                  filter === f
                    ? "bg-teal-600 text-white border-teal-600 shadow-sm"
                    : "bg-white text-gray-700 border-gray-200 hover:border-teal-400 hover:text-teal-700"
                }`}
              >
                {f} ({counts[f]})
              </button>
            )
          )}
        </div>
      </Card>

      {/* Work orders table */}
      <Card className="overflow-hidden card-soft">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gradient-to-r from-gray-50 to-gray-100/50 border-b border-gray-200">
              <tr className="text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                <th className="px-4 py-3">Priority</th>
                <th className="px-4 py-3">Station</th>
                <th className="px-4 py-3">Sensor</th>
                <th className="px-4 py-3">Issue</th>
                <th className="px-4 py-3">Recommended Action</th>
                <th className="px-4 py-3">Detected</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
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
                    className={`hover:bg-teal-50/40 transition-colors ${
                      isAck ? "opacity-60" : ""
                    }`}
                  >
                    <td className="px-4 py-3">
                      <span
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold whitespace-nowrap"
                        style={{ backgroundColor: pri.bg, color: pri.text }}
                      >
                        {alert.priority === "P1" && (
                          <AlertTriangle size={11} />
                        )}
                        {pri.label} ({alert.priority})
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-semibold text-gray-900">
                        {stationName}
                      </p>
                      <p className="text-xs text-gray-500">
                        {alert.station_id}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        {sensorIcon(alert.anomaly_type)}
                        <span className="text-xs text-gray-700">
                          {alert.anomaly_type}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-700 max-w-xs">
                      {alert.physical_reasoning?.slice(0, 80)}
                      {alert.physical_reasoning?.length > 80 ? "…" : ""}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-700 max-w-xs">
                      {maintenanceAction(alert)}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                      {alert.timestamp}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        size="sm"
                        variant={isAck ? "default" : "outline"}
                        onClick={() => toggleAck(key)}
                        className={
                          isAck
                            ? "bg-green-600 hover:bg-green-700 text-white"
                            : ""
                        }
                      >
                        {isAck ? (
                          <>
                            <Check size={13} className="mr-1" />
                            Done
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
          <div className="text-center py-12 text-sm text-gray-500">
            {filter === "Acknowledged"
              ? "No acknowledged work orders yet"
              : "No work orders match your filter"}
          </div>
        )}
      </Card>
    </div>
  );
}