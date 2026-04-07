import { Fragment } from "react";

import benchmarksData from "@/data/benchmarks.json";

type Benchmark = (typeof benchmarksData)["benchmarks"][number];

const benchmarks = benchmarksData.benchmarks as Benchmark[];

const findBenchmark = (name: string) =>
  benchmarks.find((benchmark) => benchmark.benchmark_name === name);

const playerProfile = [
  {
    value: "21",
    label: "Age · DOB Jan 2005",
  },
  {
    value: "#1.827",
    label: "ATP Singles Career High",
  },
  {
    value: "#1.784",
    label: "ATP Doubles Career High",
  },
  {
    value: findBenchmark("itf_futures_tournaments")?.value ?? "30+",
    label: "ITF Future Tournaments",
  },
  {
    value: findBenchmark("challenger_appearances")?.value ?? "4",
    label: "Challenger Appearances",
  },
  {
    value: "RH · 2HBH",
    label: "Style · 180cm / 75kg",
  },
];

const comparisonOrder = [
  "current_level",
  "development_target",
  "itf_futures_tournaments",
  "challenger_appearances",
  "points_per_game_service",
  "points_per_game_return",
  "avg_points_per_game",
  "avg_games_per_set",
  "service_hold_rate",
  "break_frequency_per_set",
  "points_per_set_avg",
  "points_per_set_clay",
  "total_points_per_match_bo3",
  "rally_distribution_overall",
  "itf_serve_return_rally_distribution",
  "first_serve_points_won",
  "second_serve_points_won",
  "total_service_points_won",
  "first_serve_in_rate",
  "serve_return_asymmetry_index",
  "atp_first_serve_effectiveness",
  "challenger_battleground_window",
  "standard_play_thresholds",
  "first_serve_variance",
  "double_faults_per_match",
  "rally_shots_per_point_avg",
  "glycolytic_demand_per_set",
  "monitoring_markers",
  "priority_serve_hold",
  "priority_asymmetry_gap",
  "priority_standard_plays",
];

const insightCards = [
  "rally_distribution_overall",
  "first_serve_points_won",
  "serve_return_asymmetry_index",
  "challenger_battleground_window",
]
  .map((name) => findBenchmark(name))
  .filter(Boolean) as Benchmark[];

const priorityCards = ["priority_serve_hold", "priority_asymmetry_gap", "priority_standard_plays"]
  .map((name) => findBenchmark(name))
  .filter(Boolean) as Benchmark[];

const formatLabel = (name: string) =>
  name
    .replace(/_/g, " ")
    .replace(/\b[a-z]/g, (letter) => letter.toUpperCase())
    .replace("Challenger", "Challenger")
    .replace("Itf", "ITF")
    .replace("Atp", "ATP");

const extractPercentSeries = (value: string) => {
  const matches = [...value.matchAll(/\\d+(?:\\.\\d+)?/g)].map((match) => Number(match[0]));
  return matches.slice(0, 3);
};

const parseRallyDistribution = (text: string) => {
  return text
    .split(";")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [level, ...rest] = line.split(" ");
      const numbers = rest.join(" ").split("|").map((item) => Number(item.replace(/[^\d]/g, "")));
      return {
        label: level.replace(/_/g, " ").toUpperCase(),
        values: numbers,
      };
    });
};

const padToThree = (values: number[]) => [...values, 0, 0].slice(0, 3);

const barMetricDefinitions = [
  { id: "service_hold_rate", label: "Service hold rate (ATP · Challenger · ITF)" },
  { id: "first_serve_points_won", label: "First serve points won (ATP · Challenger · ITF)" },
];

const barMetrics = barMetricDefinitions
  .map((definition) => {
    const benchmark = findBenchmark(definition.id);
    const values = benchmark ? padToThree(extractPercentSeries(benchmark.value)) : [];
    return { label: definition.label, values, colors: ["var(--luka-blue)", "#1cc8a0", "#f5a623"], benchmark };
  })
  .filter((metric) => metric.values.some((value) => value > 0));

const sidebarNotes = [
  "Commentary: Benchmarks anchored in ATP published data and inferred ITF/Challenger splits.",
  "Feedback: share notes via GitHub Discussions if numbers need refinements.",
];

