// components/StatusBar.tsx
"use client";

import { useEffect, useState } from "react";
import { CheckCircle, AlertTriangle, Activity } from "lucide-react";
import { getAlerts, getStations, type Alert, type Station } from "@/lib/api";

export default function StatusBar() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [stations, setStations] = useState<Station[]>([]);

  useEffect(() => {
    async function load() {
      const [al, st] = await Promise.all([getAlerts(), getStations()]);
      setAlerts(al);
      setStations(st);
    }
    load();
  }, []);

  const p1 = alerts.filter((a) => a.priority === "P1").length;
  const p2 = alerts.filter((a) => a.priority === "P2").length;
  const healthy = stations.length - new Set(alerts.map((a) => a.station_id)).size;

  const status =
    p1 > 0
      ? { label: "Attention Required", color: "#EF4444", bg: "#FEE2E2" }
      : p2 > 0
      ? { label: "Monitoring", color: "#F59E0B", bg: "#FEF3C7" }
      : { label: "All Systems Normal", color: "#10B981", bg: "#D1FAE5" };

  const Icon = p1 > 0 ? AlertTriangle : p2 > 0 ? Activity : CheckCircle;

  return (
    <div
      className="flex items-center justify-between px-6 py-2 text-xs border-b border-gray-200"
      style={{ backgroundColor: status.bg }}
    >
      <div className="flex items-center gap-2">
        <Icon size={14} style={{ color: status.color }} />
        <span className="font-semibold" style={{ color: status.color }}>
          {status.label}
        </span>
      </div>
      <div className="flex items-center gap-6 text-gray-700">
        <span>
          <b>{p1}</b> Critical
        </span>
        <span>
          <b>{p2}</b> High
        </span>
        <span>
          <b>{stations.length}</b> Stations Online
        </span>
        <span>
          <b>{healthy}</b> Healthy
        </span>
      </div>
    </div>
  );
}