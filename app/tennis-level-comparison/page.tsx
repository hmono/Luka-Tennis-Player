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

const tableClass =
  "min-w-full text-sm [&_th]:px-4 [&_th]:py-3 [&_th]:text-left [&_th]:text-[10px] [&_th]:uppercase [&_th]:tracking-[0.16em] [&_td]:px-4 [&_td]:py-3";

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

export default function TennisLevelComparisonPage() {
  return (
    <div className="section-block">
      <div className="shell">
        <section className="hero-panel">
          <div className="relative z-10">
            <div className="hero-tag">
              @{benchmarksData.subject.toLowerCase()} · Professional Tennis Player · Campinas, Brazil
            </div>
            <h1 className="max-w-3xl text-5xl font-semibold leading-none tracking-tight sm:text-7xl">
              {benchmarksData.subject.toUpperCase()}
              <br />
              ANALYTICS
            </h1>
            <div className="hero-sub">
              ATP × CHALLENGER × ITF — STRUCTURAL LEVEL COMPARISON · MARCH 2026
            </div>
          </div>
        </section>

        <section className="stat-strip">
          {playerProfile.map((item) => (
            <div key={item.label} className="stat-item">
              <span className="stat-value">{item.value}</span>
              <span className="stat-label">{item.label}</span>
            </div>
          ))}
        </section>

        <section className="level-strip">
          <span className="level-label">LEVEL KEY:</span>
          <div className="level-item">
            <span className="level-dot" style={{ background: "var(--luka-blue)" }} />
            <span className="text-luka-blue">ATP TOUR</span>
            <span className="text-[10px] text-white/35">top 100</span>
          </div>
          <div className="level-item">
            <span className="level-dot" style={{ background: "#1cc8a0" }} />
            <span className="text-[#1cc8a0]">CHALLENGER</span>
            <span className="text-[10px] text-white/35">rank 100–500</span>
          </div>
          <div className="level-item">
            <span className="level-dot" style={{ background: "#f5a623" }} />
            <span className="text-[#f5a623]">ITF M25/M15</span>
            <span className="text-[10px] text-white/35">current level</span>
          </div>
          <span className="level-note">[E] empirically established · [I] inference</span>
        </section>

        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">01</span>
            <span className="section-title">Comparison Table</span>
            <span className="section-badge">
              {tableSections.reduce((sum, section) => sum + section.rows.length, 0)} rows
            </span>
          </div>
          <div className="surface-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className={tableClass}>
                <thead className="bg-luka-dark text-left text-white">
                  <tr className="text-[10px] tracking-[0.3em]">
                    <th>Metric</th>
                    <th>Comparison Basis</th>
                    <th>Value</th>
                    <th>Summary</th>
                  </tr>
                </thead>
                <tbody>
                  {tableSections.map((section) => (
                    <Fragment key={section.label}>
                      <tr className="bg-luka-blue/5">
                        <td colSpan={4} className="text-[10px] uppercase tracking-[0.16em] text-black/60">
                          <div className="flex items-center justify-between">
                            <span>{section.label}</span>
                            <span className="text-black/40 text-[9px] uppercase tracking-[0.2em]">
                              {section.badge}
                            </span>
                          </div>
                        </td>
                      </tr>
                      {section.rows.map((row) => (
                        <tr key={row.benchmark_name} className="border-t border-black/6 align-top">
                          <td className="font-medium text-luka-black">{formatLabel(row.benchmark_name)}</td>
                          <td>
                            <p className="text-[10px] uppercase tracking-[0.16em] text-black/55">{row.comparison_basis}</p>
                            <p className="text-[9px] text-black/40">{row.reference}</p>
                          </td>
                          <td className="text-black/75">
                            <span className="font-semibold">{row.value}</span>
                          </td>
                          <td className="text-black/60">{row.summary}</td>
                        </tr>
                      ))}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section className="mt-14 grid gap-6 lg:grid-cols-[2fr_1fr]">
          <div className="space-y-6">
            <div className="surface-card p-5">
              <div className="section-head">
                <span className="section-num">02</span>
                <span className="section-title">Benchmark Bars</span>
                <span className="section-badge">Service & rally indicators</span>
              </div>
              {barMetrics.map((metric, metricIndex) => (
                <div key={metric.label} className={metricIndex ? "mt-6" : "mt-5"}>
                  <p className="text-xs uppercase tracking-[0.16em] text-luka-blue">{metric.label}</p>
                  <div className="mt-3 space-y-2">
                    {metric.values.map((value, index) => (
                      <div key={`${metric.label}-${index}`} className="flex items-center gap-3">
                        <span className="w-32 text-xs uppercase tracking-[0.14em] text-black/45">
                          {index === 0 ? "ATP" : index === 1 ? "Challenger" : "ITF"}
                        </span>
                        <div className="h-3 flex-1 rounded-full bg-black/5">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${value}%`,
                              background: metric.colors[index],
                            }}
                          />
                        </div>
                        <span className="text-sm font-semibold text-black/70">{value}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {rallySegments.length > 0 && (
              <div className="surface-card p-5">
                <div className="section-head">
                  <span className="section-num">03</span>
                  <span className="section-title">Rally Distribution</span>
                  <span className="section-badge">0-4 | 5-8 | 9+ shots</span>
                </div>
                <div className="space-y-5">
                  {rallySegments.map((segment) => (
                    <div key={segment.label} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] uppercase tracking-[0.16em] text-black/60">{segment.label}</span>
                        <span className="text-[9px] uppercase tracking-[0.2em] text-black/40">
                          {segment.values.join(" | ")}
                        </span>
                      </div>
                      <div className="flex h-3 overflow-hidden rounded-full bg-black/5">
                        {segment.values.map((value, index) => (
                          <div
                            key={`${segment.label}-${index}`}
                            className={`h-full ${index === 0 ? "bg-luka-blue" : index === 1 ? "bg-[#1cc8a0]" : "bg-[#f5a623]"}`}
                            style={{ flex: value || 1 }}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                  <p className="text-sm text-black/60">{rallyDistributionBenchmark?.summary}</p>
                </div>
              </div>
            )}

            <div className="surface-card p-5">
              <div className="section-head">
                <span className="section-num">04</span>
                <span className="section-title">Insight Sections</span>
                <span className="section-badge">Narrative callouts</span>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                {insightCards.map((item) => (
                  <div key={item.benchmark_name} className="surface-card border-0 bg-white p-4">
                    <p className="text-[10px] uppercase tracking-[0.16em] text-luka-blue">{item.reference}</p>
                    <h2 className="mt-2 text-xl font-semibold tracking-tight">{item.benchmark_name}</h2>
                    <p className="mt-3 text-sm leading-6 text-black/65">{item.summary}</p>
                    <p className="mt-4 text-sm leading-6 text-black/80">{item.value}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <aside className="surface-card p-5">
            <p className="text-xs uppercase tracking-[0.16em] text-luka-blue">Comments</p>
            <p className="text-[10px] uppercase tracking-[0.2em] text-black/45">Share your feedback</p>
            {sidebarNotes.map((note) => (
              <p key={note} className="mt-3 text-sm leading-6 text-black/70">
                {note}
              </p>
            ))}
            <p className="mt-4 text-xs uppercase tracking-[0.16em] text-black/45">
              Data sources
            </p>
            <ul className="mt-2 list-inside list-disc text-sm text-black/65">
              <li>ITF · ATP tour data</li>
              <li>CoreTennis · TennisExplorer</li>
              <li>benchmarks.json</li>
            </ul>
          </aside>
        </section>

        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">05</span>
            <span className="section-title">Development Priorities</span>
            <span className="section-badge">Structural focus</span>
          </div>
          <div className="priority-box">
            <div className="priority-tag">@luka.ono_ · Luka Bojičić Ono · Application Layer</div>
            <h2 className="priority-title">→ DEVELOPMENT PRIORITIES</h2>
            <div className="priority-grid">
              {priorityCards.map((item, index) => (
                <div key={item.benchmark_name} className="priority-item">
                  <div className="priority-num">{String(index + 1).padStart(2, "0")}</div>
                  <p className="priority-text">
                    <strong>{item.summary}.</strong> {item.value}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>
        <footer className="mt-14 border-t border-black/10 pt-6">
          <div className="flex flex-col gap-2 text-[9px] uppercase tracking-[0.18em] text-black/60 sm:flex-row sm:items-center sm:justify-between">
            <span className="font-semibold tracking-[0.25em]">LUKA ONO · @luka.ono_</span>
            <span className="text-center sm:text-left">
              Analytical framework: Darren Cahill &amp; Patrick Mouratoglou (tactical) · Olav Aleksander Bu (physiology/biochemistry)
              <br />
              [E] Peer-reviewed · ATP published · [I] Evidence-based inference · ITF granular stats limited in published literature
            </span>
            <span>March 2026</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
