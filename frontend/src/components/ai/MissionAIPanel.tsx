'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, RefreshCw, X, Cpu, FlaskConical } from 'lucide-react';
import { SimBadge } from '@/components/ui/SimBadge';
import { SkeletonText } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import type { MissionProfile, SimulationOverrides, BriefResponse, ChatMessage } from '@/types';
import { MISSION_LABELS } from '@/lib/formatters';

interface MissionAIPanelProps {
  profile: MissionProfile;
  overrides: SimulationOverrides | null;
  isSimulated: boolean;
  brief: BriefResponse | null;
  /** which profile the displayed brief actually belongs to */
  briefProfile: MissionProfile | null;
  briefState: 'idle' | 'loading' | 'success' | 'error';
  briefError: string | null;
  onLoadBrief: (profile: MissionProfile, overrides?: SimulationOverrides | null, forceRefresh?: boolean) => void;
  messages: ChatMessage[];
  chatState: 'idle' | 'loading' | 'success' | 'error';
  chatError: string | null;
  onSendMessage: (text: string, profile: MissionProfile, overrides?: SimulationOverrides | null) => void;
  onClearChat: () => void;
  onClose: () => void;
}

const STARTER_QUESTIONS = [
  'Why did risk increase?',
  'What should I monitor?',
  'Which factor matters most?',
  'Summarize current conditions.',
];

// ---------------------------------------------------------------------------
// Brief content renderer — parses labelled sections from backend plain-text
// ---------------------------------------------------------------------------

interface BriefSection {
  label: string;
  lines: string[];
}

/**
 * Parse the backend brief string into named sections.
 * The prompt instructs Granite to produce sections labelled exactly:
 *   READINESS, PRIMARY DRIVERS, MONITOR, CONTEXT
 * Fall back to rendering the whole text as a single block if no sections found.
 */