const tableSections = [
  {
    label: "Trajectory & volume",
    badge: "Player profile",
    rows: ["current_level", "development_target", "itf_futures_tournaments", "challenger_appearances"],
  },
  {
    label: "Performance benchmarks",
    badge: "ATP · Challenger · ITF",
    rows: [
      "points_per_game_service",
      "points_per_game_return",
      "avg_points_per_game",
      "avg_games_per_set",
      "service_hold_rate",
      "break_frequency_per_set",
      "points_per_set_avg",
      "points_per_set_clay",
      "total_points_per_match_bo3",
    ],
  },
  {
    label: "Technical depth",
    badge: "Quality thresholds",
    rows: [
      "rally_distribution_overall",
      "itf_serve_return_rally_distribution",
      "first_serve_points_won",
      "second_serve_points_won",
      "total_service_points_won",
      "first_serve_in_rate",
      "serve_return_asymmetry_index",
      "atp_first_serve_effectiveness",
      "challenger_battleground_window",
      "standard_play_thresholds",
      "first_serve_variance",
      "double_faults_per_match",
    ],
  },
  {
    label: "Physical context",
    badge: "Load & monitoring",
    rows: [
      "rally_shots_per_point_avg",
      "glycolytic_demand_per_set",
      "monitoring_markers",
    ],
  },
  {
    label: "Priority targets",
    badge: "Structural goals",
    rows: ["priority_serve_hold", "priority_asymmetry_gap", "priority_standard_plays"],
  },
].map((section) => ({
  ...section,
  rows: section.rows.map((name) => findBenchmark(name)).filter(Boolean) as Benchmark[],
}));

const rallyDistributionBenchmark = findBenchmark("rally_distribution_overall");
const rallySegments = rallyDistributionBenchmark
  ? parseRallyDistribution(rallyDistributionBenchmark.value)
  : [];

const roColors = ["var(--luka-blue)", "var(--luka-challenger)", "var(--luka-itf)"];

