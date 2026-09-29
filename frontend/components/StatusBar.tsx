// components/StatusBar.tsx
"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, AlertTriangle, AlertCircle, Activity, Radio } from "lucide-react";
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
      ? {
          label: "Attention Required",
          badgeBg: "bg-rose-50/90",
          badgeText: "text-rose-700",
          badgeBorder: "border-rose-200/80",
          dotClass: "bg-rose-500",
          pulseClass: "bg-rose-400",
          iconColor: "text-rose-600",
          Icon: AlertCircle,
        }
      : p2 > 0
      ? {
          label: "Monitoring",
          badgeBg: "bg-amber-50/90",
          badgeText: "text-amber-700",
          badgeBorder: "border-amber-200/80",
          dotClass: "bg-amber-500",
          pulseClass: "bg-amber-400",
          iconColor: "text-amber-600",
          Icon: Activity,
        }
      : {
          label: "All Systems Normal",
          badgeBg: "bg-emerald-50/90",
          badgeText: "text-emerald-700",
          badgeBorder: "border-emerald-200/80",
          dotClass: "bg-emerald-500",
          pulseClass: "bg-emerald-400",
          iconColor: "text-emerald-600",
          Icon: CheckCircle2,
        };

  const StatusIcon = status.Icon;

  return (
    <div className="w-full bg-white/75 backdrop-blur-md border-b border-stone-200/70 shadow-xs transition-colors">
      <div className="max-w-7xl mx-auto px-6 py-2 flex items-center justify-between flex-wrap gap-3 text-xs">
        {/* Status indicator pill with pulse dot */}
        <div className="flex items-center gap-2">
          <div
            className={`inline-flex items-center gap-2 px-3 py-1 rounded-full font-semibold border ${status.badgeBg} ${status.badgeBorder} ${status.badgeText} shadow-xs transition-all`}
          >
            <span className="relative flex h-2 w-2">
              <span
                className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${status.pulseClass}`}
              />
              <span
                className={`relative inline-flex rounded-full h-2 w-2 ${status.dotClass}`}
              />
            </span>
            <StatusIcon size={13} className={status.iconColor} />
            <span className="tracking-tight">{status.label}</span>
          </div>
        </div>

        {/* Indicators with icons, bold figures, and dividers */}
        <div className="flex items-center gap-3 sm:gap-5 text-stone-600">
          <div className="flex items-center gap-1.5">
            <AlertCircle size={13} className={p1 > 0 ? "text-rose-500" : "text-stone-400"} />
            <span className="font-bold text-stone-900">{p1}</span>
            <span className="text-stone-500">Critical</span>
          </div>

          <span className="h-3 w-px bg-stone-200" aria-hidden="true" />

          <div className="flex items-center gap-1.5">
            <AlertTriangle size={13} className={p2 > 0 ? "text-amber-500" : "text-stone-400"} />
            <span className="font-bold text-stone-900">{p2}</span>
            <span className="text-stone-500">High</span>
          </div>

          <span className="h-3 w-px bg-stone-200" aria-hidden="true" />

          <div className="flex items-center gap-1.5">
            <Radio size={13} className="text-teal-600" />
            <span className="font-bold text-stone-900">{stations.length}</span>
            <span className="text-stone-500">Stations Online</span>
          </div>

          <span className="h-3 w-px bg-stone-200" aria-hidden="true" />

          <div className="flex items-center gap-1.5">
            <CheckCircle2 size={13} className="text-emerald-600" />
            <span className="font-bold text-stone-900">{healthy}</span>
            <span className="text-stone-500">Healthy</span>
          </div>
        </div>
      </div>
    </div>
  );
}