// components/dashboard/FaultVsWeatherSummary.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CloudSun,
  ArrowRight,
  Shield,
  Activity,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { getAlerts, getStations, type Alert, type Station } from "@/lib/api";

const PRIORITY_STYLES: Record<string, { color: string; label: string }> = {
  P1: { color: "#EF4444", label: "Critical" },
  P2: { color: "#F59E0B", label: "High" },
  P3: { color: "#3B82F6", label: "Routine" },
};

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
      <Card className="p-6 text-sm text-gray-500 text-center card-soft">
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
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between bg-gradient-to-r from-teal-50/40 to-transparent">
        <div className="flex items-center gap-2">
          <Shield size={16} className="text-teal-600" />
          <h3 className="text-sm font-semibold text-gray-800">
            Today&apos;s Alerts — Sensor Faults vs Weather Events
          </h3>
        </div>
        <Link
          href="/reality-check"
          className="text-xs text-teal-600 hover:text-teal-700 font-medium flex items-center gap-1"
        >
          See Reality Check demo
          <ArrowRight size={12} />
        </Link>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 md:grid-cols-2">
        {/* FAULTS column */}
        <div className="p-5 border-r-0 md:border-r border-gray-100">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle size={16} className="text-red-600" />
            <h4 className="text-xs font-bold text-red-700 uppercase tracking-wider">
              Sensor Faults ({faultGroups.length})
            </h4>
          </div>

          {faultGroups.length === 0 ? (
            <p className="text-xs text-gray-400 italic">
              No sensor faults detected
            </p>
          ) : (
            <ul className="space-y-2">
              {faultGroups.slice(0, 6).map((g, i) => {
                const pri = PRIORITY_STYLES[g.priority] || PRIORITY_STYLES.P3;
                return (
                  <li
                    key={i}
                    className="flex items-center justify-between text-xs border-l-2 pl-2.5 py-1"
                    style={{ borderLeftColor: pri.color }}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-gray-800 truncate">
                        {stationName(g.station_id)}
                      </p>
                      <p className="text-gray-500 text-[11px] truncate">
                        {g.anomaly_type}
                      </p>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0 ml-2">
                      {g.count > 1 && (
                        <span className="text-[10px] font-bold text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
                          ×{g.count}
                        </span>
                      )}
                      <span
                        className="text-[10px] font-bold px-1.5 py-0.5 rounded"
                        style={{
                          color: pri.color,
                          backgroundColor: `${pri.color}15`,
                        }}
                      >
                        {g.priority}
                      </span>
                    </div>
                  </li>
                );
              })}
              {faultGroups.length > 6 && (
                <li className="text-xs text-gray-500 pt-1">
                  + {faultGroups.length - 6} more
                </li>
              )}
            </ul>
          )}
        </div>

        {/* WEATHER column */}
        <div className="p-5 bg-green-50/30">
          <div className="flex items-center gap-2 mb-3">
            <CloudSun size={16} className="text-green-700" />
            <h4 className="text-xs font-bold text-green-700 uppercase tracking-wider">
              Weather Events ({weatherGroups.length})
            </h4>
          </div>

          {weatherGroups.length === 0 ? (
            <p className="text-xs text-gray-400 italic">
              No regional weather events detected
            </p>
          ) : (
            <ul className="space-y-2">
              {weatherGroups.slice(0, 6).map((g, i) => (
                <li
                  key={i}
                  className="flex items-center justify-between text-xs border-l-2 pl-2.5 py-1"
                  style={{ borderLeftColor: "#10B981" }}
                >
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-gray-800 truncate">
                      {stationName(g.station_id)}
                    </p>
                    <p className="text-gray-500 text-[11px] truncate">
                      {g.anomaly_type}
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0 ml-2">
                    {g.count > 1 && (
                      <span className="text-[10px] font-bold text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
                        ×{g.count}
                      </span>
                    )}
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded text-green-700 bg-green-100">
                      Weather
                    </span>
                  </div>
                </li>
              ))}
              {weatherGroups.length > 6 && (
                <li className="text-xs text-gray-500 pt-1">
                  + {weatherGroups.length - 6} more
                </li>
              )}
            </ul>
          )}
        </div>
      </div>

      {/* Footer caption */}
      <div className="px-5 py-2.5 bg-gray-50 border-t border-gray-100">
        <p className="text-[11px] text-gray-500 flex items-center gap-1.5">
          <Activity size={11} />
          Classified using spatial consistency (isolated vs common event) and
          physics coupling checks. Live from <code className="text-[10px]">alerts.json</code>.
        </p>
      </div>
    </Card>
  );
}