export default function TennisLevelComparisonPage() {
  void comparisonOrder;
  return (
    <>
      <header className="hero">
        <div className="hero-left">
          <div className="hero-tag">
            @{benchmarksData.subject.toLowerCase()} · Professional Tennis Player · Campinas, Brazil · Born Jan 28 2005
          </div>
          <h1>
            {benchmarksData.subject.toUpperCase()}
            <br />
            ANALYTICS
          </h1>
          <div className="hero-sub">
            ATP × CHALLENGER × ITF — STRUCTURAL LEVEL COMPARISON · MARCH 2026
          </div>
        </div>
      </header>

      <div className="player-strip">
        {playerProfile.map((item, i) => (
          <Fragment key={item.label}>
            {i > 0 && <div className="stat-divider" />}
            <div className="stat-pill">
              <span className="stat-pill-val">{item.value}</span>
              <span className="stat-pill-label">{item.label}</span>
            </div>
          </Fragment>
        ))}
      </div>

      <div className="level-legend">
        <span className="ll-label">LEVEL KEY:</span>
        <div className="ll-item">
          <span className="ll-dot" style={{ background: "var(--luka-blue)" }} />
          <span style={{ color: "var(--luka-blue)" }}>ATP TOUR</span>
          <span style={{ color: "rgba(255,255,255,0.35)", fontSize: "9px" }}>top 100</span>
        </div>
        <div className="ll-item">
          <span className="ll-dot" style={{ background: "var(--luka-challenger)" }} />
          <span style={{ color: "var(--luka-challenger)" }}>CHALLENGER</span>
          <span style={{ color: "rgba(255,255,255,0.35)", fontSize: "9px" }}>rank 100–500</span>
        </div>
        <div className="ll-item">
          <span className="ll-dot" style={{ background: "var(--luka-itf)" }} />
          <span style={{ color: "var(--luka-itf)" }}>ITF M25/M15</span>
          <span style={{ color: "rgba(255,255,255,0.35)", fontSize: "9px" }}>current level</span>
        </div>
        <span className="ll-note">[E] empirically established · [I] inference</span>
      </div>

      <main className="wrapper">

        {/* S01 — COMPARISON TABLE */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">01</span>
            <span className="sec-title">Comparison Table</span>
            <span className="sec-badge">
              {tableSections.reduce((sum, s) => sum + s.rows.length, 0)} rows
            </span>
          </div>
          <table className="ctable">
            <thead>
              <tr>
                <th className="th-hdr">Metric</th>
                <th className="th-hdr">Comparison Basis</th>
                <th className="th-hdr">Value</th>
                <th className="th-hdr">Summary</th>
              </tr>
            </thead>
            <tbody>
              {tableSections.map((section) => (
                <Fragment key={section.label}>
                  <tr className="grp-row">
                    <td colSpan={4}>
                      <span className="grp-label">{section.label}</span>
                      <span style={{ float: "right", fontSize: "9px", opacity: 0.5, letterSpacing: "0.1em", textTransform: "uppercase" }}>{section.badge}</span>
                    </td>
                  </tr>
                  {section.rows.map((row) => (
                    <tr key={row.benchmark_name}>
                      <td className="row-label">{formatLabel(row.benchmark_name)}</td>
                      <td>
                        <span className="val-sub">{row.comparison_basis}</span>
                        <span className="val-sub">{row.reference}</span>
                      </td>
                      <td><span className="val">{row.value}</span></td>
                      <td><span className="val-sub">{row.summary}</span></td>
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </section>

        {/* S02 — BENCHMARK BARS */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">02</span>
            <span className="sec-title">Benchmark Bars</span>
            <span className="sec-badge">Service &amp; rally indicators</span>
          </div>
          {barMetrics.map((metric) => (
            <div key={metric.label} className="bar-block">
              <p className="bar-block-title">{metric.label}</p>
              {metric.values.map((value, index) => (
                <div key={index} className="bar-row">
                  <span className="bar-lbl">{index === 0 ? "ATP" : index === 1 ? "Challenger" : "ITF"}</span>
                  <div className="bar-track">
                    <div className="bar-fill" style={{ width: `${value}%`, background: metric.colors[index] }} />
                  </div>
                  <span className="bar-val" style={{ color: metric.colors[index] }}>{value}%</span>
                </div>
              ))}
            </div>
          ))}
        </section>

        {/* S03 — RALLY DISTRIBUTION */}
        {rallySegments.length > 0 && (
          <section className="section">
            <div className="sec-head">
              <span className="sec-num">03</span>
              <span className="sec-title">Rally Distribution</span>
              <span className="sec-badge">0–4 | 5–8 | 9+ shots</span>
            </div>
            <div className="rally-overall">
              <p className="ro-title">Rally length distribution · ATP vs Challenger vs ITF</p>
              {rallySegments.map((segment) => (
                <div key={segment.label} className="ro-row">
                  <div className="ro-level">{segment.label}</div>
                  <div className="ro-bar">
                    {segment.values.map((value, index) => (
                      <div
                        key={index}
                        className="ro-seg"
                        style={{ flex: value || 1, background: roColors[index] }}
                      >
                        {value}%
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              <p className="val-sub" style={{ marginTop: "12px" }}>{rallyDistributionBenchmark?.summary}</p>
            </div>
          </section>
        )}

        {/* S04 — INSIGHT CARDS */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">04</span>
            <span className="sec-title">Insight Sections</span>
            <span className="sec-badge">Narrative callouts</span>
          </div>
          <div className="insight-grid">
            {insightCards.map((item) => (
              <div key={item.benchmark_name} className="insight-card ic-blue">
                <span className="ins-tag">{item.reference}</span>
                <div className="ins-head">{formatLabel(item.benchmark_name)}</div>
                <p className="ins-body">{item.summary}</p>
                <p className="ins-body" style={{ marginTop: "8px" }}>{item.value}</p>
              </div>
            ))}
          </div>
        </section>

        {/* SIDEBAR NOTES */}
        <div className="sv-card" style={{ marginBottom: "48px" }}>
          <div className="sv-title">Comments · Data Sources</div>
          {sidebarNotes.map((note) => (
            <p key={note} className="val-sub" style={{ marginBottom: "8px" }}>{note}</p>
          ))}
          <ul style={{ listStyle: "disc", paddingLeft: "16px", marginTop: "12px" }}>
            <li className="val-sub">ITF · ATP tour data</li>
            <li className="val-sub">CoreTennis · TennisExplorer</li>
            <li className="val-sub">benchmarks.json</li>
          </ul>
        </div>

        {/* S05 — DEVELOPMENT PRIORITIES */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">05</span>
            <span className="sec-title">Development Priorities</span>
            <span className="sec-badge">Structural focus</span>
          </div>
          <div className="luka-box">
            <div className="luka-box-tag">@luka.ono_ · Luka Bojičić Ono · Application Layer</div>
            <h2>→ DEVELOPMENT PRIORITIES</h2>
            <div className="luka-points">
              {priorityCards.map((item, index) => (
                <div key={item.benchmark_name} className="lp">
                  <div className="lp-num">{String(index + 1).padStart(2, "0")}</div>
                  <p className="lp-text">
                    <strong>{item.summary}.</strong> {item.value}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

      </main>
    </>
  );
}
