'use client';

import { RiskBadge } from '@/components/ui/RiskBadge';
import { SimBadge } from '@/components/ui/SimBadge';
import { SkeletonScore } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import type { MissionRiskReport } from '@/types';
import {
  formatScore,
  formatCompleteness,
  formatUtcShort,
  getRiskColor,
  getRiskBorderColor,
  getRiskBgColor,
  MISSION_LABELS,
  getRiskInterpretation,
} from '@/lib/formatters';

interface MissionReadinessProps {
  report: MissionRiskReport | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

export function MissionReadiness({ report, loading, error, onRetry }: MissionReadinessProps) {
  if (loading && !report) {
    return (
      <section
        aria-label="Mission Readiness — loading"
        style={{
          background: 'var(--surface-1)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 8,
          padding: '24px 28px',
        }}
      >
        <p style={{ fontSize: 11, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 16 }}>
          Mission Readiness
        </p>
        <SkeletonScore />
      </section>
    );
  }

  if (error && !report) {
    return (
      <section
        aria-label="Mission Readiness — error"
        style={{
          background: 'var(--surface-1)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 8,
          padding: '24px 28px',
        }}
      >
        <p style={{ fontSize: 11, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 16 }}>
          Mission Readiness
        </p>
        <ErrorState variant="risk-unavailable" message={error} onRetry={onRetry} compact />
      </section>
    );
  }

  if (!report) return null;

  const borderColor = getRiskBorderColor(report.risk_level);
  const scoreColor = getRiskColor(report.risk_level);
  const bgColor = getRiskBgColor(report.risk_level);

  return (
    <section
      aria-label="Mission Readiness"
      style={{
        background: 'var(--surface-1)',
        border: '1px solid var(--border-subtle)',
        borderLeft: `3px solid ${borderColor}`,
        borderRadius: 8,
        padding: '24px 28px',
        position: 'relative',
      }}
    >
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20, gap: 12 }}>
        <div>
          <p style={{ fontSize: 11, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 4 }}>
            Mission Readiness
          </p>
          <p style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)' }}>
            {MISSION_LABELS[report.mission_profile]}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {report.is_simulated && <SimBadge size="sm" />}
        </div>
      </div>

      {/* Score + level */}
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 20, marginBottom: 16 }}>
        <div
          aria-label={`Risk score: ${Math.round(report.risk_score)} out of 100`}
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-start',
            background: bgColor,
            borderRadius: 6,
            padding: '10px 16px',
          }}
        >
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 52,
              fontWeight: 500,
              lineHeight: 1,
              color: scoreColor,
              letterSpacing: '-0.02em',
            }}
          >
            {formatScore(report.risk_score)}
          </span>
          <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', marginTop: 2 }}>
            / 100
          </span>
        </div>

        <div style={{ paddingBottom: 4 }}>
          <div style={{ marginBottom: 8 }}>
            <RiskBadge level={report.risk_level} />
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', maxWidth: 280, lineHeight: 1.5 }}>
            {getRiskInterpretation(report.risk_level)}
          </p>
        </div>
      </div>

      {/* Meta row */}
      <div
        style={{
          display: 'flex',
          gap: 24,
          paddingTop: 16,
          borderTop: '1px solid var(--border-subtle)',
          flexWrap: 'wrap',
        }}
      >
        {report.primary_risk_factor && (
          <div>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Primary contributor</p>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{report.primary_risk_factor}</p>
          </div>
        )}
        <div>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Data coverage</p>
          <p
            style={{
              fontSize: 13,
              color: report.confidence === 'degraded' ? 'var(--risk-moderate)' : 'var(--text-secondary)',
              fontFamily: 'var(--font-mono)',
            }}
            aria-label={`Data coverage: ${formatCompleteness(report.data_completeness)}${report.confidence === 'degraded' ? ' — degraded confidence' : ''}`}
          >
            {formatCompleteness(report.data_completeness)}
            {report.confidence === 'degraded' && (
              <span style={{ marginLeft: 6, fontSize: 11 }}>degraded</span>
            )}
          </p>
        </div>
        <div>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Last evaluated</p>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
            {formatUtcShort(report.computed_at)}
          </p>
        </div>
      </div>

      {/* Disclaimer */}
      <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 14, lineHeight: 1.5 }}>
        ⓘ {report.disclaimer}
      </p>
    </section>
  );
}
