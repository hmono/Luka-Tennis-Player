import Link from "next/link";

import {
  getCareerEvents,
  getSurfaceBreakdown,
  parseRank,
  formatRank,
  inferResult,
  isDoubles,
  cleanTournamentTitle,
  getSeasonStats,
  extractOpponent,
  phaseColor,
  phaseWeight,
  findRanking,
} from "@/lib/career";
import type { CareerEvent, SurfaceRecord } from "@/types";

// ── base helpers ──────────────────────────────────────────────

const careerEvents   = getCareerEvents();
const surfaceBreakdown = getSurfaceBreakdown();

// ── data slices ───────────────────────────────────────────────

const rankingEvents    = careerEvents.filter((e) => e.category === "ranking");
const tournamentEvents = careerEvents.filter((e) => e.category === "tournament");
const milestoneEvents  = careerEvents.filter((e) => e.category === "milestone");

const seasons = ["2021", "2022", "2023", "2024", "2025", "2026"];
const singlesBySeason = seasons.map((s) => getSeasonStats(tournamentEvents, s, false));
const doublesBySeason = seasons
  .map((s) => getSeasonStats(tournamentEvents, s, true))
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
const atpSinglesCareerHigh = parseRank(findRanking(careerEvents, /ATP singles career high/i) ?? "");
const atpDoublesCareerHigh = parseRank(findRanking(careerEvents, /ATP doubles career high/i) ?? "");
const atpSinglesCurrent    = parseRank(findRanking(careerEvents, /ATP singles current/i) ?? "");

const challengerAppearances = tournamentEvents.filter((e) =>
  /Challenger/i.test(e.title),
).length;

const bestMainDraw =
  milestoneEvents
    .find((e) => /career-best main draw/i.test(e.title))
    ?.title.match(/R\d+/i)?.[0] ?? "R16";

// S03 — surface breakdown
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
    summary: getSeasonStats(tournamentEvents, season, false),
    events: tournamentEvents
      .filter((e) => e.season === season)
      .sort((a, b) => (b.date ?? "").localeCompare(a.date ?? "")),
  }));

// ─────────────────────────────────────────────────────────────

