import rawBenchmarksData from '@/data/benchmarks.json';
import rawPlayerData from '@/data/player.json';
import type { BenchmarkEntry, PlayerProfile } from '@/types';

type BenchmarksJson = { subject: string; benchmarks: BenchmarkEntry[] };

const bdata = rawBenchmarksData as unknown as BenchmarksJson;

export const getBenchmarks      = (): BenchmarkEntry[] => bdata.benchmarks;
export const getBenchmarkSubject = (): string          => bdata.subject;
export const getPlayerProfile   = (): PlayerProfile   => rawPlayerData as unknown as PlayerProfile;

export const findBenchmark = (
  benchmarks: BenchmarkEntry[],
  name: string,
): BenchmarkEntry | undefined =>
  benchmarks.find((b) => b.benchmark_name === name);

export const formatLabel = (name: string): string =>
  name
    .replace(/_/g, ' ')
    .replace(/\b[a-z]/g, (l) => l.toUpperCase())
    .replace('Itf', 'ITF')
    .replace('Atp', 'ATP');

export const extractPercentSeries = (value: string): number[] =>
  [...value.matchAll(/\d+(?:\.\d+)?/g)].map((m) => Number(m[0])).slice(0, 3);

export const padToThree = (values: number[]): [number, number, number] =>
  [...values, 0, 0, 0].slice(0, 3) as [number, number, number];

export const parseRallyDistribution = (
  text: string,
): { label: string; values: number[] }[] =>
  text
    .split(';')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [level, ...rest] = line.split(' ');
      const values = rest
        .join(' ')
        .split('|')
        .map((item) => Number(item.replace(/[^\d]/g, '')));
      return { label: level.replace(/_/g, ' ').toUpperCase(), values };
    });
