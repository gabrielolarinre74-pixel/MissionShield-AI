'use client';

import { RiskBadge } from '@/components/ui/RiskBadge';
import { SimBadge } from '@/components/ui/SimBadge';
import { SkeletonScore, SkeletonFactorRow } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import type { MissionRiskReport } from '@/types';
import {
  formatScore,
  formatCompleteness,
  formatUtcShort,
  MISSION_LABELS,
  getRiskColor,
  getRiskBgColor,
  formatNumber,
} from '@/lib/formatters';
import { NOAA_SCALE_DESCRIPTIONS } from '@/lib/constants';

interface RiskAnalysisViewProps {
  report: MissionRiskReport | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

export function RiskAnalysisView({ report, loading, error, onRetry }: RiskAnalysisViewProps) {
  if (loading && !report) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: '24px 28px' }}>
          <SkeletonScore />
        </div>
        <div style={{ background: 'var(--surface-1)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: '20px 24px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {[0, 1, 2, 3].map((i) => <SkeletonFactorRow key={i} />)}
          </div>
        </div>
      </div>
    );
  }

  if (error && !report) {
    return <ErrorState variant="risk-unavailable" message={error} onRetry={onRetry} />;
  }

  if (!report) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Score summary */}
      <section
        aria-label="Risk analysis summary"
        style={{
          background: 'var(--surface-1)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 8,
          padding: '24px 28px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <p style={{ fontSize: 11, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 4 }}>
              Risk Analysis
            </p>
            <p style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)' }}>
              {MISSION_LABELS[report.mission_profile]}
            </p>
          </div>
          {report.is_simulated && <SimBadge />}
        </div>

        <div style={{ display: 'flex', gap: 20, alignItems: 'flex-end', marginBottom: 20 }}>
          <div
            style={{
              background: getRiskBgColor(report.risk_level),
              borderRadius: 6,
              padding: '10px 16px',
            }}
          >
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 52,
                fontWeight: 500,
                color: getRiskColor(report.risk_level),
                lineHeight: 1,
              }}
              aria-label={`Risk score: ${Math.round(report.risk_score)} out of 100`}
            >
              {formatScore(report.risk_score)}
            </span>
            <span style={{ display: 'block', fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              / 100
            </span>
          </div>
          <div style={{ paddingBottom: 4 }}>
            <div style={{ marginBottom: 8 }}><RiskBadge level={report.risk_level} /></div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>MissionShield prototype score</p>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 14, paddingTop: 16, borderTop: '1px solid var(--border-subtle)' }}>
          {report.primary_risk_factor && (
            <div>
              <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Primary factor</p>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{report.primary_risk_factor}</p>
            </div>
          )}
          <div>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Data coverage</p>
            <p style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: report.confidence === 'degraded' ? 'var(--risk-moderate)' : 'var(--text-secondary)' }}>
              {formatCompleteness(report.data_completeness)}
              {report.confidence === 'degraded' && <span style={{ marginLeft: 6, fontSize: 11 }}>degraded</span>}
            </p>
          </div>
          <div>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Confidence</p>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              {report.confidence === 'full' ? 'Full' : 'Degraded — missing factors renormalized'}
            </p>
          </div>
          <div>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Evaluated</p>
            <p style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
              {formatUtcShort(report.computed_at)}
            </p>
          </div>
        </div>

        <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 14, lineHeight: 1.5 }}>
          ⓘ {report.disclaimer}
        </p>
      </section>

      {/* Factor table */}
      <section
        aria-label="Risk factor detail"
        style={{
          background: 'var(--surface-1)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 8,
          padding: '20px 24px',
        }}
      >
        <p style={{ fontSize: 11, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 14 }}>
          Factor Detail
        </p>

        {/* Legend */}
        <div style={{ display: 'flex', gap: 16, marginBottom: 12, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, color: 'var(--accent)' }}>NOAA G/S/R scale — Official reference</span>
          <span style={{ fontSize: 11, color: 'var(--sim-color)' }}>Weight · Score — MissionShield prototype</span>
        </div>

        <table
          style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}
          aria-label="Risk factor breakdown table"
        >
          <thead>
            <tr>
              {['Factor', 'Observed', 'Severity', 'Weight', 'Contribution', 'NOAA Scale'].map((h) => (
                <th
                  key={h}
                  scope="col"
                  style={{
                    textAlign: 'left',
                    padding: '6px 10px 10px 0',
                    fontSize: 11,
                    color: 'var(--text-muted)',
                    fontWeight: 400,
                    borderBottom: '1px solid var(--border-subtle)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {report.factors.map((f) => (
              <tr key={f.label}>
                <td style={{ padding: '10px 10px 10px 0', color: f.data_available ? 'var(--text-secondary)' : 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>
                  {f.label}
                  {!f.data_available && <span style={{ marginLeft: 6, fontSize: 10, fontStyle: 'italic' }}>no data</span>}
                </td>
                <td style={{ padding: '10px 10px 10px 0', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-subtle)', whiteSpace: 'nowrap' }}>
                  {f.observed_value ?? '—'}
                  {f.units && <span style={{ marginLeft: 3, fontSize: 10, color: 'var(--text-muted)' }}>{f.units}</span>}
                </td>
                <td style={{ padding: '10px 10px 10px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ width: 60, height: 4, background: 'var(--surface-3)', borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${Math.round(f.normalized_severity * 100)}%`, background: getRiskColor(report.risk_level), borderRadius: 2 }} />
                    </div>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                      {formatNumber(f.normalized_severity, 2)}
                    </span>
                  </div>
                </td>
                <td style={{ padding: '10px 10px 10px 0', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>
                  {formatNumber(f.mission_weight, 2)}
                </td>
                <td style={{ padding: '10px 10px 10px 0', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-subtle)' }}>
                  +{formatNumber(f.weighted_contribution, 1)}
                </td>
                <td style={{ padding: '10px 0 10px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                  {f.reference_scale ? (
                    <span
                      title={NOAA_SCALE_DESCRIPTIONS[f.reference_scale] ?? `Official NOAA ${f.reference_scale}`}
                      style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', padding: '1px 5px', background: 'var(--accent-dim)', borderRadius: 3 }}
                    >
                      {f.reference_scale}
                    </span>
                  ) : (
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
