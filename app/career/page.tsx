import Link from "next/link";

import careerData from "@/data/career.json";

// ── types ─────────────────────────────────────────────────────

type CareerEvent = (typeof careerData)["career_events"][number];
type RankingEvent = CareerEvent & { season_end_rank?: number | null };
type SurfaceRow = { surface: string; w: number; l: number };

// ── base helpers ──────────────────────────────────────────────

const parseRank = (value: string) => {
  const match = value.match(/#(\d+)/);
  return match ? Number(match[1]) : null;
};

const formatRank = (value: number | null, approx = false) => {
  if (value === null) return "—";
  const formatted = new Intl.NumberFormat("de-DE").format(value);
  return `${approx ? "~" : "#"}${formatted}`;
};

const findRanking = (pattern: RegExp) =>
  (careerData.career_events as RankingEvent[]).find(
    (e) => e.category === "ranking" && pattern.test(e.title),
  )?.title ?? null;

const inferResult = (event: CareerEvent) => {
  const text = `${event.title} ${event.source_note}`.toLowerCase();
  if (text.includes("won")) return "W";
  if (text.includes("lost")) return "L";
  return "—";
};

const isDoubles = (event: CareerEvent) => /doubles/i.test(event.title);

// ── S04 helpers ───────────────────────────────────────────────

const extractOpponent = (event: CareerEvent): string => {
  const vsMatch = event.title.match(/vs\s+(.+)/i);
  if (vsMatch) return vsMatch[1].trim();
  const lostMatch = event.source_note.match(/lost to (.+)/i);
  if (lostMatch) return lostMatch[1].trim();
  return "—";
};

const cleanTournamentTitle = (title: string): string =>
  title
    .replace(/\s*(Q-R\d+|Q-\dR|\bR\d+\b)\s*/gi, " ")
    .replace(/\s+vs\s+.*/gi, "")
    .replace(/\bdoubles\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();

const phaseClass = (round: string | null | undefined): string => {
  if (!round) return "text-black/40";
  if (/^(R\d+|1R)$/.test(round)) return "font-semibold text-luka-blue";
  if (/^Q-/.test(round)) return "text-black/40";
  if (round === "D") return "text-black/40 italic";
  return "text-black/40";
};

// ── data slices ───────────────────────────────────────────────

const careerEvents = careerData.career_events as CareerEvent[];
const rankingEvents = careerEvents.filter((e) => e.category === "ranking") as RankingEvent[];
const tournamentEvents = careerEvents.filter((e) => e.category === "tournament");
const milestoneEvents = careerEvents.filter((e) => e.category === "milestone");

const getSeasonStats = (season: string, doubles = false) => {
  const ev = tournamentEvents.filter(
    (e) => e.season === season && isDoubles(e) === doubles,
  );
  const wins = ev.filter((e) => inferResult(e) === "W").length;
  const losses = ev.filter((e) => inferResult(e) === "L").length;
  const total = wins + losses;
  return { season, wins, losses, winPct: total > 0 ? `${Math.round((wins / total) * 100)}%` : "—" };
};

const seasons = ["2021", "2022", "2023", "2024", "2025", "2026"];
const singlesBySeason = seasons.map((s) => getSeasonStats(s, false));
const doublesBySeason = seasons
  .map((s) => getSeasonStats(s, true))
  .filter((r) => r.wins + r.losses > 0);

const totalSingles = singlesBySeason.reduce(
  (acc, r) => ({ wins: acc.wins + r.wins, losses: acc.losses + r.losses }),
  { wins: 0, losses: 0 },
);
const totalDoubles = doublesBySeason.reduce(
  (acc, r) => ({ wins: acc.wins + r.wins, losses: acc.losses + r.losses }),
  { wins: 0, losses: 0 },
);

// S02 — ranking rows with season_end_rank + career high flag
const itfSeasonRows = rankingEvents
  .filter((e) => /ITF/i.test(e.title))
  .map((e) => ({
    season: e.season,
    peak: formatRank(parseRank(e.title)),
    isCareerHigh: /career high/i.test(e.title),
    seasonEnd: e.season_end_rank != null ? formatRank(e.season_end_rank) : "—",
    note: e.source_note,
  }));

const atpSeasonRows = rankingEvents
  .filter((e) => /ATP/i.test(e.title))
  .map((e) => ({
    season: e.season,
    peak: /current/i.test(e.title)
      ? formatRank(parseRank(e.title), true)
      : formatRank(parseRank(e.title)),
    isCareerHigh: /career high/i.test(e.title),
    seasonEnd: e.season_end_rank != null ? formatRank(e.season_end_rank) : "—",
    note: e.source_note,
  }));

// stat strip
const atpSinglesCareerHigh = parseRank(findRanking(/ATP singles career high/i) ?? "");
const atpDoublesCareerHigh = parseRank(findRanking(/ATP doubles career high/i) ?? "");
const atpSinglesCurrent = parseRank(findRanking(/ATP singles current/i) ?? "");

const challengerAppearances = tournamentEvents.filter((e) =>
  /Challenger/i.test(e.title),
).length;

const bestMainDraw =
  milestoneEvents
    .find((e) => /career-best main draw/i.test(e.title))
    ?.title.match(/R\d+/i)?.[0] ?? "R16";

// S03 — surface breakdown
const surfaceBreakdown = careerData.surface_breakdown as SurfaceRow[];
const surfaceColorMap: Record<string, string> = {
  "Hard (outdoor)": "var(--luka-blue)",
  "Hard (indoor)": "var(--luka-blue-light)",
  Clay: "#f5a623",
  Grass: "#1cc8a0",
};
const surfaceRows = surfaceBreakdown
  .filter((s) => s.w + s.l > 0)
  .map((s) => ({
    ...s,
    winPct: Math.round((s.w / (s.w + s.l)) * 100),
    color: surfaceColorMap[s.surface] ?? "#888",
  }));

// S04 — tournament timeline
const latestMilestones = [...milestoneEvents]
  .sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""))
  .slice(0, 3);

