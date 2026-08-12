'use client';

import { useState, useEffect, useCallback } from 'react';

// Shell
import { NavRail } from '@/components/shell/NavRail';
import { StatusBar } from '@/components/shell/StatusBar';

// Overview
import { MissionSelector } from '@/components/overview/MissionSelector';
import { MissionReadiness } from '@/components/overview/MissionReadiness';
import { RiskFactorBreakdown } from '@/components/overview/RiskFactorBreakdown';

// Telemetry
import { TelemetryStrip } from '@/components/telemetry/TelemetryStrip';

// Risk
import { RiskAnalysisView } from '@/components/risk/RiskAnalysisView';
import { SpaceWeatherView } from '@/components/risk/SpaceWeatherView';

// Simulation
import { SimulationPanel } from '@/components/simulation/SimulationPanel';

// Events
import { EventsPanel, AnomalyPanel } from '@/components/events/EventsPanel';

// AI
import { MissionAIPanel } from '@/components/ai/MissionAIPanel';

// Hooks
import { useSpaceWeather } from '@/hooks/useSpaceWeather';
import { useMissionRisk } from '@/hooks/useMissionRisk';
import { useMissionAI } from '@/hooks/useMissionAI';
import { useSimulation } from '@/hooks/useSimulation';

// Lib
import type { MissionProfile } from '@/types';
import type { SectionId } from '@/lib/constants';

// ─── Session storage key ─────────────────────────────────────────────────────
const PROFILE_STORAGE_KEY = 'missionshield_profile';
const SECTION_STORAGE_KEY = 'missionshield_section';

function readStoredProfile(): MissionProfile {
  if (typeof window === 'undefined') return 'ASTRONAUT_EVA';
  try {
    const v = sessionStorage.getItem(PROFILE_STORAGE_KEY);
    if (v) return v as MissionProfile;
  } catch { /* ignore */ }
  return 'ASTRONAUT_EVA';
}

function readStoredSection(): SectionId {
  if (typeof window === 'undefined') return 'overview';
  try {
    const v = sessionStorage.getItem(SECTION_STORAGE_KEY);
    if (v) return v as SectionId;
  } catch { /* ignore */ }
  return 'overview';
}

