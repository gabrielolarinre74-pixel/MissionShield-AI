'use client';

import { SkeletonTelemetry } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import type { SpaceWeatherSnapshot } from '@/types';
import {
  formatKp,
  formatNumber,
  formatProtonFlux,
  formatUtcShort,
} from '@/lib/formatters';

interface TelemetryStripProps {
  snapshot: SpaceWeatherSnapshot | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

interface MetricProps {
  label: string;
  value: string;
  unit?: string;
  source?: string;
  time?: string;
  unavailable?: boolean;
  isLast?: boolean;
}

function Metric({ label, value, unit, source, time, unavailable = false, isLast = false }: MetricProps) {
  return (
    <div
      style={{
        padding: '14px 20px',
        borderRight: isLast ? 'none' : '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        gap: 3,
        minWidth: 0,
      }}
    >
      <p style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.02em', whiteSpace: 'nowrap' }}>
        {label}
      </p>
      <p
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 20,
          fontWeight: 500,
          color: unavailable ? 'var(--text-muted)' : 'var(--text-primary)',
          lineHeight: 1.2,
          fontStyle: unavailable ? 'normal' : undefined,
        }}
        aria-label={unavailable ? `${label}: unavailable` : `${label}: ${value}${unit ? ' ' + unit : ''}`}
      >
        {value}
      </p>
      <p style={{ fontSize: 11, color: 'var(--text-muted)', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {unit && <span>{unit}</span>}
        {source && <span style={{ color: 'var(--text-muted)', opacity: 0.7 }}>{source}</span>}
        {time && <span style={{ fontFamily: 'var(--font-mono)', opacity: 0.7 }}>{time}</span>}
      </p>
    </div>
  );
}

export function TelemetryStrip({ snapshot, loading, error, onRetry }: TelemetryStripProps) {
  const container = (children: React.ReactNode) => (
    <section
      aria-label="Real-time telemetry"
      style={{
        background: 'var(--surface-1)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 8,
        overflow: 'hidden',
      }}
    >
      <div style={{ padding: '12px 20px 0', display: 'flex', alignItems: 'center', gap: 8 }}>
        <p style={{ fontSize: 11, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>
          Real-time Telemetry
        </p>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>·</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>NASA DONKI · NOAA SWPC · NOAA GOES</span>
      </div>
      {children}
    </section>
  );

  if (loading && !snapshot) {
    return container(<SkeletonTelemetry />);
  }

  if (error && !snapshot) {
    return container(
      <div style={{ padding: '0 20px 16px' }}>
        <ErrorState variant="data-unavailable" message={error} onRetry={onRetry} compact />
      </div>
    );
  }

  if (!snapshot) return null;

  const kp = snapshot.latest_kp;
  const wind = snapshot.latest_solar_wind;
  const mag = snapshot.latest_mag_field;
  const proton = snapshot.latest_proton_flux_10mev;

  const metrics: MetricProps[] = [
    {
      label: 'Planetary Kp',
      value: kp ? formatKp(kp.estimated_kp) : 'Unavailable',
      unit: kp ? 'Kp units' : undefined,
      source: kp ? 'NOAA SWPC' : undefined,
      time: kp ? formatUtcShort(kp.time_tag) : undefined,
      unavailable: !kp,
    },
    {
      label: 'Solar Wind Speed',
      value: wind?.proton_speed_km_s != null ? formatNumber(wind.proton_speed_km_s, 0) : 'Unavailable',
      unit: wind?.proton_speed_km_s != null ? 'km/s' : undefined,
      source: wind ? `NOAA SWPC${wind.instrument_source ? ' · ' + wind.instrument_source : ''}` : undefined,
      time: wind ? formatUtcShort(wind.time_tag) : undefined,
      unavailable: !wind || wind.proton_speed_km_s == null,
    },
    {
      label: 'IMF Bz (GSM)',
      value: mag?.bz_gsm_nt != null ? formatNumber(mag.bz_gsm_nt, 1) : 'Unavailable',
      unit: mag?.bz_gsm_nt != null ? 'nT' : undefined,
      source: mag ? `NOAA SWPC${mag.instrument_source ? ' · ' + mag.instrument_source : ''}` : undefined,
      time: mag ? formatUtcShort(mag.time_tag) : undefined,
      unavailable: !mag || mag.bz_gsm_nt == null,
    },
    {
      label: '≥10 MeV Proton Flux',
      value: proton?.flux_pfu != null ? formatProtonFlux(proton.flux_pfu) : 'Unavailable',
      unit: proton?.flux_pfu != null ? 'pfu' : undefined,
      source: proton ? `NOAA GOES${proton.satellite ? '-' + proton.satellite : ''}` : undefined,
      time: proton ? formatUtcShort(proton.time_tag) : undefined,
      unavailable: !proton || proton.flux_pfu == null,
    },
  ];

  return container(
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        marginTop: 4,
      }}
      role="list"
      aria-label="Space weather measurements"
    >
      {metrics.map((m, i) => (
        <div key={m.label} role="listitem">
          <Metric {...m} isLast={i === metrics.length - 1} />
        </div>
      ))}
    </div>
  );
}
