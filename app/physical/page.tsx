import Link from "next/link";

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

const blockBorder: Record<string, string> = {
  load: "border-l-luka-blue",
  adaptation_deload: "border-l-luka-challenger",
  double_threshold_day: "border-l-luka-itf",
};

const dayTypeBadge: Record<string, string> = {
  double_threshold: "text-luka-itf",
  aerobic_base: "text-luka-blue",
  recovery: "text-luka-challenger",
  rest: "text-black/40",
};

// ── shared styles ─────────────────────────────────────────────

const tableClass =
  "w-full min-w-full text-sm [&_th]:px-4 [&_th]:py-3 [&_th]:text-left [&_th]:text-[10px] [&_th]:uppercase [&_th]:tracking-[0.16em] [&_td]:px-4 [&_td]:py-3";

// ─────────────────────────────────────────────────────────────

export default function PhysicalPage() {
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
              @luka.ono_ · Physical Training · Campinas, Brazil · Born Jan 28 2005
            </div>
            <h1 className="max-w-3xl text-5xl font-semibold leading-none tracking-tight sm:text-7xl">
              PHYSICAL
              <br />
              TRAINING
            </h1>
            <div className="hero-sub">
              PERIODIZATION · METABOLIC ZONES · WEEKLY STRUCTURE · BENCHMARKS
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
          <span className="level-note">Framework: Olav Bu · Peter Attia · Gabbett ACWR</span>
        </section>

        {/* S01 — PERIODIZATION BLOCKS */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">01</span>
            <span className="section-title">Periodization Blocks</span>
            <span className="section-badge">Load · Deload · Double Threshold</span>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {blocks.map((b) => (
              <div key={b.block} className={`surface-card border-l-4 p-6 ${blockBorder[b.block] ?? "border-l-luka-dark"}`}>
                <p className="text-[10px] uppercase tracking-[0.16em] text-black/40">
                  {b.duration_weeks ? `${b.duration_weeks}w block` : "protocol"}
                </p>
                <h3 className="mt-2 text-xl font-semibold tracking-tight capitalize">
                  {b.block.replace(/_/g, " ")}
                </h3>
                <p className="mt-2 text-sm font-medium">{b.objective}</p>
                {"principle" in b && b.principle && (
                  <p className="mt-3 text-sm leading-6 text-black/55">{b.principle}</p>
                )}
                {"sessions" in b && Array.isArray(b.sessions) && (
                  <ul className="mt-3 space-y-1">
                    {(b.sessions as { slot: string; type: string; lactate_ceiling_mmol?: number; lactate_range_mmol?: string }[]).map((s) => (
                      <li key={s.slot} className="text-sm text-black/55">
                        <span className="font-medium capitalize">{s.slot}:</span>{" "}
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
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">02</span>
            <span className="section-title">Metabolic Zones</span>
            <span className="section-badge">Zone 1–4</span>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {zones.map((z) => (
              <div
                key={z.zone}
                className="surface-card border-t-4 p-6"
                style={{ borderTopColor: zoneColors[z.zone] ?? "#ccc" }}
              >
                <p className="text-[10px] uppercase tracking-[0.16em] text-black/40">Zone {z.zone}</p>
                <h3 className="mt-2 text-xl font-semibold tracking-tight">{z.metabolic_state}</h3>
                <p className="mt-2 text-sm text-black/55">{z.training_type}</p>
                <p className="mt-3 text-sm leading-6 text-black/40">{z.purpose}</p>
              </div>
            ))}
          </div>
        </section>

        {/* S03 — WEEKLY STRUCTURE */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">03</span>
            <span className="section-title">Weekly Structure</span>
            <span className="section-badge">HRV-guided</span>
          </div>
          <div className="surface-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className={tableClass}>
                <thead className="bg-black/[0.03] text-black/45">
                  <tr>
                    <th>Day Type</th>
                    <th>Freq / Week</th>
                    <th>Sessions</th>
                    <th>HRV Requirement</th>
                  </tr>
                </thead>
                <tbody>
                  {weeklyStructure.map((d) => (
                    <tr key={d.day_type} className="border-t border-black/6 align-top">
                      <td className={`font-semibold capitalize ${dayTypeBadge[d.day_type] ?? ""}`}>
                        {d.day_type.replace(/_/g, " ")}
                      </td>
                      <td className="whitespace-nowrap">{d.frequency_per_week}×</td>
                      <td>
                        {d.sessions.length > 0 ? (
                          <ul className="space-y-1">
                            {d.sessions.map((s) => (
                              <li key={s} className="text-black/65">{s}</li>
                            ))}
                          </ul>
                        ) : (
                          <span className="text-black/25">—</span>
                        )}
                      </td>
                      <td className="text-black/55">{d.hrv_requirement}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* S04 — STRENGTH BENCHMARKS */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">04</span>
            <span className="section-title">Strength Benchmarks</span>
            <span className="section-badge">ITF → Challenger → ATP</span>
          </div>
          <div className="surface-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className={tableClass}>
                <thead className="bg-black/[0.03] text-black/45">
                  <tr>
                    <th>Marker</th>
                    <th className="text-luka-itf">ITF M25 (Current)</th>
                    <th className="text-luka-challenger">Challenger Target</th>
                    <th className="text-luka-atp">ATP Elite</th>
                  </tr>
                </thead>
                <tbody>
                  {benchmarks.map((b) => (
                    <tr key={b.marker} className="border-t border-black/6">
                      <td className="font-medium">{b.marker.replace(/_/g, " ")}</td>
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
            <div className="priority-tag">@luka.ono_ · Physical Development · April 2026</div>
            <h2 className="priority-title">→ PHYSICAL PRIORITIES</h2>
            <div className="priority-grid">
              <div className="priority-item">
                <div className="priority-num">01</div>
                <p className="priority-text">
                  Base aeróbica (Zona 2) provavelmente subdimensionada em temporada de torneios — 77% do jogo abaixo de VT1. Aeróbico é o fundo de recuperação que sustenta o circuito ITF.
                </p>
              </div>
              <div className="priority-item">
                <div className="priority-num">02</div>
                <p className="priority-text">
                  VO2max desconhecido — sem baseline para prescrição precisa de zonas. Mínimo competitivo: &gt;50 ml/kg/min; alvo Luka: ≥60. Teste de campo prioritário.
                </p>
              </div>
              <div className="priority-item">
                <div className="priority-num">03</div>
                <p className="priority-text">
                  Demanda glicolítica ITF subestimada — 2,0–2,8 breaks/set, mais pontos contestados que ATP. Protocolos de recuperação devem refletir esse volume real.
                </p>
              </div>
            </div>
          </div>
        </section>

      </div>
    </div>
  );
}
