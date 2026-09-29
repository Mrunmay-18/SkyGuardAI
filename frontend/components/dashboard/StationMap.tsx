// components/dashboard/StationMap.tsx
"use client";

import { useEffect, useState } from "react";
import { Radio, Activity, ShieldCheck, MapPin } from "lucide-react";
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
      <Card className="p-8 text-center text-sm text-stone-500 card-soft">
        <Activity size={18} className="mx-auto text-teal-600 animate-spin mb-2" />
        Loading network topology…
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
    if (n >= 3)
      return {
        label: "At Risk",
        color: "#EF4444",
        glow: "rgba(239, 68, 68, 0.7)",
        badgeClass: "bg-rose-50 text-rose-700 border-rose-200",
      };
    if (n >= 1)
      return {
        label: "Watch",
        color: "#F59E0B",
        glow: "rgba(245, 158, 11, 0.65)",
        badgeClass: "bg-amber-50 text-amber-700 border-amber-200",
      };
    return {
      label: "Healthy",
      color: "#10B981",
      glow: "rgba(16, 185, 129, 0.6)",
      badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200",
    };
  }

  // Map lat/lon → normalized 0-100 coordinates within a container.
  const lats = stations.map((s) => s.latitude);
  const lons = stations.map((s) => s.longitude);
  const latMin = Math.min(...lats);
  const latMax = Math.max(...lats);
  const lonMin = Math.min(...lons);
  const lonMax = Math.max(...lons);

  const PAD_X = 18; // % padding left/right
  const PAD_Y = 22; // % padding top/bottom

  const lonSpan = lonMax - lonMin || 1;
  const latSpan = latMax - latMin || 1;

  function projectX(lon: number) {
    const t = (lon - lonMin) / lonSpan;
    return PAD_X + t * (100 - 2 * PAD_X);
  }

  function projectY(lat: number) {
    const t = (lat - latMin) / latSpan;
    return 100 - PAD_Y - t * (100 - 2 * PAD_Y);
  }

  return (
    <Card className="overflow-hidden card-soft">
      {/* Subtle Gradient Header */}
      <div className="p-5 border-b border-stone-200/80 bg-gradient-to-r from-teal-50/60 via-white to-stone-50/30 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-teal-50 border border-teal-200/60 flex items-center justify-center text-teal-700 shadow-2xs">
            <Radio size={16} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-800">
              Geospatial Radar & Station Status
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Pune region • 5 AWS stations • live radar sweep
            </p>
          </div>
        </div>
        <span className="text-[10px] font-semibold text-teal-800 bg-teal-50 border border-teal-200/70 px-2.5 py-0.5 rounded-full">
          Live Mesh
        </span>
      </div>

      <div
        className="relative bg-gradient-to-br from-slate-50/80 via-[#F7F9F8] to-teal-50/40 overflow-hidden"
        style={{ height: 500 }}
      >
        {/* SVG layer: Subtle background grid texture + Radar rings + Connections */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
        >
          {/* Subtle background grid pattern */}
          <defs>
            <pattern
              id="mapGrid"
              width="5"
              height="5"
              patternUnits="userSpaceOnUse"
            >
              <path
                d="M 5 0 L 0 0 0 5"
                fill="none"
                stroke="#0F766E"
                strokeWidth="0.08"
                strokeOpacity="0.12"
              />
            </pattern>
            <radialGradient id="centerGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#0F766E" stopOpacity="0.08" />
              <stop offset="60%" stopColor="#0F766E" stopOpacity="0.02" />
              <stop offset="100%" stopColor="#0F766E" stopOpacity="0" />
            </radialGradient>
          </defs>
          <rect width="100%" height="100%" fill="url(#mapGrid)" />
          <rect width="100%" height="100%" fill="url(#centerGlow)" />

          {/* Static crosshairs */}
          <line
            x1="50"
            y1="0"
            x2="50"
            y2="100"
            stroke="#0F766E"
            strokeWidth="0.1"
            strokeOpacity="0.15"
            strokeDasharray="1 2"
          />
          <line
            x1="0"
            y1="50"
            x2="100"
            y2="50"
            stroke="#0F766E"
            strokeWidth="0.1"
            strokeOpacity="0.15"
            strokeDasharray="1 2"
          />

          {/* Connections between all stations (mesh network) */}
          {stations.map((a, i) =>
            stations.slice(i + 1).map((b) => (
              <line
                key={`${a.station_id}-${b.station_id}`}
                x1={projectX(a.longitude)}
                y1={projectY(a.latitude)}
                x2={projectX(b.longitude)}
                y2={projectY(b.latitude)}
                stroke="#0F766E"
                strokeWidth="0.25"
                strokeOpacity="0.25"
                strokeDasharray="1 1"
              />
            ))
          )}

          {/* Radar rings: Soft teal, more visible pulse */}
          {[16, 28, 40, 52].map((r, i) => (
            <circle
              key={r}
              cx="50"
              cy="50"
              r={r}
              fill="none"
              stroke="#0F766E"
              strokeWidth="0.35"
              strokeOpacity="0.45"
              style={{
                animation: `pulse-ring 3.5s cubic-bezier(0.4, 0, 0.6, 1) ${
                  i * 0.7
                }s infinite`,
                transformOrigin: "50px 50px",
              }}
            />
          ))}
        </svg>

        {/* Live Network Beacon pill in top right */}
        <div className="absolute top-4 right-4 bg-white/85 backdrop-blur-md rounded-full shadow-2xs px-3 py-1 text-[11px] font-semibold text-teal-800 border border-teal-200/70 flex items-center gap-1.5 pointer-events-none">
          <span className="w-2 h-2 rounded-full bg-teal-600 animate-pulse" />
          Mesh Topology Active
        </div>

        {/* Station markers: larger, with glow effect */}
        {stations.map((s) => {
          const status = stationStatus(s.station_id);
          const x = projectX(s.longitude);
          const y = projectY(s.latitude);
          const count = alertCounts[s.station_id] || 0;
          const isHovered = hovered === s.station_id;

          return (
            <div
              key={s.station_id}
              className="absolute cursor-pointer transition-transform duration-200"
              style={{
                left: `${x}%`,
                top: `${y}%`,
                transform: `translate(-50%, -50%) scale(${isHovered ? 1.2 : 1})`,
                zIndex: isHovered ? 30 : 10,
              }}
              onMouseEnter={() => setHovered(s.station_id)}
              onMouseLeave={() => setHovered(null)}
            >
              {/* Outer pulsing glow ring if alerts exist */}
              {count > 0 && (
                <span
                  className="absolute -inset-1 rounded-full animate-ping opacity-60"
                  style={{
                    backgroundColor: status.color,
                  }}
                />
              )}

              {/* Larger marker with rich glow effect */}
              <div
                className="relative w-7 h-7 rounded-full border-2 border-white flex items-center justify-center transition-all shadow-md"
                style={{
                  backgroundColor: status.color,
                  boxShadow: `0 0 16px ${status.glow}, 0 0 6px ${status.glow}, 0 2px 6px rgba(0,0,0,0.18)`,
                }}
              >
                <div className="w-2.5 h-2.5 rounded-full bg-white/95 shadow-2xs" />
              </div>

              {/* Station Label */}
              <div
                className="absolute whitespace-nowrap text-[11px] font-bold px-2 py-0.5 rounded-full bg-white/95 backdrop-blur-sm border border-stone-200/80 shadow-soft transition-all"
                style={{
                  left: "50%",
                  top:
                    s.latitude > (latMin + latMax) / 2
                      ? "calc(100% + 6px)" // marker on top half → label below
                      : "calc(-100% - 10px)", // marker on bottom half → label above
                  transform: "translateX(-50%)",
                  color: "#1E293B",
                }}
              >
                {s.station_name}
              </div>

              {/* Hover Tooltip card */}
              {isHovered && (
                <div
                  className="absolute bg-white/95 backdrop-blur-md shadow-soft rounded-xl border border-stone-200/90 p-3.5 text-xs animate-fade-in"
                  style={{
                    left: "50%",
                    bottom: "calc(100% + 14px)",
                    transform: "translateX(-50%)",
                    minWidth: 190,
                    zIndex: 40,
                  }}
                >
                  <div className="flex items-center justify-between mb-1.5 pb-1.5 border-b border-stone-100">
                    <p className="font-bold text-stone-900 text-sm">
                      {s.station_name}
                    </p>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${status.badgeClass}`}
                    >
                      {status.label}
                    </span>
                  </div>
                  <p className="text-stone-400 text-[11px] mb-2 font-mono">
                    {s.station_id} • {s.latitude.toFixed(3)}°N, {s.longitude.toFixed(3)}°E
                  </p>
                  <div className="space-y-1 text-stone-600 text-[11px]">
                    <div className="flex items-center justify-between">
                      <span>Active Anomalies:</span>
                      <span className="font-bold text-stone-900">{count}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>Telemetry Status:</span>
                      <span
                        className="font-bold"
                        style={{ color: status.color }}
                      >
                        {status.label}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {/* Legend: Floating card with rounded corners */}
        <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur-md rounded-2xl shadow-soft p-3.5 text-xs border border-stone-200/80 transition-all hover:bg-white/95">
          <div className="flex items-center gap-1.5 mb-2.5 text-stone-900 font-bold text-[11px] uppercase tracking-wider">
            <Radio size={12} className="text-teal-700" />
            Station Status
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]" />
              <span className="text-stone-700 font-medium text-[11px]">
                Healthy (0 alerts)
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]" />
              <span className="text-stone-700 font-medium text-[11px]">
                Watch (1–2 alerts)
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500 shadow-[0_0_8px_rgba(239,68,68,0.7)]" />
              <span className="text-stone-700 font-medium text-[11px]">
                At Risk (3+ alerts)
              </span>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}