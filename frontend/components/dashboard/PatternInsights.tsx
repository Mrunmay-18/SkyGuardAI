// components/dashboard/PatternInsights.tsx
"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, TrendingUp, Activity, CheckCircle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { getAlerts, getStations, type Alert, type Station } from "@/lib/api";

interface Insight {
  icon: "warning" | "trend" | "activity" | "success";
  title: string;
  detail: string;
  color: string;
}

export default function PatternInsights() {
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
      <Card className="p-6 text-center text-sm text-gray-500">
        Analyzing patterns…
      </Card>
    );
  }

  const insights: Insight[] = [];

  // 1. Station with most alerts
  const counts: Record<string, number> = {};
  alerts.forEach((a) => {
    counts[a.station_id] = (counts[a.station_id] || 0) + 1;
  });

  const topStation = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
  if (topStation && topStation[1] >= 3) {
    const name =
      stations.find((s) => s.station_id === topStation[0])?.station_name ||
      topStation[0];
    insights.push({
      icon: "warning",
      title: `${name} has ${topStation[1]} alerts`,
      detail: `Sensor fault cluster detected. Investigate ${topStation[0]} sensor health.`,
      color: "#EF4444",
    });
  }

  // 2. Dominant anomaly type
  const typeCounts: Record<string, number> = {};
  alerts.forEach((a) => {
    typeCounts[a.anomaly_type] = (typeCounts[a.anomaly_type] || 0) + 1;
  });
  const topType = Object.entries(typeCounts).sort((a, b) => b[1] - a[1])[0];
  if (topType && topType[1] >= 2) {
    insights.push({
      icon: "trend",
      title: `Most common: ${topType[0]}`,
      detail: `${topType[1]} of ${alerts.length} alerts are ${topType[0]} — dominant fault pattern.`,
      color: "#F59E0B",
    });
  }

  // 3. Time clustering
  const hourBuckets: Record<string, number> = {};
  alerts.forEach((a) => {
    const hour = a.timestamp.slice(11, 13);
    hourBuckets[hour] = (hourBuckets[hour] || 0) + 1;
  });
  const topHour = Object.entries(hourBuckets).sort((a, b) => b[1] - a[1])[0];
  if (topHour && topHour[1] >= 2) {
    insights.push({
      icon: "activity",
      title: `Alerts cluster around ${topHour[0]}:00`,
      detail: `${topHour[1]} alerts occurred at this hour — possible operational or environmental trigger.`,
      color: "#3B82F6",
    });
  }

  // 4. High-trust alerts
  const highTrust = alerts.filter((a) => a.trust_score >= 80).length;
  if (highTrust > 0) {
    insights.push({
      icon: "warning",
      title: `${highTrust} high-confidence fault${highTrust > 1 ? "s" : ""}`,
      detail: `Trust score ≥ 80 — prioritize investigation.`,
      color: "#EF4444",
    });
  }

  // 5. Station-specific insights
  stations.forEach((s) => {
    const stationAlerts = alerts.filter((a) => a.station_id === s.station_id);
    const isolated = stationAlerts.filter(
      (a) => a.counter_reasoning?.verdict === "sensor_fault"
    );
    if (isolated.length >= 2) {
      insights.push({
        icon: "activity",
        title: `${s.station_name} — isolated faults`,
        detail: `${isolated.length} alerts match isolated sensor signature — sensor fault likely.`,
        color: "#8B5CF6",
      });
    }
  });

  // 6. Fallback — healthy network
  if (insights.length === 0) {
    insights.push({
      icon: "success",
      title: "Network stable",
      detail: "No significant patterns detected. All stations within normal ranges.",
      color: "#10B981",
    });
  }

  function renderIcon(icon: Insight["icon"], color: string) {
    const props = { size: 20, style: { color } };
    switch (icon) {
      case "warning":
        return <AlertTriangle {...props} />;
      case "trend":
        return <TrendingUp {...props} />;
      case "activity":
        return <Activity {...props} />;
      case "success":
        return <CheckCircle {...props} />;
    }
  }

  return (
    <Card className="p-5">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-gray-800">
          Pattern Insights
        </h3>
        <p className="text-xs text-gray-500 mt-0.5">
          Auto-generated from current alert data
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {insights.slice(0, 6).map((ins, i) => (
          <div
            key={i}
            className="border border-gray-200 rounded-lg p-4 bg-white hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 fade-in"
            style={{ borderLeft: `4px solid ${ins.color}` }}
          >
            <div className="flex items-start gap-3">
              {renderIcon(ins.icon, ins.color)}
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-sm text-gray-900 mb-1">
                  {ins.title}
                </p>
                <p className="text-xs text-gray-600 leading-relaxed">
                  {ins.detail}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}