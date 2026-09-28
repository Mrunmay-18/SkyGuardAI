// components/dashboard/StationMap.tsx
"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { getAlerts, getStations, type Alert, type Station } from "@/lib/api";

export default function StationMap() {
  const [stations, setStations] = useState<Station[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [hovered, setHovered] = useState<string | null>(null);

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
      <Card className="p-8 text-center text-sm text-gray-500">
        Loading network…
      </Card>
    );
  }

  // Count alerts per station
  const alertCounts: Record<string, number> = {};
  alerts.forEach((a) => {
    alertCounts[a.station_id] = (alertCounts[a.station_id] || 0) + 1;
  });

  function stationStatus(sid: string) {
    const n = alertCounts[sid] || 0;
    if (n >= 3) return { label: "At Risk", color: "#EF4444", bg: "#FEE2E2" };
    if (n >= 1) return { label: "Watch", color: "#F59E0B", bg: "#FEF3C7" };
    return { label: "Healthy", color: "#10B981", bg: "#D1FAE5" };
  }

  // Map lat/lon → normalized 0-100 coordinates within a container.
  // Find bounding box first.
  const lats = stations.map((s) => s.latitude);
  const lons = stations.map((s) => s.longitude);
  const latMin = Math.min(...lats);
  const latMax = Math.max(...lats);
  const lonMin = Math.min(...lons);
  const lonMax = Math.max(...lons);

  function projectX(lon: number) {
    if (lonMax === lonMin) return 50;
    // Pad so markers don't stick to edges
    return 12 + ((lon - lonMin) / (lonMax - lonMin)) * 76;
  }

  function projectY(lat: number) {
    if (latMax === latMin) return 50;
    // Invert Y (latitude increases upward)
    return 88 - ((lat - latMin) / (latMax - latMin)) * 76;
  }

  return (
    <Card className="overflow-hidden card-soft">
      <div className="p-5 border-b border-gray-200 bg-gradient-to-r from-teal-50/50 to-transparent">
        <h3 className="text-sm font-bold text-gray-900 tracking-tight">
          AWS Network Topology — Pune Region
        </h3>
        <p className="text-xs text-gray-500 mt-0.5">
          5 stations • hover a marker to see details
        </p>
      </div>

      <div
        className="relative bg-gradient-to-br from-slate-50 via-white to-teal-50"
        style={{ height: 500 }}
      >
        {/* SVG layer for connections + radar sweep */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
        >
          {/* Connections between all stations (mesh) */}
          {stations.map((a, i) =>
            stations.slice(i + 1).map((b) => (
              <line
                key={`${a.station_id}-${b.station_id}`}
                x1={projectX(a.longitude)}
                y1={projectY(a.latitude)}
                x2={projectX(b.longitude)}
                y2={projectY(b.latitude)}
                stroke="#0F766E"
                strokeWidth="0.2"
                strokeOpacity="0.2"
                strokeDasharray="1 1"
              />
            ))
          )}

          {/* Radar sweep rings */}
          {[15, 25, 35, 45].map((r, i) => (
            <circle
              key={r}
              cx="50"
              cy="50"
              r={r}
              fill="none"
              stroke="#0F766E"
              strokeWidth="0.2"
              strokeOpacity="0.3"
              style={{
                animation: `pulse-ring 3s cubic-bezier(0.4, 0, 0.6, 1) ${i * 0.6}s infinite`,
                transformOrigin: "50px 50px",
              }}
            />
          ))}
        </svg>

        {/* Station markers */}
        {stations.map((s) => {
          const status = stationStatus(s.station_id);
          const x = projectX(s.longitude);
          const y = projectY(s.latitude);
          const count = alertCounts[s.station_id] || 0;
          const isHovered = hovered === s.station_id;

          return (
            <div
              key={s.station_id}
              className="absolute cursor-pointer transition-transform"
              style={{
                left: `${x}%`,
                top: `${y}%`,
                transform: `translate(-50%, -50%) scale(${isHovered ? 1.15 : 1})`,
                zIndex: isHovered ? 30 : 10,
              }}
              onMouseEnter={() => setHovered(s.station_id)}
              onMouseLeave={() => setHovered(null)}
            >
              {/* Pulse ring behind marker if alerts exist */}
              {count > 0 && (
                <span
                  className="absolute inset-0 rounded-full pulse-marker"
                  style={{
                    backgroundColor: status.color,
                    opacity: 0.3,
                  }}
                />
              )}

              {/* Marker dot */}
              <div
                className="relative w-5 h-5 rounded-full border-2 border-white shadow-md"
                style={{ backgroundColor: status.color }}
              />

              {/* Label */}
              <div
                className="absolute whitespace-nowrap text-xs font-medium"
                style={{
                  left: "50%",
                  top: "calc(100% + 6px)",
                  transform: "translateX(-50%)",
                  color: "#17201E",
                }}
              >
                {s.station_name}
              </div>

              {/* Tooltip on hover */}
              {isHovered && (
                <div
                  className="absolute bg-white shadow-lg rounded-md border border-gray-200 p-3 text-xs"
                  style={{
                    left: "50%",
                    bottom: "calc(100% + 10px)",
                    transform: "translateX(-50%)",
                    minWidth: 180,
                    zIndex: 40,
                  }}
                >
                  <p className="font-bold text-gray-900 mb-1">
                    {s.station_name}
                  </p>
                  <p className="text-gray-500 mb-2">
                    {s.station_id} • {s.latitude.toFixed(3)},{" "}
                    {s.longitude.toFixed(3)}
                  </p>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Alerts:</span>
                    <span className="font-bold">{count}</span>
                  </div>
                  <div className="flex items-center justify-between mt-1">
                    <span className="text-gray-600">Status:</span>
                    <span
                      className="font-bold"
                      style={{ color: status.color }}
                    >
                      {status.label}
                    </span>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {/* Legend overlay */}
        <div className="absolute bottom-4 right-4 bg-white/95 backdrop-blur rounded-md shadow-md p-3 text-xs border border-gray-200">
          <p className="font-semibold mb-2 text-gray-800">Status</p>
          <div className="flex items-center gap-2 mb-1">
            <span
              className="inline-block w-3 h-3 rounded-full"
              style={{ backgroundColor: "#10B981" }}
            />
            <span className="text-gray-700">Healthy (0 alerts)</span>
          </div>
          <div className="flex items-center gap-2 mb-1">
            <span
              className="inline-block w-3 h-3 rounded-full"
              style={{ backgroundColor: "#F59E0B" }}
            />
            <span className="text-gray-700">Watch (1-2 alerts)</span>
          </div>
          <div className="flex items-center gap-2">
            <span
              className="inline-block w-3 h-3 rounded-full"
              style={{ backgroundColor: "#EF4444" }}
            />
            <span className="text-gray-700">At Risk (3+ alerts)</span>
          </div>
        </div>
      </div>
    </Card>
  );
}