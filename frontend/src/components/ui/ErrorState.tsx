'use client';

import { AlertTriangle, RefreshCw, WifiOff, Database, Cpu } from 'lucide-react';

type ErrorVariant =
  | 'backend-unreachable'
  | 'data-unavailable'
  | 'partial-data'
  | 'risk-unavailable'
  | 'ai-unavailable'
  | 'generic';

interface ErrorStateProps {
  variant?: ErrorVariant;
  message?: string;
  onRetry?: () => void;
  compact?: boolean;
}

const VARIANT_CONFIG: Record<
  ErrorVariant,
  { icon: React.ElementType; title: string; default: string }
> = {
  'backend-unreachable': {
    icon: WifiOff,
    title: 'Backend Unreachable',
    default:
      'The MissionShield API is not responding. Ensure the backend is running at the configured address.',
  },
  'data-unavailable': {
    icon: Database,
    title: 'Data Unavailable',
    default:
      'Space-weather data sources are currently unavailable. The system will retry automatically.',
  },
  'partial-data': {
    icon: AlertTriangle,
    title: 'Partial Data',
    default:
      'Some data sources returned incomplete data. Displayed values may be limited.',
  },
  'risk-unavailable': {
    icon: AlertTriangle,
    title: 'Risk Computation Unavailable',
    default:
      'Mission risk could not be computed. Space-weather data may be unavailable.',
  },
  'ai-unavailable': {
    icon: Cpu,
    title: 'IBM Granite Unavailable',
    default:
      'The AI service is temporarily unavailable. Deterministic risk analysis remains operational.',
  },
  generic: {
    icon: AlertTriangle,
    title: 'Something Went Wrong',
    default: 'An unexpected error occurred. Please try again.',
  },
};

export function ErrorState({
  variant = 'generic',
  message,
  onRetry,
  compact = false,
}: ErrorStateProps) {
  const config = VARIANT_CONFIG[variant];
  const Icon = config.icon;
  const displayMessage = message ?? config.default;

  if (compact) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 10,
          padding: '12px 14px',
          background: 'rgba(239,68,68,0.06)',
          border: '1px solid rgba(239,68,68,0.2)',
          borderRadius: 6,
        }}
        role="alert"
      >
        <Icon size={14} style={{ color: 'var(--risk-extreme)', flexShrink: 0, marginTop: 1 }} aria-hidden="true" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{displayMessage}</p>
        </div>
        {onRetry && (
          <button
            onClick={onRetry}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              fontSize: 12,
              color: 'var(--accent)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              flexShrink: 0,
              padding: '0 2px',
            }}
            aria-label="Retry"
          >
            <RefreshCw size={12} aria-hidden="true" />
            Retry
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 12,
        padding: '40px 24px',
        textAlign: 'center',
      }}
      role="alert"
    >
      <Icon
        size={24}
        style={{ color: 'var(--text-muted)' }}
        aria-hidden="true"
      />
      <div>
        <p
          style={{
            fontSize: 14,
            fontWeight: 500,
            color: 'var(--text-secondary)',
            marginBottom: 4,
          }}
        >
          {config.title}
        </p>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 360 }}>
          {displayMessage}
        </p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '7px 16px',
            fontSize: 13,
            fontWeight: 500,
            color: 'var(--accent)',
            background: 'var(--accent-dim)',
            border: '1px solid rgba(110,168,254,0.25)',
            borderRadius: 6,
            cursor: 'pointer',
            transition: 'opacity 150ms ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.8')}
          onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
        >
          <RefreshCw size={13} aria-hidden="true" />
          Try Again
        </button>
      )}
    </div>
  );
}
