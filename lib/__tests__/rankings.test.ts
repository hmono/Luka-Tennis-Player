import { describe, expect, it, vi } from 'vitest';

vi.mock('@/data/rankings.json', () => ({ default: {
  schema_version: 1,
  player: { atp_id: 'B0UF', name: 'Luka Bojicic Ono' },
  // Deliberately unsorted, with a later revision and unranked doubles.
  snapshots: [
    { id: 'later', ranking_date: '2026-10-05', captured_at: '2026-10-06T12:00:00Z', source: 'itf',
      singles: { rank: 1800, points: null, career_high_rank: 1600, career_high_date: '2026-09-28' },
      doubles: { rank: null, points: null, career_high_rank: 1300, career_high_date: '2026-09-28' } },
    { id: 'earlier', ranking_date: '2026-09-28', captured_at: '2026-09-29T12:00:00Z', source: 'itf',
      singles: { rank: 2200, points: null, career_high_rank: 1827, career_high_date: '2025-12-01' },
      doubles: { rank: 1400, points: null, career_high_rank: 1400, career_high_date: '2026-09-28' } },
    { id: 'withdrawn', ranking_date: '2026-09-28', captured_at: '2026-09-29T11:00:00Z', source: 'itf',
      singles: { rank: 1600, points: null, career_high_rank: 1600, career_high_date: '2026-09-28' },
      doubles: { rank: 1300, points: null, career_high_rank: 1300, career_high_date: '2026-09-28' } },
  ],
} }));

import { getCareerHighs, getLatestRankingSnapshot, getLatestRankings, getRankingSnapshots } from '../career';

describe('ranking accessors with verified history', () => {
  it('orders history and selects the latest edition without inventing points or unranked values', () => {
    expect(getRankingSnapshots().map(item => item.id)).toEqual(['withdrawn', 'earlier', 'later']);
    expect(getLatestRankingSnapshot()?.ranking_date).toBe('2026-10-05');
    expect(getLatestRankings()?.singles.points).toBeNull();
    expect(getLatestRankings()?.doubles.rank).toBeNull();
  });

  it('preserves historical career highs when a discipline becomes unranked', () => {
    expect(getCareerHighs()).toEqual({ singles: 1800, doubles: 1400 });
  });

  it('keeps withdrawn facts and derived echoes for audit without promoting them to career highs', () => {
    expect(getRankingSnapshots()[0].singles.rank).toBe(1600);
    expect(getLatestRankings()?.singles.career_high_rank).toBe(1600);
    expect(getCareerHighs()).toEqual({ singles: 1800, doubles: 1400 });
  });
});
