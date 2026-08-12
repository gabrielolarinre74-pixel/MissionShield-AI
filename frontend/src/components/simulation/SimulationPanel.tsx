'use client';

import { SimBadge } from '@/components/ui/SimBadge';
import { RiskBadge } from '@/components/ui/RiskBadge';
import { SkeletonScore } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import type { SimulationOverrides, MissionRiskReport } from '@/types';
import { SIM_RANGES } from '@/lib/constants';
import { formatScore, MISSION_LABELS, getRiskColor, getRiskBgColor, getRiskBorderColor } from '@/lib/formatters';

interface SimulationPanelProps {
  overrides: SimulationOverrides | null;
  isSimulated: boolean;
  onSetOverride: <K extends keyof SimulationOverrides>(key: K, value: SimulationOverrides[K]) => void;
  onReset: () => void;
  report: MissionRiskReport | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

interface SliderRowProps {
  fieldKey: keyof typeof SIM_RANGES;
  value: number | null | undefined;
  onChange: (v: number | null) => void;
}

function SliderRow({ fieldKey, value, onChange }: SliderRowProps) {
  const cfg = SIM_RANGES[fieldKey];
  const isActive = value != null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <label
          htmlFor={`sim-${fieldKey}`}
          style={{ fontSize: 13, color: 'var(--text-secondary)' }}
        >
          {cfg.label}
          {cfg.unit && (
            <span style={{ marginLeft: 4, fontSize: 11, color: 'var(--text-muted)' }}>
              {cfg.unit}
            </span>
          )}
        </label>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {isActive && (
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 13,
                color: 'var(--sim-color)',
                minWidth: 48,
                textAlign: 'right',
              }}
              aria-live="polite"
            >
              {value}
            </span>
          )}
          <button
            onClick={() => onChange(isActive ? null : cfg.min)}
            aria-pressed={isActive}
            aria-label={`${isActive ? 'Disable' : 'Enable'} ${cfg.label} override`}
            style={{
              fontSize: 11,
              padding: '2px 8px',
              color: isActive ? 'var(--sim-color)' : 'var(--text-muted)',
              background: isActive ? 'var(--sim-bg)' : 'var(--surface-2)',
              border: `1px solid ${isActive ? 'var(--sim-border)' : 'var(--border-subtle)'}`,
              borderRadius: 4,
              cursor: 'pointer',
              fontFamily: 'var(--font-sans)',
              transition: 'all 150ms ease',
            }}
          >
            {isActive ? 'Override active' : 'Override'}
          </button>
        </div>
      </div>

      <input
        id={`sim-${fieldKey}`}
        type="range"
        min={cfg.min}
        max={cfg.max}
        step={cfg.step}
        value={value ?? cfg.min}
        disabled={!isActive}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={`${cfg.label}: ${value ?? cfg.min}${cfg.unit}`}
        style={{
          width: '100%',
          accentColor: isActive ? 'var(--sim-color)' : 'var(--text-muted)',
          opacity: isActive ? 1 : 0.3,
          cursor: isActive ? 'pointer' : 'not-allowed',
        }}
      />

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: 10,
          color: 'var(--text-muted)',
          fontFamily: 'var(--font-mono)',
        }}
        aria-hidden="true"
      >
        <span>{cfg.min}{cfg.unit}</span>
        <span>{cfg.max}{cfg.unit}</span>
      </div>
    </div>
  );
}

