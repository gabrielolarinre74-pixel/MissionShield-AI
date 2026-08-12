'use client';

import { useEffect, useState } from 'react';
import { fetchAnomalies, fetchEvents } from '@/lib/api';
import { ErrorState } from '@/components/ui/ErrorState';
import { FreshnessBadge } from '@/components/ui/FreshnessBadge';
import { Skeleton } from '@/components/ui/Skeleton';
import type { AnomalyFlag, EventsResponse } from '@/types';
import { formatUtcTime, formatRelativeTime, getFlareClassSeverity } from '@/lib/formatters';
import { ExternalLink } from 'lucide-react';

// ─── Anomaly Panel ───────────────────────────────────────────────────────────

export function AnomalyPanel() {
  const [flags, setFlags] = useState<AnomalyFlag[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAnomalies();
      setFlags(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Anomaly data unavailable.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const anomalous = flags?.filter((f) => f.is_anomalous) ?? [];

  return (
    <section
      aria-label="Anomaly detection"
      style={{
        background: 'var(--surface-1)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 8,
        padding: '20px 24px',
      }}
    >
      <div style={{ marginBottom: 14 }}>
        <p style={{ fontSize: 11, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 4 }}>
          Statistical Anomaly Detection
        </p>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5 }}>
          Robust z-score (median/MAD) analysis of current readings vs. recent baseline.
          Anomaly means <em>statistically unusual</em>, not automatically dangerous.
        </p>
      </div>

      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[0, 1, 2].map((i) => <Skeleton key={i} height={48} />)}
        </div>
      )}

      {error && !loading && (
        <ErrorState variant="data-unavailable" message={error} onRetry={load} compact />
      )}

      {!loading && !error && flags !== null && (
        <>
          {anomalous.length === 0 && flags.length === 0 && (
            <p style={{ fontSize: 13, color: 'var(--text-muted)', fontStyle: 'italic' }}>
              Insufficient time-series data in the current analysis window to run anomaly detection.
            </p>
          )}

          {anomalous.length === 0 && flags.length > 0 && (
            <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              No statistically unusual readings detected in the available analysis window.
            </p>
          )}

          {anomalous.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {anomalous.map((flag) => (
                <div
                  key={`${flag.parameter}-${flag.timestamp}`}
                  style={{
                    padding: '12px 14px',
                    background: 'rgba(251,191,36,0.06)',
                    border: '1px solid rgba(251,191,36,0.2)',
                    borderRadius: 6,
                  }}
                  role="listitem"
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
                    <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)' }}>
                      {flag.parameter.replace(/_/g, ' ')}
                    </span>
                    <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--sim-color)' }}>
                      z = {flag.z_score.toFixed(2)}
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: 16, marginBottom: 6, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      Observed: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                        {flag.current_value.toFixed(2)} {flag.unit}
                      </span>
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      Median: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                        {flag.baseline_median.toFixed(2)} {flag.unit}
                      </span>
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                      Direction: {flag.direction}
                    </span>
                  </div>
                  <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5 }}>
                    {flag.explanation}
                  </p>
                  <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                    {flag.source} · {flag.sample_count} samples · threshold |z| ≥ {flag.threshold}
                  </p>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}

// ─── Events Panel ────────────────────────────────────────────────────────────

function EventTypeTag({ type }: { type: string }) {
  const colors: Record<string, string> = {
    FLR: 'var(--risk-high)',
    CME: 'var(--accent)',
    GST: 'var(--risk-extreme)',
    SEP: 'var(--risk-extreme)',
  };
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 600,
        fontFamily: 'var(--font-mono)',
        color: colors[type] ?? 'var(--text-muted)',
        padding: '1px 6px',
        background: 'var(--surface-2)',
        borderRadius: 3,
        border: '1px solid var(--border-subtle)',
        flexShrink: 0,
      }}
    >
      {type}
    </span>
  );
}

