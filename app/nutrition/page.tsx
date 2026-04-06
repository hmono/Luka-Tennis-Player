import Link from "next/link";

import nutData from "@/data/nutrition.json";

// ── types ─────────────────────────────────────────────────────

type DailyTarget = (typeof nutData)["daily_targets"][number];
type PreTraining = (typeof nutData)["pre_training"][number];
type IntraTraining = (typeof nutData)["intra_training"][number];
type PostTraining = (typeof nutData)["post_training"][number];
type TournamentDay = (typeof nutData)["tournament_day"][number];

// ── data slices ───────────────────────────────────────────────

const dailyTargets = nutData.daily_targets as DailyTarget[];
const preTraining = nutData.pre_training as PreTraining[];
const intraTraining = nutData.intra_training as IntraTraining[];
const postTraining = nutData.post_training as PostTraining[];
const tournamentDay = nutData.tournament_day as TournamentDay[];

const bodyComposition = nutData.body_composition;

const preWindows = [...new Set(preTraining.map((p) => p.window))];
const tdPhases = ["pre_match", "during_match", "post_match"] as const;
const tdLabels: Record<string, string> = {
  pre_match: "Pre-Match",
  during_match: "During Match",
  post_match: "Post-Match",
};

// ── shared styles ─────────────────────────────────────────────

const tableClass =
  "w-full min-w-full text-sm [&_th]:px-4 [&_th]:py-3 [&_th]:text-left [&_th]:text-[10px] [&_th]:uppercase [&_th]:tracking-[0.16em] [&_td]:px-4 [&_td]:py-3";

// ─────────────────────────────────────────────────────────────

