// lib/api.ts — Typed API client with offline fallback

export const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

const FALLBACK_ALERTS = "/fallback/alerts.json";
const FALLBACK_STATIONS = "/fallback/station_metadata.csv";
const FALLBACK_OBSERVATIONS = "/fallback/observations.csv";

const FETCH_TIMEOUT_MS = 5000;

// Global offline flag so components can show a badge.
let _isOffline = false;
export function isOfflineMode() {
  return _isOffline;
}

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
  details?: Record<string, unknown>;
}

export interface Defensibility {
  evidence_for_fault: string[];
  evidence_against_fault: string[];
  known_limitations: string[];
  operator_action: string;
  confidence_meaning: string;
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
  corrected_temperature: number | null;
  corrected_pressure: number | null;
  corrected_humidity: number | null;
  decision_basis?: string;
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

export interface FaultTypesResponse {
  fault_types: string[];
  default_magnitudes: Record<string, number>;
}

export interface InjectionResult {
  station_id: string;
  fault_type: string;
  magnitude: number;
  original_reading: { temperature: number; pressure: number; humidity: number };
  modified_reading: { temperature: number; pressure: number; humidity: number };
  alert: Alert;
}

// ──────────────────────────────────────────────────────────────────────
// Fetch helper with timeout
// ──────────────────────────────────────────────────────────────────────

async function fetchWithTimeout(url: string, options?: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    return res;
  } finally {
    clearTimeout(timeout);
  }
}

// ──────────────────────────────────────────────────────────────────────
// Fallback loaders (read local files from /public/fallback)
// ──────────────────────────────────────────────────────────────────────

async function loadFallbackAlerts(): Promise<Alert[]> {
  try {
    const res = await fetch(FALLBACK_ALERTS);
    if (!res.ok) return [];
    return (await res.json()) as Alert[];
  } catch {
    return [];
  }
}

async function loadFallbackStations(): Promise<Station[]> {
  try {
    const res = await fetch(FALLBACK_STATIONS);
    if (!res.ok) return [];
    const text = await res.text();
    const lines = text.trim().split("\n");
    if (lines.length < 2) return [];
    const headers = lines[0].split(",").map((h) => h.trim());
    const rows: Station[] = [];
    for (let i = 1; i < lines.length; i++) {
      const values = lines[i].split(",").map((v) => v.trim());
      const row: Record<string, string> = {};
      headers.forEach((h, idx) => {
        row[h] = values[idx];
      });
      rows.push({
        station_id: row["station_id"] || "",
        station_name: row["station_name"] || row["station_id"] || "",
        latitude: parseFloat(row["latitude"]) || 0,
        longitude: parseFloat(row["longitude"]) || 0,
      });
    }
    return rows;
  } catch {
    return [];
  }
}

async function loadFallbackObservations(): Promise<Observation[]> {
  try {
    const res = await fetch(FALLBACK_OBSERVATIONS);
    if (!res.ok) return [];
    const text = await res.text();
    const lines = text.trim().split("\n");
    if (lines.length < 2) return [];
    const headers = lines[0].split(",").map((h) => h.trim());
    const rows: Observation[] = [];
    for (let i = 1; i < lines.length; i++) {
      const values = lines[i].split(",");
      const row: Record<string, string> = {};
      headers.forEach((h, idx) => {
        row[h] = values[idx];
      });
      rows.push({
        timestamp: row["timestamp"] || "",
        station_id: row["station_id"] || "",
        temperature: parseFloat(row["temperature"]) || 0,
        pressure: parseFloat(row["pressure"]) || 0,
        humidity: parseFloat(row["humidity"]) || 0,
      });
    }
    return rows;
  } catch {
    return [];
  }
}

// ──────────────────────────────────────────────────────────────────────
// Public API functions (live-first, fallback-second)
// ──────────────────────────────────────────────────────────────────────

export async function getAlerts(): Promise<Alert[]> {
  try {
    const res = await fetchWithTimeout(`${BASE_URL}/alerts`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    _isOffline = false;
    return data as Alert[];
  } catch (err) {
    console.warn("Live alerts unavailable, using fallback:", err);
    _isOffline = true;
    return loadFallbackAlerts();
  }
}

export async function getStations(): Promise<Station[]> {
  try {
    const res = await fetchWithTimeout(`${BASE_URL}/stations`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    _isOffline = false;
    return data as Station[];
  } catch (err) {
    console.warn("Live stations unavailable, using fallback:", err);
    _isOffline = true;
    return loadFallbackStations();
  }
}

export async function getObservations(): Promise<Observation[]> {
  try {
    const res = await fetchWithTimeout(`${BASE_URL}/observations`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    _isOffline = false;
    return data as Observation[];
  } catch (err) {
    console.warn("Live observations unavailable, using fallback:", err);
    _isOffline = true;
    return loadFallbackObservations();
  }
}

export async function getObservationsByStation(id: string): Promise<Observation[]> {
  try {
    const res = await fetchWithTimeout(
      `${BASE_URL}/observations/${encodeURIComponent(id)}`
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    _isOffline = false;
    return data as Observation[];
  } catch (err) {
    console.warn("Live observations unavailable, using fallback:", err);
    _isOffline = true;
    const all = await loadFallbackObservations();
    return all.filter((o) => o.station_id === id);
  }
}

export async function getFaultTypes(): Promise<FaultTypesResponse> {
  try {
    const res = await fetchWithTimeout(`${BASE_URL}/injection-fault-types`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    _isOffline = false;
    return data as FaultTypesResponse;
  } catch (err) {
    console.warn("Live fault types unavailable");
    _isOffline = true;
    return {
      fault_types: [
        "temperature_spike",
        "temperature_drop",
        "frozen_sensor",
        "humidity_spike",
        "pressure_drop",
        "total_collapse",
      ],
      default_magnitudes: {
        temperature_spike: 15.0,
        temperature_drop: 12.0,
        frozen_sensor: 0.0,
        humidity_spike: 30.0,
        pressure_drop: 20.0,
        total_collapse: 0.0,
      },
    };
  }
}

export async function injectFault(
  station_id: string,
  fault_type: string,
  magnitude: number
): Promise<InjectionResult | null> {
  try {
    const res = await fetchWithTimeout(`${BASE_URL}/inject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ station_id, fault_type, magnitude }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    _isOffline = false;
    return (await res.json()) as InjectionResult;
  } catch (err) {
    console.warn("Live injection unavailable:", err);
    _isOffline = true;
    return null;
  }
}