export default function CareerPage() {
  return (
    <>
      <header className="hero">
        <div className="hero-left">
          <a href="/" className="back-link">← Dashboard</a>
          <div className="hero-tag">
            @luka.ono_ · Professional Tennis Player · Campinas, Brazil · Born Jan 28 2005
          </div>
          <h1>CAREER &amp;<br />RANKING</h1>
          <div className="hero-sub">
            TOURNAMENT RESULTS · RANKING HISTORY · CAREER TRAJECTORY · 2021–2026
          </div>
        </div>
      </header>

      <div className="player-strip">
        <div className="stat-pill">
          <span className="stat-pill-val">{formatRank(atpSinglesCareerHigh)}</span>
          <span className="stat-pill-label">ATP Singles Career High</span>
        </div>
        <div className="stat-divider" />
        <div className="stat-pill">
          <span className="stat-pill-val">{formatRank(atpDoublesCareerHigh)}</span>
          <span className="stat-pill-label">ATP Doubles Career High</span>
        </div>
        <div className="stat-divider" />
        <div className="stat-pill">
          <span className="stat-pill-val">{totalSingles.wins}W · {totalSingles.losses}L</span>
          <span className="stat-pill-label">Career Singles Record</span>
        </div>
        <div className="stat-divider" />
        <div className="stat-pill">
          <span className="stat-pill-val">{totalDoubles.wins}W · {totalDoubles.losses}L</span>
          <span className="stat-pill-label">Career Doubles Record</span>
        </div>
        <div className="stat-divider" />
        <div className="stat-pill">
          <span className="stat-pill-val">{challengerAppearances}</span>
          <span className="stat-pill-label">Challenger Appearances</span>
        </div>
        <div className="stat-divider" />
        <div className="stat-pill">
          <span className="stat-pill-val">{bestMainDraw}</span>
          <span className="stat-pill-label">Best Main Draw Round</span>
        </div>
      </div>

      <div className="level-strip">
        <span className="ls-label">CAREER PATH:</span>
        <div className="ls-item active">
          <div className="ls-dot" style={{ background: "var(--luka-itf)" }} />
          <span style={{ color: "var(--luka-itf)" }}>ITF M25/M15</span>
          <span style={{ color: "rgba(255,255,255,0.35)", fontSize: "8.5px", marginLeft: "4px" }}>Current · {formatRank(atpSinglesCurrent, true)}</span>
        </div>
        <span className="ls-arrow">——→</span>
        <div className="ls-item">
          <div className="ls-dot" style={{ background: "var(--luka-challenger)" }} />
          <span style={{ color: "var(--luka-challenger)" }}>Challenger</span>
          <span style={{ color: "rgba(255,255,255,0.35)", fontSize: "8.5px", marginLeft: "4px" }}>Target · rank ~100–500</span>
        </div>
        <span className="ls-arrow">——→</span>
        <div className="ls-item">
          <div className="ls-dot" style={{ background: "var(--luka-blue)" }} />
          <span style={{ color: "var(--luka-blue)" }}>ATP Tour</span>
          <span style={{ color: "rgba(255,255,255,0.35)", fontSize: "8.5px", marginLeft: "4px" }}>Long-range · top 250+</span>
        </div>
        <span className="ls-note">Coaches: Ricardo Siggia · Alexandre Bonatto</span>
      </div>

      <main className="wrapper">

        {/* S01 — CAREER SUMMARY */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">01</span>
            <span className="sec-title">Career Summary</span>
            <span className="sec-badge">2021–2026</span>
          </div>
          <div className="grid-2col">
            <div className="card-table">
              <div className="tbl-section-head">Singles — W/L por ano</div>
              <div className="tbl-scroll">
                <table className="ctable">
                  <thead>
                    <tr>
                      <th className="th-hdr">Ano</th>
                      <th className="th-hdr">W</th>
                      <th className="th-hdr">L</th>
                      <th className="th-hdr">Win%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {singlesBySeason.map((row) => (
                      <tr key={row.season}>
                        <td className="row-label">{row.season}</td>
                        <td>{row.wins}</td>
                        <td>{row.losses}</td>
                        <td>{row.winPct}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="card-table">
              <div className="tbl-section-head">Doubles — W/L por ano</div>
              <div className="tbl-scroll">
                <table className="ctable">
                  <thead>
                    <tr>
                      <th className="th-hdr">Ano</th>
                      <th className="th-hdr">W</th>
                      <th className="th-hdr">L</th>
                      <th className="th-hdr">Win%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {doublesBySeason.map((row) => (
                      <tr key={row.season}>
                        <td className="row-label">{row.season}</td>
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
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">02</span>
            <span className="sec-title">Ranking History</span>
            <span className="sec-badge">ITF + ATP</span>
          </div>
          <div className="grid-2col">
            <div className="card-table">
              <div className="tbl-section-head">Rankings ITF</div>
              <div className="tbl-scroll">
                <table className="ctable">
                  <thead>
                    <tr>
                      <th className="th-hdr">Temporada</th>
                      <th className="th-hdr">Pico</th>
                      <th className="th-hdr">Fim de temp.</th>
                      <th className="th-hdr">Notas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {itfSeasonRows.map((row) => (
                      <tr key={`${row.season}-itf`}>
                        <td className="row-label">{row.season}</td>
                        <td className="fw-500" style={{ color: row.isCareerHigh ? "var(--luka-itf)" : "var(--luka-blue)" }}>
                          {row.peak}
                          {row.isCareerHigh && (
                            <span className="career-high-star" title="Career High">★</span>
                          )}
                        </td>
                        <td className="val-sub">{row.seasonEnd}</td>
                        <td className="val-sub">{row.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="card-table">
              <div className="tbl-section-head">Rankings ATP</div>
              <div className="tbl-scroll">
                <table className="ctable">
                  <thead>
                    <tr>
                      <th className="th-hdr">Temporada</th>
                      <th className="th-hdr">Pico</th>
                      <th className="th-hdr">Fim de temp.</th>
                      <th className="th-hdr">Notas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {atpSeasonRows.map((row) => (
                      <tr key={`${row.season}-atp-${row.peak}`}>
                        <td className="row-label">{row.season}</td>
                        <td className="text-blue fw-500">
                          {row.peak}
                          {row.isCareerHigh && (
                            <span className="career-high-star" title="Career High">★</span>
                          )}
                        </td>
                        <td className="val-sub">{row.seasonEnd}</td>
                        <td className="val-sub">{row.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        {/* S03 — SURFACE BREAKDOWN */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">03</span>
            <span className="sec-title">Surface Breakdown</span>
            <span className="sec-badge">Singles · Career</span>
          </div>
          <div className="grid-2-1col">
            <div className="card-table">
              <div className="tbl-section-head">W/L + win rate por superfície</div>
              <div className="tbl-scroll">
                <table className="ctable">
                  <thead>
                    <tr>
                      <th className="th-hdr">Superfície</th>
                      <th className="th-hdr">W</th>
                      <th className="th-hdr">L</th>
                      <th className="th-hdr">Win%</th>
                      <th className="th-hdr min-w-128">Win rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {surfaceRows.map((row) => (
                      <tr key={row.surface}>
                        <td className="row-label fw-500" style={{ color: row.color }}>{row.surface}</td>
                        <td>{row.w}</td>
                        <td>{row.l}</td>
                        <td className="fw-500">{row.winPct}%</td>
                        <td>
                          <div className="bar-track">
                            <div
                              className="bar-fill"
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
            <div className="insight-card ic-blue mt-0">
              <span className="ins-tag">Insight</span>
              <div className="ins-head">77% das derrotas em saibro. Hard 38% win rate.</div>
              <p className="ins-body">
                Saibro domina o volume de jogo no circuito sul-americano. Hard ainda é a superfície com maior taxa de conversão relativa — prioridade para calibrar volume por superfície.
              </p>
            </div>
          </div>
        </section>

        {/* S04 — TOURNAMENT RESULTS */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">04</span>
            <span className="sec-title">Tournament Results</span>
            <span className="sec-badge">Match by match</span>
          </div>
          <div className="flex-col-14">
            {seasonGroups.map((group) => (
              <div key={group.season} className="card-table">
                <div className="season-head">
                  <span className="season-label">{group.season}</span>
                  <span className="val-sub val-sub-inline">
                    {group.summary.wins}W / {group.summary.losses}L
                  </span>
                </div>
                <div className="tbl-scroll">
                  <table className="ctable">
                    <thead>
                      <tr>
                        <th className="th-hdr">Data</th>
                        <th className="th-hdr">Torneio</th>
                        <th className="th-hdr">Fase</th>
                        <th className="th-hdr">Adversário</th>
                        <th className="th-hdr">Local</th>
                        <th className="th-hdr">Resultado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {group.events.map((event) => {
                        const round = (event as CareerEvent & { round?: string }).round ?? null;
                        const result = inferResult(event);
                        return (
                          <tr
                            key={`${group.season}-${event.title}-${event.date ?? "na"}`}
                            className="v-top"
                          >
                            <td className="row-label nowrap">{event.date ?? group.season}</td>
                            <td className="fw-500">
                              {cleanTournamentTitle(event.title)}
                            </td>
                            <td style={{ color: phaseColor(round), fontWeight: phaseWeight(round) }}>{round ?? "—"}</td>
                            <td className="val-sub">{extractOpponent(event)}</td>
                            <td>{event.location ?? "—"}</td>
                            <td>
                              {result === "W" ? (
                                <span className="result-w">W</span>
                              ) : result === "L" ? (
                                <span className="result-l">L</span>
                              ) : (
                                <span className="result-n">—</span>
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
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">05</span>
            <span className="sec-title">Notable Tournaments</span>
            <span className="sec-badge">Highlights</span>
          </div>
          <div className="grid-2col">
            {latestMilestones.map((event) => (
              <div key={`${event.season}-${event.title}`} className="insight-card ic-blue mt-0">
                <span className="ins-tag">{event.season} · milestone</span>
                <div className="ins-head">{event.title}</div>
                <p className="ins-body">{event.source_note}</p>
              </div>
            ))}
            {notableEvents.slice(0, 5).map((event) => (
              <div key={`${event.season}-${event.title}`} className="insight-card ic-teal mt-0">
                <span className="ins-tag">{event.season} · tournament</span>
                <div className="ins-head">{event.title}</div>
                <p className="ins-body">{event.source_note}</p>
              </div>
            ))}
          </div>
        </section>

        {/* LUKA BOX */}
        <section className="section">
          <div className="luka-box">
            <div className="luka-box-tag">@luka.ono_ · Career Module · April 2026</div>
            <h2>→ CAREER DEVELOPMENT PRIORITIES</h2>
            <div className="luka-points">
              <div className="lp">
                <span className="lp-num">01</span>
                <span className="lp-text">Reverter o início de 2026 e priorizar torneios de entrada compatível antes de novo bloco em Challenger.</span>
              </div>
              <div className="lp">
                <span className="lp-num">02</span>
                <span className="lp-text">Converter qualifying em main draw com frequência maior para destravar progressão de ranking.</span>
              </div>
              <div className="lp">
                <span className="lp-num">03</span>
                <span className="lp-text">Aumentar exposição em hard court (38% win rate vs 25% em saibro). Selecionar torneios hard para construir ranking enquanto saibro é trabalhado em treino.</span>
              </div>
              <div className="lp">
                <span className="lp-num">04</span>
                <span className="lp-text">Perseguir Top 1.500 ATP com conversão de qualifyings e aparições regulares em main draw.</span>
              </div>
            </div>
          </div>
        </section>

      </main>
    </>
  );
}
