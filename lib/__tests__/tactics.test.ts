import { describe, expect, it } from 'vitest';
import { getRallyComparison, groupPatterns } from '../tactics';
import type { GamePattern } from '@/types';

const p = (id: string, group: string): GamePattern => ({
  id,
  pattern_group: group,
  description: `desc for ${id}`,
});

const fixtures: GamePattern[] = [
  p('serve_wide', 'Serve+1'),
  p('serve_t', 'Serve+1'),
  p('return_deep', 'Return Pressure'),
  p('itf_rally_04', '0–4 Shot Rally'),
  p('challenger_rally_04', '0–4 Shot Rally'),
];

// ─── groupPatterns ────────────────────────────────────────────────────────────

describe('groupPatterns', () => {
  it('excludes 0–4 Shot Rally group', () => {
    const groups = groupPatterns(fixtures);
    expect('0–4 Shot Rally' in groups).toBe(false);
  });

  it('groups by pattern_group key', () => {
    const groups = groupPatterns(fixtures);
    expect(groups['Serve+1']).toHaveLength(2);
    expect(groups['Return Pressure']).toHaveLength(1);
  });

  it('returns empty object for empty input', () => {
    expect(groupPatterns([])).toEqual({});
  });

  it('returns empty object when all patterns are 0–4 Shot Rally', () => {
    const only04 = [p('a', '0–4 Shot Rally'), p('b', '0–4 Shot Rally')];
    expect(groupPatterns(only04)).toEqual({});
  });
});

// ─── getRallyComparison ───────────────────────────────────────────────────────

describe('getRallyComparison', () => {
  it('finds itf pattern by id substring', () => {
    const { itf } = getRallyComparison(fixtures);
    expect(itf?.id).toBe('itf_rally_04');
  });

  it('finds challenger pattern by id substring', () => {
    const { challenger } = getRallyComparison(fixtures);
    expect(challenger?.id).toBe('challenger_rally_04');
  });

  it('returns undefined for itf when no matching id exists', () => {
    const { itf } = getRallyComparison([p('other_rally', '0–4 Shot Rally')]);
    expect(itf).toBeUndefined();
  });

  it('returns undefined for both when no 0–4 Shot Rally patterns exist', () => {
    const { itf, challenger } = getRallyComparison([p('serve_wide', 'Serve+1')]);
    expect(itf).toBeUndefined();
    expect(challenger).toBeUndefined();
  });
});
