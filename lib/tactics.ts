import rawTacticalData from '@/data/tactical.json';
import type {
  CoachingFramework,
  GamePattern,
  SurfaceTactics,
  TacticalBenchmark,
} from '@/types';

type TacticalJson = {
  frameworks: CoachingFramework[];
  game_patterns: GamePattern[];
  surface_tactics: SurfaceTactics[];
  target_benchmarks: TacticalBenchmark[];
};

const data = rawTacticalData as TacticalJson;

export const getTacticsFrameworks  = (): CoachingFramework[]   => data.frameworks;
export const getTacticsPatterns    = (): GamePattern[]         => data.game_patterns;
export const getTacticsSurfaces    = (): SurfaceTactics[]      => data.surface_tactics;
export const getTacticsBenchmarks  = (): TacticalBenchmark[]   => data.target_benchmarks;

export const groupPatterns = (
  patterns: GamePattern[],
): Record<string, GamePattern[]> =>
  patterns
    .filter((p) => p.pattern_group !== '0–4 Shot Rally')
    .reduce<Record<string, GamePattern[]>>((acc, p) => {
      (acc[p.pattern_group] ??= []).push(p);
      return acc;
    }, {});

export const getRallyComparison = (
  patterns: GamePattern[],
): { itf: GamePattern | undefined; challenger: GamePattern | undefined } => {
  const rally04 = patterns.filter((p) => p.pattern_group === '0–4 Shot Rally');
  return {
    itf: rally04.find((p) => p.id?.includes('itf')),
    challenger: rally04.find((p) => p.id?.includes('challenger')),
  };
};
