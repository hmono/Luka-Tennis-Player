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

const phaseColor = (round: string | null | undefined): string => {
  if (!round) return "rgba(0,0,0,0.4)";
  if (/^(R\d+|1R)$/.test(round)) return "var(--luka-blue)";
  if (/^Q-/.test(round)) return "rgba(0,0,0,0.4)";
  if (round === "D") return "rgba(0,0,0,0.4)";
  return "rgba(0,0,0,0.4)";
};

const phaseWeight = (round: string | null | undefined): string => {
  if (!round) return "normal";
  if (/^(R\d+|1R)$/.test(round)) return "600";
  return "normal";
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

// ── table wrapper style ───────────────────────────────────────

const tableWrapStyle: React.CSSProperties = {
  background: "#fff",
  border: "1px solid rgba(0,0,0,0.07)",
  borderRadius: "4px",
  overflow: "hidden",
};

const tableHeadStyle: React.CSSProperties = {
  fontFamily: "'IBM Plex Mono', monospace",
  fontSize: "8.5px",
  letterSpacing: "0.1em",
  textTransform: "uppercase" as const,
  color: "#888",
  padding: "9px 18px 10px",
  borderBottom: "1px solid rgba(0,0,0,0.06)",
};

// ─────────────────────────────────────────────────────────────

export default function CareerPage() {
  return (
    <>
      <header className="hero">
        <div className="hero-left">
          <a href="/" style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: "9px",
            letterSpacing: "0.12em",
            color: "rgba(255,255,255,0.4)",
            textDecoration: "none",
            marginBottom: "20px",
          }}>← Dashboard</a>
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
          <div className="ls-dot" style={{ background: "#f5a623" }} />
          <span style={{ color: "#f5a623" }}>ITF M25/M15</span>
          <span style={{ color: "rgba(255,255,255,0.35)", fontSize: "8.5px", marginLeft: "4px" }}>Current · {formatRank(atpSinglesCurrent, true)}</span>
        </div>
        <span className="ls-arrow">——→</span>
        <div className="ls-item">
          <div className="ls-dot" style={{ background: "#1cc8a0" }} />
          <span style={{ color: "#1cc8a0" }}>Challenger</span>
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
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
            <div style={tableWrapStyle}>
              <div style={tableHeadStyle}>Singles — W/L por ano</div>
              <div style={{ overflowX: "auto" }}>
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
            <div style={tableWrapStyle}>
              <div style={tableHeadStyle}>Doubles — W/L por ano</div>
              <div style={{ overflowX: "auto" }}>
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
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
            <div style={tableWrapStyle}>
              <div style={tableHeadStyle}>Rankings ITF</div>
              <div style={{ overflowX: "auto" }}>
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
                        <td style={{ color: row.isCareerHigh ? "#f5a623" : "var(--luka-blue)", fontWeight: 500 }}>
                          {row.peak}
                          {row.isCareerHigh && (
                            <span style={{ marginLeft: "4px", fontSize: "10px" }} title="Career High">★</span>
                          )}
                        </td>
                        <td className="val-sub" style={{ display: "table-cell" }}>{row.seasonEnd}</td>
                        <td className="val-sub" style={{ display: "table-cell" }}>{row.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div style={tableWrapStyle}>
              <div style={tableHeadStyle}>Rankings ATP</div>
              <div style={{ overflowX: "auto" }}>
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
                        <td style={{ color: "var(--luka-blue)", fontWeight: 500 }}>
                          {row.peak}
                          {row.isCareerHigh && (
                            <span style={{ marginLeft: "4px", fontSize: "10px" }} title="Career High">★</span>
                          )}
                        </td>
                        <td className="val-sub" style={{ display: "table-cell" }}>{row.seasonEnd}</td>
                        <td className="val-sub" style={{ display: "table-cell" }}>{row.note}</td>
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
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "14px" }}>
            <div style={tableWrapStyle}>
              <div style={tableHeadStyle}>W/L + win rate por superfície</div>
              <div style={{ overflowX: "auto" }}>
                <table className="ctable">
                  <thead>
                    <tr>
                      <th className="th-hdr">Superfície</th>
                      <th className="th-hdr">W</th>
                      <th className="th-hdr">L</th>
                      <th className="th-hdr">Win%</th>
                      <th className="th-hdr" style={{ minWidth: "128px" }}>Win rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {surfaceRows.map((row) => (
                      <tr key={row.surface}>
                        <td className="row-label" style={{ color: row.color, fontWeight: 500 }}>{row.surface}</td>
                        <td>{row.w}</td>
                        <td>{row.l}</td>
                        <td style={{ fontWeight: 500 }}>{row.winPct}%</td>
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
            <div className="insight-card ic-blue" style={{ marginTop: 0 }}>
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
          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            {seasonGroups.map((group) => (
              <div key={group.season} style={tableWrapStyle}>
                <div style={{
                  display: "flex",
                  flexWrap: "wrap",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "12px",
                  borderBottom: "1px solid rgba(0,0,0,0.06)",
                  padding: "14px 18px",
                }}>
                  <span style={{
                    fontFamily: "'Bebas Neue', sans-serif",
                    fontSize: "22px",
                    letterSpacing: "0.06em",
                    color: "var(--luka-blue)",
                  }}>{group.season}</span>
                  <span className="val-sub" style={{ display: "inline" }}>
                    {group.summary.wins}W / {group.summary.losses}L
                  </span>
                </div>
                <div style={{ overflowX: "auto" }}>
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
                            style={{ verticalAlign: "top" }}
                          >
                            <td className="row-label" style={{ whiteSpace: "nowrap" }}>{event.date ?? group.season}</td>
                            <td style={{ fontWeight: 500 }}>
                              {cleanTournamentTitle(event.title)}
                            </td>
                            <td style={{ color: phaseColor(round), fontWeight: phaseWeight(round) }}>{round ?? "—"}</td>
                            <td className="val-sub" style={{ display: "table-cell" }}>{extractOpponent(event)}</td>
                            <td>{event.location ?? "—"}</td>
                            <td>
                              {result === "W" ? (
                                <span style={{ fontWeight: 600, color: "#1cc8a0" }}>W</span>
                              ) : result === "L" ? (
                                <span style={{ color: "rgba(0,0,0,0.35)" }}>L</span>
                              ) : (
                                <span style={{ color: "rgba(0,0,0,0.25)" }}>—</span>
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
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
            {latestMilestones.map((event) => (
              <div key={`${event.season}-${event.title}`} className="insight-card ic-blue" style={{ marginTop: 0 }}>
                <span className="ins-tag">{event.season} · milestone</span>
                <div className="ins-head">{event.title}</div>
                <p className="ins-body">{event.source_note}</p>
              </div>
            ))}
            {notableEvents.slice(0, 5).map((event) => (
              <div key={`${event.season}-${event.title}`} className="insight-card ic-teal" style={{ marginTop: 0 }}>
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
