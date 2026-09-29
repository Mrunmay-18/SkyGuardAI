// lib/api.ts — Typed API client for SkyGuard AI FastAPI backend

export const BASE_URL = "http://localhost:8000/api";

// ──────────────────────────────────────────────────────────────────────
// TypeScript Interfaces
// ──────────────────────────────────────────────────────────────────────

export interface CounterReasoning {
  verdict: string;
  reason: string;
  reliability: string;
  reliability_note?: string;
}

export interface MultivariateAnalysis {
  verdict: string;
  reason: string;
}

export interface Defensibility {
  evidence_for_fault: string[];
  known_limitations: string[];
  operator_action: string;
}

export interface EvidenceBreakdown {
  [key: string]: unknown;
}

export interface Alert {
  station_id: string;
  timestamp: string;
  temperature: number;
  pressure: number;
  humidity: number;
  status: string;
  anomaly_type: string;
  confidence: number;
  severity: string;
  priority: string;
  trust_score: number;
  physical_reasoning: string;
  weather_verdict_reason: string;
  maintenance_recommendation: string;
  corrected_temperature: number;
  corrected_pressure: number;
  corrected_humidity: number;
  decision_basis: string;
  correction_confidence?: number;
  correction_basis?: string;
  counter_evidence?: string;
  genuine_weather_event?: boolean;
  event_class?: string;
  counter_reasoning: CounterReasoning;
  multivariate_analysis: MultivariateAnalysis;
  defensibility: Defensibility;
  evidence_breakdown: EvidenceBreakdown;
}

export interface Station {
  station_id: string;
  station_name: string;
  latitude: number;
  longitude: number;
}

export interface Observation {
  timestamp: string;
  station_id: string;
  temperature: number;
  pressure: number;
  humidity: number;
}

// ──────────────────────────────────────────────────────────────────────
// Fetch helper
// ──────────────────────────────────────────────────────────────────────

async function fetchJson<T>(endpoint: string): Promise<T[]> {
  try {
    const res = await fetch(`${BASE_URL}${endpoint}`);
    if (!res.ok) {
      console.error(`API error ${res.status}: ${res.statusText} for ${endpoint}`);
      return [];
    }
    const data = await res.json();
    return data as T[];
  } catch (err) {
    console.error(`Fetch failed for ${endpoint}:`, err);
    return [];
  }
}

// ──────────────────────────────────────────────────────────────────────
// Public API functions
// ──────────────────────────────────────────────────────────────────────

/** Fetch all alerts from the backend. */
export async function getAlerts(): Promise<Alert[]> {
  return fetchJson<Alert>("/alerts");
}

/** Fetch all stations from the backend. */
export async function getStations(): Promise<Station[]> {
  return fetchJson<Station>("/stations");
}

/** Fetch all observations from the backend. */
export async function getObservations(): Promise<Observation[]> {
  return fetchJson<Observation>("/observations");
}

/** Fetch observations filtered by station ID. */
export async function getObservationsByStation(id: string): Promise<Observation[]> {
  return fetchJson<Observation>(`/observations/${encodeURIComponent(id)}`);
}
// ----------------------------------------------------------------------
// Fault Injection Lab
// ----------------------------------------------------------------------
export interface FaultTypesResponse {
  fault_types: string[];
  default_magnitudes: Record<string, number>;
}

export interface InjectionResult {
  station_id: string;
  fault_type: string;
  magnitude: number;
  original_reading: {
    temperature: number;
    pressure: number;
    humidity: number;
  };
  modified_reading: {
    temperature: number;
    pressure: number;
    humidity: number;
  };
  alert: Alert;
}

export async function getFaultTypes(): Promise<FaultTypesResponse> {
  try {
    const res = await fetch(`${BASE_URL}/injection-fault-types`);
    if (!res.ok) {
      console.error(`API error ${res.status}`);
      return { fault_types: [], default_magnitudes: {} };
    }
    return await res.json();
  } catch (err) {
    console.error("Fetch failed:", err);
    return { fault_types: [], default_magnitudes: {} };
  }
}

export async function injectFault(
  station_id: string,
  fault_type: string,
  magnitude: number
): Promise<InjectionResult | null> {
  try {
    const res = await fetch(`${BASE_URL}/inject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ station_id, fault_type, magnitude }),
    });
    if (!res.ok) {
      console.error(`API error ${res.status}`);
      return null;
    }
    return await res.json();
  } catch (err) {
    console.error("Fetch failed:", err);
    return null;
  }
}