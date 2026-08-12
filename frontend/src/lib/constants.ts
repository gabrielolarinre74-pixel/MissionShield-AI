// MissionShield AI — application-level constants

export const APP_NAME = 'MissionShield AI';
export const APP_SHORT_NAME = 'MissionShield';

// Backend polling — conservative, aligned with 5-minute backend cache TTL
export const SNAPSHOT_POLL_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

// Chat history limit (match backend max_length=16)
export const CHAT_HISTORY_MAX = 16;

// Brief client cache duration (ms) — slightly shorter than backend 300s
export const BRIEF_CLIENT_CACHE_MS = 4 * 60 * 1000; // 4 minutes

// Nav sections
export const NAV_SECTIONS = [
  { id: 'overview', label: 'Overview' },
  { id: 'space-weather', label: 'Space Weather' },
  { id: 'risk', label: 'Risk Analysis' },
  { id: 'simulation', label: 'Simulation' },
  { id: 'events', label: 'Events' },
] as const;

export type SectionId = typeof NAV_SECTIONS[number]['id'];

// Simulation override ranges (match backend validation)
export const SIM_RANGES = {
  kp_index: { min: 0.0, max: 9.0, step: 0.5, label: 'Kp Index', unit: '' },
  solar_wind_speed_km_s: { min: 200, max: 2000, step: 50, label: 'Solar Wind Speed', unit: 'km/s' },
  bz_gsm_nt: { min: -100, max: 50, step: 1, label: 'IMF Bz (GSM)', unit: 'nT' },
} as const;

// NOAA scale reference labels
export const NOAA_SCALE_DESCRIPTIONS: Record<string, string> = {
  G0: 'No geomagnetic storm',
  G1: 'Minor geomagnetic storm (Kp=5)',
  G2: 'Moderate geomagnetic storm (Kp=6)',
  G3: 'Strong geomagnetic storm (Kp=7)',
  G4: 'Severe geomagnetic storm (Kp=8)',
  G5: 'Extreme geomagnetic storm (Kp=9)',
  S0: 'No solar radiation storm',
  S1: 'Minor solar radiation storm (≥10 MeV > 10 pfu)',
  S2: 'Moderate solar radiation storm (≥10 MeV > 100 pfu)',
  S3: 'Strong solar radiation storm (≥10 MeV > 1000 pfu)',
  S4: 'Severe solar radiation storm (≥10 MeV > 10,000 pfu)',
  S5: 'Extreme solar radiation storm (≥10 MeV > 100,000 pfu)',
  R0: 'No radio blackout',
  R1: 'Minor radio blackout (M1 flare)',
  R2: 'Moderate radio blackout (M5 flare)',
  R3: 'Strong radio blackout (X1 flare)',
  R4: 'Severe radio blackout (X10 flare)',
  R5: 'Extreme radio blackout (X20 flare)',
};
