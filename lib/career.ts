import rawCareerData from "@/data/career.json";
import rawRankingData from "@/data/rankings.json";
import type { CareerData, CareerEvent, RankingData, RankingDisciplineSnapshot, RankingSnapshot, SurfaceRecord } from "@/types";

const data = rawCareerData as CareerData;
const rankingData = rawRankingData as RankingData;

export const getCareerEvents = (): CareerEvent[] => data.career_events ?? [];
export const getSurfaceBreakdown = (): SurfaceRecord[] => data.surface_breakdown ?? [];

export const getRankingSnapshots = (): RankingSnapshot[] =>
  [...(rankingData.snapshots ?? [])].sort((left, right) =>
    `${left.ranking_date}|${left.captured_at}|${left.id}`.localeCompare(
      `${right.ranking_date}|${right.captured_at}|${right.id}`,
    ),
  );

export const getLatestRankingSnapshot = (): RankingSnapshot | null => {
  const snapshots = getRankingSnapshots();
  return snapshots.at(-1) ?? null;
};

export const getLatestRankings = (): Pick<RankingSnapshot, "singles" | "doubles"> | null => {
  const snapshot = getLatestRankingSnapshot();
  return snapshot ? { singles: snapshot.singles, doubles: snapshot.doubles } : null;
};

export const getCareerHighs = (): { singles: number | null; doubles: number | null } | null => {
  const snapshots = getRankingSnapshots();
  if (snapshots.length === 0) return null;

  const bestRank = (discipline: keyof Pick<RankingSnapshot, "singles" | "doubles">): number | null => {
    const candidates = snapshots
      .flatMap((snapshot) => {
        const ranking: RankingDisciplineSnapshot = snapshot[discipline];
        return [ranking.rank, ranking.career_high_rank];
      })
      .filter((rank): rank is number => rank !== null);
    return candidates.length > 0 ? Math.min(...candidates) : null;
  };

  return { singles: bestRank("singles"), doubles: bestRank("doubles") };
};

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
  // Word-bounded so an opponent surname like 'Wong' does not match 'won'.
  if (/\bwon\b/.test(text)) return 'W';
  if (/\blost\b/.test(text)) return 'L';
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

export const extractOpponent = (event: CareerEvent): string => {
  const vsMatch = event.title.match(/vs\s+(.+)/i);
  if (vsMatch) return vsMatch[1].trim();
  const lostMatch = event.source_note.match(/lost to (.+)/i);
  if (lostMatch) return lostMatch[1].trim();
  return '—';
};

export const phaseColor = (round: string | null | undefined): string =>
  round && /^(R\d+|1R)$/.test(round) ? 'var(--luka-blue)' : 'rgba(0,0,0,0.4)';

export const phaseWeight = (round: string | null | undefined): string =>
  round && /^(R\d+|1R)$/.test(round) ? '600' : 'normal';

/** Pure — pass the events array explicitly; no closure over module scope. */
export const findRanking = (events: CareerEvent[], pattern: RegExp): string | null =>
  events.find((e) => e.category === 'ranking' && pattern.test(e.title))?.title ?? null;

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