export function SimulationPanel({
  overrides,
  isSimulated,
  onSetOverride,
  onReset,
  report,
  loading,
  error,
  onRetry,
}: SimulationPanelProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Simulation controls */}
      <section
        aria-label="Simulation controls"
        style={{
          background: 'var(--surface-1)',
          border: `1px solid ${isSimulated ? 'var(--sim-border)' : 'var(--border-subtle)'}`,
          borderRadius: 8,
          padding: '20px 24px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <div>
            <p style={{ fontSize: 11, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 4 }}>
              What-If Simulation
            </p>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.4 }}>
              Override live values to explore hypothetical scenarios. Simulated values are never
              mistaken for live NASA/NOAA data.
            </p>
          </div>
          {isSimulated && <SimBadge />}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Numeric overrides */}
          {(Object.keys(SIM_RANGES) as Array<keyof typeof SIM_RANGES>).map((key) => (
            <SliderRow
              key={key}
              fieldKey={key}
              value={overrides?.[key] as number | null | undefined}
              onChange={(v) => onSetOverride(key, v)}
            />
          ))}

          {/* Boolean overrides */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {/* CME Earth-directed */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <label
                htmlFor="sim-cme"
                style={{ fontSize: 13, color: 'var(--text-secondary)' }}
              >
                Earth-directed CME active
              </label>
              <button
                id="sim-cme"
                role="switch"
                aria-checked={overrides?.cme_earth_directed === true}
                onClick={() => onSetOverride(
                  'cme_earth_directed',
                  overrides?.cme_earth_directed === true ? null : true
                )}
                style={{
                  padding: '4px 12px',
                  fontSize: 12,
                  fontWeight: 500,
                  color: overrides?.cme_earth_directed === true ? 'var(--sim-color)' : 'var(--text-muted)',
                  background: overrides?.cme_earth_directed === true ? 'var(--sim-bg)' : 'var(--surface-2)',
                  border: `1px solid ${overrides?.cme_earth_directed === true ? 'var(--sim-border)' : 'var(--border-subtle)'}`,
                  borderRadius: 4,
                  cursor: 'pointer',
                  fontFamily: 'var(--font-sans)',
                  transition: 'all 150ms ease',
                }}
                aria-label="Toggle Earth-directed CME override"
              >
                {overrides?.cme_earth_directed === true ? 'Active' : 'Inactive'}
              </button>
            </div>

            {/* SEP event */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <label
                htmlFor="sim-sep"
                style={{ fontSize: 13, color: 'var(--text-secondary)' }}
              >
                Recent SEP event active
              </label>
              <button
                id="sim-sep"
                role="switch"
                aria-checked={overrides?.sep_event_active === true}
                onClick={() => onSetOverride(
                  'sep_event_active',
                  overrides?.sep_event_active === true ? null : true
                )}
                style={{
                  padding: '4px 12px',
                  fontSize: 12,
                  fontWeight: 500,
                  color: overrides?.sep_event_active === true ? 'var(--sim-color)' : 'var(--text-muted)',
                  background: overrides?.sep_event_active === true ? 'var(--sim-bg)' : 'var(--surface-2)',
                  border: `1px solid ${overrides?.sep_event_active === true ? 'var(--sim-border)' : 'var(--border-subtle)'}`,
                  borderRadius: 4,
                  cursor: 'pointer',
                  fontFamily: 'var(--font-sans)',
                  transition: 'all 150ms ease',
                }}
                aria-label="Toggle SEP event override"
              >
                {overrides?.sep_event_active === true ? 'Active' : 'Inactive'}
              </button>
            </div>
          </div>

          {/* Reset */}
          {isSimulated && (
            <button
              onClick={onReset}
              style={{
                padding: '8px 16px',
                fontSize: 13,
                fontWeight: 500,
                color: 'var(--text-secondary)',
                background: 'var(--surface-2)',
                border: '1px solid var(--border-medium)',
                borderRadius: 6,
                cursor: 'pointer',
                alignSelf: 'flex-start',
                fontFamily: 'var(--font-sans)',
                transition: 'opacity 150ms ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.8')}
              onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
              aria-label="Reset simulation to live values"
            >
              Reset simulation
            </button>
          )}
        </div>
      </section>

      {/* Simulated risk result */}
      {(report || loading || error) && (
        <section
          aria-label="Simulation risk result"
          style={{
            background: 'var(--surface-1)',
            border: `1px solid ${report?.is_simulated ? 'var(--sim-border)' : 'var(--border-subtle)'}`,
            borderRadius: 8,
            padding: '20px 24px',
          }}
        >
          <p style={{ fontSize: 11, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 14 }}>
            Simulated Risk Result
          </p>

          {loading && !report && <SkeletonScore />}
          {error && !report && (
            <ErrorState variant="risk-unavailable" message={error} onRetry={onRetry} compact />
          )}

          {report && (
            <div>
              {report.is_simulated && (
                <div style={{ marginBottom: 10 }}>
                  <SimBadge />
                  <p style={{ fontSize: 12, color: 'var(--sim-color)', marginTop: 6 }}>
                    This score reflects simulated override values, not live NASA/NOAA data.
                  </p>
                </div>
              )}
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16, marginBottom: 14 }}>
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 48,
                    fontWeight: 500,
                    color: getRiskColor(report.risk_level),
                    background: getRiskBgColor(report.risk_level),
                    padding: '8px 14px',
                    borderRadius: 6,
                    lineHeight: 1,
                    border: `1px solid ${getRiskBorderColor(report.risk_level)}`,
                  }}
                  aria-label={`Simulated risk score: ${Math.round(report.risk_score)}`}
                >
                  {formatScore(report.risk_score)}
                </span>
                <div>
                  <p style={{ fontSize: 14, color: 'var(--text-muted)', marginBottom: 4 }}>
                    {MISSION_LABELS[report.mission_profile]}
                  </p>
                  <RiskBadge level={report.risk_level} />
                </div>
              </div>

              {report.factors.map((f) => (
                <div key={f.label} style={{ padding: '8px 0', borderTop: '1px solid var(--border-subtle)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{f.label}</span>
                    <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                      {f.observed_value ?? '—'}
                      {f.units && <span style={{ marginLeft: 3, fontSize: 11 }}>{f.units}</span>}
                    </span>
                  </div>
                  <div style={{ height: 4, background: 'var(--surface-3)', borderRadius: 2, overflow: 'hidden' }}>
                    <div
                      style={{
                        height: '100%',
                        width: `${Math.round(f.normalized_severity * 100)}%`,
                        background: getRiskColor(report.risk_level),
                        borderRadius: 2,
                        transition: 'width 400ms ease',
                      }}
                    />
                  </div>
                </div>
              ))}

              <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 12, lineHeight: 1.5 }}>
                ⓘ {report.disclaimer}
              </p>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
