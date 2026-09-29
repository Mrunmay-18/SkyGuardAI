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

  if (loading) {
    return (
      <div className="text-sm text-gray-500 py-8 text-center">
        Loading stations…
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

  function statusColor(status: StationRow["status"]) {
    switch (status) {
      case "At Risk":
        return { bg: "#FEE2E2", text: "#991B1B", dot: "#EF4444" };
      case "Watch":
        return { bg: "#FEF3C7", text: "#92400E", dot: "#F59E0B" };
      case "Offline":
        return { bg: "#E5E7EB", text: "#374151", dot: "#6B7280" };
      default:
        return { bg: "#D1FAE5", text: "#065F46", dot: "#10B981" };
    }
  }

  return (
    <div className="space-y-6 fade-in">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 tracking-tight">
          AWS Network
        </h1>
        <p className="text-sm text-gray-500 mt-2">
          All {stations.length} Automatic Weather Stations in the Pune region
        </p>
      </div>

      {/* Filter + search bar */}
      <Card className="p-4 card-soft">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Filter size={16} />
            <span className="font-medium">Filter:</span>
          </div>

          {(
            ["All", "Healthy", "Watch", "At Risk", "Offline"] as FilterType[]
          ).map((f) => (
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
          ))}

          <div className="ml-auto flex items-center gap-2 bg-gray-50 rounded-md px-3 py-1.5 border border-gray-200 focus-within:border-teal-400 transition-colors">
            <Search size={14} className="text-gray-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search station…"
              className="bg-transparent text-sm outline-none w-40"
            />
          </div>
        </div>
      </Card>

      {/* Station table */}
      <Card className="overflow-hidden card-soft">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gradient-to-r from-gray-50 to-gray-100/50 border-b border-gray-200">
              <tr className="text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                <th className="px-4 py-3">Station</th>
                <th className="px-4 py-3">Coordinates</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Temp</th>
                <th className="px-4 py-3 text-right">Humidity</th>
                <th className="px-4 py-3 text-right">Pressure</th>
                <th className="px-4 py-3 text-right">Alerts</th>
                <th className="px-4 py-3">Last Alert</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((r) => {
                const c = statusColor(r.status);
                return (
                  <tr
                    key={r.station_id}
                    className="hover:bg-teal-50/40 cursor-pointer transition-colors"
                    onClick={() => setSelected(r)}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <MapPin size={14} className="text-teal-600" />
                        <div>
                          <p className="font-semibold text-gray-900">
                            {r.station_name}
                          </p>
                          <p className="text-xs text-gray-500">
                            {r.station_id}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-600 font-mono">
                      {r.latitude.toFixed(3)}, {r.longitude.toFixed(3)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
                        style={{ backgroundColor: c.bg, color: c.text }}
                      >
                        <span
                          className="w-1.5 h-1.5 rounded-full"
                          style={{ backgroundColor: c.dot }}
                        />
                        {r.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700">
                      {r.latestTemp !== null ? (
                        <span className="flex items-center justify-end gap-1">
                          <Thermometer size={12} className="text-red-500" />
                          {r.latestTemp.toFixed(1)}°C
                        </span>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700">
                      {r.latestHumidity !== null ? (
                        <span className="flex items-center justify-end gap-1">
                          <Droplet size={12} className="text-green-500" />
                          {r.latestHumidity.toFixed(0)}%
                        </span>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700">
                      {r.latestPressure !== null ? (
                        <span className="flex items-center justify-end gap-1">
                          <Gauge size={12} className="text-blue-500" />
                          {r.latestPressure.toFixed(0)}
                        </span>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span
                        className={`font-bold ${
                          r.alerts >= 3
                            ? "text-red-600"
                            : r.alerts >= 1
                            ? "text-amber-600"
                            : "text-gray-400"
                        }`}
                      >
                        {r.alerts}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {r.lastAlertTime || "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {filtered.length === 0 && (
          <div className="text-center py-12 text-sm text-gray-500">
            No stations match your filter
          </div>
        )}
      </Card>

      {/* Station detail modal */}
      {selected && (
        <div
          className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4 fade-in"
          onClick={() => setSelected(null)}
        >
          <div
            className="bg-white rounded-lg max-w-2xl w-full max-h-[80vh] overflow-y-auto p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-lg font-bold text-gray-900">
                  {selected.station_name}
                </h3>
                <p className="text-sm text-gray-500">
                  {selected.station_id} • {selected.latitude.toFixed(4)},{" "}
                  {selected.longitude.toFixed(4)}
                </p>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="text-gray-400 hover:text-gray-700 text-2xl leading-none transition-colors"
              >
                ×
              </button>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <Card className="p-3 card-soft">
                <p className="text-xs text-gray-500 mb-1">Status</p>
                <p
                  className="font-semibold"
                  style={{ color: statusColor(selected.status).dot }}
                >
                  {selected.status}
                </p>
              </Card>
              <Card className="p-3 card-soft">
                <p className="text-xs text-gray-500 mb-1">Alerts</p>
                <p className="font-semibold text-gray-900">{selected.alerts}</p>
              </Card>
              <Card className="p-3 card-soft">
                <p className="text-xs text-gray-500 mb-1">Latest Temp</p>
                <p className="font-semibold text-gray-900">
                  {selected.latestTemp !== null
                    ? `${selected.latestTemp.toFixed(1)}°C`
                    : "—"}
                </p>
              </Card>
              <Card className="p-3 card-soft">
                <p className="text-xs text-gray-500 mb-1">Latest Humidity</p>
                <p className="font-semibold text-gray-900">
                  {selected.latestHumidity !== null
                    ? `${selected.latestHumidity.toFixed(0)}%`
                    : "—"}
                </p>
              </Card>
            </div>

            <h4 className="text-sm font-semibold text-gray-800 mb-2">
              Recent Alerts
            </h4>
            {alerts.filter((a) => a.station_id === selected.station_id)
              .length === 0 ? (
              <p className="text-sm text-gray-500">
                No alerts for this station.
              </p>
            ) : (
              <ul className="space-y-2">
                {alerts
                  .filter((a) => a.station_id === selected.station_id)
                  .map((a, i) => (
                    <li
                      key={i}
                      className="border border-gray-200 rounded-md p-3 text-xs bg-white hover:shadow-sm transition-shadow"
                      style={{
                        borderLeft: `3px solid ${
                          a.priority === "P1"
                            ? "#EF4444"
                            : a.priority === "P2"
                            ? "#F59E0B"
                            : "#3B82F6"
                        }`,
                      }}
                    >
                      <div className="flex justify-between items-start mb-1">
                        <span className="font-semibold text-gray-800">
                          {a.anomaly_type}
                        </span>
                        <Badge variant="outline" className="text-xs">
                          {a.priority}
                        </Badge>
                      </div>
                      <p className="text-gray-500 mb-1">{a.timestamp}</p>
                      <p className="text-gray-700">{a.physical_reasoning}</p>
                    </li>
                  ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}