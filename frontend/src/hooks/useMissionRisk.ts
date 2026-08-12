'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchMissionRisk } from '@/lib/api';
import type { MissionProfile, MissionRiskReport, SimulationOverrides } from '@/types';

export type FetchState = 'idle' | 'loading' | 'success' | 'error';

export interface UseMissionRiskResult {
  report: MissionRiskReport | null;
  state: FetchState;
  error: string | null;
  refresh: () => void;
}

export function useMissionRisk(
  profile: MissionProfile,
  overrides: SimulationOverrides | null
): UseMissionRiskResult {
  const [report, setReport] = useState<MissionRiskReport | null>(null);
  const [state, setState] = useState<FetchState>('idle');
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState('loading');
    setError(null);
    try {
      const data = await fetchMissionRisk(profile, overrides, controller.signal);
      if (!controller.signal.aborted) {
        setReport(data);
        setState('success');
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      const msg = err instanceof Error ? err.message : 'Risk computation failed.';
      setError(msg);
      setState('error');
    }
  }, [profile, overrides]);

  useEffect(() => {
    load();
    return () => { abortRef.current?.abort(); };
  }, [load]);

  return { report, state, error, refresh: load };
}
