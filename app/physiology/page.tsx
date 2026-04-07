import physData from "@/data/physiology.json";

// ── types ─────────────────────────────────────────────────────

type Zone = (typeof physData)["metabolic_zones"][number];
type HRVRow = (typeof physData)["hrv_decision_matrix"][number];
type LogEntry = (typeof physData)["daily_log"][number];

// ── data slices ───────────────────────────────────────────────

const zones = physData.metabolic_zones as Zone[];
const hrvMatrix = physData.hrv_decision_matrix as HRVRow[];
const dailyLog = physData.daily_log as LogEntry[];

// ── visual maps ───────────────────────────────────────────────

const zoneColors: Record<number, string> = {
  1: "#A5D6A7",
  2: "#64B5F6",
  3: "#FFB74D",
  4: "#E57373",
  5: "#CE93D8",
};

const hrvColor: Record<string, string> = {
  "Full Send": "var(--luka-challenger)",
  "Seguir Plano": "var(--luka-blue)",
  "Reduzir": "var(--luka-itf)",
  "Reset Total": "rgba(0,0,0,0.4)",
};

// ─────────────────────────────────────────────────────────────

export default function PhysiologyPage() {
  return (
    <>
      <header className="hero">
        <div className="hero-left">
          <div className="hero-tag">
            @luka.ono_ · Fisiologia & Monitoramento · Campinas, Brazil · Born Jan 28 2005
          </div>
          <h1>FISIOLOGIA<br />&amp; MONITOR.</h1>
          <div className="hero-sub">DAILY LOG · METABOLIC ZONES · HRV MATRIX · MONITORING PROTOCOLS</div>
        </div>
      </header>

      <div className="level-strip">
        <span className="ls-label">FRAMEWORK:</span>
        <span className="ls-note">Olav Aleksander Bu · Whoop · Lactate thresholds</span>
      </div>

      <main className="wrapper">

        {/* S01 — DAILY LOG */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">01</span>
            <span className="sec-title">Daily Log</span>
            <span className="sec-badge">HRV · Strain · Sleep</span>
          </div>
          <table className="ctable">
            <thead>
              <tr>
                <th className="th-hdr">Date</th>
                <th className="th-hdr">Recovery %</th>
                <th className="th-hdr">HRV (ms)</th>
                <th className="th-hdr">RHR (bpm)</th>
                <th className="th-hdr">Strain</th>
                <th className="th-hdr">sRPE</th>
                <th className="th-hdr">Sleep %</th>
                <th className="th-hdr">Notes</th>
              </tr>
            </thead>
            <tbody>
              {dailyLog.map((e) => (
                <tr key={e.date}>
                  <td className="row-label">{e.date}</td>
                  <td><span className="val val-atp">{e.recovery_pct}%</span></td>
                  <td><span className="val">{e.hrv_ms}</span></td>
                  <td><span className="val">{e.rhr_bpm}</span></td>
                  <td><span className="val">{e.strain}</span></td>
                  <td><span className="val">{e.srpe}</span></td>
                  <td><span className="val">{e.sleep_score_pct}%</span></td>
                  <td><span className="val-sub">{e.notes}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* S02 — METABOLIC ZONES */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">02</span>
            <span className="sec-title">Metabolic Zones</span>
            <span className="sec-badge">Zone 1–5 · Bu Method</span>
          </div>
          <div className="insight-grid" style={{ gridTemplateColumns: "repeat(5, 1fr)" }}>
            {zones.map((z) => (
              <div
                key={z.zone}
                className="insight-card"
                style={{ borderLeftColor: zoneColors[z.zone] ?? "#ccc" }}
              >
                <span className="ins-tag">Zone {z.zone}</span>
                <div className="ins-head">{z.focus}</div>
                <p className="ins-body">Lactate: <strong>{z.lactate_mmol} mmol/L</strong></p>
                <p className="ins-body">Strain: <strong>{z.whoop_strain}</strong></p>
                <p className="ins-body" style={{ marginTop: "6px", opacity: 0.7 }}>{z.bu_objective}</p>
              </div>
            ))}
          </div>
        </section>

        {/* S03 — HRV DECISION MATRIX */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">03</span>
            <span className="sec-title">HRV Decision Matrix</span>
            <span className="sec-badge">Daily readiness protocol</span>
          </div>
          <table className="ctable">
            <thead>
              <tr>
                <th className="th-hdr">HRV Status</th>
                <th className="th-hdr">Recovery ≥</th>
                <th className="th-hdr">Recommendation</th>
                <th className="th-hdr">Max Zone</th>
                <th className="th-hdr">Notes</th>
              </tr>
            </thead>
            <tbody>
              {hrvMatrix.map((row) => (
                <tr key={row.status}>
                  <td className="row-label">{row.status}</td>
                  <td><span className="val">{row.recovery_pct_min}%</span></td>
                  <td><span className="val" style={{ color: hrvColor[row.recommendation] ?? "inherit" }}>{row.recommendation}</span></td>
                  <td><span className="val">Z{row.max_zone}</span></td>
                  <td><span className="val-sub">{row.notes}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* S04 — MONITORING PROTOCOLS */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">04</span>
            <span className="sec-title">Monitoring Protocols</span>
            <span className="sec-badge">HRV · sRPE · Whoop</span>
          </div>
          <div className="rally-grid">
            <div className="insight-card ic-blue">
              <span className="ins-tag" style={{ color: "var(--luka-blue)" }}>HRV Morning</span>
              <div className="ins-head">Baseline Individual</div>
              <p className="ins-body">Medir ao acordar, antes de levantar. Nunca usar HRV em isolamento — combinar com RPE, qualidade do sono e questionário de bem-estar.</p>
              <p className="ins-tag" style={{ marginTop: "10px" }}>Alerta: queda &gt;15% por &gt;5 dias seguidos</p>
            </div>
            <div className="insight-card ic-teal">
              <span className="ins-tag" style={{ color: "var(--luka-challenger)" }}>sRPE · Session Load</span>
              <div className="ins-head">RPE × Duração (min)</div>
              <p className="ins-body">Registrar 30min pós-sessão. Alvo de jogo: 6–8 / 10. Acima de 8,5 sustentado = sessão excessiva. Variação de massa &lt;2% por sessão.</p>
              <p className="ins-tag" style={{ marginTop: "10px" }}>ACWR sweet spot: 0.8 – 1.3</p>
            </div>
            <div className="insight-card ic-amber">
              <span className="ins-tag" style={{ color: "var(--luka-itf)" }}>Recuperação Pós-Sessão</span>
              <div className="ins-head">Retorno em ≤72h</div>
              <p className="ins-body">HRV deve retornar ao baseline em até 72h após sessão difícil. Sem retorno = sessão excessiva. HRV-CV &gt;30% = sobrecarga acumulada.</p>
              <p className="ins-tag" style={{ marginTop: "10px" }}>Fonte: PMC 11204851</p>
            </div>
          </div>
        </section>

        {/* PRIORITY BOX */}
        <div className="luka-box">
          <div className="luka-box-tag">@luka.ono_ · Physiological Monitoring · April 2026</div>
          <h2>→ MONITORING PRIORITIES</h2>
          <div className="luka-points">
            <div className="lp">
              <div className="lp-num">01</div>
              <p className="lp-text">Estabelecer LT1/LT2 individuais via teste de lactato — zonas atualmente prescritas por FC genérica, o que reduz precisão da carga.</p>
            </div>
            <div className="lp">
              <div className="lp-num">02</div>
              <p className="lp-text">Registrar sRPE e HRV diariamente durante blocos de torneio para identificar sobrecarga acumulada antes que se torne lesão.</p>
            </div>
            <div className="lp">
              <div className="lp-num">03</div>
              <p className="lp-text">Manter ACWR entre 0.8–1.3 em stretches de torneios ITF — demanda glicolítica maior que ATP por set exige monitoramento ativo de carga.</p>
            </div>
          </div>
        </div>

      </main>
    </>
  );
}
