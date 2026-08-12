'use client';

import type { SpaceWeatherSnapshot } from '@/types';
import { FreshnessBadge } from '@/components/ui/FreshnessBadge';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import {
  formatKp,
  formatNumber,
  formatProtonFlux,
  formatUtcTime,
  formatUtcShort,
} from '@/lib/formatters';

interface SpaceWeatherViewProps {
  snapshot: SpaceWeatherSnapshot | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

function MeasurementCard({
  title,
  source,
  children,
}: {
  title: string;
  source: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        background: 'var(--surface-1)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 8,
        padding: '18px 22px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
        <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>{title}</p>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{source}</span>
      </div>
      {children}
    </div>
  );
}

function Field({ label, value, unit, mono = true }: { label: string; value: string | null; unit?: string; mono?: boolean }) {
  const isUnavail = !value || value === '—';
  return (
    <div style={{ marginBottom: 10 }}>
      <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>{label}</p>
      <p
        style={{
          fontSize: 14,
          fontFamily: mono ? 'var(--font-mono)' : 'var(--font-sans)',
          color: isUnavail ? 'var(--text-muted)' : 'var(--text-primary)',
          fontStyle: isUnavail ? 'italic' : 'normal',
        }}
        aria-label={isUnavail ? `${label}: unavailable` : `${label}: ${value} ${unit ?? ''}`}
      >
        {value ?? 'Unavailable'}
        {unit && !isUnavail && (
          <span style={{ marginLeft: 4, fontSize: 11, color: 'var(--text-muted)' }}>{unit}</span>
        )}
      </p>
    </div>
  );
}

export function SpaceWeatherView({ snapshot, loading, error, onRetry }: SpaceWeatherViewProps) {
  if (loading && !snapshot) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
          {[0, 1, 2, 3].map((i) => (
            <div key={i} style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: '18px 22px' }}>
              <Skeleton width={120} height={13} />
              <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
                {[0, 1, 2].map((j) => (
                  <div key={j} style={{ marginBottom: 4 }}>
                    <Skeleton width={80} height={11} />
                    <Skeleton width={100} height={16} />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error && !snapshot) {
    return (
      <ErrorState variant="data-unavailable" message={error} onRetry={onRetry} />
    );
  }

  if (!snapshot) return null;

  const kp = snapshot.latest_kp;
  const wind = snapshot.latest_solar_wind;
  const mag = snapshot.latest_mag_field;
  const proton = snapshot.latest_proton_flux_10mev;

  const bzColor = (bz: number | null | undefined): string => {
    if (bz == null) return 'var(--text-primary)';
    if (bz < -20) return 'var(--risk-extreme)';
    if (bz < -10) return 'var(--risk-high)';
    if (bz < -5) return 'var(--risk-moderate)';
    return 'var(--text-primary)';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Status header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <FreshnessBadge freshness={snapshot.freshness} />
        {snapshot.freshness === 'stale' && snapshot.last_successful_fetch && (
          <span style={{ fontSize: 12, color: 'var(--stale-color)' }}>
            Last successful fetch: {formatUtcShort(snapshot.last_successful_fetch)}
          </span>
        )}
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          Assembled {formatUtcTime(snapshot.fetched_at)}
        </span>
      </div>

      {/* Source status */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        {snapshot.source_status.map((s) => (
          <div
            key={s.source}
            style={{
              padding: '6px 12px',
              background: 'var(--surface-1)',
              border: `1px solid ${s.available ? 'var(--border-subtle)' : 'rgba(249,115,22,0.3)'}`,
              borderRadius: 6,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: s.available ? 'var(--live-color)' : 'var(--stale-color)',
                display: 'inline-block',
              }}
              aria-hidden="true"
            />
            <span style={{ fontSize: 12, color: s.available ? 'var(--text-secondary)' : 'var(--stale-color)' }}>
              {s.source}
            </span>
            {!s.available && s.error && (
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>— {s.error}</span>
            )}
          </div>
        ))}
      </div>

      {/* Measurement cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
        {/* Kp */}
        <MeasurementCard title="Planetary Kp Index" source="NOAA SWPC">
          <Field
            label="Estimated Kp"
            value={kp ? formatKp(kp.estimated_kp) : null}
            unit="Kp units"
          />
          {kp && (
            <>
              <Field label="Kp code" value={kp.kp_text ?? '—'} />
              <Field label="Measured" value={formatUtcTime(kp.time_tag)} mono={false} />
            </>
          )}
          {!kp && <p style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>NOAA SWPC data unavailable</p>}
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
            NOAA G-scale: G0 (Kp&lt;5) → G5 (Kp=9). Official NOAA reference.
          </p>
        </MeasurementCard>

        {/* Solar wind */}
        <MeasurementCard title="Solar Wind" source="NOAA SWPC">
          <Field
            label="Proton speed"
            value={wind?.proton_speed_km_s != null ? formatNumber(wind.proton_speed_km_s, 0) : null}
            unit="km/s"
          />
          <Field
            label="Proton density"
            value={wind?.proton_density_cm3 != null ? formatNumber(wind.proton_density_cm3, 2) : null}
            unit="cm⁻³"
          />
          {wind?.instrument_source && (
            <Field label="Instrument" value={wind.instrument_source} mono={false} />
          )}
          {wind && <Field label="Measured" value={formatUtcTime(wind.time_tag)} mono={false} />}
          {!wind && <p style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>NOAA SWPC data unavailable</p>}
        </MeasurementCard>

        {/* Magnetic field */}
        <MeasurementCard title="Interplanetary Magnetic Field" source="NOAA SWPC">
          <Field
            label="Bz (GSM)"
            value={mag?.bz_gsm_nt != null ? formatNumber(mag.bz_gsm_nt, 1) : null}
            unit="nT"
          />
          <Field
            label="Bt total"
            value={mag?.bt_nt != null ? formatNumber(mag.bt_nt, 1) : null}
            unit="nT"
          />
          {mag?.bz_gsm_nt != null && (
            <p style={{ fontSize: 12, color: bzColor(mag.bz_gsm_nt), lineHeight: 1.4, marginTop: 4 }}>
              {mag.bz_gsm_nt < -10
                ? 'Strongly southward — high geoeffective potential'
                : mag.bz_gsm_nt < -5
                ? 'Southward — moderate geoeffective potential'
                : mag.bz_gsm_nt < 0
                ? 'Mildly southward'
                : 'Northward — low geoeffective potential'}
            </p>
          )}
          {mag && <Field label="Measured" value={formatUtcTime(mag.time_tag)} mono={false} />}
          {!mag && <p style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>NOAA SWPC data unavailable</p>}
        </MeasurementCard>

        {/* Proton flux */}
        <MeasurementCard title="≥10 MeV Proton Flux" source="NOAA GOES">
          <Field
            label="Integral flux"
            value={proton?.flux_pfu != null ? formatProtonFlux(proton.flux_pfu) : null}
            unit="pfu"
          />
          {proton?.satellite && (
            <Field label="Satellite" value={`GOES-${proton.satellite}`} />
          )}
          {proton && <Field label="Measured" value={formatUtcTime(proton.time_tag)} mono={false} />}
          {!proton && <p style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>NOAA GOES data unavailable</p>}
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
            NOAA S-scale: S1 (≥10 pfu) → S5 (≥100,000 pfu). Official NOAA reference.
          </p>
        </MeasurementCard>
      </div>
    </div>
  );
}
