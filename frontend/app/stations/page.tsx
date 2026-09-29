// app/stations/page.tsx
"use client";

import { useEffect, useState } from "react";
import {
  MapPin,
  Thermometer,
  Droplet,
  Gauge,
  Filter,
  Search,
  Radio,
  ShieldCheck,
  AlertTriangle,
  X,
  SlidersHorizontal,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getAlerts, getStations, type Alert, type Station } from "@/lib/api";

type FilterType = "All" | "Healthy" | "Watch" | "At Risk" | "Offline";

interface StationRow extends Station {
  alerts: number;
  status: "Healthy" | "Watch" | "At Risk" | "Offline";
  latestTemp: number | null;
  latestHumidity: number | null;
  latestPressure: number | null;
  lastAlertTime: string | null;
}

export default function StationsPage() {
  const [stations, setStations] = useState<Station[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterType>("All");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<StationRow | null>(null);

  useEffect(() => {
    async function load() {
      const [st, al] = await Promise.all([getStations(), getAlerts()]);
      setStations(st);
      setAlerts(al);
      setLoading(false);
    }
    load();
  }, []);

  // Skeleton shimmer loading state
  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        {/* Header Skeleton */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="h-5 w-44 bg-stone-200 rounded-full mb-3" />
            <div className="h-8 w-64 bg-stone-200 rounded-lg mb-2" />
            <div className="h-4 w-80 bg-stone-100 rounded" />
          </div>
          <div className="flex gap-2">
            <div className="h-8 w-24 bg-stone-100 rounded-xl" />
            <div className="h-8 w-24 bg-stone-100 rounded-xl" />
          </div>
        </div>

        {/* Filter bar Skeleton */}
        <Card className="p-4 card-soft border border-stone-200/80 rounded-2xl bg-white">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <div className="h-6 w-16 bg-stone-200 rounded-md" />
              <div className="h-7 w-20 bg-stone-100 rounded-full" />
              <div className="h-7 w-24 bg-stone-100 rounded-full" />
              <div className="h-7 w-20 bg-stone-100 rounded-full" />
            </div>
            <div className="h-8 w-52 bg-stone-100 rounded-xl" />
          </div>
        </Card>

        {/* Table Skeleton */}
        <Card className="overflow-hidden card-soft border border-stone-200/80 rounded-2xl bg-white">
          <div className="p-4 border-b border-stone-100 bg-stone-50/50 flex gap-4">
            <div className="h-4 w-28 bg-stone-200 rounded" />
            <div className="h-4 w-24 bg-stone-200 rounded ml-auto" />
          </div>
          <div className="divide-y divide-stone-100">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="py-4 px-5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-stone-200" />
                  <div className="space-y-1.5">
                    <div className="h-4 w-36 bg-stone-200 rounded" />
                    <div className="h-3 w-20 bg-stone-100 rounded" />
                  </div>
                </div>
                <div className="h-6 w-20 bg-stone-100 rounded-full" />
                <div className="h-4 w-12 bg-stone-100 rounded hidden md:block" />
                <div className="h-4 w-12 bg-stone-100 rounded hidden md:block" />
                <div className="h-4 w-12 bg-stone-100 rounded hidden md:block" />
                <div className="h-6 w-12 bg-stone-100 rounded-full" />
              </div>
            ))}
          </div>
        </Card>
      </div>
    );
  }

  const rows: StationRow[] = stations.map((s) => {
    const stationAlerts = alerts.filter((a) => a.station_id === s.station_id);
    const alertsCount = stationAlerts.length;

    let status: StationRow["status"] = "Healthy";
    if (alertsCount >= 3) status = "At Risk";
    else if (alertsCount >= 1) status = "Watch";

    const latest = stationAlerts.length > 0 ? stationAlerts[0] : null;

    return {
      ...s,
      alerts: alertsCount,
      status,
      latestTemp: latest?.temperature ?? null,
      latestHumidity: latest?.humidity ?? null,
      latestPressure: latest?.pressure ?? null,
      lastAlertTime: latest?.timestamp ?? null,
    };
  });

  let filtered = rows;
  if (filter !== "All") {
    filtered = filtered.filter((r) => r.status === filter);
  }
  if (search.trim()) {
    const q = search.toLowerCase();
    filtered = filtered.filter(
      (r) =>
        r.station_name.toLowerCase().includes(q) ||
        r.station_id.toLowerCase().includes(q)
    );
  }

  const counts = {
    All: rows.length,
    Healthy: rows.filter((r) => r.status === "Healthy").length,
    Watch: rows.filter((r) => r.status === "Watch").length,
    "At Risk": rows.filter((r) => r.status === "At Risk").length,
    Offline: rows.filter((r) => r.status === "Offline").length,
  };

  function statusBadge(status: StationRow["status"]) {
    switch (status) {
      case "At Risk":
        return {
          bg: "bg-rose-50",
          text: "text-rose-700",
          border: "border-rose-200/80",
          dot: "bg-rose-500",
          pulse: true,
        };
      case "Watch":
        return {
          bg: "bg-amber-50",
          text: "text-amber-700",
          border: "border-amber-200/80",
          dot: "bg-amber-500",
          pulse: false,
        };
      case "Offline":
        return {
          bg: "bg-stone-100",
          text: "text-stone-600",
          border: "border-stone-200/80",
          dot: "bg-stone-400",
          pulse: false,
        };
      default:
        return {
          bg: "bg-emerald-50",
          text: "text-emerald-700",
          border: "border-emerald-200/80",
          dot: "bg-emerald-500",
          pulse: false,
        };
    }
  }

  return (
    <div className="space-y-6 fade-in">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-teal-50 border border-teal-200/60 text-teal-800 text-xs font-semibold mb-2 shadow-2xs">
            <Radio size={12} className="text-teal-600 animate-pulse" />
            Pune Mesonet Grid
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-stone-900 tracking-tight">
            AWS Network Stations
          </h1>
          <p className="text-xs sm:text-sm text-stone-500 mt-1">
            Real-time telemetry and health monitoring for all {stations.length} Automatic Weather Stations
          </p>
        </div>

        {/* Quick status summary chips */}
        <div className="flex items-center gap-2">
          <div className="px-3 py-1.5 rounded-xl bg-white border border-stone-200/80 shadow-2xs flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="text-xs font-medium text-stone-600">Healthy:</span>
            <span className="text-xs font-bold text-stone-900">{counts.Healthy}</span>
          </div>
          <div className="px-3 py-1.5 rounded-xl bg-white border border-stone-200/80 shadow-2xs flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            <span className="text-xs font-medium text-stone-600">Watch:</span>
            <span className="text-xs font-bold text-stone-900">{counts.Watch}</span>
          </div>
          {counts["At Risk"] > 0 && (
            <div className="px-3 py-1.5 rounded-xl bg-rose-50 border border-rose-200/80 shadow-2xs flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
              <span className="text-xs font-medium text-rose-700">At Risk:</span>
              <span className="text-xs font-bold text-rose-900">{counts["At Risk"]}</span>
            </div>
          )}
        </div>
      </div>

      {/* Filter + search bar */}
      <Card className="p-3.5 sm:p-4 card-soft border border-stone-200/80 rounded-2xl shadow-soft bg-white/90 backdrop-blur-xs">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-stone-500 mr-1">
            <Filter size={14} className="text-teal-600" />
            <span>Filter:</span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {(
              ["All", "Healthy", "Watch", "At Risk", "Offline"] as FilterType[]
            ).map((f) => {
              const isActive = filter === f;
              return (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`px-3 py-1 text-xs rounded-full border transition-all duration-150 font-medium flex items-center gap-1.5 ${
                    isActive
                      ? "bg-teal-700 text-white border-teal-700 shadow-sm font-semibold"
                      : "bg-white text-stone-600 border-stone-200 hover:border-teal-400 hover:text-teal-700 hover:bg-stone-50/50"
                  }`}
                >
                  <span>{f}</span>
                  <span
                    className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono leading-tight ${
                      isActive
                        ? "bg-white/20 text-white font-bold"
                        : "bg-stone-100 text-stone-500"
                    }`}
                  >
                    {counts[f]}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="ml-auto w-full sm:w-auto flex items-center gap-2 bg-stone-50/80 rounded-xl px-3 py-1.5 border border-stone-200/80 focus-within:border-teal-500 focus-within:ring-2 focus-within:ring-teal-500/15 focus-within:bg-white transition-all">
            <Search size={14} className="text-stone-400 shrink-0" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search station ID or name…"
              className="bg-transparent text-xs text-stone-800 outline-none w-full sm:w-48 placeholder:text-stone-400"
            />
            {search && (
              <button
                onClick={() => setSearch("")}
                className="text-stone-400 hover:text-stone-600 text-xs font-bold leading-none p-0.5"
                title="Clear search"
              >
                ✕
              </button>
            )}
          </div>
        </div>
      </Card>

      {/* Station table */}
      <Card className="overflow-hidden card-soft border border-stone-200/80 rounded-2xl shadow-soft bg-white">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gradient-to-r from-stone-50/90 via-stone-50/60 to-white border-b border-stone-200/80">
              <tr className="text-left text-xs font-semibold text-stone-600 uppercase tracking-wider">
                <th className="px-5 py-3.5">Station</th>
                <th className="px-4 py-3.5">Coordinates</th>
                <th className="px-4 py-3.5">Status</th>
                <th className="px-4 py-3.5 text-right">Temp</th>
                <th className="px-4 py-3.5 text-right">Humidity</th>
                <th className="px-4 py-3.5 text-right">Pressure</th>
                <th className="px-4 py-3.5 text-center">Active Alerts</th>
                <th className="px-5 py-3.5 text-right">Last Alert</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {filtered.map((r) => {
                const badge = statusBadge(r.status);
                return (
                  <tr
                    key={r.station_id}
                    className="hover:bg-teal-50/30 cursor-pointer transition-colors even:bg-stone-50/20 group"
                    onClick={() => setSelected(r)}
                  >
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-xl bg-teal-50 border border-teal-200/60 flex items-center justify-center text-teal-700 shrink-0 shadow-2xs group-hover:scale-105 transition-transform">
                          <MapPin size={15} />
                        </div>
                        <div>
                          <p className="font-semibold text-stone-900 group-hover:text-teal-900 transition-colors">
                            {r.station_name}
                          </p>
                          <p className="text-[11px] font-mono text-stone-400">
                            {r.station_id}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3.5 text-xs text-stone-600">
                      <span className="font-mono bg-stone-100/70 border border-stone-200/50 px-2 py-0.5 rounded-md text-[11px]">
                        {r.latitude.toFixed(3)}, {r.longitude.toFixed(3)}
                      </span>
                    </td>
                    <td className="px-4 py-3.5">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${badge.bg} ${badge.text} ${badge.border}`}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${badge.dot} ${
                            badge.pulse ? "animate-pulse" : ""
                          }`}
                        />
                        {r.status}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-right text-stone-700">
                      {r.latestTemp !== null ? (
                        <span className="inline-flex items-center justify-end gap-1 font-medium">
                          <Thermometer size={13} className="text-rose-500" />
                          {r.latestTemp.toFixed(1)}°C
                        </span>
                      ) : (
                        <span className="text-stone-300 font-mono">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3.5 text-right text-stone-700">
                      {r.latestHumidity !== null ? (
                        <span className="inline-flex items-center justify-end gap-1 font-medium">
                          <Droplet size={13} className="text-emerald-500" />
                          {r.latestHumidity.toFixed(0)}%
                        </span>
                      ) : (
                        <span className="text-stone-300 font-mono">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3.5 text-right text-stone-700">
                      {r.latestPressure !== null ? (
                        <span className="inline-flex items-center justify-end gap-1 font-medium">
                          <Gauge size={13} className="text-sky-500" />
                          {r.latestPressure.toFixed(0)} hPa
                        </span>
                      ) : (
                        <span className="text-stone-300 font-mono">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3.5 text-center">
                      {r.alerts >= 3 ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-700 border border-rose-200">
                          <AlertTriangle size={11} />
                          {r.alerts}
                        </span>
                      ) : r.alerts >= 1 ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200">
                          {r.alerts}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs text-stone-400 font-medium">
                          <ShieldCheck size={13} className="text-emerald-500" />
                          0
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-right text-xs text-stone-500 font-mono">
                      {r.lastAlertTime ? r.lastAlertTime.slice(11, 16) + " UTC" : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Empty State */}
        {filtered.length === 0 && (
          <div className="py-16 text-center">
            <div className="w-14 h-14 rounded-2xl bg-stone-100 border border-stone-200 flex items-center justify-center mx-auto mb-3 text-stone-400 shadow-2xs">
              <Search size={24} />
            </div>
            <p className="text-base font-bold text-stone-800">No stations found</p>
            <p className="text-xs text-stone-500 mt-1 max-w-sm mx-auto">
              No weather stations match your current filter and search query. Try clearing filters or using different terms.
            </p>
            <button
              onClick={() => {
                setFilter("All");
                setSearch("");
              }}
              className="mt-4 px-4 py-1.5 text-xs font-semibold rounded-lg bg-teal-50 text-teal-700 hover:bg-teal-100 border border-teal-200 transition-colors shadow-2xs"
            >
              Reset Filters
            </button>
          </div>
        )}
      </Card>

      {/* Station detail modal */}
      {selected && (
        <div
          className="fixed inset-0 bg-stone-900/50 backdrop-blur-xs flex items-center justify-center z-50 p-4 fade-in"
          onClick={() => setSelected(null)}
        >
          <div
            className="bg-white rounded-2xl max-w-2xl w-full max-h-[85vh] overflow-hidden shadow-2xl border border-stone-200/90 flex flex-col animate-scale-in"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="bg-gradient-to-r from-stone-50 via-white to-stone-50/40 px-6 py-4 border-b border-stone-200/80 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-teal-50 border border-teal-200/80 flex items-center justify-center text-teal-700 shadow-2xs">
                  <MapPin size={20} />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-stone-900 leading-tight">
                    {selected.station_name}
                  </h3>
                  <p className="text-xs text-stone-500 font-mono mt-0.5">
                    {selected.station_id} • {selected.latitude.toFixed(4)}°N,{" "}
                    {selected.longitude.toFixed(4)}°E
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="w-8 h-8 rounded-lg hover:bg-stone-200/70 text-stone-400 hover:text-stone-700 flex items-center justify-center transition-colors"
                title="Close"
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6">
              {/* Metric Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3.5 rounded-xl border border-stone-200/80 bg-stone-50/50 card-soft">
                  <p className="text-[11px] font-bold uppercase tracking-wider text-stone-400 mb-1">
                    Status
                  </p>
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        statusBadge(selected.status).dot
                      }`}
                    />
                    <span className="font-bold text-sm text-stone-800">
                      {selected.status}
                    </span>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl border border-stone-200/80 bg-stone-50/50 card-soft">
                  <p className="text-[11px] font-bold uppercase tracking-wider text-stone-400 mb-1">
                    Alert Count
                  </p>
                  <p className="font-bold text-sm text-stone-800">
                    {selected.alerts} active
                  </p>
                </div>

                <div className="p-3.5 rounded-xl border border-stone-200/80 bg-stone-50/50 card-soft">
                  <p className="text-[11px] font-bold uppercase tracking-wider text-stone-400 mb-1">
                    Latest Temp
                  </p>
                  <p className="font-bold text-sm text-stone-800">
                    {selected.latestTemp !== null
                      ? `${selected.latestTemp.toFixed(1)}°C`
                      : "—"}
                  </p>
                </div>

                <div className="p-3.5 rounded-xl border border-stone-200/80 bg-stone-50/50 card-soft">
                  <p className="text-[11px] font-bold uppercase tracking-wider text-stone-400 mb-1">
                    Latest Humidity
                  </p>
                  <p className="font-bold text-sm text-stone-800">
                    {selected.latestHumidity !== null
                      ? `${selected.latestHumidity.toFixed(0)}%`
                      : "—"}
                  </p>
                </div>
              </div>

              {/* Recent Alerts Section */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-stone-700 flex items-center gap-1.5">
                    <AlertTriangle size={14} className="text-amber-500" />
                    Recorded Alerts & Fault Signatures
                  </h4>
                  <span className="text-xs text-stone-400">
                    {
                      alerts.filter((a) => a.station_id === selected.station_id)
                        .length
                    }{" "}
                    total
                  </span>
                </div>

                {alerts.filter((a) => a.station_id === selected.station_id)
                  .length === 0 ? (
                  <div className="p-6 rounded-2xl border border-emerald-200/60 bg-emerald-50/30 text-center">
                    <ShieldCheck size={28} className="mx-auto text-emerald-600 mb-2" />
                    <p className="text-xs font-bold text-emerald-900">
                      Station Operating Reliably
                    </p>
                    <p className="text-[11px] text-emerald-700 mt-0.5">
                      No active anomalies or physical rule violations detected for {selected.station_name}.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {alerts
                      .filter((a) => a.station_id === selected.station_id)
                      .map((a, i) => (
                        <div
                          key={i}
                          className="border border-stone-200/80 rounded-xl p-3.5 text-xs bg-white hover:shadow-soft transition-shadow"
                          style={{
                            borderLeft: `4px solid ${
                              a.priority === "P1"
                                ? "#EF4444"
                                : a.priority === "P2"
                                ? "#F59E0B"
                                : "#3B82F6"
                            }`,
                          }}
                        >
                          <div className="flex justify-between items-start mb-1">
                            <span className="font-semibold text-stone-900 text-sm">
                              {a.anomaly_type}
                            </span>
                            <Badge
                              variant="outline"
                              className={`text-[10px] font-bold font-mono ${
                                a.priority === "P1"
                                  ? "bg-rose-50 text-rose-700 border-rose-200"
                                  : a.priority === "P2"
                                  ? "bg-amber-50 text-amber-700 border-amber-200"
                                  : "bg-sky-50 text-sky-700 border-sky-200"
                              }`}
                            >
                              {a.priority}
                            </Badge>
                          </div>
                          <p className="text-stone-400 font-mono text-[11px] mb-1.5">
                            {a.timestamp}
                          </p>
                          <p className="text-stone-700 leading-relaxed bg-stone-50/70 p-2 rounded-lg border border-stone-100">
                            {a.physical_reasoning}
                          </p>
                        </div>
                      ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}