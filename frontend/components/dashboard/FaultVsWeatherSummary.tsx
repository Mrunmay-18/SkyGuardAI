// components/dashboard/FaultVsWeatherSummary.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CloudSun,
  CloudRain,
  Sun,
  ArrowRight,
  Shield,
  Activity,
  Thermometer,
  Droplet,
  Zap,
  Snowflake,
  CheckCircle2,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { getAlerts, getStations, type Alert, type Station } from "@/lib/api";

const PRIORITY_STYLES: Record<string, { label: string; badgeClass: string }> = {
  P1: {
    label: "Critical",
    badgeClass: "text-rose-700 bg-rose-50 border-rose-200/80",
  },
  P2: {
    label: "High",
    badgeClass: "text-amber-700 bg-amber-50 border-amber-200/80",
  },
  P3: {
    label: "Routine",
    badgeClass: "text-sky-700 bg-sky-50 border-sky-200/80",
  },
};

function getFaultIcon(anomalyType: string) {
  const t = anomalyType.toLowerCase();
  if (t.includes("frozen") || t.includes("freeze") || t.includes("ice") || t.includes("cold")) {
    return Snowflake;
  }
  if (t.includes("temperature") || t.includes("temp") || t.includes("spike") || t.includes("heat")) {
    return Thermometer;
  }
  if (t.includes("humidity") || t.includes("rain") || t.includes("droplet") || t.includes("moisture")) {
    return Droplet;
  }
  if (t.includes("power") || t.includes("voltage") || t.includes("battery") || t.includes("collapse")) {
    return Zap;
  }
  return AlertTriangle;
}

function getWeatherIcon(anomalyType: string) {
  const t = anomalyType.toLowerCase();
  if (t.includes("rain") || t.includes("precipitation") || t.includes("storm") || t.includes("monsoon")) {
    return CloudRain;
  }
  if (t.includes("temp") || t.includes("heat") || t.includes("sun") || t.includes("wave")) {
    return Sun;
  }
  return CloudSun;
}

