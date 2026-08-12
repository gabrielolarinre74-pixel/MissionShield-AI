'use client';

// Skeleton shapes used while data is loading

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  className?: string;
}

export function Skeleton({ width = '100%', height = 16, className = '' }: SkeletonProps) {
  return (
    <span
      className={`skeleton ${className}`}
      style={{ display: 'block', width, height }}
      aria-hidden="true"
    />
  );
}

export function SkeletonText({ lines = 3 }: { lines?: number }) {
  const widths = ['100%', '88%', '72%', '94%', '80%', '66%'];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }} aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} width={widths[i % widths.length]} height={14} />
      ))}
    </div>
  );
}

export function SkeletonScore() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }} aria-hidden="true">
      <Skeleton width={64} height={56} />
      <Skeleton width={80} height={20} />
      <Skeleton width={200} height={14} />
      <Skeleton width={160} height={14} />
    </div>
  );
}

export function SkeletonFactorRow() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }} aria-hidden="true">
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <Skeleton width={140} height={13} />
        <Skeleton width={40} height={13} />
      </div>
      <Skeleton width="100%" height={4} />
    </div>
  );
}

export function SkeletonTelemetry() {
  return (
    <div
      style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 1 }}
      aria-hidden="true"
    >
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <Skeleton width={60} height={11} />
          <Skeleton width={48} height={20} />
          <Skeleton width={36} height={11} />
        </div>
      ))}
    </div>
  );
}
