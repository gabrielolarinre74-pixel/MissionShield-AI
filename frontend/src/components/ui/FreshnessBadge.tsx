'use client';

import type { DataFreshness } from '@/types';
import { FRESHNESS_LABELS, getFreshnessColor } from '@/lib/formatters';

interface FreshnessBadgeProps {
  freshness: DataFreshness;
  showDot?: boolean;
}

export function FreshnessBadge({ freshness, showDot = true }: FreshnessBadgeProps) {
  const color = getFreshnessColor(freshness);

  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs font-medium"
      style={{ color }}
      aria-label={`Data freshness: ${FRESHNESS_LABELS[freshness]}`}
    >
      {showDot && (
        <span
          className={freshness === 'live' ? 'live-dot' : ''}
          style={{
            display: 'inline-block',
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: color,
            flexShrink: 0,
          }}
          aria-hidden="true"
        />
      )}
      {FRESHNESS_LABELS[freshness]}
    </span>
  );
}