export function EventsPanel() {
  const [events, setEvents] = useState<EventsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchEvents();
      setEvents(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Events unavailable.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  type EventItem = {
    type: string;
    time: string;
    title: string;
    detail: string;
    link: string | null;
    severity?: string;
  };

  const allEvents: EventItem[] = [];

  if (events) {
    events.flares.forEach((f) => {
      const severity = getFlareClassSeverity(f.class_type);
      allEvents.push({
        type: 'FLR',
        time: f.begin_time,
        title: f.class_type ? `${f.class_type} Solar Flare` : 'Solar Flare',
        detail: [
          f.source_location,
          f.peak_time ? `Peak: ${formatUtcTime(f.peak_time)}` : null,
        ].filter(Boolean).join(' · '),
        link: f.link,
        severity,
      });
    });
    events.cmes.forEach((c) => {
      const earthDir = c.analyses.some((a) => a.enlil_runs.some((r) => r.is_earth_directed));
      allEvents.push({
        type: 'CME',
        time: c.start_time,
        title: `Coronal Mass Ejection${earthDir ? ' — Earth-directed' : ''}`,
        detail: [
          c.source_location,
          c.note?.substring(0, 80),
        ].filter(Boolean).join(' · '),
        link: c.link,
        severity: earthDir ? 'moderate' : 'low',
      });
    });
    events.geomagnetic_storms.forEach((g) => {
      const maxKp = g.observed_kp_readings.reduce((m, r) => Math.max(m, r.kp_index), 0);
      allEvents.push({
        type: 'GST',
        time: g.start_time,
        title: `Geomagnetic Storm`,
        detail: maxKp > 0 ? `Peak Kp: ${maxKp}` : 'Geomagnetic storm event',
        link: g.link,
        severity: maxKp >= 7 ? 'extreme' : maxKp >= 5 ? 'high' : 'moderate',
      });
    });
    events.sep_events.forEach((s) => {
      allEvents.push({
        type: 'SEP',
        time: s.event_time,
        title: 'Solar Energetic Particle Event',
        detail: s.instruments.join(', '),
        link: s.link,
        severity: 'high',
      });
    });
    // Sort most recent first
    allEvents.sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime());
  }

  return (
    <section
      aria-label="Recent space weather events"
      style={{
        background: 'var(--surface-1)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 8,
        padding: '20px 24px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <p style={{ fontSize: 11, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>
          Recent Events — 7-day lookback
        </p>
        {events && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <FreshnessBadge freshness={events.freshness} showDot={false} />
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>NASA DONKI</span>
          </div>
        )}
      </div>

      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} height={56} />)}
        </div>
      )}

      {error && !loading && (
        <ErrorState variant="data-unavailable" message={error} onRetry={load} compact />
      )}

      {!loading && !error && allEvents.length === 0 && (
        <p style={{ fontSize: 13, color: 'var(--text-muted)', fontStyle: 'italic' }}>
          No significant space-weather events recorded in the 7-day lookback window.
        </p>
      )}

      {!loading && !error && allEvents.length > 0 && (
        <div role="list" aria-label="Space weather event list">
          {allEvents.map((ev, i) => (
            <div
              key={i}
              role="listitem"
              style={{
                padding: '12px 0',
                borderTop: i === 0 ? 'none' : '1px solid var(--border-subtle)',
                display: 'flex',
                gap: 12,
                alignItems: 'flex-start',
              }}
            >
              <EventTypeTag type={ev.type} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 2 }}>
                  <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)' }}>
                    {ev.title}
                  </span>
                  {ev.link && (
                    <a
                      href={ev.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label={`View ${ev.title} on NASA DONKI`}
                      style={{ color: 'var(--accent)', flexShrink: 0 }}
                    >
                      <ExternalLink size={12} aria-hidden="true" />
                    </a>
                  )}
                </div>
                <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 2, lineHeight: 1.4 }}>
                  {ev.detail}
                </p>
                <p style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  {formatUtcTime(ev.time)} · {formatRelativeTime(ev.time)}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
