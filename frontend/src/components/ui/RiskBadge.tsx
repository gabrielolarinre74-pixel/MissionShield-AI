'use client';

import type { RiskLevel } from '@/types';
import { RISK_LEVEL_LABELS, getRiskColor, getRiskBgColor, getRiskBorderColor } from '@/lib/formatters';

interface RiskBadgeProps {
  level: RiskLevel;
  size?: 'sm' | 'md';
}

export function RiskBadge({ level, size = 'md' }: RiskBadgeProps) {
  const color = getRiskColor(level);
  const bg = getRiskBgColor(level);
  const border = getRiskBorderColor(level);

  return (
    <span
      style={{
        display: 'inline-block',
        padding: size === 'sm' ? '2px 8px' : '3px 10px',
        fontSize: size === 'sm' ? 11 : 12,
        fontWeight: 600,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        color,
        background: bg,
        border: `1px solid ${border}`,
        borderRadius: 4,
      }}
      aria-label={`Risk level: ${RISK_LEVEL_LABELS[level]}`}
    >
      {RISK_LEVEL_LABELS[level]}
    </span>
  );
}
