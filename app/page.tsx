import Link from "next/link";

const stats = [
  { value: "21", label: "Age · DOB Jan 2005" },
  { value: "#1.827", label: "ATP Singles Career High" },
  { value: "#1.784", label: "ATP Doubles Career High" },
  { value: "30+", label: "ITF Future Tournaments" },
  { value: "4", label: "Challenger Appearances" },
  { value: "RH · 2HBH", label: "Style · 180cm / 75kg" },
];

const modules = [
  {
    href: "/tennis-level-comparison",
    tag: "Module 01 · Benchmarks",
    title: "Level\nComparison",
    desc: "Structural benchmarks across ATP Tour, Challenger, and ITF M25/M15. Points per game, rally distribution, serve/return asymmetry, and key findings for Luka's development path.",
    status: "live",
    accent: "linear-gradient(90deg,var(--luka-blue),#1cc8a0,#f5a623)",
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
    accent: "#1cc8a0",
  },
  {
    href: "/physical",
    tag: "Module 04 · Physical",
    title: "Physical\nTraining",
    desc: "Periodization protocols, training load metrics, and physical development targets. Strength, speed, and endurance benchmarks aligned to ITF and Challenger metabolic demands.",
    status: "live",
    accent: "#7c6ef5",
  },
  {
    href: "/physiology",
    tag: "Module 05 · Physiology",
    title: "Physiology &\nMonitoring",
    desc: "Whoop band data: HRV, recovery score, sleep, and strain. Match and training load monitoring aligned to Olav Aleksander Bu's physiological framework for elite tennis.",
    status: "live",
    accent: "#f5a623",
  },
  {
    href: "/nutrition",
    tag: "Module 06 · Nutrition",
    title: "Nutrition &\nHealth",
    desc: "Nutrition protocols and health guidelines based on Peter Attia and Olav Aleksander Bu frameworks. Tournament nutrition, recovery fueling, and body composition targets.",
    status: "live",
    accent: "#e05c3b",
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
            @luka.ono_ · Professional Tennis Player · Campinas, Brazil · Born Jan 28 2005
          </div>
          <h1>LUKA ONO<br />ANALYTICS</h1>
          <div className="hero-sub">DATA-DRIVEN PERFORMANCE INTELLIGENCE · MAY 2026</div>
        </div>
      </header>

      <div className="player-strip">
        {stats.map((stat, i) => (
          <>
            {i > 0 && <div key={`div-${stat.label}`} className="stat-divider" />}
            <div key={stat.label} className="stat-pill">
              <span className="stat-pill-val">{stat.value}</span>
              <span className="stat-pill-label">{stat.label}</span>
            </div>
          </>
        ))}
      </div>

      <div className="level-strip">
        <span className="ls-label">CAREER PATH:</span>
        <div className="ls-item active">
          <div className="ls-dot" style={{ background: "#f5a623" }} />
          <span style={{ color: "#f5a623" }}>ITF M25/M15</span>
          <span style={{ color: "rgba(255,255,255,0.35)", fontSize: "8.5px", marginLeft: "4px" }}>Current · ATP ~1.951</span>
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
            <span className="sec-badge">Sprint 02 · April 2026</span>
          </div>
          <div className="luka-box">
            <div className="luka-box-tag">@luka.ono_ · Luka Bojičić Ono · Application Layer</div>
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
