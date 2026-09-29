// components/dashboard/PatternInsights.tsx
"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle,
  TrendingUp,
  Activity,
  CheckCircle,
  Sparkles,
  Zap,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { getAlerts, getStations, type Alert, type Station } from "@/lib/api";

interface Insight {
  icon: "warning" | "trend" | "activity" | "success";
  title: string;
  detail: string;
  color: string;
}

function getInsightStyle(color: string, icon: Insight["icon"]) {
  if (color === "#EF4444" || icon === "warning") {
    return {
      cardClass: "bg-rose-50/30 border-rose-200/80 border-l-4 border-l-rose-500",
      bubbleClass: "bg-rose-100/80 border-rose-200 text-rose-600",
      tag: "Alert Cluster",
      tagClass: "bg-rose-100/70 text-rose-700 border-rose-200/60",
    };
  }
  if (color === "#F59E0B" || icon === "trend") {
    return {
      cardClass: "bg-amber-50/30 border-amber-200/80 border-l-4 border-l-amber-500",
      bubbleClass: "bg-amber-100/80 border-amber-200 text-amber-600",
      tag: "Trend",
      tagClass: "bg-amber-100/70 text-amber-700 border-amber-200/60",
    };
  }
  if (color === "#8B5CF6") {
    return {
      cardClass: "bg-purple-50/30 border-purple-200/80 border-l-4 border-l-purple-500",
      bubbleClass: "bg-purple-100/80 border-purple-200 text-purple-600",
      tag: "Hardware",
      tagClass: "bg-purple-100/70 text-purple-700 border-purple-200/60",
    };
  }
  if (color === "#3B82F6" || icon === "activity") {
    return {
      cardClass: "bg-sky-50/30 border-sky-200/80 border-l-4 border-l-sky-500",
      bubbleClass: "bg-sky-100/80 border-sky-200 text-sky-600",
      tag: "Temporal",
      tagClass: "bg-sky-100/70 text-sky-700 border-sky-200/60",
    };
  }
  return {
    cardClass: "bg-emerald-50/30 border-emerald-200/80 border-l-4 border-l-emerald-500",
    bubbleClass: "bg-emerald-100/80 border-emerald-200 text-emerald-600",
    tag: "Nominal",
    tagClass: "bg-emerald-100/70 text-emerald-700 border-emerald-200/60",
  };
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
      <Card className="p-8 text-center text-sm text-stone-500 card-soft">
        <Activity size={18} className="mx-auto text-teal-600 animate-spin mb-2" />
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
      detail:
        "No significant patterns detected. All stations within normal ranges.",
      color: "#10B981",
    });
  }

  function renderIcon(icon: Insight["icon"]) {
    const props = { size: 18 };
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
    <Card className="card-soft overflow-hidden">
      {/* Subtle Gradient Header */}
      <div className="px-5 py-3.5 border-b border-stone-200/80 bg-gradient-to-r from-stone-50/80 via-white to-stone-50/30 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-teal-50 border border-teal-200/60 flex items-center justify-center text-teal-700 shadow-2xs">
            <Sparkles size={16} />
          </div>
          <div>
            <h3 className="text-sm font-bold text-stone-900 tracking-tight">
              Pattern Insights
            </h3>
            <p className="text-[11px] text-stone-500 font-medium">
              Automated anomaly pattern discovery & clustering
            </p>
          </div>
        </div>
        <span className="text-[10px] font-semibold text-teal-800 bg-teal-50 border border-teal-200/70 px-2.5 py-0.5 rounded-full">
          AI Synthesis
        </span>
      </div>

      <div className="p-5">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {insights.slice(0, 6).map((ins, i) => {
            const style = getInsightStyle(ins.color, ins.icon);
            return (
              <div
                key={i}
                className={`rounded-2xl p-4.5 border shadow-soft shadow-lift hover:-translate-y-1 transition-all duration-200 flex flex-col justify-between ${style.cardClass}`}
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-2.5">
                    {/* Icon Bubble */}
                    <div
                      className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 border shadow-2xs ${style.bubbleClass}`}
                    >
                      {renderIcon(ins.icon)}
                    </div>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full border shadow-2xs ${style.tagClass}`}
                    >
                      {style.tag}
                    </span>
                  </div>

                  <p className="font-bold text-sm text-stone-900 mb-1 leading-snug">
                    {ins.title}
                  </p>
                  <p className="text-xs text-stone-600 leading-relaxed">
                    {ins.detail}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
}