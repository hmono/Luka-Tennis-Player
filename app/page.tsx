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
    <div className="section-block">
      <div className="shell">
        <section className="hero-panel">
          <div className="relative z-10">
            <div className="hero-tag">
              @luka.ono_ · Professional Tennis Player · Campinas, Brazil · Born Jan 28 2005
            </div>
            <h1 className="max-w-3xl text-5xl font-semibold leading-none tracking-tight sm:text-7xl">
              LUKA ONO
              <br />
              ANALYTICS
            </h1>
            <div className="hero-sub">DATA-DRIVEN PERFORMANCE INTELLIGENCE · MAY 2026</div>
          </div>
        </section>

        <section className="stat-strip">
          {stats.map((stat) => (
            <div key={stat.label} className="stat-item">
              <span className="stat-value">{stat.value}</span>
              <span className="stat-label">{stat.label}</span>
            </div>
          ))}
        </section>

        <section className="level-strip">
          <span className="level-label">CAREER PATH:</span>
          <div className="level-item font-semibold">
            <span className="level-dot" style={{ background: "#f5a623", boxShadow: "0 0 0 2px rgba(245,166,35,0.35)" }} />
            <span className="text-[#f5a623]">ITF M25/M15</span>
            <span className="text-[10px] text-white/35">Current · ATP ~1.951</span>
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

        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">01</span>
            <span className="section-title">Analytics Modules</span>
            <span className="section-badge">6 domains</span>
          </div>
          <div className="module-grid">
            {modules.map((module) => (
              <Link key={module.tag} href={module.href} className="module-card">
                <div className="module-accent" style={{ background: module.accent }} />
                <div className="module-body">
                  <span className="module-tag">{module.tag}</span>
                  <h2 className="module-title">
                    {module.title.split("\n").map((line) => (
                      <span key={line} className="block">
                        {line}
                      </span>
                    ))}
                  </h2>
                  <p className="module-desc">{module.desc}</p>
                </div>
                <div className="module-footer">
                  <span
                    className={`module-status ${module.status === "live" ? "module-status-live" : "module-status-soon"}`}
                  >
                    {module.status === "live" ? "Live" : "Coming soon"}
                  </span>
                  <span className="module-arrow">→</span>
                </div>
              </Link>
            ))}
          </div>
        </section>

        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">02</span>
            <span className="section-title">Development Priorities</span>
            <span className="section-badge">Sprint 02 · April 2026</span>
          </div>
          <div className="priority-box">
            <div className="priority-tag">@luka.ono_ · Luka Bojičić Ono · Application Layer</div>
            <h2 className="priority-title">→ CURRENT FOCUS AREAS</h2>
            <div className="priority-grid">
              {priorities.map((text, index) => (
                <div key={text} className="priority-item">
                  <div className="priority-num">{String(index + 1).padStart(2, "0")}</div>
                  <p className="priority-text">{text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
