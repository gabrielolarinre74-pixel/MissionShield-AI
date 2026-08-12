'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchSnapshot } from '@/lib/api';
import type { SpaceWeatherSnapshot } from '@/types';
import { SNAPSHOT_POLL_INTERVAL_MS } from '@/lib/constants';

export type FetchState = 'idle' | 'loading' | 'success' | 'error';

export interface UseSpaceWeatherResult {
  snapshot: SpaceWeatherSnapshot | null;
  state: FetchState;
  error: string | null;
  lastFetched: Date | null;
  refresh: () => void;
}

export function useSpaceWeather(): UseSpaceWeatherResult {
  const [snapshot, setSnapshot] = useState<SpaceWeatherSnapshot | null>(null);
  const [state, setState] = useState<FetchState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [lastFetched, setLastFetched] = useState<Date | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    // Cancel any in-flight request
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState('loading');
    setError(null);
    try {
      const data = await fetchSnapshot(controller.signal);
      if (!controller.signal.aborted) {
        setSnapshot(data);
        setState('success');
        setLastFetched(new Date());
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      const msg =
        err instanceof Error ? err.message : 'Failed to fetch space weather data.';
      setError(msg);
      setState('error');
    }
  }, []);

  // Initial load
  useEffect(() => {
    load();
    return () => { abortRef.current?.abort(); };
  }, [load]);

  // Polling — conservative interval aligned with backend cache TTL
  useEffect(() => {
    const id = setInterval(load, SNAPSHOT_POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [load]);

  return { snapshot, state, error, lastFetched, refresh: load };
}
