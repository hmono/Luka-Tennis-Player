import Link from "next/link";

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

const hrvBadge: Record<string, string> = {
  "Full Send": "text-luka-challenger",
  "Seguir Plano": "text-luka-blue",
  "Reduzir": "text-luka-itf",
  "Reset Total": "text-black/40",
};

// ── shared styles ─────────────────────────────────────────────

const tableClass =
  "w-full min-w-full text-sm [&_th]:px-4 [&_th]:py-3 [&_th]:text-left [&_th]:text-[10px] [&_th]:uppercase [&_th]:tracking-[0.16em] [&_td]:px-4 [&_td]:py-3";

// ─────────────────────────────────────────────────────────────

export default function PhysiologyPage() {
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
              @luka.ono_ · Fisiologia & Monitoramento · Campinas, Brazil · Born Jan 28 2005
            </div>
            <h1 className="max-w-3xl text-5xl font-semibold leading-none tracking-tight sm:text-7xl">
              FISIOLOGIA
              <br />& MONITOR.
            </h1>
            <div className="hero-sub">
              DAILY LOG · METABOLIC ZONES · HRV MATRIX · MONITORING PROTOCOLS
            </div>
          </div>
        </section>

        {/* LEVEL STRIP */}
        <section className="level-strip">
          <span className="level-label">FRAMEWORK:</span>
          <span className="level-note">Olav Aleksander Bu · Whoop · Lactate thresholds</span>
        </section>

        {/* S01 — DAILY LOG */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">01</span>
            <span className="section-title">Daily Log</span>
            <span className="section-badge">HRV · Strain · Sleep</span>
          </div>
          <div className="surface-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className={tableClass}>
                <thead className="bg-black/[0.03] text-black/45">
                  <tr>
                    <th>Date</th>
                    <th>Recovery %</th>
                    <th>HRV (ms)</th>
                    <th>RHR (bpm)</th>
                    <th>Strain</th>
                    <th>sRPE</th>
                    <th>Sleep %</th>
                    <th>Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {dailyLog.map((e) => (
                    <tr key={e.date} className="border-t border-black/6">
                      <td className="whitespace-nowrap font-medium">{e.date}</td>
                      <td className="font-semibold text-luka-blue">{e.recovery_pct}%</td>
                      <td>{e.hrv_ms}</td>
                      <td>{e.rhr_bpm}</td>
                      <td>{e.strain}</td>
                      <td>{e.srpe}</td>
                      <td>{e.sleep_score_pct}%</td>
                      <td className="text-black/55">{e.notes}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* S02 — METABOLIC ZONES */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">02</span>
            <span className="section-title">Metabolic Zones</span>
            <span className="section-badge">Zone 1–5 · Bu Method</span>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {zones.map((z) => (
              <div
                key={z.zone}
                className="surface-card border-t-4 p-5"
                style={{ borderTopColor: zoneColors[z.zone] ?? "#ccc" }}
              >
                <p className="text-[10px] uppercase tracking-[0.16em] text-black/40">Zone {z.zone}</p>
                <h3 className="mt-2 text-lg font-semibold tracking-tight">{z.focus}</h3>
                <p className="mt-2 text-sm text-black/55">Lactate: <span className="font-medium">{z.lactate_mmol} mmol/L</span></p>
                <p className="text-sm text-black/55">Strain: <span className="font-medium">{z.whoop_strain}</span></p>
                <p className="mt-3 text-sm leading-5 text-black/40">{z.bu_objective}</p>
              </div>
            ))}
          </div>
        </section>

        {/* S03 — HRV DECISION MATRIX */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">03</span>
            <span className="section-title">HRV Decision Matrix</span>
            <span className="section-badge">Daily readiness protocol</span>
          </div>
          <div className="surface-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className={tableClass}>
                <thead className="bg-black/[0.03] text-black/45">
                  <tr>
                    <th>HRV Status</th>
                    <th>Recovery ≥</th>
                    <th>Recommendation</th>
                    <th>Max Zone</th>
                    <th>Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {hrvMatrix.map((row) => (
                    <tr key={row.status} className="border-t border-black/6">
                      <td className="font-medium">{row.status}</td>
                      <td>{row.recovery_pct_min}%</td>
                      <td className={`font-semibold ${hrvBadge[row.recommendation] ?? ""}`}>
                        {row.recommendation}
                      </td>
                      <td>Z{row.max_zone}</td>
                      <td className="text-black/55">{row.notes}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* S04 — MONITORING PROTOCOLS */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">04</span>
            <span className="section-title">Monitoring Protocols</span>
            <span className="section-badge">HRV · sRPE · Whoop</span>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="surface-card border-l-4 border-l-luka-blue p-6">
              <p className="text-[10px] uppercase tracking-[0.16em] text-luka-blue">HRV Morning</p>
              <h3 className="mt-2 text-xl font-semibold tracking-tight">Baseline Individual</h3>
              <p className="mt-3 text-sm leading-6 text-black/55">
                Medir ao acordar, antes de levantar. Nunca usar HRV em isolamento — combinar com RPE, qualidade do sono e questionário de bem-estar.
              </p>
              <p className="mt-3 text-[10px] uppercase tracking-[0.16em] text-black/40">Alerta: queda &gt;15% por &gt;5 dias seguidos</p>
            </div>
            <div className="surface-card border-l-4 border-l-luka-challenger p-6">
              <p className="text-[10px] uppercase tracking-[0.16em] text-luka-challenger">sRPE · Session Load</p>
              <h3 className="mt-2 text-xl font-semibold tracking-tight">RPE × Duração (min)</h3>
              <p className="mt-3 text-sm leading-6 text-black/55">
                Registrar 30min pós-sessão. Alvo de jogo: 6–8 / 10. Acima de 8,5 sustentado = sessão excessiva. Variação de massa &lt;2% por sessão.
              </p>
              <p className="mt-3 text-[10px] uppercase tracking-[0.16em] text-black/40">ACWR sweet spot: 0.8 – 1.3</p>
            </div>
            <div className="surface-card border-l-4 border-l-luka-itf p-6">
              <p className="text-[10px] uppercase tracking-[0.16em] text-luka-itf">Recuperação Pós-Sessão</p>
              <h3 className="mt-2 text-xl font-semibold tracking-tight">Retorno em ≤72h</h3>
              <p className="mt-3 text-sm leading-6 text-black/55">
                HRV deve retornar ao baseline em até 72h após sessão difícil. Sem retorno = sessão excessiva. HRV-CV &gt;30% = sobrecarga acumulada.
              </p>
              <p className="mt-3 text-[10px] uppercase tracking-[0.16em] text-black/40">Fonte: PMC 11204851</p>
            </div>
          </div>
        </section>

        {/* PRIORITY BOX */}
        <section className="mt-14">
          <div className="priority-box">
            <div className="priority-tag">@luka.ono_ · Physiological Monitoring · April 2026</div>
            <h2 className="priority-title">→ MONITORING PRIORITIES</h2>
            <div className="priority-grid">
              <div className="priority-item">
                <div className="priority-num">01</div>
                <p className="priority-text">
                  Estabelecer LT1/LT2 individuais via teste de lactato — zonas atualmente prescritas por FC genérica, o que reduz precisão da carga.
                </p>
              </div>
              <div className="priority-item">
                <div className="priority-num">02</div>
                <p className="priority-text">
                  Registrar sRPE e HRV diariamente durante blocos de torneio para identificar sobrecarga acumulada antes que se torne lesão.
                </p>
              </div>
              <div className="priority-item">
                <div className="priority-num">03</div>
                <p className="priority-text">
                  Manter ACWR entre 0.8–1.3 em stretches de torneios ITF — demanda glicolítica maior que ATP por set exige monitoramento ativo de carga.
                </p>
              </div>
            </div>
          </div>
        </section>

      </div>
    </div>
  );
}
