'use client';

import { LayoutDashboard, Cloud, ShieldAlert, FlaskConical, ListOrdered } from 'lucide-react';
import type { SectionId } from '@/lib/constants';
import { NAV_SECTIONS } from '@/lib/constants';

const ICONS: Record<SectionId, React.ElementType> = {
  'overview': LayoutDashboard,
  'space-weather': Cloud,
  'risk': ShieldAlert,
  'simulation': FlaskConical,
  'events': ListOrdered,
};

interface NavRailProps {
  activeSection: SectionId;
  onNavigate: (section: SectionId) => void;
  collapsed?: boolean;
}

export function NavRail({ activeSection, onNavigate, collapsed = false }: NavRailProps) {
  return (
    <nav
      aria-label="Main navigation"
      style={{
        width: collapsed ? 56 : 220,
        flexShrink: 0,
        background: 'var(--surface-1)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 200ms ease',
        overflow: 'hidden',
      }}
    >
      {/* Identity */}
      <div
        style={{
          padding: collapsed ? '18px 0' : '18px 20px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-start',
          gap: 10,
          minHeight: 56,
        }}
      >
        {/* Shield icon mark */}
        <svg
          width="22"
          height="22"
          viewBox="0 0 22 22"
          fill="none"
          aria-hidden="true"
          style={{ flexShrink: 0 }}
        >
          <path
            d="M11 2L3 5.5V11c0 4.418 3.36 8.11 8 9 4.64-.89 8-4.582 8-9V5.5L11 2Z"
            fill="none"
            stroke="var(--accent)"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          <path
            d="M8 11l2 2 4-4"
            stroke="var(--accent)"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        {!collapsed && (
          <div>
            <span
              style={{
                display: 'block',
                fontSize: 14,
                fontWeight: 600,
                color: 'var(--text-primary)',
                letterSpacing: '-0.01em',
                lineHeight: 1.2,
              }}
            >
              MissionShield
            </span>
            <span
              style={{
                display: 'block',
                fontSize: 10,
                color: 'var(--text-muted)',
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
              }}
            >
              AI
            </span>
          </div>
        )}
      </div>

      {/* Nav items */}
      <ul
        role="list"
        style={{
          listStyle: 'none',
          padding: '8px 0',
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          gap: 1,
        }}
      >
        {NAV_SECTIONS.map((section) => {
          const Icon = ICONS[section.id];
          const isActive = activeSection === section.id;
          return (
            <li key={section.id}>
              <button
                onClick={() => onNavigate(section.id)}
                aria-current={isActive ? 'page' : undefined}
                title={collapsed ? section.label : undefined}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  width: '100%',
                  padding: collapsed ? '9px 0' : '9px 16px',
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  background: isActive ? 'rgba(110,168,254,0.1)' : 'transparent',
                  borderTop: 'none',
                  borderRight: 'none',
                  borderBottom: 'none',
                  borderLeft: isActive ? '2px solid var(--accent)' : '2px solid transparent',
                  color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                  fontSize: 13,
                  fontWeight: isActive ? 500 : 400,
                  cursor: 'pointer',
                  borderRadius: 0,
                  transition: 'color 150ms ease, background 150ms ease',
                  whiteSpace: 'nowrap',
                  fontFamily: 'var(--font-sans)',
                }}
                onMouseEnter={(e) => {
                  if (!isActive) e.currentTarget.style.color = 'var(--text-primary)';
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.currentTarget.style.color = 'var(--text-secondary)';
                }}
              >
                <Icon size={16} aria-hidden="true" style={{ flexShrink: 0 }} />
                {!collapsed && section.label}
              </button>
            </li>
          );
        })}
      </ul>

      {/* Footer */}
      {!collapsed && (
        <div
          style={{
            padding: '12px 16px',
            borderTop: '1px solid var(--border-subtle)',
            fontSize: 10,
            color: 'var(--text-muted)',
            lineHeight: 1.4,
          }}
        >
          Data: NASA DONKI · NOAA SWPC
          <br />
          AI: IBM Granite via watsonx.ai
        </div>
      )}
    </nav>
  );
}
