import Link from "next/link";

import tacticalData from "@/data/tactical.json";

// ── types ─────────────────────────────────────────────────────

type Framework = (typeof tacticalData)["frameworks"][number];
type Pattern = (typeof tacticalData)["game_patterns"][number];
type Surface = (typeof tacticalData)["surface_tactics"][number];
type Benchmark = (typeof tacticalData)["target_benchmarks"][number];

// ── data slices ───────────────────────────────────────────────

const frameworks = tacticalData.frameworks as Framework[];
const allPatterns = tacticalData.game_patterns as Pattern[];
const surfaces = tacticalData.surface_tactics as Surface[];
const benchmarks = tacticalData.target_benchmarks as Benchmark[];

const patternGroups = allPatterns
  .filter((p) => p.pattern_group !== "0–4 Shot Rally")
  .reduce<Record<string, Pattern[]>>((acc, p) => {
    (acc[p.pattern_group] ??= []).push(p);
    return acc;
  }, {});

const rally04 = allPatterns.filter((p) => p.pattern_group === "0–4 Shot Rally");
const itfRally = rally04.find((p) => p.id?.includes("itf"));
const chalRally = rally04.find((p) => p.id?.includes("challenger"));

const hard = surfaces.find((s) => s.surface === "Hard Court")!;
const clay = surfaces.find((s) => s.surface === "Clay")!;

const groupInsightClass: Record<string, string> = {
  "Serve+1": "ic-blue",
  "Return Pressure": "ic-teal",
};

// ─────────────────────────────────────────────────────────────

