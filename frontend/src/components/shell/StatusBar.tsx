'use client';

import { RefreshCw, PanelRightOpen, PanelRightClose, Sun, Moon } from 'lucide-react';
import { FreshnessBadge } from '@/components/ui/FreshnessBadge';
import { SimBadge } from '@/components/ui/SimBadge';
import type { SpaceWeatherSnapshot } from '@/types';
import type { ThemeMode } from '@/hooks/useTheme';
import { formatUtcShort } from '@/lib/formatters';

interface StatusBarProps {
  snapshot: SpaceWeatherSnapshot | null;
  loading: boolean;
  isSimulated: boolean;
  aiPanelOpen: boolean;
  theme: ThemeMode;
  onToggleTheme: () => void;
  onToggleAiPanel: () => void;
  onRefresh: () => void;
}

export function StatusBar({
  snapshot,
  loading,
  isSimulated,
  aiPanelOpen,
  theme,
  onToggleTheme,
  onToggleAiPanel,
  onRefresh,
}: StatusBarProps) {
  const nasaStatus = snapshot?.source_status.find((s) => s.source === 'NASA DONKI');
  const noaaSwpcStatus = snapshot?.source_status.find((s) => s.source === 'NOAA SWPC');
  const noaaGoesStatus = snapshot?.source_status.find((s) => s.source === 'NOAA GOES');

  return (
    <header
      style={{
        height: 40,
        background: 'var(--surface-1)',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        gap: 16,
        flexShrink: 0,
        overflow: 'hidden',
      }}
      aria-label="System status bar"
    >
      {/* Freshness */}
      {snapshot && (
        <FreshnessBadge freshness={snapshot.freshness} />
      )}

      {/* Sync time */}
      {snapshot && (
        <span
          style={{
            fontSize: 11,
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
          }}
          aria-label={`Last synchronized ${formatUtcShort(snapshot.fetched_at)}`}
        >
          Synced {formatUtcShort(snapshot.fetched_at)}
        </span>
      )}

      {/* Source status pills */}
      <div
        style={{ display: 'flex', alignItems: 'center', gap: 8 }}
        aria-label="Data source availability"
      >
        {[
          { label: 'NASA', status: nasaStatus },
          { label: 'NOAA SWPC', status: noaaSwpcStatus },
          { label: 'NOAA GOES', status: noaaGoesStatus },
        ].map(({ label, status }) => {
          if (!status) return null;
          const ok = status.available;
          return (
            <span
              key={label}
              title={!ok ? status.error ?? 'Unavailable' : 'Available'}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                fontSize: 11,
                color: ok ? 'var(--text-muted)' : 'var(--stale-color)',
                padding: '1px 6px',
                background: ok ? 'transparent' : 'rgba(249,115,22,0.08)',
                borderRadius: 3,
                border: ok ? '1px solid transparent' : '1px solid rgba(249,115,22,0.2)',
              }}
              aria-label={`${label}: ${ok ? 'available' : 'unavailable'}`}
            >
              <span
                style={{
                  width: 5,
                  height: 5,
                  borderRadius: '50%',
                  background: ok ? 'var(--live-color)' : 'var(--stale-color)',
                  display: 'inline-block',
                  flexShrink: 0,
                }}
                aria-hidden="true"
              />
              {label}
            </span>
          );
        })}
      </div>

      {/* Simulation badge */}
      {isSimulated && <SimBadge size="sm" />}

      {/* Stale notice */}
      {snapshot?.freshness === 'stale' && snapshot.last_successful_fetch && (
        <span style={{ fontSize: 11, color: 'var(--stale-color)' }}>
          Last data: {formatUtcShort(snapshot.last_successful_fetch)}
        </span>
      )}

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Theme toggle */}
      <button
        onClick={onToggleTheme}
        aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
        title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 28,
          height: 28,
          color: 'var(--text-muted)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          borderRadius: 4,
          transition: 'color 150ms ease, background-color 150ms ease',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = 'var(--accent-hover)';
          e.currentTarget.style.background = 'var(--accent-dim)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.color = 'var(--text-muted)';
          e.currentTarget.style.background = 'none';
        }}
      >
        {theme === 'dark' ? (
          <Sun size={14} aria-hidden="true" />
        ) : (
          <Moon size={14} aria-hidden="true" />
        )}
      </button>

      {/* Refresh */}
      <button
        onClick={onRefresh}
        disabled={loading}
        aria-label="Refresh data"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          fontSize: 11,
          color: 'var(--text-muted)',
          background: 'none',
          border: 'none',
          cursor: loading ? 'default' : 'pointer',
          padding: '4px 6px',
          borderRadius: 4,
          opacity: loading ? 0.5 : 1,
          transition: 'opacity 150ms ease',
          fontFamily: 'var(--font-sans)',
        }}
      >
        <RefreshCw
          size={12}
          aria-hidden="true"
          style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }}
        />
        Refresh
      </button>

      {/* AI panel toggle */}
      <button
        onClick={onToggleAiPanel}
        aria-label={aiPanelOpen ? 'Close Mission AI panel' : 'Open Mission AI panel'}
        aria-expanded={aiPanelOpen}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          fontSize: 11,
          color: aiPanelOpen ? 'var(--accent)' : 'var(--text-muted)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '4px 6px',
          borderRadius: 4,
          transition: 'color 150ms ease',
          fontFamily: 'var(--font-sans)',
        }}
      >
        {aiPanelOpen ? <PanelRightClose size={14} aria-hidden="true" /> : <PanelRightOpen size={14} aria-hidden="true" />}
        Mission AI
      </button>
    </header>
  );
}
