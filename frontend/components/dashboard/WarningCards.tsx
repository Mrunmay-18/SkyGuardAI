// components/dashboard/WarningCards.tsx
"use client";

import { useEffect, useState } from "react";
import {
  ChevronRight,
  Check,
  Thermometer,
  Droplet,
  Zap,
  Snowflake,
  Activity,
  ShieldCheck,
  Clock,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getAlerts, type Alert } from "@/lib/api";

interface WarningCardsProps {
  onSelect: (alert: Alert) => void;
}

const PRIORITY_CONFIG: Record<
  string,
  {
    label: string;
    badgeClass: string;
    headingColor: string;
    cardAccentBorder: string;
  }
> = {
  P1: {
    label: "Critical",
    badgeClass: "text-rose-700 bg-rose-50 border-rose-200/90",
    headingColor: "text-rose-700",
    cardAccentBorder: "border-l-4 border-l-rose-500",
  },
  P2: {
    label: "High",
    badgeClass: "text-amber-700 bg-amber-50 border-amber-200/90",
    headingColor: "text-amber-700",
    cardAccentBorder: "border-l-4 border-l-amber-500",
  },
  P3: {
    label: "Routine",
    badgeClass: "text-sky-700 bg-sky-50 border-sky-200/90",
    headingColor: "text-sky-700",
    cardAccentBorder: "border-l-4 border-l-sky-500",
  },
};

function getAnomalyIconInfo(anomalyType: string) {
  const t = anomalyType.toLowerCase();
  if (
    t.includes("frozen") ||
    t.includes("freeze") ||
    t.includes("ice") ||
    t.includes("cold")
  ) {
    return {
      Icon: Snowflake,
      color: "text-sky-600",
      bg: "bg-sky-50 border-sky-200/70",
    };
  }
  if (
    t.includes("temperature") ||
    t.includes("temp") ||
    t.includes("heat") ||
    t.includes("spike")
  ) {
    return {
      Icon: Thermometer,
      color: "text-rose-600",
      bg: "bg-rose-50 border-rose-200/70",
    };
  }
  if (
    t.includes("humidity") ||
    t.includes("rain") ||
    t.includes("precipitation") ||
    t.includes("droplet") ||
    t.includes("moisture")
  ) {
    return {
      Icon: Droplet,
      color: "text-blue-600",
      bg: "bg-blue-50 border-blue-200/70",
    };
  }
  if (
    t.includes("power") ||
    t.includes("voltage") ||
    t.includes("battery") ||
    t.includes("collapse") ||
    t.includes("zap")
  ) {
    return {
      Icon: Zap,
      color: "text-amber-600",
      bg: "bg-amber-50 border-amber-200/70",
    };
  }
  return {
    Icon: Activity,
    color: "text-teal-600",
    bg: "bg-teal-50 border-teal-200/70",
  };
}