export default function NutritionPage() {
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
              @luka.ono_ · Nutrição & Saúde · Campinas, Brazil · Born Jan 28 2005
            </div>
            <h1 className="max-w-3xl text-5xl font-semibold leading-none tracking-tight sm:text-7xl">
              NUTRIÇÃO
              <br />& SAÚDE
            </h1>
            <div className="hero-sub">
              PARÂMETROS · PRÉ/DURANTE/PÓS · DIA DE TORNEIO · COMPOSIÇÃO CORPORAL
            </div>
          </div>
        </section>

        {/* LEVEL STRIP */}
        <section className="level-strip">
          <span className="level-label">FRAMEWORK:</span>
          <span className="level-note">Peter Attia · Olav Aleksander Bu · Sports Nutrition Evidence Base</span>
        </section>

        {/* S01 — PARÂMETROS BASAIS */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">01</span>
            <span className="section-title">Parâmetros Basais</span>
            <span className="section-badge">Macros · Hidratação · Daily targets</span>
          </div>
          <div className="surface-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className={tableClass}>
                <thead className="bg-black/[0.03] text-black/45">
                  <tr>
                    <th>Macronutriente</th>
                    <th>Quantidade</th>
                    <th>Base</th>
                    <th>Contexto</th>
                    <th>Framework</th>
                  </tr>
                </thead>
                <tbody>
                  {dailyTargets.map((t, i) => (
                    <tr key={i} className="border-t border-black/6">
                      <td className="font-semibold capitalize text-luka-blue">{t.macronutrient.replace(/_/g, " ")}</td>
                      <td className="font-medium">
                        {"amount_g_per_kg" in t ? `${t.amount_g_per_kg} g/kg` : `${(t as { amount_ml_per_kg?: string }).amount_ml_per_kg} ml/kg`}
                      </td>
                      <td className="text-black/55">{t.basis}</td>
                      <td className="text-black/55">{t.context}</td>
                      <td className="text-[10px] uppercase tracking-[0.14em] text-black/40">{t.framework}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* S02 — PRÉ-TREINO */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">02</span>
            <span className="section-title">Pré-Treino</span>
            <span className="section-badge">Timing · Glycogen loading</span>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {preWindows.map((window) => (
              <div key={window} className="surface-card overflow-hidden">
                <div className="border-b border-black/6 px-4 py-3 text-[10px] uppercase tracking-[0.16em] text-luka-blue">
                  {window}
                </div>
                <table className={tableClass}>
                  <thead className="bg-black/[0.03] text-black/45">
                    <tr>
                      <th>Item</th>
                      <th>Quantidade</th>
                      <th>Objetivo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preTraining.filter((p) => p.window === window).map((p, i) => (
                      <tr key={i} className="border-t border-black/6">
                        <td className="font-medium">{p.item}</td>
                        <td className="whitespace-nowrap text-black/65">{p.amount}</td>
                        <td className="text-black/55">{p.objective}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </section>

        {/* S03 — DURANTE */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">03</span>
            <span className="section-title">Durante o Treino</span>
            <span className="section-badge">Intra-session fueling</span>
          </div>
          {intraTraining.map((entry, i) => (
            <div key={i} className="grid gap-4 md:grid-cols-2">
              <div className="surface-card border-l-4 border-l-luka-blue p-6">
                <p className="text-[10px] uppercase tracking-[0.16em] text-black/40">Gatilho</p>
                <p className="mt-2 font-medium">{entry.trigger}</p>
                <div className="mt-4 grid grid-cols-3 gap-4">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.14em] text-black/40">Intervalo</p>
                    <p className="mt-1 font-semibold">{entry.interval_min} min</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.14em] text-black/40">Carbs</p>
                    <p className="mt-1 font-semibold">{entry.carbohydrate_g} g</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.14em] text-black/40">Fluido/h</p>
                    <p className="mt-1 font-semibold">{entry.fluid_ml_per_hour} ml</p>
                  </div>
                </div>
                <p className="mt-3 text-[10px] uppercase tracking-[0.14em] text-black/40">
                  Sódio: {entry.sodium_mg_per_hour} mg/h
                </p>
              </div>
              <div className="surface-card p-6">
                <p className="text-[10px] uppercase tracking-[0.16em] text-black/40">Fontes recomendadas</p>
                <ul className="mt-3 space-y-2">
                  {entry.sources.map((s) => (
                    <li key={s} className="text-sm text-black/65">{s}</li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </section>

        {/* S04 — PÓS-TREINO */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">04</span>
            <span className="section-title">Pós-Treino</span>
            <span className="section-badge">Recovery window · MPS</span>
          </div>
          <div className="surface-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className={tableClass}>
                <thead className="bg-black/[0.03] text-black/45">
                  <tr>
                    <th>Janela</th>
                    <th>Item</th>
                    <th>Quantidade</th>
                    <th>Objetivo</th>
                  </tr>
                </thead>
                <tbody>
                  {postTraining.map((p, i) => (
                    <tr key={i} className="border-t border-black/6">
                      <td className={`whitespace-nowrap font-medium ${p.window.includes("0–45") ? "text-luka-blue" : "text-black/55"}`}>
                        {p.window}
                      </td>
                      <td>{p.item}</td>
                      <td className="whitespace-nowrap text-black/65">{p.amount}</td>
                      <td className="text-black/55">{p.objective}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* S05 — DIA DE TORNEIO */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">05</span>
            <span className="section-title">Dia de Torneio</span>
            <span className="section-badge">Pre · During · Post match</span>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {tdPhases.map((phase) => (
              <div key={phase} className="surface-card overflow-hidden">
                <div className={`border-b border-black/6 px-4 py-3 text-[10px] uppercase tracking-[0.16em] ${
                  phase === "pre_match" ? "text-luka-blue" : phase === "during_match" ? "text-luka-challenger" : "text-luka-itf"
                }`}>
                  {tdLabels[phase]}
                </div>
                <div className="divide-y divide-black/6">
                  {tournamentDay.filter((t) => t.phase === phase).map((t, i) => (
                    <div key={i} className="px-4 py-3">
                      <p className="text-[10px] uppercase tracking-[0.14em] text-black/40">{t.window}</p>
                      <p className="mt-1 text-sm text-black/65">{t.protocol}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* S06 — COMPOSIÇÃO CORPORAL */}
        <section className="mt-14">
          <div className="section-head">
            <span className="section-num">06</span>
            <span className="section-title">Composição Corporal</span>
            <span className="section-badge">Targets · Fases</span>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="surface-card overflow-hidden">
              <div className="border-b border-black/6 px-4 py-3 text-[10px] uppercase tracking-[0.16em] text-black/45">
                Marcadores · ITF vs Challenger
              </div>
              <table className={tableClass}>
                <thead className="bg-black/[0.03] text-black/45">
                  <tr>
                    <th>Marker</th>
                    <th className="text-luka-itf">ITF M25</th>
                    <th className="text-luka-challenger">Challenger Target</th>
                  </tr>
                </thead>
                <tbody>
                  {bodyComposition.filter((b) => "itf_m25_reference" in b).map((b, i) => {
                    const row = b as { marker?: string; itf_m25_reference: string; challenger_target: string };
                    return (
                      <tr key={i} className="border-t border-black/6">
                        <td className="font-medium capitalize">{row.marker?.replace(/_/g, " ")}</td>
                        <td className="font-semibold text-luka-itf">{row.itf_m25_reference}</td>
                        <td className="font-semibold text-luka-challenger">{row.challenger_target}</td>
                      </tr>
                    );
                  })}
                  {bodyComposition.filter((b) => "value" in b).map((b, i) => {
                    const row = b as { marker?: string; value: string; context: string };
                    return (
                      <tr key={`v${i}`} className="border-t border-black/6">
                        <td className="font-medium capitalize">{row.marker?.replace(/_/g, " ")}</td>
                        <td colSpan={2} className="text-black/55">{row.value} <span className="text-[10px]">({row.context})</span></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="surface-card overflow-hidden">
              <div className="border-b border-black/6 px-4 py-3 text-[10px] uppercase tracking-[0.16em] text-black/45">
                Fases de Periodização Nutricional
              </div>
              <table className={tableClass}>
                <thead className="bg-black/[0.03] text-black/45">
                  <tr>
                    <th>Fase</th>
                    <th>Duração</th>
                    <th>Calórico</th>
                    <th>Foco</th>
                  </tr>
                </thead>
                <tbody>
                  {bodyComposition.filter((b) => "phase" in b && "caloric_target" in b).map((b, i) => {
                    const row = b as { phase: string; duration_weeks: string | number; caloric_target: string; focus: string };
                    return (
                      <tr key={i} className="border-t border-black/6">
                        <td className="font-medium capitalize">{row.phase.replace(/_/g, " ")}</td>
                        <td className="whitespace-nowrap text-black/55">{row.duration_weeks}w</td>
                        <td className="text-black/65">{row.caloric_target}</td>
                        <td className="text-black/55">{row.focus}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* PRIORITY BOX */}
        <section className="mt-14">
          <div className="priority-box">
            <div className="priority-tag">@luka.ono_ · Nutrição · April 2026</div>
            <h2 className="priority-title">→ NUTRITION PRIORITIES</h2>
            <div className="priority-grid">
              <div className="priority-item">
                <div className="priority-num">01</div>
                <p className="priority-text">
                  Janela de 0–45min pós-treino é crítica: 25–30g proteína + 1.0–1.2g/kg carboidrato. Perder essa janela atrasa MPS e reposição de glicogênio.
                </p>
              </div>
              <div className="priority-item">
                <div className="priority-num">02</div>
                <p className="priority-text">
                  Nunca aplicar déficit calórico durante torneios — performance e recuperação dependem de manutenção ou leve superávit calórico (+100 kcal/dia).
                </p>
              </div>
              <div className="priority-item">
                <div className="priority-num">03</div>
                <p className="priority-text">
                  Carbs no intra-treino (30–60g/45min) apenas em sessões acima de 60min ou Whoop Strain ≥14. Não suplementar em Zona 1–2 sem necessidade.
                </p>
              </div>
            </div>
          </div>
        </section>

      </div>
    </div>
  );
}
