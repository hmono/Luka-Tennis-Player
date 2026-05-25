import rawCareerData from '@/data/career.json';
import type { CareerEvent } from '@/types';

// Actual top-level key confirmed from career/page.tsx: `career_events`.
type CareerJson = { career_events: CareerEvent[]; [key: string]: unknown };

export const getCareerEvents = (): CareerEvent[] =>
  (rawCareerData as unknown as CareerJson).career_events ?? [];

export const parseRank = (value: string): number | null => {
  const match = value.match(/#(\d+)/);
  return match ? Number(match[1]) : null;
};

export const formatRank = (value: number | null, approx = false): string => {
  if (value === null) return '—';
  const formatted = new Intl.NumberFormat('de-DE').format(value);
  return `${approx ? '~' : '#'}${formatted}`;
};

export const inferResult = (event: CareerEvent): 'W' | 'L' | '—' => {
  const text = `${event.title} ${event.source_note}`.toLowerCase();
  if (text.includes('won')) return 'W';
  if (text.includes('lost')) return 'L';
  return '—';
};

export const cleanTournamentTitle = (title: string): string =>
  title
    .replace(/\s*(Q-R\d+|Q-\dR|\bR\d+\b)\s*/gi, ' ')
    .replace(/\s+vs\s+.*/gi, '')
    .replace(/\bdoubles\b/gi, '')
    .replace(/\s+/g, ' ')
    .trim();

export const isDoubles = (event: CareerEvent): boolean =>
  event.title.toLowerCase().includes('doubles');

/** Pure version — accepts events array as parameter instead of closing over module scope. */
export const getSeasonStats = (
  events: CareerEvent[],
  season: string,
  doubles = false,
) => {
  const ev = events.filter((e) => e.season === season && isDoubles(e) === doubles);
  const wins = ev.filter((e) => inferResult(e) === 'W').length;
  const losses = ev.filter((e) => inferResult(e) === 'L').length;
  const total = wins + losses;
  return {
    season,
    wins,
    losses,
    winPct: total > 0 ? `${Math.round((wins / total) * 100)}%` : '—',
  };
};
