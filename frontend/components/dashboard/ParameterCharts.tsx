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
import { Thermometer, Droplet, Gauge, Check } from "lucide-react";
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
      <div className="text-sm text-gray-500 py-8 text-center">
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
      <Card className="p-5 card-soft">
        <div className="flex items-center gap-2 mb-4">
          <div
            className="w-7 h-7 rounded-md flex items-center justify-center"
            style={{ backgroundColor: `${color}15` }}
          >
            <Icon size={16} style={{ color }} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-800">{yLabel}</h3>
            <p className="text-[11px] text-gray-500">
              Unit: {unit} • last 300 readings
            </p>
          </div>
        </div>
        {visibleStations.length === 0 ? (
          <div className="text-sm text-gray-400 text-center py-16">
            Select at least one station to view data
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
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
              <Tooltip
                contentStyle={{
                  fontSize: 11,
                  borderRadius: 6,
                  border: "1px solid #E2E8F0",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.06)",
                }}
              />
              <Legend
                wrapperStyle={{ fontSize: 10, paddingTop: 8 }}
                iconType="circle"
              />
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
                  activeDot={{ r: 4 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      {/* Station filter */}
      <Card className="p-4 card-soft">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-gray-600 mr-2">
            Stations:
          </span>

          {/* All button */}
          <button
            onClick={toggleAll}
            className={`px-3 py-1.5 text-xs rounded-full border transition-all duration-150 font-medium flex items-center gap-1.5 ${
              selected.size === ALL_STATIONS.length
                ? "bg-teal-600 text-white border-teal-600 shadow-sm"
                : "bg-white text-gray-700 border-gray-200 hover:border-teal-400"
            }`}
          >
            {selected.size === ALL_STATIONS.length && <Check size={12} />}
            All
          </button>

          {/* Individual station buttons */}
          {ALL_STATIONS.map((sid) => {
            const isSelected = selected.has(sid);
            return (
              <button
                key={sid}
                onClick={() => toggleStation(sid)}
                className={`px-3 py-1.5 text-xs rounded-full border transition-all duration-150 font-medium flex items-center gap-1.5 ${
                  isSelected
                    ? "bg-white text-gray-900 border-gray-300 shadow-sm"
                    : "bg-white text-gray-400 border-gray-200 hover:border-gray-300"
                }`}
              >
                <span
                  className="w-2 h-2 rounded-full"
                  style={{
                    backgroundColor: isSelected
                      ? STATION_COLORS[sid]
                      : "#CBD5E1",
                  }}
                />
                {STATION_NAMES[sid]}
                {isSelected && <Check size={11} className="text-teal-600" />}
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