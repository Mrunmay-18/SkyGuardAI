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
  ReferenceDot,
} from "recharts";
import { Thermometer, Droplet, Gauge } from "lucide-react";
import { Card } from "@/components/ui/card";
import { getAlerts, getObservations, type Alert, type Observation } from "@/lib/api";

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

export default function ParameterCharts() {
  const [observations, setObservations] = useState<Observation[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [obs, al] = await Promise.all([getObservations(), getAlerts()]);
      // Keep last 300 rows for performance
      setObservations(obs.slice(-300));
      setAlerts(al);
      setLoading(false);
    }
    load();
  }, []);

  if (loading) {
    return <div className="text-sm text-gray-500 py-8 text-center">Loading charts…</div>;
  }

  // Group observations by timestamp for multi-line charts
  const byTime = new Map<string, any>();
  observations.forEach((o) => {
    const key = o.timestamp;
    if (!byTime.has(key)) byTime.set(key, { timestamp: key });
    const row = byTime.get(key);
    row[`${o.station_id}_temperature`] = o.temperature;
    row[`${o.station_id}_humidity`] = o.humidity;
    row[`${o.station_id}_pressure`] = o.pressure;
  });
  const chartData = Array.from(byTime.values()).sort((a, b) =>
    a.timestamp.localeCompare(b.timestamp)
  );

  const stations = Array.from(new Set(observations.map((o) => o.station_id)));

  function renderChart(
    paramKey: "temperature" | "humidity" | "pressure",
    yLabel: string,
    unit: string,
    Icon: any,
    color: string
  ) {
    return (
        <Card className="p-5 card-soft">
        <div className="flex items-center gap-2 mb-3">
          <Icon size={18} style={{ color }} />
          <h3 className="text-sm font-semibold text-gray-800">
            {yLabel} ({unit})
          </h3>
        </div>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
            <XAxis
              dataKey="timestamp"
              tick={{ fontSize: 10 }}
              interval="preserveStartEnd"
              tickFormatter={(v) => String(v).slice(11, 16)}
            />
            <YAxis tick={{ fontSize: 10 }} domain={["auto", "auto"]} />
            <Tooltip
              contentStyle={{ fontSize: 11 }}
              labelFormatter={(v) => String(v)}
            />
            <Legend wrapperStyle={{ fontSize: 10 }} />
            {stations.map((sid) => (
              <Line
                key={sid}
                type="monotone"
                dataKey={`${sid}_${paramKey}`}
                name={`${sid} (${STATION_NAMES[sid] || sid})`}
                stroke={STATION_COLORS[sid]}
                strokeWidth={1.5}
                dot={false}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {renderChart("temperature", "Temperature", "°C", Thermometer, "#EF4444")}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {renderChart("humidity", "Humidity", "%", Droplet, "#10B981")}
        {renderChart("pressure", "Pressure", "hPa", Gauge, "#3B82F6")}
      </div>
    </div>
  );
}