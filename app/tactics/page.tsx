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

// ── shared styles ─────────────────────────────────────────────

const tableClass =
  "w-full min-w-full text-sm [&_th]:px-4 [&_th]:py-3 [&_th]:text-left [&_th]:text-[10px] [&_th]:uppercase [&_th]:tracking-[0.16em] [&_td]:px-4 [&_td]:py-3";

const groupBorderColor: Record<string, string> = {
  "Serve+1": "border-l-luka-blue",
  "Return Pressure": "border-l-luka-challenger",
};

// ─────────────────────────────────────────────────────────────

export default function TacticsPage() {
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
              @luka.ono_ · Tactical Insights · Campinas, Brazil · Born Jan 28 2005
            </div>
            <h1 className="max-w-3xl text-5xl font-semibold leading-none tracking-tight sm:text-7xl">
              TACTICAL
              <br />
              INSIGHTS
            </h1>
            <div className="hero-sub">
              FRAMEWORKS · GAME PATTERNS · SURFACE SPECIFICS · BENCHMARKS
            </div>
          </div>
        </section>

        {/* LEVEL STRIP */}
        <section className="level-strip">
          <span className="level-label">LEVEL KEY:</span>
          <div className="level-item">
            <span className="level-dot bg-luka-atp" />
            <span className="text-luka-atp">ATP Tour</span>
          </div>
          <div className="level-item">
            <span className="level-dot bg-luka-challenger" />
            <span className="text-luka-challenger">Challenger</span>
          </div>
          <div className="level-item">
            <span className="level-dot bg-luka-itf" />
            <span className="text-luka-itf">ITF M25/M15</span>
          </div>
          <span className="level-note">[E] empirically established · [I] inference</span>
        </section>

        {/* S01 — COACHING FRAMEWORKS */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">01</span>
            <span className="section-title">Coaching Frameworks</span>
            <span className="section-badge">Pro-Transition Model</span>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {frameworks.map((f) => (
              <div key={f.coach} className="surface-card border-l-4 border-l-luka-blue p-6">
                <p className="text-[10px] uppercase tracking-[0.16em] text-luka-blue">{f.philosophy}</p>
                <h3 className="mt-2 text-xl font-semibold tracking-tight">{f.coach}</h3>
                <p className="mt-3 text-sm leading-6 text-black/55">{f.application}</p>
              </div>
            ))}
          </div>
        </section>

        {/* S02 — GAME PATTERNS */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">02</span>
            <span className="section-title">Game Patterns</span>
            <span className="section-badge">3-Shot Unit</span>
          </div>

          {/* Serve+1 · Return Pressure */}
          {Object.entries(patternGroups).map(([group, patterns]) => (
            <div key={group} className="mb-6">
              <p className="mb-3 text-[10px] uppercase tracking-[0.18em] text-black/40">{group}</p>
              <div className="grid gap-4 md:grid-cols-3">
                {patterns.map((p) => (
                  <div
                    key={p.id}
                    className={`surface-card border-l-4 p-5 ${groupBorderColor[group] ?? "border-l-luka-dark"}`}
                  >
                    <p className="text-sm font-medium leading-snug">{p.description}</p>
                  </div>
                ))}
              </div>
            </div>
          ))}

          {/* 0–4 Shot Rally — ITF vs Challenger */}
          <div>
            <p className="mb-3 text-[10px] uppercase tracking-[0.18em] text-black/40">0–4 Shot Rally · ITF vs Challenger</p>
            <div className="grid gap-4 md:grid-cols-2">
              {itfRally && (
                <div className="surface-card border-l-4 border-l-luka-itf p-5">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-luka-itf">{itfRally.level}</p>
                  <p className="mt-2 text-2xl font-semibold tracking-tight">{itfRally.pct_points_ending_here}</p>
                  <p className="text-[10px] uppercase tracking-[0.16em] text-black/40">points end in 0–4 shots</p>
                  <p className="mt-3 text-sm text-black/55">Dominant cause: <span className="font-medium">{itfRally.dominant_cause}</span></p>
                </div>
              )}
              {chalRally && (
                <div className="surface-card border-l-4 border-l-luka-challenger p-5">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-luka-challenger">{chalRally.level}</p>
                  <p className="mt-2 text-2xl font-semibold tracking-tight">{chalRally.pct_points_ending_here}</p>
                  <p className="text-[10px] uppercase tracking-[0.16em] text-black/40">points end in 0–4 shots</p>
                  <p className="mt-3 text-sm text-black/55">Dominant cause: <span className="font-medium">{chalRally.dominant_cause}</span></p>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* S03 — SURFACE TACTICS */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">03</span>
            <span className="section-title">Surface Tactics</span>
            <span className="section-badge">Hard vs Clay</span>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {[hard, clay].map((s) => {
              const isHard = s.surface === "Hard Court";
              const accent = isHard ? "text-luka-blue" : "text-luka-itf";
              const border = isHard ? "border-l-luka-blue" : "border-l-luka-itf";
              return (
                <div key={s.surface} className={`surface-card border-l-4 ${border} overflow-hidden`}>
                  <div className="border-b border-black/6 px-4 py-3">
                    <p className={`text-[10px] uppercase tracking-[0.16em] ${accent}`}>{s.style}</p>
                    <h3 className="mt-1 text-xl font-semibold tracking-tight">{s.surface}</h3>
                  </div>
                  <div className={tableClass}>
                    {[
                      ["Movement", s.primary_movement],
                      ["Point Construction", s.point_construction],
                      ["Spin", s.spin_weight],
                      ["Metabolic Load", s.metabolic_load],
                      ["Priority", s.tactical_priority],
                    ].map(([label, value]) => (
                      <div key={label} className="border-t border-black/6 px-4 py-3">
                        <p className="text-[10px] uppercase tracking-[0.16em] text-black/40">{label}</p>
                        <p className="mt-1 text-sm">{value}</p>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* S04 — TARGET BENCHMARKS */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">04</span>
            <span className="section-title">Target Benchmarks</span>
            <span className="section-badge">Tactical Metrics</span>
          </div>
          <div className="surface-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className={tableClass}>
                <thead className="bg-black/[0.03] text-black/45">
                  <tr>
                    <th>Metric</th>
                    <th className="text-luka-itf">ITF M25 (Current)</th>
                    <th className="text-luka-challenger">Challenger Target</th>
                    <th className="text-luka-atp">ATP Elite</th>
                  </tr>
                </thead>
                <tbody>
                  {benchmarks.map((b) => (
                    <tr key={b.metric} className="border-t border-black/6">
                      <td className="font-medium">{b.metric.replace(/_/g, " ")}</td>
                      <td className="font-semibold text-luka-itf">{b.itf_m25_current}</td>
                      <td className="font-semibold text-luka-challenger">{b.challenger_target}</td>
                      <td className="font-semibold text-luka-atp">{b.atp_elite}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* PRIORITY BOX */}
        <section className="mt-14">
          <div className="priority-box">
            <div className="priority-tag">@luka.ono_ · Tactical Development · April 2026</div>
            <h2 className="priority-title">→ TACTICAL PRIORITIES</h2>
            <div className="priority-grid">
              <div className="priority-item">
                <div className="priority-num">01</div>
                <p className="priority-text">
                  <strong>Stop Reacting, Start Executing.</strong> Move from "Read and React" to "Trigger and Pattern." Use the Serve to lock the opponent into a predictable return corridor.
                </p>
              </div>
              <div className="priority-item">
                <div className="priority-num">02</div>
                <p className="priority-text">
                  <strong>Master the 5–8 Shot Battleground.</strong> In Challenger matches, the server's advantage fades by shot 5. Training must focus on winning the transition from "Attack" to "Neutral."
                </p>
              </div>
              <div className="priority-item">
                <div className="priority-num">03</div>
                <p className="priority-text">
                  <strong>First-Strike Efficiency.</strong> Increase Winner/Error ratio in the 0–4 window. Focus on aggressive forehand placement immediately after the serve.
                </p>
              </div>
            </div>
          </div>
        </section>

      </div>
    </div>
  );
}
