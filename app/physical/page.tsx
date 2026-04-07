import physicalData from "@/data/physical.json";

// ── types ─────────────────────────────────────────────────────

type PeriodizationBlock = (typeof physicalData)["periodization_blocks"][number];
type MetabolicZone = (typeof physicalData)["metabolic_zones"][number];
type Benchmark = (typeof physicalData)["strength_benchmarks"][number];
type WeekDay = (typeof physicalData)["weekly_structure"][number];

// ── data slices ───────────────────────────────────────────────

const blocks = physicalData.periodization_blocks as PeriodizationBlock[];
const zones = physicalData.metabolic_zones as MetabolicZone[];
const benchmarks = physicalData.strength_benchmarks as Benchmark[];
const weeklyStructure = physicalData.weekly_structure as WeekDay[];

// ── visual maps ───────────────────────────────────────────────

const zoneColors: Record<number, string> = {
  1: "#A5D6A7",
  2: "#64B5F6",
  3: "#FFB74D",
  4: "#E57373",
};

const blockAccent: Record<string, string> = {
  load: "var(--luka-blue)",
  adaptation_deload: "var(--luka-challenger)",
  double_threshold_day: "var(--luka-itf)",
};

const dayTypeColor: Record<string, string> = {
  double_threshold: "var(--luka-itf)",
  aerobic_base: "var(--luka-blue)",
  recovery: "var(--luka-challenger)",
  rest: "rgba(0,0,0,0.4)",
};

// ─────────────────────────────────────────────────────────────

export default function PhysicalPage() {
  return (
    <>
      <header className="hero">
        <div className="hero-left">
          <div className="hero-tag">
            @luka.ono_ · Physical Training · Campinas, Brazil · Born Jan 28 2005
          </div>
          <h1>PHYSICAL<br />TRAINING</h1>
          <div className="hero-sub">PERIODIZATION · METABOLIC ZONES · WEEKLY STRUCTURE · BENCHMARKS</div>
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
        <span className="ls-note">Framework: Olav Bu · Peter Attia · Gabbett ACWR</span>
      </div>

      <main className="wrapper">

        {/* S01 — PERIODIZATION BLOCKS */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">01</span>
            <span className="sec-title">Periodization Blocks</span>
            <span className="sec-badge">Load · Deload · Double Threshold</span>
          </div>
          <div className="rally-grid">
            {blocks.map((b) => (
              <div
                key={b.block}
                className="insight-card"
                style={{ borderLeftColor: blockAccent[b.block] ?? "var(--luka-dark)" }}
              >
                <span className="ins-tag">{b.duration_weeks ? `${b.duration_weeks}w block` : "protocol"}</span>
                <div className="ins-head" style={{ textTransform: "capitalize" }}>{b.block.replace(/_/g, " ")}</div>
                <p className="ins-body" style={{ fontWeight: 500 }}>{b.objective}</p>
                {"principle" in b && b.principle && (
                  <p className="ins-body">{b.principle}</p>
                )}
                {"sessions" in b && Array.isArray(b.sessions) && (
                  <ul style={{ marginTop: "8px", paddingLeft: "0", listStyle: "none" }}>
                    {(b.sessions as { slot: string; type: string; lactate_ceiling_mmol?: number; lactate_range_mmol?: string }[]).map((s) => (
                      <li key={s.slot} className="ins-body">
                        <strong style={{ textTransform: "capitalize" }}>{s.slot}:</strong>{" "}
                        {s.type}
                        {s.lactate_ceiling_mmol && ` · lactate ≤${s.lactate_ceiling_mmol} mmol/L`}
                        {s.lactate_range_mmol && ` · lactate ${s.lactate_range_mmol} mmol/L`}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* S02 — METABOLIC ZONES */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">02</span>
            <span className="sec-title">Metabolic Zones</span>
            <span className="sec-badge">Zone 1–4</span>
          </div>
          <div className="insight-grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
            {zones.map((z) => (
              <div
                key={z.zone}
                className="insight-card"
                style={{ borderLeftColor: zoneColors[z.zone] ?? "#ccc" }}
              >
                <span className="ins-tag">Zone {z.zone}</span>
                <div className="ins-head">{z.metabolic_state}</div>
                <p className="ins-body">{z.training_type}</p>
                <p className="ins-body" style={{ marginTop: "6px", opacity: 0.7 }}>{z.purpose}</p>
              </div>
            ))}
          </div>
        </section>

        {/* S03 — WEEKLY STRUCTURE */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">03</span>
            <span className="sec-title">Weekly Structure</span>
            <span className="sec-badge">HRV-guided</span>
          </div>
          <table className="ctable">
            <thead>
              <tr>
                <th className="th-hdr">Day Type</th>
                <th className="th-hdr">Freq / Week</th>
                <th className="th-hdr">Sessions</th>
                <th className="th-hdr">HRV Requirement</th>
              </tr>
            </thead>
            <tbody>
              {weeklyStructure.map((d) => (
                <tr key={d.day_type}>
                  <td className="row-label" style={{ color: dayTypeColor[d.day_type] ?? "inherit", textTransform: "capitalize" }}>
                    {d.day_type.replace(/_/g, " ")}
                  </td>
                  <td><span className="val">{d.frequency_per_week}×</span></td>
                  <td>
                    {d.sessions.length > 0 ? (
                      <ul style={{ listStyle: "none", padding: 0 }}>
                        {d.sessions.map((s) => (
                          <li key={s} className="val-sub">{s}</li>
                        ))}
                      </ul>
                    ) : (
                      <span className="val-sub">—</span>
                    )}
                  </td>
                  <td><span className="val-sub">{d.hrv_requirement}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* S04 — STRENGTH BENCHMARKS */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">04</span>
            <span className="sec-title">Strength Benchmarks</span>
            <span className="sec-badge">ITF → Challenger → ATP</span>
          </div>
          <table className="ctable">
            <thead>
              <tr>
                <th className="th-hdr">Marker</th>
                <th className="th-itf">ITF M25 (Current)</th>
                <th className="th-chal">Challenger Target</th>
                <th className="th-atp">ATP Elite</th>
              </tr>
            </thead>
            <tbody>
              {benchmarks.map((b) => (
                <tr key={b.marker}>
                  <td className="row-label">{b.marker.replace(/_/g, " ")}</td>
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
          <div className="luka-box-tag">@luka.ono_ · Physical Development · April 2026</div>
          <h2>→ PHYSICAL PRIORITIES</h2>
          <div className="luka-points">
            <div className="lp">
              <div className="lp-num">01</div>
              <p className="lp-text">Base aeróbica (Zona 2) provavelmente subdimensionada em temporada de torneios — 77% do jogo abaixo de VT1. Aeróbico é o fundo de recuperação que sustenta o circuito ITF.</p>
            </div>
            <div className="lp">
              <div className="lp-num">02</div>
              <p className="lp-text">VO2max desconhecido — sem baseline para prescrição precisa de zonas. Mínimo competitivo: &gt;50 ml/kg/min; alvo Luka: ≥60. Teste de campo prioritário.</p>
            </div>
            <div className="lp">
              <div className="lp-num">03</div>
              <p className="lp-text">Demanda glicolítica ITF subestimada — 2,0–2,8 breaks/set, mais pontos contestados que ATP. Protocolos de recuperação devem refletir esse volume real.</p>
            </div>
          </div>
        </div>

      </main>
    </>
  );
}
