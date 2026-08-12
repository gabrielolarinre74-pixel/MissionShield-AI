'use client';

import { useState, useCallback } from 'react';
import type { SimulationOverrides } from '@/types';

export interface UseSimulationResult {
  overrides: SimulationOverrides | null;
  isSimulated: boolean;
  setOverride: <K extends keyof SimulationOverrides>(key: K, value: SimulationOverrides[K]) => void;
  reset: () => void;
}

export function useSimulation(): UseSimulationResult {
  const [overrides, setOverrides] = useState<SimulationOverrides | null>(null);

  const isSimulated =
    overrides !== null &&
    Object.values(overrides).some((v) => v !== null && v !== undefined);

  const setOverride = useCallback(
    <K extends keyof SimulationOverrides>(key: K, value: SimulationOverrides[K]) => {
      setOverrides((prev) => ({
        ...prev,
        [key]: value,
      }));
    },
    []
  );

  const reset = useCallback(() => {
    setOverrides(null);
  }, []);

  return { overrides, isSimulated, setOverride, reset };
}
