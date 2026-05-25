import { describe, expect, it } from 'vitest';
import {
  extractPercentSeries,
  findBenchmark,
  formatLabel,
  getBenchmarkSubject,
  getBenchmarks,
  getPlayerProfile,
  padToThree,
  parseRallyDistribution,
} from '../benchmarks';
import type { BenchmarkEntry } from '@/types';

// ─── data accessor smoke tests ────────────────────────────────────────────────

describe('getBenchmarks', () => {
  it('returns an array', () => {
    expect(Array.isArray(getBenchmarks())).toBe(true);
  });
  it('returns BenchmarkEntry objects with benchmark_name', () => {
    const first = getBenchmarks()[0];
    expect(first).toHaveProperty('benchmark_name');
  });
});

describe('getBenchmarkSubject', () => {
  it('returns a non-empty string', () => {
    const subject = getBenchmarkSubject();
    expect(typeof subject).toBe('string');
    expect(subject.length).toBeGreaterThan(0);
  });
});

describe('getPlayerProfile', () => {
  it('returns a player with required fields', () => {
    const p = getPlayerProfile();
    expect(p).toHaveProperty('name');
    expect(p).toHaveProperty('birthDate');
    expect(p).toHaveProperty('careerHighs');
    expect(typeof p.careerHighs.atpSingles).toBe('number');
  });
});

const bm = (name: string, value = ''): BenchmarkEntry => ({
  benchmark_name: name,
  comparison_basis: '',
  reference: '',
  value,
  summary: '',
});

// ─── findBenchmark ────────────────────────────────────────────────────────────

describe('findBenchmark', () => {
  const list = [bm('service_hold_rate'), bm('first_serve_points_won')];

  it('finds by exact name', () => {
    expect(findBenchmark(list, 'service_hold_rate')).toEqual(list[0]);
  });

  it('returns undefined for unknown name', () => {
    expect(findBenchmark(list, 'unknown')).toBeUndefined();
  });

  it('returns undefined for empty list', () => {
    expect(findBenchmark([], 'service_hold_rate')).toBeUndefined();
  });
});

// ─── formatLabel ──────────────────────────────────────────────────────────────

describe('formatLabel', () => {
  it('converts snake_case to Title Case', () => {
    expect(formatLabel('service_hold_rate')).toBe('Service Hold Rate');
  });

  it('uppercases ITF abbreviation', () => {
    expect(formatLabel('itf_futures_tournaments')).toBe('ITF Futures Tournaments');
  });

  it('uppercases ATP abbreviation', () => {
    expect(formatLabel('atp_first_serve_effectiveness')).toBe('ATP First Serve Effectiveness');
  });

  it('handles single word', () => {
    expect(formatLabel('challenger')).toBe('Challenger');
  });
});

// ─── extractPercentSeries ─────────────────────────────────────────────────────

describe('extractPercentSeries', () => {
  it('extracts up to three numbers', () => {
    expect(extractPercentSeries('ATP: 73% · Challenger: 65% · ITF: 60%')).toEqual([73, 65, 60]);
  });

  it('returns at most three even with more numbers present', () => {
    expect(extractPercentSeries('10 20 30 40 50')).toHaveLength(3);
  });

  it('handles decimal values', () => {
    expect(extractPercentSeries('73.5% 65.0%')).toEqual([73.5, 65.0]);
  });

  it('returns empty array for no numbers', () => {
    expect(extractPercentSeries('no numbers here')).toEqual([]);
  });
});

// ─── padToThree ───────────────────────────────────────────────────────────────

describe('padToThree', () => {
  it('pads short array with zeros', () => {
    expect(padToThree([73])).toEqual([73, 0, 0]);
  });

  it('passes through array of exactly three', () => {
    expect(padToThree([73, 65, 60])).toEqual([73, 65, 60]);
  });

  it('truncates arrays longer than three', () => {
    expect(padToThree([73, 65, 60, 55])).toEqual([73, 65, 60]);
  });

  it('pads empty array', () => {
    expect(padToThree([])).toEqual([0, 0, 0]);
  });
});

// ─── parseRallyDistribution ───────────────────────────────────────────────────

describe('parseRallyDistribution', () => {
  const input = 'ATP_Tour 62|23|15; Challenger 58|26|16; ITF_M25 62|24|14';

  it('returns one entry per semicolon segment', () => {
    expect(parseRallyDistribution(input)).toHaveLength(3);
  });

  it('uppercases and de-underscores labels', () => {
    const result = parseRallyDistribution(input);
    expect(result[0].label).toBe('ATP TOUR');
  });

  it('extracts numeric values per segment', () => {
    const result = parseRallyDistribution(input);
    expect(result[1].values).toEqual([58, 26, 16]);
  });

  it('ignores empty segments', () => {
    expect(parseRallyDistribution('  ;  ;  ')).toHaveLength(0);
  });
});
