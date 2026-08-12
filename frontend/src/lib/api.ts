// MissionShield AI — typed API client
// Only NEXT_PUBLIC_API_URL is exposed to the browser. No secrets.

import type {
  SpaceWeatherSnapshot,
  EventsResponse,
  AnomalyFlag,
  MissionProfile,
  MissionRiskReport,
  SimulationOverrides,
  BriefRequest,
  BriefResponse,
  ChatRequest,
  ChatResponse,
} from '@/types';

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ?? 'http://localhost:8000';

// ─── Generic fetch helper ────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options?: RequestInit,
  signal?: AbortSignal
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
    signal: signal ?? options?.signal,
  });
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = { error: 'HTTP_ERROR', message: `HTTP ${res.status}` };
    }
    throw new ApiClientError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export class ApiClientError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: unknown
  ) {
    const msg =
      typeof detail === 'object' &&
      detail !== null &&
      'message' in detail
        ? String((detail as Record<string, unknown>).message)
        : `HTTP ${status}`;
    super(msg);
    this.name = 'ApiClientError';
  }

  get errorCode(): string {
    if (
      typeof this.detail === 'object' &&
      this.detail !== null &&
      'error' in this.detail
    ) {
      return String((this.detail as Record<string, unknown>).error);
    }
    return 'UNKNOWN';
  }
}

// ─── Endpoints ──────────────────────────────────────────────────────────────

export async function fetchSnapshot(signal?: AbortSignal): Promise<SpaceWeatherSnapshot> {
  return apiFetch<SpaceWeatherSnapshot>('/api/space-weather/snapshot', {}, signal);
}

export async function fetchEvents(signal?: AbortSignal): Promise<EventsResponse> {
  return apiFetch<EventsResponse>('/api/space-weather/events', {}, signal);
}

export async function fetchAnomalies(signal?: AbortSignal): Promise<AnomalyFlag[]> {
  return apiFetch<AnomalyFlag[]>('/api/space-weather/anomalies', {}, signal);
}

export async function fetchMissionRisk(
  profile: MissionProfile,
  simulation_overrides?: SimulationOverrides | null,
  signal?: AbortSignal
): Promise<MissionRiskReport> {
  return apiFetch<MissionRiskReport>(
    '/api/mission/risk',
    {
      method: 'POST',
      body: JSON.stringify({ profile, simulation_overrides: simulation_overrides ?? null }),
    },
    signal
  );
}

export async function fetchMissionBrief(
  req: BriefRequest,
  signal?: AbortSignal
): Promise<BriefResponse> {
  return apiFetch<BriefResponse>(
    '/api/ai/brief',
    { method: 'POST', body: JSON.stringify(req) },
    signal
  );
}

export async function sendChatMessage(
  req: ChatRequest,
  signal?: AbortSignal
): Promise<ChatResponse> {
  return apiFetch<ChatResponse>(
    '/api/ai/chat',
    { method: 'POST', body: JSON.stringify(req) },
    signal
  );
}

export async function fetchHealth(signal?: AbortSignal): Promise<{ status: string; service: string; version: string }> {
  return apiFetch('/api/health', {}, signal);
}
