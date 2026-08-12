// MissionShield AI — formatting utilities

import type { MissionProfile, RiskLevel, DataFreshness } from '@/types';

// ─── Mission labels ──────────────────────────────────────────────────────────

export const MISSION_LABELS: Record<MissionProfile, string> = {
  ROCKET_LAUNCH: 'Rocket Launch',
  LEO_SATELLITE: 'LEO Satellite',
  ASTRONAUT_EVA: 'Astronaut EVA',
  LUNAR_MISSION: 'Lunar Mission',
};

export const MISSION_PROFILES: MissionProfile[] = [
  'ROCKET_LAUNCH',
  'LEO_SATELLITE',
  'ASTRONAUT_EVA',
  'LUNAR_MISSION',
];

// ─── Risk level ──────────────────────────────────────────────────────────────

export const RISK_LEVEL_LABELS: Record<RiskLevel, string> = {
  LOW: 'Low',
  MODERATE: 'Moderate',
  HIGH: 'High',
  EXTREME: 'Extreme',
};

export function getRiskColor(level: RiskLevel): string {
  switch (level) {
    case 'LOW': return 'var(--risk-low)';
    case 'MODERATE': return 'var(--risk-moderate)';
    case 'HIGH': return 'var(--risk-high)';
    case 'EXTREME': return 'var(--risk-extreme)';
  }
}

export function getRiskBgColor(level: RiskLevel): string {
  switch (level) {
    case 'LOW': return 'var(--risk-low-bg)';
    case 'MODERATE': return 'var(--risk-moderate-bg)';
    case 'HIGH': return 'var(--risk-high-bg)';
    case 'EXTREME': return 'var(--risk-extreme-bg)';
  }
}

export function getRiskBorderColor(level: RiskLevel): string {
  switch (level) {
    case 'LOW': return 'var(--risk-low-border)';
    case 'MODERATE': return 'var(--risk-moderate-border)';
    case 'HIGH': return 'var(--risk-high-border)';
    case 'EXTREME': return 'var(--risk-extreme-border)';
  }
}

// ─── Freshness ───────────────────────────────────────────────────────────────

export const FRESHNESS_LABELS: Record<DataFreshness, string> = {
  live: 'Live',
  cached: 'Cached',
  stale: 'Stale',
};

export function getFreshnessColor(freshness: DataFreshness): string {
  switch (freshness) {
    case 'live': return 'var(--live-color)';
    case 'cached': return 'var(--cached-color)';
    case 'stale': return 'var(--stale-color)';
  }
}

// ─── Numeric formatting ──────────────────────────────────────────────────────

export function formatScore(score: number): string {
  return Math.round(score).toString().padStart(2, '0');
}

export function formatNumber(
  value: number | null | undefined,
  decimals = 1,
  fallback = '—'
): string {
  if (value === null || value === undefined) return fallback;
  return value.toFixed(decimals);
}

export function formatKp(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return value.toFixed(1);
}

export function formatProtonFlux(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  if (value < 0.01) return value.toExponential(2);
  return value.toFixed(2);
}

// ─── DateTime formatting ─────────────────────────────────────────────────────

export function formatUtcTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '—';
    return d.toISOString().replace('T', ' ').substring(0, 16) + ' UTC';
  } catch {
    return '—';
  }
}

export function formatUtcShort(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '—';
    return d.toISOString().substring(11, 16) + ' UTC';
  } catch {
    return '—';
  }
}

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '—';
    const diffMs = Date.now() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return 'just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return `${diffH}h ago`;
    return `${Math.floor(diffH / 24)}d ago`;
  } catch {
    return '—';
  }
}

// ─── Flare class ─────────────────────────────────────────────────────────────

export function getFlareClassSeverity(classType: string | null): 'none' | 'low' | 'moderate' | 'high' | 'extreme' {
  if (!classType) return 'none';
  const letter = classType[0].toUpperCase();
  switch (letter) {
    case 'X': return 'extreme';
    case 'M': return 'high';
    case 'C': return 'moderate';
    case 'B': return 'low';
    default: return 'none';
  }
}

// ─── Completeness ────────────────────────────────────────────────────────────

export function formatCompleteness(value: number): string {
  return `${Math.round(value * 100)}%`;
}

// ─── Risk score interpretation ───────────────────────────────────────────────

export function getRiskInterpretation(level: RiskLevel): string {
  switch (level) {
    case 'LOW':
      return 'Current observed conditions indicate low prototype mission risk.';
    case 'MODERATE':
      return 'Conditions warrant increased attention. Review primary contributors.';
    case 'HIGH':
      return 'Elevated space-weather hazards present. Consider mission constraints.';
    case 'EXTREME':
      return 'Severe space-weather conditions. Mission risk is critically elevated.';
  }
}
