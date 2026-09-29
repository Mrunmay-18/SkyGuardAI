// app/parameters/page.tsx
"use client";

import { SlidersHorizontal, Activity, Layers } from "lucide-react";
import ParameterCharts from "@/components/dashboard/ParameterCharts";

export default function ParametersPage() {
  return (
    <div className="space-y-8 fade-in">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-teal-50 border border-teal-200/60 text-teal-800 text-xs font-semibold mb-2 shadow-2xs">
            <SlidersHorizontal size={12} className="text-teal-600 animate-pulse" />
            Sensor Telemetry Feeds
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-stone-900 tracking-tight">
            Parameter Analysis
          </h1>
          <p className="text-xs sm:text-sm text-stone-500 mt-1">
            Real-time multi-station trends for temperature, relative humidity, and atmospheric pressure
          </p>
        </div>

        {/* Live sync badge */}
        <div className="flex items-center gap-2">
          <div className="px-3 py-1.5 rounded-xl bg-white border border-stone-200/80 shadow-2xs flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-medium text-stone-600">Telemetry Stream:</span>
            <span className="text-xs font-bold text-teal-700">15-min Sync</span>
          </div>
        </div>
      </div>

      {/* Main Charts Component */}
      <ParameterCharts />
    </div>
  );
}