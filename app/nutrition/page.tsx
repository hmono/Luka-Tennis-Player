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
const tdColor: Record<string, string> = {
  pre_match: "var(--luka-blue)",
  during_match: "var(--luka-challenger)",
  post_match: "var(--luka-itf)",
};

// ─────────────────────────────────────────────────────────────

export default function NutritionPage() {
  return (
    <>
      <header className="hero">
        <div className="hero-left">
          <div className="hero-tag">
            @luka.ono_ · Nutrição & Saúde · Campinas, Brazil · Born Jan 28 2005
          </div>
          <h1>NUTRIÇÃO<br />&amp; SAÚDE</h1>
          <div className="hero-sub">PARÂMETROS · PRÉ/DURANTE/PÓS · DIA DE TORNEIO · COMPOSIÇÃO CORPORAL</div>
        </div>
      </header>

      <div className="level-strip">
        <span className="ls-label">FRAMEWORK:</span>
        <span className="ls-note">Peter Attia · Olav Aleksander Bu · Sports Nutrition Evidence Base</span>
      </div>

      <main className="wrapper">

        {/* S01 — PARÂMETROS BASAIS */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">01</span>
            <span className="sec-title">Parâmetros Basais</span>
            <span className="sec-badge">Macros · Hidratação · Daily targets</span>
          </div>
          <table className="ctable">
            <thead>
              <tr>
                <th className="th-hdr">Macronutriente</th>
                <th className="th-hdr">Quantidade</th>
                <th className="th-hdr">Base</th>
                <th className="th-hdr">Contexto</th>
                <th className="th-hdr">Framework</th>
              </tr>
            </thead>
            <tbody>
              {dailyTargets.map((t, i) => (
                <tr key={i}>
                  <td className="row-label" style={{ color: "var(--luka-blue)", textTransform: "capitalize" }}>
                    {t.macronutrient.replace(/_/g, " ")}
                  </td>
                  <td>
                    <span className="val">
                      {"amount_g_per_kg" in t ? `${t.amount_g_per_kg} g/kg` : `${(t as { amount_ml_per_kg?: string }).amount_ml_per_kg} ml/kg`}
                    </span>
                  </td>
                  <td><span className="val-sub">{t.basis}</span></td>
                  <td><span className="val-sub">{t.context}</span></td>
                  <td><span className="val-sub">{t.framework}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* S02 — PRÉ-TREINO */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">02</span>
            <span className="sec-title">Pré-Treino</span>
            <span className="sec-badge">Timing · Glycogen loading</span>
          </div>
          <div className="sv-grid">
            {preWindows.map((window) => (
              <div key={window} className="sv-card">
                <div className="sv-title" style={{ color: "var(--luka-blue)" }}>{window}</div>
                <table className="ctable" style={{ marginTop: "12px" }}>
                  <thead>
                    <tr>
                      <th className="th-hdr">Item</th>
                      <th className="th-hdr">Quantidade</th>
                      <th className="th-hdr">Objetivo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preTraining.filter((p) => p.window === window).map((p, i) => (
                      <tr key={i}>
                        <td className="row-label">{p.item}</td>
                        <td><span className="val-sub">{p.amount}</span></td>
                        <td><span className="val-sub">{p.objective}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </section>

        {/* S03 — DURANTE */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">03</span>
            <span className="sec-title">Durante o Treino</span>
            <span className="sec-badge">Intra-session fueling</span>
          </div>
          {intraTraining.map((entry, i) => (
            <div key={i} className="sv-grid">
              <div className="insight-card ic-blue">
                <span className="ins-tag">Gatilho</span>
                <p className="ins-body"><strong>{entry.trigger}</strong></p>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "12px", marginTop: "12px" }}>
                  <div>
                    <span className="ins-tag">Intervalo</span>
                    <span className="val val-atp">{entry.interval_min} min</span>
                  </div>
                  <div>
                    <span className="ins-tag">Carbs</span>
                    <span className="val val-atp">{entry.carbohydrate_g} g</span>
                  </div>
                  <div>
                    <span className="ins-tag">Fluido/h</span>
                    <span className="val val-atp">{entry.fluid_ml_per_hour} ml</span>
                  </div>
                </div>
                <span className="ins-tag" style={{ marginTop: "10px", display: "block" }}>Sódio: {entry.sodium_mg_per_hour} mg/h</span>
              </div>
              <div className="sv-card">
                <div className="sv-title">Fontes recomendadas</div>
                <ul style={{ listStyle: "none", padding: 0, marginTop: "10px" }}>
                  {entry.sources.map((s) => (
                    <li key={s} className="val-sub" style={{ marginBottom: "6px" }}>{s}</li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </section>

        {/* S04 — PÓS-TREINO */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">04</span>
            <span className="sec-title">Pós-Treino</span>
            <span className="sec-badge">Recovery window · MPS</span>
          </div>
          <table className="ctable">
            <thead>
              <tr>
                <th className="th-hdr">Janela</th>
                <th className="th-hdr">Item</th>
                <th className="th-hdr">Quantidade</th>
                <th className="th-hdr">Objetivo</th>
              </tr>
            </thead>
            <tbody>
              {postTraining.map((p, i) => (
                <tr key={i}>
                  <td className="row-label" style={{ color: p.window.includes("0–45") ? "var(--luka-blue)" : "inherit" }}>
                    {p.window}
                  </td>
                  <td><span className="val-sub">{p.item}</span></td>
                  <td><span className="val-sub">{p.amount}</span></td>
                  <td><span className="val-sub">{p.objective}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* S05 — DIA DE TORNEIO */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">05</span>
            <span className="sec-title">Dia de Torneio</span>
            <span className="sec-badge">Pre · During · Post match</span>
          </div>
          <div className="rally-grid">
            {tdPhases.map((phase) => (
              <div key={phase} className="insight-card" style={{ borderLeftColor: tdColor[phase] }}>
                <span className="ins-tag" style={{ color: tdColor[phase] }}>{tdLabels[phase]}</span>
                {tournamentDay.filter((t) => t.phase === phase).map((t, i) => (
                  <div key={i} style={{ marginBottom: "10px" }}>
                    <span className="ins-tag">{t.window}</span>
                    <p className="ins-body">{t.protocol}</p>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </section>

        {/* S06 — COMPOSIÇÃO CORPORAL */}
        <section className="section">
          <div className="sec-head">
            <span className="sec-num">06</span>
            <span className="sec-title">Composição Corporal</span>
            <span className="sec-badge">Targets · Fases</span>
          </div>
          <div className="sv-grid">
            <div>
              <p className="bar-block-title">Marcadores · ITF vs Challenger</p>
              <table className="ctable">
                <thead>
                  <tr>
                    <th className="th-hdr">Marker</th>
                    <th className="th-itf">ITF M25</th>
                    <th className="th-chal">Challenger Target</th>
                  </tr>
                </thead>
                <tbody>
                  {bodyComposition.filter((b) => "itf_m25_reference" in b).map((b, i) => {
                    const row = b as { marker?: string; itf_m25_reference: string; challenger_target: string };
                    return (
                      <tr key={i}>
                        <td className="row-label" style={{ textTransform: "capitalize" }}>{row.marker?.replace(/_/g, " ")}</td>
                        <td><span className="val val-itf">{row.itf_m25_reference}</span></td>
                        <td><span className="val val-chal">{row.challenger_target}</span></td>
                      </tr>
                    );
                  })}
                  {bodyComposition.filter((b) => "value" in b).map((b, i) => {
                    const row = b as { marker?: string; value: string; context: string };
                    return (
                      <tr key={`v${i}`}>
                        <td className="row-label" style={{ textTransform: "capitalize" }}>{row.marker?.replace(/_/g, " ")}</td>
                        <td colSpan={2}><span className="val-sub">{row.value} ({row.context})</span></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div>
              <p className="bar-block-title">Fases de Periodização Nutricional</p>
              <table className="ctable">
                <thead>
                  <tr>
                    <th className="th-hdr">Fase</th>
                    <th className="th-hdr">Duração</th>
                    <th className="th-hdr">Calórico</th>
                    <th className="th-hdr">Foco</th>
                  </tr>
                </thead>
                <tbody>
                  {bodyComposition.filter((b) => "phase" in b && "caloric_target" in b).map((b, i) => {
                    const row = b as { phase: string; duration_weeks: string | number; caloric_target: string; focus: string };
                    return (
                      <tr key={i}>
                        <td className="row-label" style={{ textTransform: "capitalize" }}>{row.phase.replace(/_/g, " ")}</td>
                        <td><span className="val-sub">{row.duration_weeks}w</span></td>
                        <td><span className="val-sub">{row.caloric_target}</span></td>
                        <td><span className="val-sub">{row.focus}</span></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* PRIORITY BOX */}
        <div className="luka-box">
          <div className="luka-box-tag">@luka.ono_ · Nutrição · April 2026</div>
          <h2>→ NUTRITION PRIORITIES</h2>
          <div className="luka-points">
            <div className="lp">
              <div className="lp-num">01</div>
              <p className="lp-text">Janela de 0–45min pós-treino é crítica: 25–30g proteína + 1.0–1.2g/kg carboidrato. Perder essa janela atrasa MPS e reposição de glicogênio.</p>
            </div>
            <div className="lp">
              <div className="lp-num">02</div>
              <p className="lp-text">Nunca aplicar déficit calórico durante torneios — performance e recuperação dependem de manutenção ou leve superávit calórico (+100 kcal/dia).</p>
            </div>
            <div className="lp">
              <div className="lp-num">03</div>
              <p className="lp-text">Carbs no intra-treino (30–60g/45min) apenas em sessões acima de 60min ou Whoop Strain ≥14. Não suplementar em Zona 1–2 sem necessidade.</p>
            </div>
          </div>
        </div>

      </main>
    </>
  );
}
