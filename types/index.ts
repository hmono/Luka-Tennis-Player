// ─── Shared ───────────────────────────────────────────────────────────────────

export type Surface = 'hard_outdoor' | 'clay' | 'grass' | 'hard_indoor';
export type TournamentLevel = 'M15' | 'M25' | 'Challenger' | 'ATP';
export type MatchResult = 'W' | 'L';
export type CompetitiveLevel = 'ITF_M15' | 'ITF_M25' | 'Challenger' | 'ATP';
export type HRVStatus = 'above_baseline' | 'stable' | 'declining' | 'critical';

// ─── Career ───────────────────────────────────────────────────────────────────

/** Shape of each entry in career.json `career_events` array — confirmed from career/page.tsx */
export interface CareerEvent {
  title: string;
  source_note: string;
  season: string;
  category: 'ranking' | 'tournament' | 'milestone';
  date: string | null;
  location: string | null;
  round: string | null;
  season_end_rank?: number | null;   // ranking events only
}

/** Shape of each entry in career.json `surface_breakdown` array */
export interface SurfaceRecord {
  surface: string;
  w: number;
  l: number;
}

/** Flat benchmark row shape from benchmarks.json */
export interface BenchmarkEntry {
  benchmark_name: string;
  comparison_basis: string;
  reference: string;
  value: string;
  summary: string;
}

/** Canonical shape of data/player.json */
export interface PlayerProfile {
  name: string;
  handle: string;
  birthDate: string;        // ISO 8601
  nationality: string;
  basedIn: string;
  hand: 'right' | 'left';
  backhand: 'one-handed' | 'two-handed';
  heightCm: number;
  weightKg: number;
  coaches: string[];
  careerHighs: { atpSingles: number; atpDoubles: number };
  currentRankings: { atpSingles: number; atpDoubles: number };
  tournamentsPlayed: { itfFutures: string; challenger: number };
}

/** Actual shape of career.json — confirmed from career/page.tsx */
export interface CareerData {
  career_events: CareerEvent[];
  surface_breakdown: SurfaceRecord[];
}

// ─── Benchmarks ───────────────────────────────────────────────────────────────

export interface RallyDistribution {
  shots_0_4: number;        // 0–1 fraction
  shots_5_8: number;
  shots_9_plus: number;
}

export interface LevelBenchmark {
  level: CompetitiveLevel;
  serviceHoldRate: number;          // 0–1
  firstServePointsWon: number;      // 0–1
  avgPointsPerGame: number;
  avgGamesPerSet: number;
  serveReturnGapPp: number;         // percentage points
  rallyDistribution: RallyDistribution;
}

export interface DevelopmentTarget {
  metric: string;
  current: number | string;
  target: number | string;
  description: string;
}

export interface BenchmarksData {
  playerLevel: CompetitiveLevel;
  levels: LevelBenchmark[];
  targets: DevelopmentTarget[];
}

// ─── Tactics ──────────────────────────────────────────────────────────────────

export interface CoachingFramework {
  coach: string;
  philosophy: string;
  application: string;
}

export interface GamePattern {
  id: string;
  pattern_group: string;
  description: string;
  level?: string;
  pct_points_ending_here?: string;
  dominant_cause?: string;
}

export interface SurfaceTactics {
  surface: string;            // "Hard Court" | "Clay"
  style: string;
  primary_movement: string;
  point_construction: string;
  spin_weight: string;
  metabolic_load: string;
  tactical_priority: string;
}

export interface TacticalBenchmark {
  metric: string;
  itf_m25_current: number | string;
  challenger_target: number | string;
  atp_elite: number | string;
}

export interface TacticalData {
  frameworks: CoachingFramework[];
  patterns: GamePattern[];
  surfaces: SurfaceTactics[];
  benchmarks: TacticalBenchmark[];
}

// ─── Physiology ───────────────────────────────────────────────────────────────

export interface MetabolicZone {
  zone: 1 | 2 | 3 | 4 | 5;
  name: string;
  lactateMin: number;
  lactateMax: number | null;        // null = unbounded (Zone 5)
  whoopStrainRange: [number, number];
  description: string;
}

export interface HRVDecision {
  status: HRVStatus;
  recoveryThresholdPct: number;     // 0–100
  recommendation: string;
  maxStrain?: number;
  approvedZones: number[];
}

export interface PhysiologyLogEntry {
  date: string;                     // ISO 8601
  recoveryPct: number;
  sleepQualityPct: number;
  strain: number;
  classification: 'High readiness' | 'Moderate readiness' | 'Low readiness' | 'Rest';
  hrvStatus: HRVStatus;
}

export interface PhysiologyData {
  zones: MetabolicZone[];
  hrvDecisionMatrix: HRVDecision[];
  log: PhysiologyLogEntry[];
}

// ─── Nutrition ────────────────────────────────────────────────────────────────

export interface MacroTargets {
  proteinGPerKgLBM: [number, number];
  carbsTrainingGPerKg: [number, number];
  carbsRecoveryGPerKg: [number, number];
  fatGPerKg: [number, number];
  hydrationMlPerKg: [number, number];
}

export interface MealProtocol {
  timing: string;
  carbsGPerKg?: [number, number];
  proteinG?: [number, number];
  fatMaxG?: number;
  fluidMl?: [number, number];
  notes?: string;
}

export interface IntraTrainingProtocol {
  triggerMinutes: number;
  triggerWhoopStrain: number;
  carbsGPer45Min: [number, number];
  fluidMlPerHour: [number, number];
  sodiumMgPerHour: [number, number];
}

export interface BodyCompositionTargets {
  bodyFatPctRange: [number, number];
  leanMassGainKg: [number, number];
  maxDailyDeficitKcal: [number, number];
}

export interface NutritionData {
  macros: MacroTargets;
  preTraining: MealProtocol[];
  intraTraining: IntraTrainingProtocol;
  postTraining: MealProtocol;
  tournamentDay: MealProtocol[];
  bodyComposition: BodyCompositionTargets;
}

// ─── Physical Training ────────────────────────────────────────────────────────

export interface PeriodizationBlock {
  type: 'load' | 'adaptation';
  durationWeeks: number;
  emphasis: string;
  lactateTargetMmol?: number;
}

export interface TrainingZone {
  zone: 1 | 2 | 3 | 4;
  name: string;
  description: string;
}

export interface PhysicalTargets {
  vo2MaxMlKgMin: [number, number];
  verticalJumpCm: [number, number];
  spiderDrillMaxSeconds: number;
  avgPointsPerSet: [number, number];
}

export interface WeeklySession {
  type: string;
  sessionsPerWeek: [number, number];
  hvrCondition?: string;
  notes: string;
}

export interface PhysicalData {
  periodization: PeriodizationBlock[];
  zones: TrainingZone[];
  targets: PhysicalTargets;
  weeklyDistribution: WeeklySession[];
}
