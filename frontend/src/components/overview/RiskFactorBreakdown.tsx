'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, Info } from 'lucide-react';
import { SkeletonFactorRow } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import type { MissionRiskReport, RiskFactor } from '@/types';
import { NOAA_SCALE_DESCRIPTIONS } from '@/lib/constants';
import { formatNumber } from '@/lib/formatters';

interface RiskFactorBreakdownProps {
  report: MissionRiskReport | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

function FactorBar({ severity, weight }: { severity: number; weight: number }) {
  // Weighted contribution as fraction of max possible (severity * weight)
  const pct = Math.min(100, Math.round(severity * 100));
  const barColor =
    severity >= 0.75
      ? 'var(--risk-extreme)'
      : severity >= 0.5
      ? 'var(--risk-high)'
      : severity >= 0.25
      ? 'var(--risk-moderate)'
      : 'var(--risk-low)';

  return (
    <div
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Severity ${pct}%`}
      style={{
        height: 4,
        background: 'var(--surface-3)',
        borderRadius: 2,
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          height: '100%',
          width: `${pct}%`,
          background: barColor,
          borderRadius: 2,
          transition: 'width 400ms ease',
        }}
      />
      {/* Weight overlay — lighter bar showing full weight allocation */}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          height: '100%',
          width: `${Math.round(weight * 100)}%`,
          border: `1px solid rgba(255,255,255,0.1)`,
          borderRadius: 2,
          pointerEvents: 'none',
        }}
      />
    </div>
  );
}

function FactorRow({ factor }: { factor: RiskFactor }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      style={{
        borderTop: '1px solid var(--border-subtle)',
        padding: '12px 0',
      }}
    >
      {/* Main row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr auto auto auto',
          gap: 12,
          alignItems: 'center',
          marginBottom: 6,
        }}
      >
        {/* Label */}
        <div>
          <span
            style={{
              fontSize: 13,
              color: factor.data_available ? 'var(--text-secondary)' : 'var(--text-muted)',
              fontStyle: factor.data_available ? 'normal' : 'italic',
            }}
          >
            {factor.label}
          </span>
          {!factor.data_available && (
            <span style={{ marginLeft: 6, fontSize: 11, color: 'var(--text-muted)' }}>
              — no data
            </span>
          )}
        </div>

        {/* Observed value */}
        <span
          style={{
            fontSize: 12,
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-muted)',
            whiteSpace: 'nowrap',
          }}
          title={factor.source ?? undefined}
        >
          {factor.observed_value ?? '—'}
          {factor.units && (
            <span style={{ marginLeft: 3, fontSize: 11 }}>{factor.units}</span>
          )}
        </span>

        {/* Reference scale */}
        {factor.reference_scale && (
          <span
            style={{
              fontSize: 11,
              fontFamily: 'var(--font-mono)',
              color: 'var(--accent)',
              padding: '1px 5px',
              background: 'var(--accent-dim)',
              borderRadius: 3,
              whiteSpace: 'nowrap',
            }}
            title={NOAA_SCALE_DESCRIPTIONS[factor.reference_scale] ?? `NOAA ${factor.reference_scale}`}
            aria-label={`NOAA scale: ${factor.reference_scale}`}
          >
            {factor.reference_scale}
          </span>
        )}

        {/* Contribution */}
        <span
          style={{
            fontSize: 12,
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-secondary)',
            minWidth: 36,
            textAlign: 'right',
          }}
          aria-label={`Contribution: ${formatNumber(factor.weighted_contribution, 1)}`}
        >
          +{formatNumber(factor.weighted_contribution, 1)}
        </span>
      </div>

      {/* Bar */}
      <FactorBar severity={factor.normalized_severity} weight={factor.mission_weight} />

      {/* Expand toggle */}
      <button
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        aria-label={`${expanded ? 'Collapse' : 'Expand'} details for ${factor.label}`}
        style={{
          marginTop: 6,
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          fontSize: 11,
          color: 'var(--text-muted)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '2px 0',
          fontFamily: 'var(--font-sans)',
        }}
      >
        {expanded ? <ChevronUp size={12} aria-hidden="true" /> : <ChevronDown size={12} aria-hidden="true" />}
        {expanded ? 'Less' : 'Details'}
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div
          style={{
            marginTop: 8,
            padding: '10px 12px',
            background: 'var(--surface-2)',
            borderRadius: 6,
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '8px 16px',
          }}
        >
          <div>
            <p style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 2 }}>Normalized severity</p>
            <p style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
              {formatNumber(factor.normalized_severity, 3)}
            </p>
          </div>
          <div>
            <p style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 2 }}>Mission weight</p>
            <p style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
              {formatNumber(factor.mission_weight, 2)}
              <span style={{ marginLeft: 4, fontSize: 10, color: 'var(--text-muted)' }}>prototype</span>
            </p>
          </div>
          {factor.source && (
            <div>
              <p style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 2 }}>Source</p>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{factor.source}</p>
            </div>
          )}
          {factor.reference_scale && (
            <div>
              <p style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 2 }}>NOAA reference</p>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                {factor.reference_scale} —{' '}
                {NOAA_SCALE_DESCRIPTIONS[factor.reference_scale] ?? 'Official NOAA scale'}
                <span style={{ marginLeft: 4, fontSize: 10, color: 'var(--text-muted)' }}>official</span>
              </p>
            </div>
          )}
          <div style={{ gridColumn: '1 / -1' }}>
            <p style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 2 }}>Explanation</p>
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{factor.explanation}</p>
          </div>
        </div>
      )}
    </div>
  );
}

export function RiskFactorBreakdown({ report, loading, error, onRetry }: RiskFactorBreakdownProps) {
  const [showMethodology, setShowMethodology] = useState(false);

  const header = (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 4,
      }}
    >
      <p style={{ fontSize: 11, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>
        Risk Factor Breakdown
      </p>
      <button
        onClick={() => setShowMethodology((v) => !v)}
        aria-label="View risk methodology"
        aria-expanded={showMethodology}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          fontSize: 11,
          color: 'var(--accent)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontFamily: 'var(--font-sans)',
        }}
      >
        <Info size={12} aria-hidden="true" />
        Methodology
      </button>
    </div>
  );

  if (loading && !report) {
    return (
      <section
        aria-label="Risk Factor Breakdown — loading"
        style={{
          background: 'var(--surface-1)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 8,
          padding: '20px 24px',
        }}
      >
        {header}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 16 }}>
          {[0, 1, 2, 3].map((i) => <SkeletonFactorRow key={i} />)}
        </div>
      </section>
    );
  }

  if (error && !report) {
    return (
      <section
        aria-label="Risk Factor Breakdown — error"
        style={{
          background: 'var(--surface-1)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 8,
          padding: '20px 24px',
        }}
      >
        {header}
        <ErrorState variant="risk-unavailable" message={error} onRetry={onRetry} compact />
      </section>
    );
  }

  if (!report) return null;

  return (
    <section
      aria-label="Risk Factor Breakdown"
      style={{
        background: 'var(--surface-1)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 8,
        padding: '20px 24px',
      }}
    >
      {header}

      {/* Methodology panel */}
      {showMethodology && (
        <div
          style={{
            margin: '12px 0',
            padding: '14px 16px',
            background: 'var(--surface-2)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 6,
          }}
          role="region"
          aria-label="Methodology information"
        >
          <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 8 }}>
            How the score is computed
          </p>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: 6 }}>
            The 0&ndash;100 score is a <strong style={{ color: 'var(--text-secondary)' }}>MissionShield prototype heuristic</strong>, not an official NASA, NOAA, or flight-safety rating.
            Each factor&apos;s normalized severity (0&ndash;1) is derived from real NASA/NOAA measurements using
            official NOAA G/S/R scale thresholds as anchors.
          </p>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6 }}>
            Mission-specific weights reflect the relative sensitivity of each mission type to each hazard.
            These weights are <strong style={{ color: 'var(--text-secondary)' }}>prototype design decisions</strong>, not operational standards.
            When factor data is unavailable, weights are renormalized so available factors still sum correctly.
          </p>
          <div style={{ marginTop: 8, display: 'flex', gap: 16 }}>
            <span style={{ fontSize: 11, color: 'var(--accent)' }}>NOAA G/S/R thresholds — Official</span>
            <span style={{ fontSize: 11, color: 'var(--sim-color)' }}>Weights · Score — MissionShield Prototype</span>
          </div>
        </div>
      )}

      {/* Missing factors notice */}
      {report.missing_factors.length > 0 && (
        <div
          style={{
            padding: '8px 12px',
            background: 'rgba(251,146,60,0.06)',
            border: '1px solid rgba(251,146,60,0.2)',
            borderRadius: 5,
            marginBottom: 8,
            fontSize: 12,
            color: 'var(--risk-moderate)',
          }}
          role="note"
          aria-label="Missing data factors"
        >
          Missing data: {report.missing_factors.join(', ')} — weights renormalized
        </div>
      )}

      {/* Factor rows */}
      <div>
        {report.factors.map((factor) => (
          <FactorRow key={factor.label} factor={factor} />
        ))}
      </div>
    </section>
  );
}
