'use client';

import type { MissionProfile } from '@/types';
import { MISSION_LABELS, MISSION_PROFILES } from '@/lib/formatters';

interface MissionSelectorProps {
  selected: MissionProfile;
  onChange: (profile: MissionProfile) => void;
}

export function MissionSelector({ selected, onChange }: MissionSelectorProps) {
  return (
    <div
      role="group"
      aria-label="Mission profile selector"
      style={{
        display: 'flex',
        gap: 2,
        background: 'var(--surface-2)',
        padding: 3,
        borderRadius: 8,
        border: '1px solid var(--border-subtle)',
        flexWrap: 'wrap',
      }}
    >
      {MISSION_PROFILES.map((profile) => {
        const isActive = profile === selected;
        return (
          <button
            key={profile}
            onClick={() => onChange(profile)}
            aria-pressed={isActive}
            aria-label={`Select mission: ${MISSION_LABELS[profile]}`}
            style={{
              padding: '6px 14px',
              fontSize: 13,
              fontWeight: isActive ? 500 : 400,
              color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
              background: isActive ? 'var(--surface-3)' : 'transparent',
              border: isActive ? '1px solid var(--border-medium)' : '1px solid transparent',
              borderRadius: 5,
              cursor: 'pointer',
              transition: 'all 150ms ease',
              fontFamily: 'var(--font-sans)',
              whiteSpace: 'nowrap',
            }}
            onMouseEnter={(e) => {
              if (!isActive) e.currentTarget.style.color = 'var(--text-primary)';
            }}
            onMouseLeave={(e) => {
              if (!isActive) e.currentTarget.style.color = 'var(--text-secondary)';
            }}
          >
            {MISSION_LABELS[profile]}
          </button>
        );
      })}
    </div>
  );
}
