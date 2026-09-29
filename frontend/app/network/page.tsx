// app/network/page.tsx
"use client";

import StationMap from "@/components/dashboard/StationMap";
import PatternInsights from "@/components/dashboard/PatternInsights";

export default function NetworkPage() {
  return (
    <div className="space-y-10 fade-in">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 tracking-tight">
          Station Network
        </h1>
        <p className="text-sm text-gray-500 mt-2">
          Geographic topology and network-wide pattern analysis
        </p>
      </div>

      <section>
        <h2 className="section-title mb-5">Network Map</h2>
        <StationMap />
      </section>

      <section>
        <h2 className="section-title mb-5">Insights</h2>
        <PatternInsights />
      </section>
    </div>
  );
}