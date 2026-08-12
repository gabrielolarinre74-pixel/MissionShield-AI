'use client';

import { useState, useCallback, useRef } from 'react';
import { fetchMissionBrief, sendChatMessage } from '@/lib/api';
import type {
  MissionProfile,
  BriefResponse,
  ChatMessage,
  ChatResponse,
  SimulationOverrides,
} from '@/types';
import { CHAT_HISTORY_MAX, BRIEF_CLIENT_CACHE_MS } from '@/lib/constants';

export type AiState = 'idle' | 'loading' | 'success' | 'error';

// Brief client-side cache entry.
// Keyed by a string that encodes profile + simulation snapshot.
interface BriefCacheEntry {
  profile: MissionProfile;
  isSimulated: boolean;
  // Stable key for the simulation overrides payload so two distinct
  // simulated scenarios cannot collide.
  overridesKey: string;
  data: BriefResponse;
  timestamp: number;
}

// Module-level cache map — keyed by the full context key so each
// profile/simulation combination has its own slot.
const _briefCacheMap = new Map<string, BriefCacheEntry>();

/** Produce a stable string key for a set of overrides. */
function overridesKey(overrides: SimulationOverrides | null | undefined): string {
  if (!overrides) return '';
  const active = Object.entries(overrides)
    .filter(([, v]) => v !== null && v !== undefined)
    .sort(([a], [b]) => a.localeCompare(b));
  return active.length === 0 ? '' : JSON.stringify(active);
}

/** Full cache key: profile + simulation context. */
function briefCacheKey(profile: MissionProfile, overrides: SimulationOverrides | null | undefined): string {
  return `${profile}::${overridesKey(overrides)}`;
}

function isCacheValid(entry: BriefCacheEntry, profile: MissionProfile, oKey: string): boolean {
  return (
    entry.profile === profile &&
    entry.overridesKey === oKey &&
    Date.now() - entry.timestamp < BRIEF_CLIENT_CACHE_MS
  );
}

export interface UseMissionAIResult {
  brief: BriefResponse | null;
  briefState: AiState;
  briefError: string | null;
  /** profile this brief belongs to, so consumers can validate before rendering */
  briefProfile: MissionProfile | null;
  loadBrief: (profile: MissionProfile, overrides?: SimulationOverrides | null, forceRefresh?: boolean) => void;
  clearBrief: () => void;

  messages: ChatMessage[];
  chatState: AiState;
  chatError: string | null;
  sendMessage: (
    text: string,
    profile: MissionProfile,
    overrides?: SimulationOverrides | null
  ) => void;
  clearChat: () => void;
}

export function useMissionAI(): UseMissionAIResult {
  const [brief, setBrief] = useState<BriefResponse | null>(null);
  const [briefState, setBriefState] = useState<AiState>('idle');
  const [briefError, setBriefError] = useState<string | null>(null);
  // Track which profile the currently displayed brief belongs to.
  const [briefProfile, setBriefProfile] = useState<MissionProfile | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatState, setChatState] = useState<AiState>('idle');
  const [chatError, setChatError] = useState<string | null>(null);

  const briefAbortRef = useRef<AbortController | null>(null);
  const chatAbortRef = useRef<AbortController | null>(null);
  // Generation counter — incremented whenever a new profile/scenario is requested.
  // A response is only accepted if the generation it was started under is still current.
  const briefGenRef = useRef<number>(0);
  // Same for chat.
  const chatGenRef = useRef<number>(0);

  const clearBrief = useCallback(() => {
    briefAbortRef.current?.abort();
    setBrief(null);
    setBriefState('idle');
    setBriefError(null);
    setBriefProfile(null);
  }, []);

  const loadBrief = useCallback(
    async (
      profile: MissionProfile,
      overrides?: SimulationOverrides | null,
      forceRefresh = false
    ) => {
      const oKey = overridesKey(overrides);
      const cacheKey = briefCacheKey(profile, overrides);

      // Check client cache first (skip on force refresh).
      if (!forceRefresh) {
        const entry = _briefCacheMap.get(cacheKey);
        if (entry && isCacheValid(entry, profile, oKey)) {
          // Cancel any in-flight request — cache wins.
          briefAbortRef.current?.abort();
          setBrief(entry.data);
          setBriefState('success');
          setBriefProfile(profile);
          return;
        }
      }

      // Cancel any previous in-flight request for a different profile/scenario.
      briefAbortRef.current?.abort();
      const controller = new AbortController();
      briefAbortRef.current = controller;

      // Increment generation — this request must match the generation on response.
      briefGenRef.current += 1;
      const myGen = briefGenRef.current;

      // Clear the currently displayed brief immediately so a stale brief
      // from a different profile cannot show under the new profile.
      setBrief(null);
      setBriefProfile(null);
      setBriefState('loading');
      setBriefError(null);

      try {
        const data = await fetchMissionBrief(
          { profile, simulation_overrides: overrides ?? null, force_refresh: forceRefresh },
          controller.signal
        );
        // Ignore if: request was aborted OR another loadBrief superseded us.
        if (controller.signal.aborted || briefGenRef.current !== myGen) return;

        setBrief(data);
        setBriefState('success');
        setBriefProfile(profile);
        _briefCacheMap.set(cacheKey, { profile, isSimulated: data.is_simulated, overridesKey: oKey, data, timestamp: Date.now() });
      } catch (err: unknown) {
        if (controller.signal.aborted || briefGenRef.current !== myGen) return;
        const msg = err instanceof Error ? err.message : 'Mission Brief unavailable.';
        setBriefError(msg);
        setBriefState('error');
      }
    },
    []
  );

  const sendMessage = useCallback(
    async (
      text: string,
      profile: MissionProfile,
      overrides?: SimulationOverrides | null
    ) => {
      if (!text.trim() || chatState === 'loading') return;

      // Append user message optimistically.
      const userMsg: ChatMessage = { role: 'user', content: text.trim() };
      setMessages((prev) => [...prev, userMsg]);
      setChatState('loading');
      setChatError(null);

      chatAbortRef.current?.abort();
      const controller = new AbortController();
      chatAbortRef.current = controller;

      chatGenRef.current += 1;
      const myGen = chatGenRef.current;

      // Build bounded history (exclude the just-appended message).
      const history = messages.slice(-(CHAT_HISTORY_MAX - 2));

      try {
        const res: ChatResponse = await sendChatMessage(
          {
            profile,
            message: text.trim(),
            history,
            simulation_overrides: overrides ?? null,
          },
          controller.signal
        );
        // Ignore if aborted or superseded by a profile change.
        if (controller.signal.aborted || chatGenRef.current !== myGen) return;
        const assistantMsg: ChatMessage = { role: 'assistant', content: res.answer };
        setMessages((prev) => [...prev, assistantMsg]);
        setChatState('success');
      } catch (err: unknown) {
        if (controller.signal.aborted || chatGenRef.current !== myGen) return;
        const msg = err instanceof Error ? err.message : 'Message failed to send.';
        setChatError(msg);
        setChatState('idle');
      }
    },
    [messages, chatState]
  );

  const clearChat = useCallback(() => {
    chatAbortRef.current?.abort();
    // Increment generation so any in-flight chat response is discarded.
    chatGenRef.current += 1;
    setMessages([]);
    setChatState('idle');
    setChatError(null);
  }, []);

  return {
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
  };
}
