// app/page.tsx
"use client";

import { useState } from "react";
import WarningCards from "@/components/dashboard/WarningCards";
import RiskLevelChart from "@/components/dashboard/RiskLevelChart";
import AlertDetailModal from "@/components/dashboard/AlertDetailModal";
import type { Alert } from "@/lib/api";

export default function DashboardPage() {
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);

  return (
    <div className="space-y-10 fade-in">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 tracking-tight">
          Dashboard
        </h1>
        <p className="text-sm text-gray-500 mt-2">
          Real-time AWS anomaly detection and monitoring
        </p>
      </div>

      <section>
        <h2 className="section-title mb-5">Active Alerts</h2>
        <WarningCards onSelect={setSelectedAlert} />
      </section>

      <section>
        <h2 className="section-title mb-5">Risk Overview</h2>
        <RiskLevelChart />
      </section>

      <AlertDetailModal
        alert={selectedAlert}
        onClose={() => setSelectedAlert(null)}
      />
    </div>
  );
}