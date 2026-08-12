'use client';

interface SimBadgeProps {
  size?: 'sm' | 'md';
}

export function SimBadge({ size = 'md' }: SimBadgeProps) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        padding: size === 'sm' ? '2px 8px' : '3px 10px',
        fontSize: size === 'sm' ? 11 : 12,
        fontWeight: 600,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        color: 'var(--sim-color)',
        background: 'var(--sim-bg)',
        border: '1px solid var(--sim-border)',
        borderRadius: 4,
      }}
      role="status"
      aria-label="Simulation active — values are not live NASA/NOAA data"
    >
      <span
        style={{
          display: 'inline-block',
          width: 5,
          height: 5,
          borderRadius: '50%',
          background: 'var(--sim-color)',
        }}
        aria-hidden="true"
      />
      Simulation
    </span>
  );
}
