import { Fragment } from "react";
import Link from "next/link";
import { getPlayerProfile } from "@/lib/benchmarks";
import { formatRank, getCareerHighs, getLatestRankings } from "@/lib/career";

const player = getPlayerProfile();
const careerHighs = getCareerHighs();
const latestRankings = getLatestRankings();

// Age — computed at build time from ISO birthDate
const _birth = new Date(player.birthDate);
const _now   = new Date();
let age = _now.getFullYear() - _birth.getFullYear();
if (
  _now.getMonth() < _birth.getMonth() ||
  (_now.getMonth() === _birth.getMonth() && _now.getDate() < _birth.getDate())
) age--;

const handLabel     = player.hand === "right" ? "RH" : "LH";
const backhandLabel = player.backhand === "two-handed" ? "2HBH" : "1HBH";
const monthYear     = _now.toLocaleDateString("en-US", { month: "long", year: "numeric" });

const stats = [
  { value: String(age),                                          label: `Age · DOB Jan ${_birth.getFullYear()}` },
  { value: formatRank(careerHighs?.singles ?? null),            label: "ATP Singles Career High" },
  { value: formatRank(careerHighs?.doubles ?? null),            label: "ATP Doubles Career High" },
  { value: player.tournamentsPlayed.itfFutures,                  label: "ITF Future Tournaments" },
  { value: String(player.tournamentsPlayed.challenger),          label: "Challenger Appearances" },
  { value: `${handLabel} · ${backhandLabel}`,                    label: `Style · ${player.heightCm}cm / ${player.weightKg}kg` },
];

const modules = [
  {
    href: "/tennis-level-comparison",
    tag: "Module 01 · Benchmarks",
    title: "Level\nComparison",
    desc: "Structural benchmarks across ATP Tour, Challenger, and ITF M25/M15. Points per game, rally distribution, serve/return asymmetry, and key findings for Luka's development path.",
    status: "live",
    accent: "linear-gradient(90deg,var(--luka-blue),var(--luka-challenger),var(--luka-itf))",
  },
  {
    href: "/career",
    tag: "Module 02 · Career",
    title: "Career &\nRanking",
    desc: "Tournament results, ranking history, and career trajectory. ITF and ATP point progression, surface breakdown, and win/loss records by tournament level.",
    status: "live",
    accent: "var(--luka-blue)",
  },
  {
    href: "/tactics",
    tag: "Module 03 · Tactics",
    title: "Tactics &\nGame Patterns",
    desc: "Pattern-of-play analysis based on Cahill, Mouratoglou, and Ferrero frameworks. Serve construction, rally patterns, transition quality, and tactical priorities by surface.",
    status: "live",
    accent: "var(--luka-challenger)",
  },
  {
    href: "/physical",
    tag: "Module 04 · Physical",
    title: "Physical\nTraining",
    desc: "Periodization protocols, training load metrics, and physical development targets. Strength, speed, and endurance benchmarks aligned to ITF and Challenger metabolic demands.",
    status: "live",
    accent: "var(--luka-physical)",
  },
  {
    href: "/physiology",
    tag: "Module 05 · Physiology",
    title: "Physiology &\nMonitoring",
    desc: "Whoop band data: HRV, recovery score, sleep, and strain. Match and training load monitoring aligned to Olav Aleksander Bu's physiological framework for elite tennis.",
    status: "live",
    accent: "var(--luka-itf)",
  },
  {
    href: "/nutrition",
    tag: "Module 06 · Nutrition",
    title: "Nutrition &\nHealth",
    desc: "Nutrition protocols and health guidelines based on Peter Attia and Olav Aleksander Bu frameworks. Tournament nutrition, recovery fueling, and body composition targets.",
    status: "live",
    accent: "var(--luka-nutrition)",
  },
];

const priorities = [
  "Build serve hold rate to Challenger norms (≥83%). Current ITF hold rate (~68%) is a structural liability. Requires placement repeatability, pressure-routine management, and 1st serve % consistently above 60%.",
  "Train the 5–8 shot construction block explicitly. Practice design must extend beyond S+1/R+1 to systematic 3rd and 4th shot patterns off both wings.",
  "Close the serve/return asymmetry gap: 9pp → 16pp. Serve dominance is the architectural target on the path from ITF to Challenger.",
  "Periodize energy systems for ITF metabolic reality. Recovery and nutrition periodization must account for higher per-set stress from more contested points.",
];

export default function HomePage() {
  return (
    <>
      <header className="hero">
        <div className="hero-left">
          <div className="hero-tag">
            @{player.handle} · Professional Tennis Player · {player.basedIn} · Born Jan 28 {_birth.getFullYear()}
          </div>
          <h1>LUKA ONO<br />ANALYTICS</h1>
          <div className="hero-sub">DATA-DRIVEN PERFORMANCE INTELLIGENCE · {monthYear.toUpperCase()}</div>
        </div>
      </header>

      <div className="player-strip">
        {stats.map((stat, i) => (
          <Fragment key={stat.label}>
            {i > 0 && <div className="stat-divider" />}
            <div className="stat-pill">
              <span className="stat-pill-val">{stat.value}</span>
              <span className="stat-pill-label">{stat.label}</span>
            </div>
          </Fragment>
        ))}
      </div>

      <div className="level-strip">
        <span className="ls-label">CAREER PATH:</span>
        <div className="ls-item active">
          <div className="ls-dot" style={{ background: "var(--luka-itf)" }} />
          <span style={{ color: "var(--luka-itf)" }}>ITF M25/M15</span>
          <span style={{ color: "rgba(255,255,255,0.35)", fontSize: "8.5px", marginLeft: "4px" }}>
            Current · ATP {formatRank(latestRankings?.singles.rank ?? null)}
          </span>
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
        <span className="ls-note">Coaches: {player.coaches.join(" · ")}</span>
      </div>

      <main className="wrapper">
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">01</span>
            <span className="sec-title">Analytics Modules</span>
            <span className="sec-badge">6 domains</span>
          </div>
          <div className="module-grid">
            {modules.map((module) => (
              <Link key={module.tag} href={module.href} className="module-card">
                <div className="mc-accent" style={{ background: module.accent }} />
                <div className="mc-body">
                  <span className="mc-tag">{module.tag}</span>
                  <div className="mc-title">
                    {module.title.split("\n").map((line) => (
                      <span key={line} style={{ display: "block" }}>
                        {line}
                      </span>
                    ))}
                  </div>
                  <p className="mc-desc">{module.desc}</p>
                </div>
                <div className="mc-footer">
                  <span className={`mc-status ${module.status === "live" ? "live" : "soon"}`}>
                    {module.status === "live" ? "Live" : "Coming soon"}
                  </span>
                  <span className="mc-arrow">→</span>
                </div>
              </Link>
            ))}
          </div>
        </section>

        <section className="section">
          <div className="sec-head">
            <span className="sec-num">02</span>
            <span className="sec-title">Development Priorities</span>
            <span className="sec-badge">Sprint 02 · {monthYear}</span>
          </div>
          <div className="luka-box">
            <div className="luka-box-tag">@{player.handle} · {player.name} · Application Layer</div>
            <h2>→ CURRENT FOCUS AREAS</h2>
            <div className="luka-points">
              {priorities.map((text, index) => (
                <div key={text} className="lp">
                  <span className="lp-num">{String(index + 1).padStart(2, "0")}</span>
                  <span className="lp-text">{text}</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>
    </>
  );
}