export default function WarningCards({ onSelect }: WarningCardsProps) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [acknowledged, setAcknowledged] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const data = await getAlerts();
      setAlerts(data);
      setLoading(false);
    }
    load();
  }, []);

  function toggleAcknowledge(key: string) {
    const next = new Set(acknowledged);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setAcknowledged(next);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 text-sm text-stone-500 py-12">
        <Activity size={18} className="text-teal-600 animate-spin" />
        Loading alerts…
      </div>
    );
  }

  // Friendly Empty State
  if (alerts.length === 0) {
    return (
      <Card className="rounded-2xl p-10 text-center card-soft border border-stone-200/80 bg-gradient-to-b from-white to-stone-50/50 shadow-soft">
        <div className="relative w-16 h-16 mx-auto mb-4 flex items-center justify-center">
          <div className="absolute inset-0 rounded-2xl bg-emerald-100/60 animate-ping opacity-30" />
          <div className="relative w-14 h-14 rounded-2xl bg-emerald-50 border border-emerald-200/80 flex items-center justify-center text-emerald-600 shadow-sm">
            <ShieldCheck size={28} />
          </div>
        </div>
        <h3 className="text-base font-bold text-stone-900 mb-1">
          All Monitoring Stations Normal
        </h3>
        <p className="text-xs text-stone-500 max-w-md mx-auto leading-relaxed mb-4">
          No active anomaly alerts detected across the IMD meteorological
          network. All sensor readings conform to physical and regional baseline
          constraints.
        </p>
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200/70 shadow-2xs">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          Live Surveillance Active
        </div>
      </Card>
    );
  }

  const grouped = {
    P1: alerts.filter((a) => a.priority === "P1"),
    P2: alerts.filter((a) => a.priority === "P2"),
    P3: alerts.filter((a) => a.priority === "P3"),
  };

  return (
    <div className="space-y-7">
      {(["P1", "P2", "P3"] as const).map((tier) => {
        const items = grouped[tier];
        if (items.length === 0) return null;
        const cfg = PRIORITY_CONFIG[tier];
        return (
          <div key={tier} className="space-y-3">
            <div className="flex items-center gap-2">
              <h3
                className={`text-xs font-bold tracking-wider uppercase ${cfg.headingColor}`}
              >
                {cfg.label} ({tier}) — {items.length} alert
                {items.length !== 1 ? "s" : ""}
              </h3>
              <span className="h-px flex-1 bg-stone-200/80" />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {items.map((alert, i) => {
                const key = `${alert.station_id}-${alert.timestamp}`;
                const isAck = acknowledged.has(key);
                const anomaly = getAnomalyIconInfo(alert.anomaly_type);
                const AnomalyIcon = anomaly.Icon;

                return (
                  <Card
                    key={i}
                    className={`rounded-2xl p-5 bg-white border border-stone-200/80 shadow-soft shadow-lift transition-all duration-200 flex flex-col justify-between ${
                      cfg.cardAccentBorder
                    } ${isAck ? "opacity-60 bg-stone-50/50" : ""}`}
                  >
                    <div>
                      {/* Top bar: station info + top-right priority badge */}
                      <div className="flex items-start justify-between gap-3 mb-3">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div
                            className={`w-8 h-8 rounded-xl border flex items-center justify-center shrink-0 shadow-2xs ${anomaly.bg} ${anomaly.color}`}
                          >
                            <AnomalyIcon size={16} />
                          </div>
                          <div className="min-w-0">
                            <p className="font-bold text-sm text-stone-900 truncate">
                              {alert.station_id}
                            </p>
                            <p className="text-[11px] text-stone-400 font-medium flex items-center gap-1">
                              <Clock size={11} />
                              {alert.timestamp}
                            </p>
                          </div>
                        </div>

                        {/* Priority badge in top-right corner */}
                        <span
                          className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border shadow-2xs shrink-0 ${cfg.badgeClass}`}
                        >
                          {tier} • {cfg.label}
                        </span>
                      </div>

                      {/* Anomaly type & reasoning */}
                      <div className="mb-3">
                        <p className="text-sm font-semibold text-stone-900 mb-1">
                          {alert.anomaly_type}
                        </p>
                        <p className="text-xs text-stone-600 line-clamp-2 leading-relaxed">
                          {alert.physical_reasoning}
                        </p>
                      </div>

                      {/* Confidence and Trust as small colored chips */}
                      <div className="flex flex-wrap items-center gap-2 mb-4">
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-teal-50 text-teal-800 border border-teal-200/70 shadow-2xs">
                          <span className="w-1.5 h-1.5 rounded-full bg-teal-600" />
                          Confidence:{" "}
                          <b className="font-bold">{alert.confidence}</b>
                        </span>
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-800 border border-amber-200/70 shadow-2xs">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                          Trust:{" "}
                          <b className="font-bold">{alert.trust_score}</b>
                        </span>
                      </div>
                    </div>

                    {/* Action buttons: Primary teal for View Details, Ghost for Acknowledge */}
                    <div className="flex items-center gap-2 pt-3 border-t border-stone-100 mt-2">
                      <Button
                        size="sm"
                        className="flex-1 bg-[#0F766E] hover:bg-[#115E59] text-white shadow-xs font-medium cursor-pointer rounded-lg text-xs"
                        onClick={() => onSelect(alert)}
                      >
                        View Details
                        <ChevronRight size={13} className="ml-1" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => toggleAcknowledge(key)}
                        className={`cursor-pointer rounded-lg text-xs transition-colors ${
                          isAck
                            ? "text-emerald-700 bg-emerald-50 hover:bg-emerald-100 font-semibold"
                            : "text-stone-600 hover:text-stone-900 hover:bg-stone-100"
                        }`}
                      >
                        {isAck ? (
                          <span className="flex items-center gap-1 text-emerald-700">
                            <Check size={13} />
                            Acknowledged
                          </span>
                        ) : (
                          "Acknowledge"
                        )}
                      </Button>
                    </div>
                  </Card>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}