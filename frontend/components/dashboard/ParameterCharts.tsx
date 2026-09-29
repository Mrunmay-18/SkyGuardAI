// components/dashboard/ParameterCharts.tsx
"use client";

import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import {
  Thermometer,
  Droplet,
  Gauge,
  Check,
  Clock,
  SlidersHorizontal,
  Activity,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { getObservations, type Observation } from "@/lib/api";

const STATION_COLORS: Record<string, string> = {
  AWS_01: "#EF4444",
  AWS_02: "#3B82F6",
  AWS_03: "#10B981",
  AWS_04: "#F59E0B",
  AWS_05: "#8B5CF6",
};

const STATION_NAMES: Record<string, string> = {
  AWS_01: "Pashan",
  AWS_02: "Lonavala",
  AWS_03: "Junnar",
  AWS_04: "Shivajinagar",
  AWS_05: "Daund",
};

const ALL_STATIONS = ["AWS_01", "AWS_02", "AWS_03", "AWS_04", "AWS_05"];

// Custom Tooltip: rounded, soft shadow, small icons
function ChartTooltip({ active, payload, label, unit }: any) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white/95 backdrop-blur-md px-3.5 py-2.5 rounded-xl border border-stone-200/90 shadow-soft text-xs min-w-[160px] animate-fade-in">
        <div className="text-[10px] font-bold text-stone-400 uppercase tracking-wider mb-2 flex items-center gap-1.5 pb-1.5 border-b border-stone-100">
          <Clock size={11} className="text-teal-600" />
          <span>{label ? String(label).slice(11, 16) : ""} UTC</span>
        </div>
        <div className="space-y-1.5">
          {payload.map((item: any, idx: number) => (
            <div key={idx} className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-1.5">
                <span
                  className="w-2 h-2 rounded-full shrink-0 shadow-2xs"
                  style={{ backgroundColor: item.color }}
                />
                <span className="text-stone-700 font-medium text-[11px]">
                  {item.name}
                </span>
              </div>
              <span className="font-bold text-stone-900 text-[11px] tabular-nums">
                {typeof item.value === "number" ? item.value.toFixed(1) : item.value}
                <span className="text-[10px] text-stone-400 font-normal ml-0.5">
                  {unit}
                </span>
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  }
  return null;
}

// Custom Legend: pill-shaped dots
function CustomLegend(props: any) {
  const { payload } = props;
  if (!payload || !payload.length) return null;
  return (
    <div className="flex flex-wrap items-center justify-center gap-2 pt-3">
      {payload.map((entry: any, index: number) => (
        <div
          key={`item-${index}`}
          className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-stone-50 border border-stone-200/80 text-stone-700 shadow-2xs"
        >
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{ backgroundColor: entry.color }}
          />
          <span>{entry.value}</span>
        </div>
      ))}
    </div>
  );
}

export default function ParameterCharts() {
  const [observations, setObservations] = useState<Observation[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set(ALL_STATIONS));

  useEffect(() => {
    async function load() {
      const obs = await getObservations();
      setObservations(obs.slice(-300));
      setLoading(false);
    }
    load();
  }, []);

  function toggleStation(sid: string) {
    const next = new Set(selected);
    if (next.has(sid)) next.delete(sid);
    else next.add(sid);
    setSelected(next);
  }

  function toggleAll() {
    if (selected.size === ALL_STATIONS.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(ALL_STATIONS));
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 text-sm text-stone-500 py-12">
        <Activity size={18} className="text-teal-600 animate-spin" />
        Loading charts…
      </div>
    );
  }

  // Group observations by timestamp
  const byTime = new Map<string, Record<string, unknown>>();
  observations.forEach((o) => {
    if (!selected.has(o.station_id)) return;
    const key = o.timestamp;
    if (!byTime.has(key)) byTime.set(key, { timestamp: key });
    const row = byTime.get(key)!;
    row[`${o.station_id}_temperature`] = o.temperature;
    row[`${o.station_id}_humidity`] = o.humidity;
    row[`${o.station_id}_pressure`] = o.pressure;
  });
  const chartData = Array.from(byTime.values()).sort((a, b) =>
    String(a.timestamp).localeCompare(String(b.timestamp))
  );

  const visibleStations = ALL_STATIONS.filter((s) => selected.has(s));

  function renderChart(
    paramKey: "temperature" | "humidity" | "pressure",
    yLabel: string,
    unit: string,
    Icon: typeof Thermometer,
    color: string
  ) {
    return (
      <Card className="card-soft overflow-hidden">
        {/* Subtle Gradient Header */}
        <div className="px-5 py-3.5 border-b border-stone-200/80 bg-gradient-to-r from-stone-50/80 via-white to-stone-50/30 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center border shadow-2xs"
              style={{ backgroundColor: `${color}12`, borderColor: `${color}30` }}
            >
              <Icon size={16} style={{ color }} />
            </div>
            <div>
              <h3 className="text-sm font-bold text-stone-900 tracking-tight">
                {yLabel}
              </h3>
              <p className="text-[11px] text-stone-500 font-medium">
                Unit: {unit} • Last 300 readings
              </p>
            </div>
          </div>
          <span className="text-[10px] font-semibold text-stone-600 bg-stone-100/80 px-2 py-0.5 rounded-full border border-stone-200/70">
            Live Stream
          </span>
        </div>

        <div className="p-5">
          {visibleStations.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="w-10 h-10 rounded-xl bg-stone-100 flex items-center justify-center text-stone-400 mb-2 border border-stone-200/60">
                <SlidersHorizontal size={18} />
              </div>
              <p className="text-xs font-semibold text-stone-700">No stations selected</p>
              <p className="text-[11px] text-stone-400 mt-0.5">Toggle at least one station filter above to visualize stream data</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={chartData}>
                {/* Softer gridlines */}
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                <XAxis
                  dataKey="timestamp"
                  tick={{ fontSize: 10, fill: "#94A3B8" }}
                  interval="preserveStartEnd"
                  tickFormatter={(v) => String(v).slice(11, 16)}
                  axisLine={{ stroke: "#E2E8F0" }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "#94A3B8" }}
                  domain={["auto", "auto"]}
                  axisLine={false}
                  tickLine={false}
                />
                {/* Rounded soft-shadow Tooltip with small icons */}
                <Tooltip
                  content={<ChartTooltip unit={unit} />}
                />
                {/* Pill-shaped dots Legend */}
                <Legend content={<CustomLegend />} />
                {visibleStations.map((sid) => (
                  <Line
                    key={sid}
                    type="monotone"
                    dataKey={`${sid}_${paramKey}`}
                    name={STATION_NAMES[sid] || sid}
                    stroke={STATION_COLORS[sid]}
                    strokeWidth={1.75}
                    dot={false}
                    connectNulls
                    activeDot={{ r: 4, stroke: "#FFFFFF", strokeWidth: 2 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      {/* Station filter: styled as toggle pills with station color dot */}
      <Card className="p-3.5 card-soft bg-white/90 backdrop-blur-sm rounded-2xl border border-stone-200/80 shadow-soft">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold text-stone-700 uppercase tracking-wider mr-2 flex items-center gap-1.5">
            <SlidersHorizontal size={13} className="text-teal-600" />
            Filter Stations:
          </span>

          {/* All button */}
          <button
            onClick={toggleAll}
            className={`px-3 py-1.5 text-xs rounded-full border transition-all duration-150 font-medium flex items-center gap-1.5 cursor-pointer ${
              selected.size === ALL_STATIONS.length
                ? "bg-teal-700 text-white border-teal-700 shadow-xs ring-1 ring-teal-700/20"
                : "bg-white text-stone-600 border-stone-200 hover:border-teal-400 hover:text-stone-900"
            }`}
          >
            {selected.size === ALL_STATIONS.length && <Check size={12} />}
            All Stations
          </button>

          {/* Individual station toggle pills */}
          {ALL_STATIONS.map((sid) => {
            const isSelected = selected.has(sid);
            return (
              <button
                key={sid}
                onClick={() => toggleStation(sid)}
                className={`px-3 py-1.5 text-xs rounded-full border transition-all duration-150 font-medium flex items-center gap-1.5 cursor-pointer ${
                  isSelected
                    ? "bg-white text-stone-900 border-stone-300 shadow-2xs ring-1 ring-stone-900/5 font-semibold"
                    : "bg-stone-50/70 text-stone-400 border-stone-200 hover:bg-white hover:text-stone-700 opacity-60"
                }`}
              >
                <span
                  className="w-2 h-2 rounded-full transition-transform"
                  style={{
                    backgroundColor: isSelected
                      ? STATION_COLORS[sid]
                      : "#CBD5E1",
                  }}
                />
                {STATION_NAMES[sid]}
                {isSelected && <Check size={11} className="text-teal-600 ml-0.5" />}
              </button>
            );
          })}
        </div>
      </Card>

      {renderChart("temperature", "Temperature", "°C", Thermometer, "#EF4444")}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {renderChart("humidity", "Humidity", "%", Droplet, "#10B981")}
        {renderChart("pressure", "Pressure", "hPa", Gauge, "#3B82F6")}
      </div>
    </div>
  );
}