// MissionShield AI — Frontend type definitions
// Mirrors the backend Pydantic models exactly. Do not add fields not returned by the API.

// ─── Enums ──────────────────────────────────────────────────────────────────

export type DataFreshness = 'live' | 'cached' | 'stale';

export type DataSource = 'NASA DONKI' | 'NOAA SWPC' | 'NOAA GOES';

export type MissionProfile =
  | 'ROCKET_LAUNCH'
  | 'LEO_SATELLITE'
  | 'ASTRONAUT_EVA'
  | 'LUNAR_MISSION';

export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'EXTREME';

// ─── Space Weather readings ─────────────────────────────────────────────────

export interface KpReading {
  time_tag: string;
  kp_index: number;
  estimated_kp: number;
  kp_text: string | null;
  source: DataSource;
}

export interface SolarWindReading {
  time_tag: string;
  instrument_source: string | null;
  active: boolean;
  proton_speed_km_s: number | null;
  proton_density_cm3: number | null;
  proton_temperature_k: number | null;
  overall_quality: number | null;
  source: DataSource;
}

export interface MagneticFieldReading {
  time_tag: string;
  instrument_source: string | null;
  active: boolean;
  bt_nt: number | null;
  bz_gsm_nt: number | null;
  by_gsm_nt: number | null;
  bx_gsm_nt: number | null;
  overall_quality: number | null;
  source: DataSource;
}

export interface ProtonFluxReading {
  time_tag: string;
  satellite: number | null;
  flux_pfu: number | null;
  energy_channel: string;
  source: DataSource;
}

// ─── NASA DONKI events ───────────────────────────────────────────────────────

export interface LinkedEvent {
  activity_id: string;
}

export interface EnlilRun {
  model_completion_time: string | null;
  estimated_shock_arrival_time: string | null;
  estimated_duration_hours: number | null;
  kp_18: number | null;
  kp_90: number | null;
  kp_135: number | null;
  kp_180: number | null;
  is_earth_directed: boolean;
  is_earth_minor_impact: boolean;
  link: string | null;
}

export interface CMEAnalysis {
  is_most_accurate: boolean;
  time_21_5: string | null;
  latitude_deg: number | null;
  longitude_deg: number | null;
  half_angle_deg: number | null;
  speed_km_s: number | null;
  cme_type: string | null;
  enlil_runs: EnlilRun[];
  link: string | null;
}

export interface SolarFlareEvent {
  flr_id: string;
  begin_time: string;
  peak_time: string | null;
  end_time: string | null;
  class_type: string | null;
  source_location: string | null;
  active_region_num: number | null;
  linked_events: LinkedEvent[];
  link: string | null;
  source: DataSource;
}

export interface CMEEvent {
  activity_id: string;
  start_time: string;
  source_location: string | null;
  active_region_num: number | null;
  note: string | null;
  analyses: CMEAnalysis[];
  linked_events: LinkedEvent[];
  link: string | null;
  source: DataSource;
}

export interface ObservedKpPoint {
  observed_time: string;
  kp_index: number;
  kp_source: string | null;
}

export interface GeomagneticStormEvent {
  gst_id: string;
  start_time: string;
  observed_kp_readings: ObservedKpPoint[];
  linked_events: LinkedEvent[];
  link: string | null;
  source: DataSource;
}

export interface SEPEvent {
  sep_id: string;
  event_time: string;
  instruments: string[];
  linked_events: LinkedEvent[];
  link: string | null;
  source: DataSource;
}

// ─── Source status ───────────────────────────────────────────────────────────

export interface SourceStatus {
  source: DataSource;
  available: boolean;
  error: string | null;
}

// ─── Snapshot ────────────────────────────────────────────────────────────────

export interface SpaceWeatherSnapshot {
  fetched_at: string;
  freshness: DataFreshness;
  last_successful_fetch: string | null;
  source_status: SourceStatus[];
  latest_kp: KpReading | null;
  latest_solar_wind: SolarWindReading | null;
  latest_mag_field: MagneticFieldReading | null;
  latest_proton_flux_10mev: ProtonFluxReading | null;
  recent_flares: SolarFlareEvent[];
  recent_cmes: CMEEvent[];
  recent_geomagnetic_storms: GeomagneticStormEvent[];
  recent_sep_events: SEPEvent[];
}

// ─── Events response ─────────────────────────────────────────────────────────

export interface EventsResponse {
  freshness: DataFreshness;
  fetched_at: string;
  flares: SolarFlareEvent[];
  cmes: CMEEvent[];
  geomagnetic_storms: GeomagneticStormEvent[];
  sep_events: SEPEvent[];
}

// ─── Risk ────────────────────────────────────────────────────────────────────

export interface RiskFactor {
  label: string;
  normalized_severity: number;
  mission_weight: number;
  weighted_contribution: number;
  observed_value: string | null;
  units: string | null;
  source: string | null;
  explanation: string;
  reference_scale: string | null;
  data_available: boolean;
}

export interface MissionRiskReport {
  mission_profile: MissionProfile;
  risk_score: number;
  risk_level: RiskLevel;
  primary_risk_factor: string | null;
  factors: RiskFactor[];
  is_simulated: boolean;
  computed_at: string;
  data_completeness: number;
  missing_factors: string[];
  confidence: string;
  disclaimer: string;
}

// ─── Anomaly ─────────────────────────────────────────────────────────────────

export interface AnomalyFlag {
  parameter: string;
  timestamp: string;
  current_value: number;
  unit: string;
  baseline_median: number;
  baseline_dispersion: number;
  dispersion_type: string;
  z_score: number;
  threshold: number;
  direction: string;
  sample_count: number;
  is_anomalous: boolean;
  source: string;
  explanation: string;
}

// ─── AI ──────────────────────────────────────────────────────────────────────

export interface BriefRequest {
  profile: MissionProfile;
  simulation_overrides?: SimulationOverrides | null;
  force_refresh?: boolean;
}

export interface BriefResponse {
  brief: string;
  attribution: string;
  cached: boolean;
  risk_score: number;
  risk_level: string;
  is_simulated: boolean;
  disclaimer: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  profile: MissionProfile;
  message: string;
  history: ChatMessage[];
  simulation_overrides?: SimulationOverrides | null;
}

export interface ChatResponse {
  answer: string;
  attribution: string;
  is_simulated: boolean;
  disclaimer: string;
}

// ─── Simulation ──────────────────────────────────────────────────────────────

export interface SimulationOverrides {
  kp_index?: number | null;
  solar_wind_speed_km_s?: number | null;
  bz_gsm_nt?: number | null;
  cme_earth_directed?: boolean | null;
  sep_event_active?: boolean | null;
}

// ─── API error ───────────────────────────────────────────────────────────────

export interface ApiError {
  error: string;
  message: string;
  source?: string;
}
