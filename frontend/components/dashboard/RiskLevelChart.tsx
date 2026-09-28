// components/dashboard/RiskLevelChart.tsx
"use client";

import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Card } from "@/components/ui/card";
import { getAlerts, getStations, type Alert, type Station } from "@/lib/api";

export default function RiskLevelChart() {
  const [stations, setStations] = useState<Station[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

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
        Loading risk levels…
      </Card>
    );
  }

  // Build per-station counts
  const data = stations.map((s) => {
    const count = alerts.filter((a) => a.station_id === s.station_id).length;
    const stationAlerts = alerts.filter((a) => a.station_id === s.station_id);
    const avgTrust =
      stationAlerts.length > 0
        ? Math.round(
            stationAlerts.reduce((sum, a) => sum + a.trust_score, 0) /
              stationAlerts.length
          )
        : 0;

    // Risk score: 0-100 (higher = riskier)
    // 3+ alerts = 100, 2 alerts = 66, 1 alert = 33, 0 alerts = 0
    // Adjusted by trust (higher trust = higher risk)
    const baseRisk = Math.min(100, count * 33);
    const trustFactor = count > 0 ? avgTrust / 100 : 0;
    const risk = Math.round(baseRisk * (0.7 + 0.3 * trustFactor));

    return {
      station: s.station_name,
      station_id: s.station_id,
      alerts: count,
      risk,
      avgTrust,
    };
  });

  function riskColor(risk: number) {
    if (risk >= 60) return "#EF4444";
    if (risk >= 20) return "#F59E0B";
    return "#10B981";
  }

  function riskLabel(risk: number) {
    if (risk >= 60) return "At Risk";
    if (risk >= 20) return "Watch";
    return "Healthy";
  }

  // Sort by risk descending
  data.sort((a, b) => b.risk - a.risk);

  return (
    <Card className="p-5 card-soft">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-gray-800">
          Station Risk Level
        </h3>
        <p className="text-xs text-gray-500 mt-0.5">
          Risk score combines alert frequency and trust score
        </p>
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" horizontal={false} />
          <XAxis
            type="number"
            domain={[0, 100]}
            tick={{ fontSize: 11 }}
            ticks={[0, 25, 50, 75, 100]}
          />
          <YAxis
            type="category"
            dataKey="station"
            tick={{ fontSize: 12 }}
            width={100}
          />
          <Tooltip
            contentStyle={{ fontSize: 12 }}
            formatter={((value: any, _name: any, props: any) => {
              const row = props?.payload;
              if (!row) return [String(value), ""];
              return [`${row.risk} / 100 (${riskLabel(row.risk)})`, "Risk"];
            }) as any}
          />
          <Bar dataKey="risk" radius={[0, 6, 6, 0]} barSize={22}>
            {data.map((entry, i) => (
              <Cell key={i} fill={riskColor(entry.risk)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 mt-4 text-xs text-gray-600">
        <div className="flex items-center gap-2">
          <span
            className="inline-block w-3 h-3 rounded"
            style={{ backgroundColor: "#10B981" }}
          />
          Healthy (0-19)
        </div>
        <div className="flex items-center gap-2">
          <span
            className="inline-block w-3 h-3 rounded"
            style={{ backgroundColor: "#F59E0B" }}
          />
          Watch (20-59)
        </div>
        <div className="flex items-center gap-2">
          <span
            className="inline-block w-3 h-3 rounded"
            style={{ backgroundColor: "#EF4444" }}
          />
          At Risk (60-100)
        </div>
      </div>
    </Card>
  );
}