export default function TacticsPage() {
  return (
    <>
      <header className="hero">
        <div className="hero-left">
          <div className="hero-tag">
            @luka.ono_ · Tactical Insights · Campinas, Brazil · Born Jan 28 2005
          </div>
          <h1>TACTICAL<br />INSIGHTS</h1>
          <div className="hero-sub">FRAMEWORKS · GAME PATTERNS · SURFACE SPECIFICS · BENCHMARKS</div>
        </div>
      </header>

      <div className="level-strip">
        <span className="ls-label">LEVEL KEY:</span>
        <div className="ls-item">
          <span className="ls-dot" style={{ background: "var(--luka-atp)" }} />
          <span style={{ color: "var(--luka-atp)" }}>ATP Tour</span>
        </div>
        <div className="ls-item">
          <span className="ls-dot" style={{ background: "var(--luka-challenger)" }} />
          <span style={{ color: "var(--luka-challenger)" }}>Challenger</span>
        </div>
        <div className="ls-item">
          <span className="ls-dot" style={{ background: "var(--luka-itf)" }} />
          <span style={{ color: "var(--luka-itf)" }}>ITF M25/M15</span>
        </div>
        <span className="ls-note">[E] empirically established · [I] inference</span>
      </div>

      <main className="wrapper">

        {/* S01 — COACHING FRAMEWORKS */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">01</span>
            <span className="sec-title">Coaching Frameworks</span>
            <span className="sec-badge">Pro-Transition Model</span>
          </div>
          <div className="rally-grid">
            {frameworks.map((f) => (
              <div key={f.coach} className="insight-card ic-blue">
                <span className="ins-tag">{f.philosophy}</span>
                <div className="ins-head">{f.coach}</div>
                <p className="ins-body">{f.application}</p>
              </div>
            ))}
          </div>
        </section>

        {/* S02 — GAME PATTERNS */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">02</span>
            <span className="sec-title">Game Patterns</span>
            <span className="sec-badge">3-Shot Unit</span>
          </div>

          {Object.entries(patternGroups).map(([group, patterns]) => (
            <div key={group} style={{ marginBottom: "20px" }}>
              <p className="bar-block-title">{group}</p>
              <div className="rally-grid">
                {patterns.map((p) => (
                  <div key={p.id} className={`insight-card ${groupInsightClass[group] ?? "ic-dark"}`}>
                    <p className="ins-body">{p.description}</p>
                  </div>
                ))}
              </div>
            </div>
          ))}

          <div>
            <p className="bar-block-title">0–4 Shot Rally · ITF vs Challenger</p>
            <div className="sv-grid">
              {itfRally && (
                <div className="insight-card ic-amber">
                  <span className="ins-tag" style={{ color: "var(--luka-itf)" }}>{itfRally.level}</span>
                  <div className="ins-head" style={{ fontSize: "28px" }}>{itfRally.pct_points_ending_here}</div>
                  <span className="ins-tag">points end in 0–4 shots</span>
                  <p className="ins-body">Dominant cause: <strong>{itfRally.dominant_cause}</strong></p>
                </div>
              )}
              {chalRally && (
                <div className="insight-card ic-teal">
                  <span className="ins-tag" style={{ color: "var(--luka-challenger)" }}>{chalRally.level}</span>
                  <div className="ins-head" style={{ fontSize: "28px" }}>{chalRally.pct_points_ending_here}</div>
                  <span className="ins-tag">points end in 0–4 shots</span>
                  <p className="ins-body">Dominant cause: <strong>{chalRally.dominant_cause}</strong></p>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* S03 — SURFACE TACTICS */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">03</span>
            <span className="sec-title">Surface Tactics</span>
            <span className="sec-badge">Hard vs Clay</span>
          </div>
          <div className="sv-grid">
            {[hard, clay].map((s) => {
              const isHard = s.surface === "Hard Court";
              const accentColor = isHard ? "var(--luka-blue)" : "var(--luka-itf)";
              return (
                <div key={s.surface} className="sv-card">
                  <div className="sv-title" style={{ color: accentColor }}>{s.surface} · {s.style}</div>
                  {[
                    ["Movement", s.primary_movement],
                    ["Point Construction", s.point_construction],
                    ["Spin", s.spin_weight],
                    ["Metabolic Load", s.metabolic_load],
                    ["Priority", s.tactical_priority],
                  ].map(([label, value]) => (
                    <div key={label} style={{ marginBottom: "10px" }}>
                      <span className="ins-tag">{label}</span>
                      <p className="ins-body">{value}</p>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        </section>

        {/* S04 — TARGET BENCHMARKS */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">04</span>
            <span className="sec-title">Target Benchmarks</span>
            <span className="sec-badge">Tactical Metrics</span>
          </div>
          <table className="ctable">
            <thead>
              <tr>
                <th className="th-hdr">Metric</th>
                <th className="th-itf">ITF M25 (Current)</th>
                <th className="th-chal">Challenger Target</th>
                <th className="th-atp">ATP Elite</th>
              </tr>
            </thead>
            <tbody>
              {benchmarks.map((b) => (
                <tr key={b.metric}>
                  <td className="row-label">{b.metric.replace(/_/g, " ")}</td>
                  <td><span className="val val-itf">{b.itf_m25_current}</span></td>
                  <td><span className="val val-chal">{b.challenger_target}</span></td>
                  <td><span className="val val-atp">{b.atp_elite}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* PRIORITY BOX */}
        <div className="luka-box">
          <div className="luka-box-tag">@luka.ono_ · Tactical Development · April 2026</div>
          <h2>→ TACTICAL PRIORITIES</h2>
          <div className="luka-points">
            <div className="lp">
              <div className="lp-num">01</div>
              <p className="lp-text"><strong>Stop Reacting, Start Executing.</strong> Move from "Read and React" to "Trigger and Pattern." Use the Serve to lock the opponent into a predictable return corridor.</p>
            </div>
            <div className="lp">
              <div className="lp-num">02</div>
              <p className="lp-text"><strong>Master the 5–8 Shot Battleground.</strong> In Challenger matches, the server's advantage fades by shot 5. Training must focus on winning the transition from "Attack" to "Neutral."</p>
            </div>
            <div className="lp">
              <div className="lp-num">03</div>
              <p className="lp-text"><strong>First-Strike Efficiency.</strong> Increase Winner/Error ratio in the 0–4 window. Focus on aggressive forehand placement immediately after the serve.</p>
            </div>
          </div>
        </div>

      </main>

      <Link href="/" style={{ display: "none" }}>← Dashboard</Link>
    </>
  );
}