export default function MissionShieldApp() {
  const [profile, setProfile] = useState<MissionProfile>('ASTRONAUT_EVA');
  const [section, setSection] = useState<SectionId>('overview');
  const [aiPanelOpen, setAiPanelOpen] = useState(true);
  const [navCollapsed, setNavCollapsed] = useState(false);

  // Hydrate from session storage after mount (avoids SSR mismatch)
  useEffect(() => {
    setProfile(readStoredProfile());
    setSection(readStoredSection());
  }, []);

  // Simulation
  const { overrides, isSimulated, setOverride, reset: resetSimulation } = useSimulation();

  // Space weather data
  const { snapshot, state: swState, error: swError, refresh: refreshSnapshot } = useSpaceWeather();

  // Mission risk — driven by profile + overrides
  const { report, state: riskState, error: riskError, refresh: refreshRisk } = useMissionRisk(profile, overrides);

  // Mission AI
  const {
    brief,
    briefState,
    briefError,
    briefProfile,
    loadBrief,
    clearBrief,
    messages,
    chatState,
    chatError,
    sendMessage,
    clearChat,
  } = useMissionAI();

  // Handle profile change — cancel in-flight brief, clear stale brief + chat immediately.
  const handleProfileChange = useCallback(
    (newProfile: MissionProfile) => {
      if (newProfile === profile) return;
      setProfile(newProfile);
      clearBrief();   // abort in-flight request & clear displayed brief instantly
      clearChat();    // abort in-flight chat & clear history
      try { sessionStorage.setItem(PROFILE_STORAGE_KEY, newProfile); } catch { /* ignore */ }
    },
    [profile, clearBrief, clearChat]
  );

  const handleNavigate = useCallback((s: SectionId) => {
    setSection(s);
    try { sessionStorage.setItem(SECTION_STORAGE_KEY, s); } catch { /* ignore */ }
  }, []);

  // Auto-load brief once when: profile changes (brief is now idle) AND we are on
  // overview or the AI panel is open.  Simulation overrides do NOT trigger auto-load —
  // the user must explicitly request a simulated brief via the "Generate" button.
  useEffect(() => {
    if ((section === 'overview' || aiPanelOpen) && briefState === 'idle') {
      // Only load a live-mode brief automatically (no overrides).
      // Simulated briefs are always user-initiated.
      if (!isSimulated) {
        loadBrief(profile);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile, section, aiPanelOpen]);

  const isLoading = swState === 'loading';

  // ─── Responsive: collapse nav on small screens ──────────────────────────
  useEffect(() => {
    const mql = window.matchMedia('(max-width: 900px)');
    const handler = (e: MediaQueryListEvent) => setNavCollapsed(e.matches);
    setNavCollapsed(mql.matches);
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, []);

  // ─── Render section content ──────────────────────────────────────────────
  const renderContent = () => {
    switch (section) {
      case 'overview':
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Mission readiness */}
            <MissionReadiness
              report={report}
              loading={riskState === 'loading'}
              error={riskError}
              onRetry={refreshRisk}
            />

            {/* Risk factor breakdown */}
            <RiskFactorBreakdown
              report={report}
              loading={riskState === 'loading'}
              error={riskError}
              onRetry={refreshRisk}
            />

            {/* Telemetry */}
            <TelemetryStrip
              snapshot={snapshot}
              loading={swState === 'loading'}
              error={swError}
              onRetry={refreshSnapshot}
            />
          </div>
        );

      case 'space-weather':
        return (
          <SpaceWeatherView
            snapshot={snapshot}
            loading={swState === 'loading'}
            error={swError}
            onRetry={refreshSnapshot}
          />
        );

      case 'risk':
        return (
          <RiskAnalysisView
            report={report}
            loading={riskState === 'loading'}
            error={riskError}
            onRetry={refreshRisk}
          />
        );

      case 'simulation':
        return (
          <SimulationPanel
            overrides={overrides}
            isSimulated={isSimulated}
            onSetOverride={setOverride}
            onReset={resetSimulation}
            report={report}
            loading={riskState === 'loading'}
            error={riskError}
            onRetry={refreshRisk}
          />
        );

      case 'events':
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <EventsPanel />
            <AnomalyPanel />
          </div>
        );

      default:
        return null;
    }
  };

  // ─── Section title ────────────────────────────────────────────────────────
  const SECTION_TITLES: Record<SectionId, string> = {
    'overview': 'Overview',
    'space-weather': 'Space Weather',
    'risk': 'Risk Analysis',
    'simulation': 'Simulation',
    'events': 'Events',
  };

  return (
    <div
      style={{
        display: 'flex',
        height: '100vh',
        overflow: 'hidden',
        background: 'var(--background)',
      }}
    >
      {/* Left navigation rail */}
      <NavRail
        activeSection={section}
        onNavigate={handleNavigate}
        collapsed={navCollapsed}
      />

      {/* Main column */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        {/* Status bar */}
        <StatusBar
          snapshot={snapshot}
          loading={isLoading}
          isSimulated={isSimulated}
          aiPanelOpen={aiPanelOpen}
          onToggleAiPanel={() => setAiPanelOpen((v) => !v)}
          onRefresh={refreshSnapshot}
        />

        {/* Content row: workspace + AI panel */}
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          {/* Central workspace */}
          <main
            id="main-content"
            tabIndex={-1}
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '24px 28px',
              minWidth: 0,
            }}
            aria-label={`${SECTION_TITLES[section]} workspace`}
          >
            {/* Section header with mission selector */}
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                marginBottom: 20,
                gap: 16,
                flexWrap: 'wrap',
              }}
            >
              <div>
                <h1
                  style={{
                    fontSize: 18,
                    fontWeight: 600,
                    color: 'var(--text-primary)',
                    letterSpacing: '-0.01em',
                    marginBottom: 2,
                  }}
                >
                  {SECTION_TITLES[section]}
                </h1>
                <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  MissionShield AI · Space mission decision support
                </p>
              </div>

              {/* Mission selector — visible everywhere relevant */}
              <MissionSelector
                selected={profile}
                onChange={handleProfileChange}
              />
            </div>

            {/* Section content */}
            {renderContent()}
          </main>

          {/* Right AI panel */}
          {aiPanelOpen && (
            <MissionAIPanel
              profile={profile}
              overrides={overrides}
              isSimulated={isSimulated}
              brief={brief}
              briefProfile={briefProfile}
              briefState={briefState}
              briefError={briefError}
              onLoadBrief={loadBrief}
              messages={messages}
              chatState={chatState}
              chatError={chatError}
              onSendMessage={sendMessage}
              onClearChat={clearChat}
              onClose={() => setAiPanelOpen(false)}
            />
          )}
        </div>
      </div>
    </div>
  );
}