function parseBriefSections(text: string): BriefSection[] {
  // Known section headers (lowercase matching)
  const HEADERS = ['READINESS', 'PRIMARY DRIVERS', 'MONITOR', 'CONTEXT'];
  const pattern = new RegExp(`^(${HEADERS.join('|')})\\s*:?\\s*$`, 'i');

  const sections: BriefSection[] = [];
  let current: BriefSection | null = null;

  for (const raw of text.split('\n')) {
    const line = raw.trim();
    if (!line) {
      if (current) current.lines.push('');
      continue;
    }
    if (pattern.test(line)) {
      if (current) sections.push(current);
      current = { label: line.replace(/:$/, '').trim().toUpperCase(), lines: [] };
    } else {
      if (!current) current = { label: '', lines: [] };
      // Strip any residual Markdown heading markers.
      current.lines.push(line.replace(/^#{1,4}\s*/, '').replace(/\*\*/g, '').replace(/^\*\s/, '• '));
    }
  }
  if (current) sections.push(current);

  // Filter out empty sections.
  return sections.filter((s) => s.lines.some((l) => l.trim().length > 0));
}

const SECTION_DISPLAY: Record<string, string> = {
  'READINESS': 'Readiness',
  'PRIMARY DRIVERS': 'Primary drivers',
  'MONITOR': 'Monitor',
  'CONTEXT': 'Context',
};

function BriefContent({ brief, isSimulated }: { brief: BriefResponse; isSimulated: boolean }) {
  const sections = parseBriefSections(brief.brief);
  const hasSections = sections.some((s) => s.label.length > 0);

  return (
    <div>
      {isSimulated && (
        <p style={{ fontSize: 11, color: 'var(--sim-color)', marginBottom: 8 }}>
          ⚠ Based on simulated scenario values
        </p>
      )}

      {hasSections ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {sections.map((section, idx) => (
            <div key={idx}>
              {section.label && (
                <p
                  style={{
                    fontSize: 9,
                    fontWeight: 600,
                    letterSpacing: '0.1em',
                    textTransform: 'uppercase',
                    color: 'var(--text-muted)',
                    marginBottom: 3,
                  }}
                >
                  {SECTION_DISPLAY[section.label] ?? section.label}
                </p>
              )}
              <div
                style={{
                  fontSize: 12,
                  color: 'var(--text-secondary)',
                  lineHeight: 1.6,
                }}
              >
                {section.lines
                  .filter((l) => l.trim().length > 0)
                  .map((line, li) => (
                    <p key={li} style={{ margin: '0 0 2px' }}>
                      {line}
                    </p>
                  ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        // Fallback: plain text, Markdown markers stripped
        <p
          style={{
            fontSize: 12,
            color: 'var(--text-secondary)',
            lineHeight: 1.65,
            whiteSpace: 'pre-wrap',
          }}
        >
          {brief.brief.replace(/\*\*/g, '').replace(/^#{1,4}\s*/gm, '')}
        </p>
      )}

      <p style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 10 }}>
        {brief.attribution}
        {brief.cached && ' · Cached'}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export function MissionAIPanel({
  profile,
  overrides,
  isSimulated,
  brief,
  briefProfile,
  briefState,
  briefError,
  onLoadBrief,
  messages,
  chatState,
  chatError,
  onSendMessage,
  onClearChat,
  onClose,
}: MissionAIPanelProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const isChatLoading = chatState === 'loading';

  // Auto-scroll to latest message.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || isChatLoading) return;
    setInput('');
    onSendMessage(text, profile, overrides);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // A brief is only valid to display if it belongs to the currently selected profile.
  const briefBelongsToCurrentProfile = brief !== null && briefProfile === profile;

  // In simulation mode, a brief loaded for the live scenario is stale for the current sim context.
  // We show a "generate simulated brief" prompt instead of auto-loading.
  const briefIsStaleForSimulation =
    isSimulated &&
    briefBelongsToCurrentProfile &&
    brief !== null &&
    !brief.is_simulated;

  // Determine what to render in the brief area.
  const showBriefContent = briefBelongsToCurrentProfile && !briefIsStaleForSimulation;
  const showSimBriefPrompt =
    isSimulated && !briefBelongsToCurrentProfile && briefState !== 'loading' && !briefError;
  const showSimBriefStale =
    isSimulated && briefIsStaleForSimulation && briefState !== 'loading';

  return (
    <aside
      aria-label="Mission AI panel"
      style={{
        width: 360,
        flexShrink: 0,
        background: 'var(--surface-1)',
        borderLeft: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '14px 16px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 8,
          flexShrink: 0,
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
            <Cpu size={14} style={{ color: 'var(--accent)' }} aria-hidden="true" />
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
              Mission AI
            </span>
            {isSimulated && <SimBadge size="sm" />}
          </div>
          <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {MISSION_LABELS[profile]} · Current analysis
          </p>
          <p style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
            Powered by IBM Granite via watsonx.ai
          </p>
        </div>
        <button
          onClick={onClose}
          aria-label="Close Mission AI panel"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 28,
            height: 28,
            background: 'none',
            borderTop: 'none',
            borderRight: 'none',
            borderBottom: 'none',
            borderLeft: 'none',
            cursor: 'pointer',
            color: 'var(--text-muted)',
            borderRadius: 4,
            flexShrink: 0,
          }}
        >
          <X size={14} aria-hidden="true" />
        </button>
      </div>

      {/* Scrollable content region: Mission Brief + conversation + suggestions.
          flex: 1 + min-height: 0 keeps this the only scrolling area, so the
          header and composer below are never pushed out or covered. */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
      {/* Mission Brief */}
      <div
        style={{
          padding: '14px 16px 16px',
          borderBottom: '1px solid var(--border-subtle)',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <p style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>
            Mission Brief
          </p>
          {/* Only show regenerate when not in simulation mode — in sim, use explicit generate button */}
          {!isSimulated && (
            <button
              onClick={() => onLoadBrief(profile, null, true)}
              disabled={briefState === 'loading'}
              aria-label="Regenerate Mission Brief"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                fontSize: 11,
                color: 'var(--accent)',
                background: 'none',
                borderTop: 'none',
                borderRight: 'none',
                borderBottom: 'none',
                borderLeft: 'none',
                cursor: briefState === 'loading' ? 'default' : 'pointer',
                opacity: briefState === 'loading' ? 0.5 : 1,
                fontFamily: 'var(--font-sans)',
              }}
            >
              <RefreshCw
                size={11}
                aria-hidden="true"
                style={{ animation: briefState === 'loading' ? 'spin 1s linear infinite' : 'none' }}
              />
              Regenerate
            </button>
          )}
        </div>

        {/* Loading skeleton */}
        {briefState === 'loading' && <SkeletonText lines={4} />}

        {/* Error */}
        {briefState === 'error' && (
          <ErrorState
            variant="ai-unavailable"
            message={briefError ?? undefined}
            onRetry={() => onLoadBrief(profile, isSimulated ? overrides : null)}
            compact
          />
        )}

        {/* Stale live brief in simulation — prompt to generate simulated brief */}
        {showSimBriefStale && (
          <div>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>
              Brief reflects live conditions. Generate a brief for the current simulated scenario:
            </p>
            <button
              onClick={() => onLoadBrief(profile, overrides, true)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontSize: 12,
                color: 'var(--sim-color)',
                background: 'none',
                borderTop: 'none',
                borderRight: 'none',
                borderBottom: 'none',
                borderLeft: 'none',
                cursor: 'pointer',
                padding: 0,
                fontFamily: 'var(--font-sans)',
              }}
            >
              <FlaskConical size={13} aria-hidden="true" />
              Generate simulated brief
            </button>
          </div>
        )}

        {/* No brief yet in simulation mode */}
        {showSimBriefPrompt && briefState !== 'error' && (
          <div>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>
              Simulation active. Generate a brief for the current simulated scenario:
            </p>
            <button
              onClick={() => onLoadBrief(profile, overrides, true)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontSize: 12,
                color: 'var(--sim-color)',
                background: 'none',
                borderTop: 'none',
                borderRight: 'none',
                borderBottom: 'none',
                borderLeft: 'none',
                cursor: 'pointer',
                padding: 0,
                fontFamily: 'var(--font-sans)',
              }}
            >
              <FlaskConical size={13} aria-hidden="true" />
              Generate simulated brief
            </button>
          </div>
        )}

        {/* Brief content — only render when it belongs to this profile */}
        {showBriefContent && brief && <BriefContent brief={brief} isSimulated={isSimulated} />}

        {/* Live mode idle — no brief yet */}
        {!isSimulated && briefState === 'idle' && !brief && (
          <button
            onClick={() => onLoadBrief(profile)}
            style={{
              fontSize: 12,
              color: 'var(--accent)',
              background: 'none',
              borderTop: 'none',
              borderRight: 'none',
              borderBottom: 'none',
              borderLeft: 'none',
              cursor: 'pointer',
              padding: 0,
              fontFamily: 'var(--font-sans)',
            }}
          >
            Generate Mission Brief
          </button>
        )}
      </div>

      {/* Conversation */}
      <div
        role="log"
        aria-label="Mission AI conversation"
        aria-live="polite"
        style={{
          flexShrink: 0,
          padding: '12px 16px 18px',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        {messages.length === 0 && (
          <div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>
              Ask about the current mission context:
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {STARTER_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => {
                    setInput(q);
                    inputRef.current?.focus();
                  }}
                  style={{
                    padding: '7px 12px',
                    textAlign: 'left',
                    fontSize: 12,
                    color: 'var(--text-secondary)',
                    background: 'var(--surface-2)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 6,
                    cursor: 'pointer',
                    transition: 'border-color 150ms ease',
                    fontFamily: 'var(--font-sans)',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--border-medium)')}
                  onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-subtle)')}
                  aria-label={`Ask: ${q}`}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
              gap: 2,
            }}
          >
            <p
              style={{
                fontSize: 10,
                color: 'var(--text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
              }}
            >
              {msg.role === 'user' ? 'You' : 'Mission AI'}
            </p>
            <div
              style={{
                maxWidth: '90%',
                padding: '9px 12px',
                background: msg.role === 'user' ? 'var(--accent-dim)' : 'var(--surface-2)',
                border: `1px solid ${msg.role === 'user' ? 'rgba(110,168,254,0.2)' : 'var(--border-subtle)'}`,
                borderRadius: 8,
                fontSize: 13,
                color: 'var(--text-secondary)',
                lineHeight: 1.6,
                wordBreak: 'break-word',
              }}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {/* Generating indicator */}
        {isChatLoading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
            <div style={{ display: 'flex', gap: 4 }} aria-label="Mission AI is generating a response">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  style={{
                    width: 5,
                    height: 5,
                    borderRadius: '50%',
                    background: 'var(--text-muted)',
                    animation: `skeleton-pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
                  }}
                  aria-hidden="true"
                />
              ))}
            </div>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Generating…</span>
          </div>
        )}

        {chatError && (
          <ErrorState variant="ai-unavailable" message={chatError} compact />
        )}

        <div ref={messagesEndRef} />
      </div>
      </div>

      {/* Clear chat */}
      {messages.length > 0 && (
        <div
          style={{
            padding: '0 16px 4px',
            display: 'flex',
            justifyContent: 'flex-end',
            flexShrink: 0,
          }}
        >
          <button
            onClick={onClearChat}
            style={{
              fontSize: 11,
              color: 'var(--text-muted)',
              background: 'none',
              borderTop: 'none',
              borderRight: 'none',
              borderBottom: 'none',
              borderLeft: 'none',
              cursor: 'pointer',
              fontFamily: 'var(--font-sans)',
            }}
          >
            Clear conversation
          </button>
        </div>
      )}

      {/* Input */}
      <div
        style={{
          padding: '10px 12px',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          gap: 8,
          alignItems: 'flex-end',
          flexShrink: 0,
        }}
      >
        <label htmlFor="mission-ai-input" className="sr-only">
          Ask a question about the current mission
        </label>
        <textarea
          id="mission-ai-input"
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isChatLoading}
          placeholder="Ask about this mission…"
          rows={1}
          style={{
            flex: 1,
            resize: 'none',
            background: 'var(--surface-2)',
            border: '1px solid var(--border-medium)',
            borderRadius: 6,
            padding: '8px 10px',
            fontSize: 13,
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-sans)',
            lineHeight: 1.4,
            outline: 'none',
            maxHeight: 100,
            overflowY: 'auto',
          }}
          onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
          onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border-medium)')}
          aria-label="Question input"
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || isChatLoading}
          aria-label="Send message"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 34,
            height: 34,
            borderRadius: 6,
            background: !input.trim() || isChatLoading ? 'var(--surface-3)' : 'var(--accent-dim)',
            border: `1px solid ${!input.trim() || isChatLoading ? 'var(--border-subtle)' : 'rgba(110,168,254,0.3)'}`,
            color: !input.trim() || isChatLoading ? 'var(--text-muted)' : 'var(--accent)',
            cursor: !input.trim() || isChatLoading ? 'default' : 'pointer',
            transition: 'all 150ms ease',
            flexShrink: 0,
          }}
        >
          <Send size={14} aria-hidden="true" />
        </button>
      </div>
      <p style={{ fontSize: 10, color: 'var(--text-muted)', padding: '0 12px 8px', textAlign: 'center', flexShrink: 0 }}>
        Enter to send · Shift+Enter for new line
      </p>
    </aside>
  );
}