export default function FaultVsWeatherSummary() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [stations, setStations] = useState<Station[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [al, st] = await Promise.all([getAlerts(), getStations()]);
      setAlerts(al);
      setStations(st);
      setLoading(false);
    }
    load();
  }, []);

  if (loading) {
    return (
      <Card className="p-8 text-sm text-stone-500 text-center card-soft">
        <Activity size={20} className="mx-auto text-teal-600 animate-spin mb-2" />
        Analyzing alerts…
      </Card>
    );
  }

  // Classify each alert: fault vs weather
  const faultList: Alert[] = [];
  const weatherList: Alert[] = [];

  alerts.forEach((a) => {
    if (a.genuine_weather_event === true) {
      weatherList.push(a);
    } else {
      faultList.push(a);
    }
  });

  // Deduplicate by (station_id, anomaly_type) and count occurrences
  type Group = {
    station_id: string;
    anomaly_type: string;
    priority: string;
    count: number;
    latest_ts: string;
  };

  function groupAlerts(list: Alert[]): Group[] {
    const map = new Map<string, Group>();
    list.forEach((a) => {
      const key = `${a.station_id}|${a.anomaly_type}`;
      const existing = map.get(key);
      if (existing) {
        existing.count += 1;
        if (a.timestamp > existing.latest_ts) {
          existing.latest_ts = a.timestamp;
        }
      } else {
        map.set(key, {
          station_id: a.station_id,
          anomaly_type: a.anomaly_type,
          priority: a.priority,
          count: 1,
          latest_ts: a.timestamp,
        });
      }
    });
    return Array.from(map.values());
  }

  const faultGroups = groupAlerts(faultList);
  const weatherGroups = groupAlerts(weatherList);

  // Sort fault groups by priority
  const priorityOrder: Record<string, number> = { P1: 1, P2: 2, P3: 3 };
  faultGroups.sort(
    (a, b) =>
      (priorityOrder[a.priority] || 99) - (priorityOrder[b.priority] || 99)
  );

  const stationName = (sid: string) =>
    stations.find((s) => s.station_id === sid)?.station_name || sid;

  return (
    <Card className="card-soft overflow-hidden">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-stone-200/80 flex items-center justify-between bg-gradient-to-r from-teal-50/60 via-white to-stone-50/40">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-teal-50 border border-teal-200/60 flex items-center justify-center text-teal-700">
            <Shield size={15} />
          </div>
          <h3 className="text-sm font-semibold text-stone-900 tracking-tight">
            Today&apos;s Alerts — Sensor Faults vs Weather Events
          </h3>
        </div>
        <Link
          href="/reality-check"
          className="text-xs text-teal-700 hover:text-teal-800 bg-teal-50/80 hover:bg-teal-100/80 px-2.5 py-1 rounded-full border border-teal-200/60 transition-colors font-medium flex items-center gap-1.5"
        >
          Reality Check Demo
          <ArrowRight size={12} />
        </Link>
      </div>

      {/* Two-column layout with soft divider between columns */}
      <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-stone-200/80">
        {/* FAULTS column: red-tinted card background */}
        <div className="p-5 bg-gradient-to-b from-rose-50/40 to-transparent">
          <div className="flex items-center justify-between mb-3.5">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-md bg-rose-100/80 border border-rose-200/70 flex items-center justify-center text-rose-700">
                <AlertTriangle size={13} />
              </div>
              <h4 className="text-xs font-bold text-rose-800 uppercase tracking-wider">
                Sensor Faults ({faultGroups.length})
              </h4>
            </div>
            <span className="text-[10px] font-semibold text-rose-700 bg-rose-100/70 border border-rose-200/60 px-2 py-0.5 rounded-full">
              Hardware
            </span>
          </div>

          {faultGroups.length === 0 ? (
            <div className="p-6 text-center rounded-xl bg-white/70 border border-rose-100/80 text-xs text-stone-500">
              <CheckCircle2 size={22} className="mx-auto text-emerald-500 mb-1.5" />
              No sensor faults detected
            </div>
          ) : (
            <ul className="space-y-2">
              {faultGroups.slice(0, 6).map((g, i) => {
                const pri = PRIORITY_STYLES[g.priority] || PRIORITY_STYLES.P3;
                const RowIcon = getFaultIcon(g.anomaly_type);
                return (
                  <li
                    key={i}
                    className="flex items-center justify-between gap-3 text-xs bg-white/90 hover:bg-white p-2.5 rounded-xl border border-rose-100/90 shadow-2xs hover:shadow-xs transition-all"
                  >
                    <div className="flex items-center gap-2.5 min-w-0 flex-1">
                      <div className="w-7 h-7 rounded-lg bg-rose-50 border border-rose-200/60 flex items-center justify-center shrink-0 text-rose-600">
                        <RowIcon size={14} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="font-semibold text-stone-900 truncate">
                          {stationName(g.station_id)}
                        </p>
                        <p className="text-stone-500 text-[11px] truncate">
                          {g.anomaly_type}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {g.count > 1 && (
                        <span className="text-[10px] font-bold text-stone-600 bg-stone-100 px-1.5 py-0.5 rounded-full border border-stone-200/70">
                          ×{g.count}
                        </span>
                      )}
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full border shadow-2xs ${pri.badgeClass}`}
                      >
                        {pri.label}
                      </span>
                    </div>
                  </li>
                );
              })}
              {faultGroups.length > 6 && (
                <li className="text-xs text-stone-500 pt-1 text-center font-medium">
                  + {faultGroups.length - 6} more sensor faults
                </li>
              )}
            </ul>
          )}
        </div>

        {/* WEATHER column: green-tinted card background */}
        <div className="p-5 bg-gradient-to-b from-emerald-50/40 to-transparent">
          <div className="flex items-center justify-between mb-3.5">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-md bg-emerald-100/80 border border-emerald-200/70 flex items-center justify-center text-emerald-700">
                <CloudSun size={13} />
              </div>
              <h4 className="text-xs font-bold text-emerald-800 uppercase tracking-wider">
                Weather Events ({weatherGroups.length})
              </h4>
            </div>
            <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-100/70 border border-emerald-200/60 px-2 py-0.5 rounded-full">
              Atmospheric
            </span>
          </div>

          {weatherGroups.length === 0 ? (
            <div className="p-6 text-center rounded-xl bg-white/70 border border-emerald-100/80 text-xs text-stone-500">
              <CloudSun size={22} className="mx-auto text-emerald-500 mb-1.5" />
              No regional weather events detected
            </div>
          ) : (
            <ul className="space-y-2">
              {weatherGroups.slice(0, 6).map((g, i) => {
                const RowIcon = getWeatherIcon(g.anomaly_type);
                return (
                  <li
                    key={i}
                    className="flex items-center justify-between gap-3 text-xs bg-white/90 hover:bg-white p-2.5 rounded-xl border border-emerald-100/90 shadow-2xs hover:shadow-xs transition-all"
                  >
                    <div className="flex items-center gap-2.5 min-w-0 flex-1">
                      <div className="w-7 h-7 rounded-lg bg-emerald-50 border border-emerald-200/60 flex items-center justify-center shrink-0 text-emerald-600">
                        <RowIcon size={14} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="font-semibold text-stone-900 truncate">
                          {stationName(g.station_id)}
                        </p>
                        <p className="text-stone-500 text-[11px] truncate">
                          {g.anomaly_type}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {g.count > 1 && (
                        <span className="text-[10px] font-bold text-stone-600 bg-stone-100 px-1.5 py-0.5 rounded-full border border-stone-200/70">
                          ×{g.count}
                        </span>
                      )}
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full text-emerald-800 bg-emerald-100/80 border border-emerald-200/80 shadow-2xs">
                        Weather Event
                      </span>
                    </div>
                  </li>
                );
              })}
              {weatherGroups.length > 6 && (
                <li className="text-xs text-stone-500 pt-1 text-center font-medium">
                  + {weatherGroups.length - 6} more weather events
                </li>
              )}
            </ul>
          )}
        </div>
      </div>

      {/* Footer caption */}
      <div className="px-5 py-2.5 bg-stone-50/80 border-t border-stone-200/80">
        <p className="text-[11px] text-stone-500 flex items-center gap-1.5">
          <Activity size={12} className="text-teal-600" />
          Classified using spatial consistency (isolated vs common event) and
          physics coupling checks. Live from <code className="text-[10px] bg-stone-200/60 text-stone-800 px-1 py-0.5 rounded font-mono">alerts.json</code>.
        </p>
      </div>
    </Card>
  );
}