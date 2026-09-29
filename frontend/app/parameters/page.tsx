// app/parameters/page.tsx
"use client";

import ParameterCharts from "@/components/dashboard/ParameterCharts";

export default function ParametersPage() {
  return (
    <div className="space-y-10 fade-in">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 tracking-tight">
          Parameters
        </h1>
        <p className="text-sm text-gray-500 mt-2">
          Live temperature, humidity, and pressure across the network
        </p>
      </div>

      <ParameterCharts />
    </div>
  );
}