// components/dashboard/WarningCards.tsx
"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle, ChevronRight, Check } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getAlerts, type Alert } from "@/lib/api";

interface WarningCardsProps {
  onSelect: (alert: Alert) => void;
}

const PRIORITY_CONFIG: Record<string, {
  label: string;
  color: string;
  bg: string;
  border: string;
}> = {
  P1: {
    label: "Critical",
    color: "text-red-700",
    bg: "bg-red-50",
    border: "border-l-4 border-red-500",
  },
  P2: {
    label: "High",
    color: "text-amber-700",
    bg: "bg-amber-50",
    border: "border-l-4 border-amber-500",
  },
  P3: {
    label: "Routine",
    color: "text-blue-700",
    bg: "bg-blue-50",
    border: "border-l-4 border-blue-500",
  },
};

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
      <div className="text-sm text-gray-500 py-8 text-center">
        Loading alerts…
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <Card className="p-6 text-center">
        <CheckCircle className="mx-auto text-green-500 mb-2" size={32} />
        <p className="text-gray-700 font-medium">No active alerts</p>
        <p className="text-sm text-gray-500 mt-1">
          All stations operating normally
        </p>
      </Card>
    );
  }

  const grouped = {
    P1: alerts.filter((a) => a.priority === "P1"),
    P2: alerts.filter((a) => a.priority === "P2"),
    P3: alerts.filter((a) => a.priority === "P3"),
  };

  return (
    <div className="space-y-6">
      {(["P1", "P2", "P3"] as const).map((tier) => {
        const items = grouped[tier];
        if (items.length === 0) return null;
        const cfg = PRIORITY_CONFIG[tier];
        return (
          <div key={tier}>
                        <h3 className={`text-xs font-bold mb-3 tracking-wider uppercase ${cfg.color}`}>
              {cfg.label} ({tier}) — {items.length} alert
              {items.length !== 1 ? "s" : ""}
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {items.map((alert, i) => {
                const key = `${alert.station_id}-${alert.timestamp}`;
                const isAck = acknowledged.has(key);
                return (
                  <Card 
                    key={i}
                    className={`p-4 ${cfg.border} ${cfg.bg} card-soft fade-in ${
                      isAck ? "opacity-60" : ""
                    }`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <p className="font-semibold text-gray-900">
                          {alert.station_id}
                        </p>
                        <p className="text-xs text-gray-500">
                          {alert.timestamp}
                        </p>
                      </div>
                      <Badge variant="outline" className={cfg.color}>
                        {tier}
                      </Badge>
                    </div>

                    <p className="text-sm font-medium text-gray-800 mb-1">
                      {alert.anomaly_type}
                    </p>
                    <p className="text-xs text-gray-600 mb-3 line-clamp-2">
                      {alert.physical_reasoning}
                    </p>

                    <div className="flex items-center gap-3 text-xs text-gray-600 mb-3">
                      <span>
                        Confidence: <b>{alert.confidence}</b>
                      </span>
                      <span>
                        Trust: <b>{alert.trust_score}</b>
                      </span>
                    </div>

                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        className="flex-1"
                        onClick={() => onSelect(alert)}
                      >
                        View Details
                        <ChevronRight size={14} className="ml-1" />
                      </Button>
                      <Button
                        size="sm"
                        variant={isAck ? "default" : "ghost"}
                        onClick={() => toggleAcknowledge(key)}
                        className={isAck ? "bg-green-600 text-white" : ""}
                      >
                        {isAck ? <Check size={14} /> : "Acknowledge"}
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