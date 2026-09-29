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
import { ShieldAlert, Activity, Radio, AlertCircle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { getAlerts, getStations, type Alert, type Station } from "@/lib/api";

function CustomYAxisTick(props: any) {
  const { x, y, payload } = props;
  return (
    <g transform={`translate(${x - 120},${y - 8})`}>
      {/* Small station radio / radar icon on Y-axis */}
      <g
        transform="translate(0, 1.5) scale(0.6)"
        stroke="#0F766E"
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9" />
        <path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5" />
        <circle cx="12" cy="12" r="2" fill="#0F766E" />
        <path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5" />
        <path d="M19.1 4.9C23 8.8 23 15.1 19.1 19" />
      </g>
      <text
        x={20}
        y={11}
        fill="#334155"
        fontSize={12}
        fontWeight={600}
        textAnchor="start"
      >
        {payload.value}
      </text>
    </g>
  );
}

function CustomRiskTooltip({ active, payload }: any) {
  if (active && payload && payload.length) {
    const row = payload[0].payload;
    const isAtRisk = row.risk >= 60;
    const isWatch = row.risk >= 20 && row.risk < 60;

    const badgeClass = isAtRisk
      ? "bg-rose-50 text-rose-700 border-rose-200"
      : isWatch
      ? "bg-amber-50 text-amber-700 border-amber-200"
      : "bg-emerald-50 text-emerald-700 border-emerald-200";

    const label = isAtRisk ? "At Risk" : isWatch ? "Watch" : "Healthy";

    return (
      <div className="bg-white/95 backdrop-blur-md px-3.5 py-3 rounded-xl border border-stone-200/90 shadow-soft text-xs min-w-[170px] animate-fade-in">
        <div className="flex items-center justify-between gap-2 mb-2 pb-1.5 border-b border-stone-100">
          <span className="font-bold text-stone-900 text-sm">
            {row.station}
          </span>
          <span
            className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${badgeClass}`}
          >
            {label}
          </span>
        </div>
        <div className="space-y-1.5 text-stone-600 text-[11px]">
          <div className="flex items-center justify-between">
            <span>Risk Score:</span>
            <span className="font-bold text-stone-900">{row.risk} / 100</span>
          </div>
          <div className="flex items-center justify-between">
            <span>Active Alerts:</span>
            <span className="font-bold text-stone-900">{row.alerts}</span>
          </div>
          <div className="flex items-center justify-between">
            <span>Avg Trust:</span>
            <span className="font-bold text-stone-900">{row.avgTrust}%</span>
          </div>
        </div>
      </div>
    );
  }
  return null;
}

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
      <Card className="p-8 text-center text-sm text-stone-500 card-soft">
        <Activity size={18} className="mx-auto text-teal-600 animate-spin mb-2" />
        Loading risk levels…
      </Card>
    );
  }

  // Build per-station counts
  const data = stations.map((s) => {
    const stationAlerts = alerts.filter((a) => a.station_id === s.station_id);
    const count = stationAlerts.length;
    const avgTrust =
      count > 0
        ? Math.round(
            stationAlerts.reduce((sum, a) => sum + a.trust_score, 0) / count
          )
        : 0;

    // Risk score: base from count, adjusted by trust
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

  function getBarFill(risk: number) {
    if (risk >= 60) return "url(#riskGradient)";
    if (risk >= 20) return "url(#watchGradient)";
    return "url(#healthyGradient)";
  }

  // Sort by risk descending
  data.sort((a, b) => b.risk - a.risk);

  return (
    <Card className="card-soft overflow-hidden">
      {/* Subtle Gradient Header */}
      <div className="px-5 py-3.5 border-b border-stone-200/80 bg-gradient-to-r from-stone-50/80 via-white to-stone-50/30 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-teal-50 border border-teal-200/60 flex items-center justify-center text-teal-700 shadow-2xs">
            <ShieldAlert size={16} />
          </div>
          <div>
            <h3 className="text-sm font-bold text-stone-900 tracking-tight">
              Station Risk Level
            </h3>
            <p className="text-[11px] text-stone-500 font-medium">
              Multivariate risk index combining alert volume & sensor trust
            </p>
          </div>
        </div>
        <span className="text-[10px] font-semibold text-stone-600 bg-stone-100/80 px-2 py-0.5 rounded-full border border-stone-200/70">
          Ranked by Severity
        </span>
      </div>

      <div className="p-5">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
          >
            {/* SVG Gradient Definitions */}
            <defs>
              {/* Green → Teal gradient for Healthy */}
              <linearGradient id="healthyGradient" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#10B981" />
                <stop offset="100%" stopColor="#0F766E" />
              </linearGradient>

              {/* Amber → Orange gradient for Watch */}
              <linearGradient id="watchGradient" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#F59E0B" />
                <stop offset="100%" stopColor="#EA580C" />
              </linearGradient>

              {/* Red → Rose gradient for At Risk */}
              <linearGradient id="riskGradient" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#EF4444" />
                <stop offset="100%" stopColor="#E11D48" />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#F1F5F9"
              horizontal={false}
            />
            <XAxis
              type="number"
              domain={[0, 100]}
              tick={{ fontSize: 11, fill: "#94A3B8" }}
              ticks={[0, 25, 50, 75, 100]}
              axisLine={false}
              tickLine={false}
            />
            {/* YAxis with custom station icons */}
            <YAxis
              type="category"
              dataKey="station"
              tick={<CustomYAxisTick />}
              width={130}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<CustomRiskTooltip />} />
            {/* Gradient-filled bars */}
            <Bar dataKey="risk" radius={[0, 6, 6, 0]} barSize={22}>
              {data.map((entry, i) => (
                <Cell key={i} fill={getBarFill(entry.risk)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>

        {/* Legend with gradient color swatches */}
        <div className="flex flex-wrap items-center justify-center gap-6 mt-4 pt-4 border-t border-stone-100 text-xs text-stone-600">
          <div className="flex items-center gap-2">
            <span className="w-3.5 h-3 rounded bg-gradient-to-r from-emerald-500 to-teal-700 shadow-2xs" />
            <span className="font-medium text-stone-700">Healthy (0–19)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3.5 h-3 rounded bg-gradient-to-r from-amber-500 to-orange-600 shadow-2xs" />
            <span className="font-medium text-stone-700">Watch (20–59)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3.5 h-3 rounded bg-gradient-to-r from-rose-500 to-pink-600 shadow-2xs" />
            <span className="font-medium text-stone-700">At Risk (60–100)</span>
          </div>
        </div>
      </div>
    </Card>
  );
}