const notableEvents = tournamentEvents.filter(
  (e) => /Challenger/i.test(e.title) || /R16/i.test(e.title) || /\b1R\b/i.test(e.title),
);

const seasonGroups = [...new Set(tournamentEvents.map((e) => e.season))]
  .sort((a, b) => Number(b) - Number(a))
  .map((season) => ({
    season,
    summary: getSeasonStats(season, false),
    events: tournamentEvents
      .filter((e) => e.season === season)
      .sort((a, b) => (b.date ?? "").localeCompare(a.date ?? "")),
  }));

// ── shared styles ─────────────────────────────────────────────

const tableClass =
  "w-full min-w-full text-sm [&_th]:px-4 [&_th]:py-3 [&_th]:text-left [&_th]:text-[10px] [&_th]:uppercase [&_th]:tracking-[0.16em] [&_td]:px-4 [&_td]:py-3";

// ─────────────────────────────────────────────────────────────

export default function CareerPage() {
  return (
    <div className="section-block">
      <div className="shell">

        {/* HERO */}
        <section className="hero-panel">
          <div className="relative z-10">
            <Link href="/" className="mb-5 inline-flex text-xs uppercase tracking-[0.18em] text-white/50">
              ← Dashboard
            </Link>
            <div className="hero-tag">
              @luka.ono_ · Professional Tennis Player · Campinas, Brazil · Born Jan 28 2005
            </div>
            <h1 className="max-w-3xl text-5xl font-semibold leading-none tracking-tight sm:text-7xl">
              CAREER &
              <br />
              RANKING
            </h1>
            <div className="hero-sub">
              TOURNAMENT RESULTS · RANKING HISTORY · CAREER TRAJECTORY · 2021–2026
            </div>
          </div>
        </section>

        {/* STAT STRIP */}
        <section className="stat-strip">
          <div className="stat-item">
            <span className="stat-value">{formatRank(atpSinglesCareerHigh)}</span>
            <span className="stat-label">ATP Singles Career High</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">{formatRank(atpDoublesCareerHigh)}</span>
            <span className="stat-label">ATP Doubles Career High</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">
              {totalSingles.wins}W · {totalSingles.losses}L
            </span>
            <span className="stat-label">Career Singles Record</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">
              {totalDoubles.wins}W · {totalDoubles.losses}L
            </span>
            <span className="stat-label">Career Doubles Record</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">{challengerAppearances}</span>
            <span className="stat-label">Challenger Appearances</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">{bestMainDraw}</span>
            <span className="stat-label">Best Main Draw Round</span>
          </div>
        </section>

        {/* LEVEL STRIP */}
        <section className="level-strip">
          <span className="level-label">CAREER PATH:</span>
          <div className="level-item font-semibold">
            <span className="level-dot" style={{ background: "#f5a623", boxShadow: "0 0 0 2px rgba(245,166,35,0.35)" }} />
            <span className="text-[#f5a623]">ITF M25/M15</span>
            <span className="text-[10px] text-white/35">Current · {formatRank(atpSinglesCurrent, true)}</span>
          </div>
          <span className="text-white/20">→</span>
          <div className="level-item">
            <span className="level-dot" style={{ background: "#1cc8a0" }} />
            <span className="text-[#1cc8a0]">Challenger</span>
            <span className="text-[10px] text-white/35">Target · rank ~100–500</span>
          </div>
          <span className="text-white/20">→</span>
          <div className="level-item">
            <span className="level-dot" style={{ background: "var(--luka-blue)" }} />
            <span className="text-luka-blue">ATP Tour</span>
            <span className="text-[10px] text-white/35">Long-range · top 250+</span>
          </div>
          <span className="level-note">Coaches: Ricardo Siggia · Alexandre Bonatto</span>
        </section>

        {/* S01 — CAREER SUMMARY */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">01</span>
            <span className="section-title">Career Summary</span>
            <span className="section-badge">2021–2026</span>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="surface-card overflow-hidden">
              <div className="border-b border-black/6 px-4 py-3 text-[10px] uppercase tracking-[0.16em] text-black/45">
                Singles — W/L por ano
              </div>
              <div className="overflow-x-auto">
                <table className={tableClass}>
                  <thead className="bg-black/[0.03] text-black/45">
                    <tr>
                      <th>Ano</th>
                      <th>W</th>
                      <th>L</th>
                      <th>Win%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {singlesBySeason.map((row) => (
                      <tr key={row.season} className="border-t border-black/6">
                        <td>{row.season}</td>
                        <td>{row.wins}</td>
                        <td>{row.losses}</td>
                        <td>{row.winPct}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="surface-card overflow-hidden">
              <div className="border-b border-black/6 px-4 py-3 text-[10px] uppercase tracking-[0.16em] text-black/45">
                Doubles — W/L por ano
              </div>
              <div className="overflow-x-auto">
                <table className={tableClass}>
                  <thead className="bg-black/[0.03] text-black/45">
                    <tr>
                      <th>Ano</th>
                      <th>W</th>
                      <th>L</th>
                      <th>Win%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {doublesBySeason.map((row) => (
                      <tr key={row.season} className="border-t border-black/6">
                        <td>{row.season}</td>
                        <td>{row.wins}</td>
                        <td>{row.losses}</td>
                        <td>{row.winPct}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        {/* S02 — RANKING HISTORY */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">02</span>
            <span className="section-title">Ranking History</span>
            <span className="section-badge">ITF + ATP</span>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="surface-card overflow-hidden">
              <div className="border-b border-black/6 px-4 py-3 text-[10px] uppercase tracking-[0.16em] text-black/45">
                Rankings ITF
              </div>
              <div className="overflow-x-auto">
                <table className={tableClass}>
                  <thead className="bg-black/[0.03] text-black/45">
                    <tr>
                      <th>Temporada</th>
                      <th>Pico</th>
                      <th>Fim de temp.</th>
                      <th>Notas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {itfSeasonRows.map((row) => (
                      <tr key={`${row.season}-itf`} className="border-t border-black/6">
                        <td>{row.season}</td>
                        <td
                          className="font-medium"
                          style={{ color: row.isCareerHigh ? "#f5a623" : "var(--luka-blue)" }}
                        >
                          {row.peak}
                          {row.isCareerHigh && (
                            <span className="ml-1 text-[10px]" title="Career High">★</span>
                          )}
                        </td>
                        <td className="text-black/55">{row.seasonEnd}</td>
                        <td className="text-black/55">{row.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="surface-card overflow-hidden">
              <div className="border-b border-black/6 px-4 py-3 text-[10px] uppercase tracking-[0.16em] text-black/45">
                Rankings ATP
              </div>
              <div className="overflow-x-auto">
                <table className={tableClass}>
                  <thead className="bg-black/[0.03] text-black/45">
                    <tr>
                      <th>Temporada</th>
                      <th>Pico</th>
                      <th>Fim de temp.</th>
                      <th>Notas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {atpSeasonRows.map((row) => (
                      <tr key={`${row.season}-atp-${row.peak}`} className="border-t border-black/6">
                        <td>{row.season}</td>
                        <td
                          className="font-medium text-luka-blue"
                          style={{ color: row.isCareerHigh ? "var(--luka-blue)" : undefined }}
                        >
                          {row.peak}
                          {row.isCareerHigh && (
                            <span className="ml-1 text-[10px]" title="Career High">★</span>
                          )}
                        </td>
                        <td className="text-black/55">{row.seasonEnd}</td>
                        <td className="text-black/55">{row.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        {/* S03 — SURFACE BREAKDOWN */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">03</span>
            <span className="section-title">Surface Breakdown</span>
            <span className="section-badge">Singles · Career</span>
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="surface-card overflow-hidden lg:col-span-2">
              <div className="border-b border-black/6 px-4 py-3 text-[10px] uppercase tracking-[0.16em] text-black/45">
                W/L + win rate por superfície
              </div>
              <div className="overflow-x-auto">
                <table className={tableClass}>
                  <thead className="bg-black/[0.03] text-black/45">
                    <tr>
                      <th>Superfície</th>
                      <th>W</th>
                      <th>L</th>
                      <th>Win%</th>
                      <th className="min-w-32">Win rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {surfaceRows.map((row) => (
                      <tr key={row.surface} className="border-t border-black/6">
                        <td className="font-medium" style={{ color: row.color }}>
                          {row.surface}
                        </td>
                        <td>{row.w}</td>
                        <td>{row.l}</td>
                        <td className="font-medium">{row.winPct}%</td>
                        <td>
                          <div className="flex h-2 w-full overflow-hidden rounded-full bg-black/8">
                            <div
                              className="rounded-full"
                              style={{ width: `${row.winPct}%`, background: row.color }}
                            />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="surface-card p-5">
              <p className="text-[10px] uppercase tracking-[0.16em] text-luka-blue">Insight</p>
              <p className="mt-3 text-lg font-semibold leading-snug tracking-tight">
                77% das derrotas em saibro. Hard 38% win rate.
              </p>
              <p className="mt-3 text-sm leading-6 text-black/55">
                Saibro domina o volume de jogo no circuito sul-americano. Hard ainda é a superfície com maior taxa de conversão relativa — prioridade para calibrar volume por superfície.
              </p>
            </div>
          </div>
        </section>

        {/* S04 — TOURNAMENT RESULTS */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">04</span>
            <span className="section-title">Tournament Results</span>
            <span className="section-badge">Match by match</span>
          </div>
          <div className="grid gap-4">
            {seasonGroups.map((group) => (
              <div key={group.season} className="surface-card overflow-hidden">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-black/6 px-4 py-4">
                  <h2 className="text-2xl font-semibold tracking-tight text-luka-blue">{group.season}</h2>
                  <span className="text-xs uppercase tracking-[0.16em] text-black/45">
                    {group.summary.wins}W / {group.summary.losses}L
                  </span>
                </div>
                <div className="overflow-x-auto">
                  <table className={tableClass}>
                    <thead className="bg-black/[0.03] text-black/45">
                      <tr>
                        <th>Data</th>
                        <th>Torneio</th>
                        <th>Fase</th>
                        <th>Adversário</th>
                        <th>Local</th>
                        <th>Resultado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {group.events.map((event) => {
                        const round = (event as CareerEvent & { round?: string }).round ?? null;
                        const result = inferResult(event);
                        return (
                          <tr
                            key={`${group.season}-${event.title}-${event.date ?? "na"}`}
                            className="border-t border-black/6 align-top"
                          >
                            <td className="whitespace-nowrap">{event.date ?? group.season}</td>
                            <td className="font-medium text-luka-black">
                              {cleanTournamentTitle(event.title)}
                            </td>
                            <td className={phaseClass(round)}>{round ?? "—"}</td>
                            <td className="text-black/65">{extractOpponent(event)}</td>
                            <td>{event.location ?? "—"}</td>
                            <td>
                              {result === "W" ? (
                                <span className="font-semibold text-[#1cc8a0]">W</span>
                              ) : result === "L" ? (
                                <span className="text-black/35">L</span>
                              ) : (
                                <span className="text-black/25">—</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* S05 — NOTABLE TOURNAMENTS */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">05</span>
            <span className="section-title">Notable Tournaments</span>
            <span className="section-badge">Highlights</span>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {latestMilestones.map((event) => (
              <div key={`${event.season}-${event.title}`} className="surface-card p-5">
                <p className="text-xs uppercase tracking-[0.16em] text-luka-blue">{event.season} · milestone</p>
                <h3 className="mt-2 text-xl font-semibold tracking-tight">{event.title}</h3>
                <p className="mt-2 text-sm leading-6 text-black/65">{event.source_note}</p>
              </div>
            ))}
            {notableEvents.slice(0, 5).map((event) => (
              <div key={`${event.season}-${event.title}`} className="surface-card p-5">
                <p className="text-xs uppercase tracking-[0.16em] text-luka-blue">{event.season} · tournament</p>
                <h3 className="mt-2 text-xl font-semibold tracking-tight">{event.title}</h3>
                <p className="mt-2 text-sm leading-6 text-black/65">{event.source_note}</p>
              </div>
            ))}
          </div>
        </section>

        {/* PRIORITY BOX */}
        <section className="mt-14">
          <div className="priority-box">
            <div className="priority-tag">@luka.ono_ · Career Module · April 2026</div>
            <h2 className="priority-title">→ CAREER DEVELOPMENT PRIORITIES</h2>
            <div className="priority-grid">
              <div className="priority-item">
                <div className="priority-num">01</div>
                <p className="priority-text">Reverter o início de 2026 e priorizar torneios de entrada compatível antes de novo bloco em Challenger.</p>
              </div>
              <div className="priority-item">
                <div className="priority-num">02</div>
                <p className="priority-text">Converter qualifying em main draw com frequência maior para destravar progressão de ranking.</p>
              </div>
              <div className="priority-item">
                <div className="priority-num">03</div>
                <p className="priority-text">Aumentar exposição em hard court (38% win rate vs 25% em saibro). Selecionar torneios hard para construir ranking enquanto saibro é trabalhado em treino.</p>
              </div>
              <div className="priority-item">
                <div className="priority-num">04</div>
                <p className="priority-text">Perseguir Top 1.500 ATP com conversão de qualifyings e aparições regulares em main draw.</p>
              </div>
            </div>
          </div>
        </section>

      </div>
    </div>
  );
}
