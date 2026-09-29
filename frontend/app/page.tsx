// app/page.tsx
"use client";

import { useState } from "react";
import WarningCards from "@/components/dashboard/WarningCards";
import ParameterCharts from "@/components/dashboard/ParameterCharts";
import StationMap from "@/components/dashboard/StationMap";
import RiskLevelChart from "@/components/dashboard/RiskLevelChart";
import PatternInsights from "@/components/dashboard/PatternInsights";
import type { Alert } from "@/lib/api";

export default function DashboardPage() {
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);

  return (
    <div className="space-y-10 fade-in">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 tracking-tight">
          Dashboard
        </h1>
        <p className="text-sm text-gray-500 mt-2">
          Real-time AWS anomaly detection and monitoring
        </p>
      </div>

      {/* Warning cards section */}
      <section>
        <h2 className="section-title mb-5">Active Alerts</h2>
        <WarningCards onSelect={setSelectedAlert} />
      </section>

      {/* Parameter charts section */}
      <section>
        <h2 className="section-title mb-5">Live Parameters</h2>
        <ParameterCharts />
      </section>

      {/* Station map section */}
      <section>
        <h2 className="section-title mb-5">Station Network</h2>
        <StationMap />
      </section>

      {/* Risk level section */}
      <section>
        <h2 className="section-title mb-5">Risk Overview</h2>
        <RiskLevelChart />
      </section>

      {/* Pattern insights section */}
      <section>
        <h2 className="section-title mb-5">Insights</h2>
        <PatternInsights />
      </section>

      {/* Alert detail modal */}
      {selectedAlert && (
        <div
          className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4 fade-in"
          onClick={() => setSelectedAlert(null)}
        >
          <div
            className="bg-white rounded-lg max-w-2xl w-full max-h-[80vh] overflow-y-auto p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-lg font-bold text-gray-900">
                  {selectedAlert.station_id} — {selectedAlert.anomaly_type}
                </h3>
                <p className="text-xs text-gray-500 mt-1">
                  {selectedAlert.timestamp}
                </p>
              </div>
              <button
                onClick={() => setSelectedAlert(null)}
                className="text-gray-400 hover:text-gray-700 text-2xl leading-none transition-colors"
              >
                ×
              </button>
            </div>
            <pre className="text-xs bg-gray-50 p-3 rounded overflow-auto border border-gray-200">
              {JSON.stringify(selectedAlert, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}