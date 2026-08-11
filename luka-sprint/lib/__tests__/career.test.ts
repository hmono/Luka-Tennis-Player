import { describe, expect, it } from 'vitest';
import {
  cleanTournamentTitle,
  formatRank,
  getSeasonStats,
  inferResult,
  isDoubles,
  parseRank,
} from '../career';
import type { CareerEvent } from '@/types';

// ─── parseRank ────────────────────────────────────────────────────────────────

describe('parseRank', () => {
  it('extracts integer from rank string', () => {
    expect(parseRank('#42')).toBe(42);
  });

  it('extracts large rank', () => {
    expect(parseRank('#1827')).toBe(1827);
  });

  it('returns null when no # prefix', () => {
    expect(parseRank('no rank')).toBeNull();
  });

  it('returns null for empty string', () => {
    expect(parseRank('')).toBeNull();
  });
});

// ─── formatRank ───────────────────────────────────────────────────────────────

describe('formatRank', () => {
  it('returns em dash for null', () => {
    expect(formatRank(null)).toBe('—');
  });

  it('formats with # prefix by default', () => {
    expect(formatRank(42)).toBe('#42');
  });

  it('formats with ~ prefix when approx=true', () => {
    expect(formatRank(1951, true)).toBe('~1.951');
  });

  it('applies de-DE thousand separator', () => {
    expect(formatRank(1827)).toBe('#1.827');
  });
});

// ─── inferResult ──────────────────────────────────────────────────────────────

const evt = (title: string, source_note = ''): CareerEvent => ({
  title,
  source_note,
  season: '2025',
});

describe('inferResult', () => {
  it('returns W when title contains "won"', () => {
    expect(inferResult(evt('Won vs B. Malla R1'))).toBe('W');
  });

  it('returns L when source_note contains "lost"', () => {
    expect(inferResult(evt('R2 match', 'lost to opponent'))).toBe('L');
  });

  it('is case-insensitive', () => {
    expect(inferResult(evt('WON the match'))).toBe('W');
  });

  it('returns — when neither won nor lost appears', () => {
    expect(inferResult(evt('ITF M25 Brazil'))).toBe('—');
  });
});

// ─── cleanTournamentTitle ─────────────────────────────────────────────────────

describe('cleanTournamentTitle', () => {
  it('removes round indicators like R1, R2', () => {
    expect(cleanTournamentTitle('ITF M25 Brazil R1')).toBe('ITF M25 Brazil');
  });

  it('removes Q-R prefixed rounds', () => {
    expect(cleanTournamentTitle('ITF M25 Q-R2 Brazil')).toBe('ITF M25 Brazil');
  });

  it('removes opponent after "vs"', () => {
    expect(cleanTournamentTitle('Brazil Open vs J. Smith')).toBe('Brazil Open');
  });

  it('removes the word "doubles"', () => {
    expect(cleanTournamentTitle('ITF M25 Doubles Brazil')).toBe('ITF M25 Brazil');
  });

  it('collapses multiple spaces', () => {
    expect(cleanTournamentTitle('ITF   M25   Brazil')).toBe('ITF M25 Brazil');
  });
});

// ─── isDoubles ────────────────────────────────────────────────────────────────

describe('isDoubles', () => {
  it('returns true when title contains "doubles"', () => {
    expect(isDoubles(evt('ITF M25 Doubles R1'))).toBe(true);
  });

  it('is case-insensitive', () => {
    expect(isDoubles(evt('ITF M25 DOUBLES'))).toBe(true);
  });

  it('returns false for singles events', () => {
    expect(isDoubles(evt('ITF M25 Brazil R1'))).toBe(false);
  });
});

// ─── getSeasonStats ───────────────────────────────────────────────────────────

describe('getSeasonStats', () => {
  const events: CareerEvent[] = [
    { title: 'Won R1', source_note: '', season: '2025' },
    { title: 'Won R2', source_note: '', season: '2025' },
    { title: 'Lost R3', source_note: '', season: '2025' },
    { title: 'Won Doubles R1', source_note: '', season: '2025' },
    { title: 'Won R1', source_note: '', season: '2024' },
  ];

  it('counts singles wins and losses for a season', () => {
    const stats = getSeasonStats(events, '2025');
    expect(stats.wins).toBe(2);
    expect(stats.losses).toBe(1);
  });

  it('calculates win percentage', () => {
    const stats = getSeasonStats(events, '2025');
    expect(stats.winPct).toBe('67%');
  });

  it('counts doubles separately', () => {
    const stats = getSeasonStats(events, '2025', true);
    expect(stats.wins).toBe(1);
    expect(stats.losses).toBe(0);
  });

  it('returns — for winPct when no events found', () => {
    const stats = getSeasonStats(events, '2023');
    expect(stats.winPct).toBe('—');
  });

  it('isolates by season', () => {
    const stats = getSeasonStats(events, '2024');
    expect(stats.wins).toBe(1);
  });
});
