// app/network/page.tsx
"use client";

import { Radio, Share2, Sparkles, Activity } from "lucide-react";
import StationMap from "@/components/dashboard/StationMap";
import PatternInsights from "@/components/dashboard/PatternInsights";

export default function NetworkPage() {
  return (
    <div className="space-y-8 fade-in">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-teal-50 border border-teal-200/60 text-teal-800 text-xs font-semibold mb-2 shadow-2xs">
            <Share2 size={12} className="text-teal-600 animate-pulse" />
            Spatial Cross-Validation
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-stone-900 tracking-tight">
            Station Network Topology
          </h1>
          <p className="text-xs sm:text-sm text-stone-500 mt-1">
            Geographic mesonet arrangement and cross-station spatial correlation insights
          </p>
        </div>

        {/* Status badges */}
        <div className="flex items-center gap-2">
          <div className="px-3 py-1.5 rounded-xl bg-white border border-stone-200/80 shadow-2xs flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-medium text-stone-600">Spatial Mesh:</span>
            <span className="text-xs font-bold text-teal-700">Active</span>
          </div>
        </div>
      </div>

      {/* Network Map Section */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-teal-600" />
          <h2 className="text-base font-bold text-stone-900 tracking-tight flex items-center gap-2">
            <Radio size={16} className="text-teal-600" />
            Geospatial Radar & Station Status
          </h2>
        </div>
        <StationMap />
      </section>

      {/* Pattern Insights Section */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-teal-600" />
          <h2 className="text-base font-bold text-stone-900 tracking-tight flex items-center gap-2">
            <Sparkles size={16} className="text-teal-600" />
            Cross-Station Physical Insights
          </h2>
        </div>
        <PatternInsights />
      </section>
    </div>
  );
}