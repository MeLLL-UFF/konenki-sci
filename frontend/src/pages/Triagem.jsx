import { useState, useEffect } from "react";
import { useAsk } from "../hooks/useAsk";
import ChatBubble from "../components/ChatBubble";
import StepIndicator from "../components/StepIndicator";

const FASES = [
  { id: "peri",    label: "Perimenopausa",             desc: "Ainda menstruo, mas de forma irregular" },
  { id: "meno",    label: "Menopausa",                 desc: "Sem menstruação há 12 meses ou mais" },
  { id: "pos",     label: "Pós-menopausa",             desc: "Sem menstruação há vários anos" },
  { id: "nao_sei", label: "Não sei / prefiro não dizer", desc: "" },
];

const SINTOMAS = [
  "Fogachos / ondas de calor",
  "Insônia ou dificuldade para dormir",
  "Ansiedade ou irritabilidade",
  "Cansaço e baixa energia",
  "Ressecamento vaginal",
  "Dificuldade de concentração ou memória",
  "Dores nas articulações",
  "Alterações de humor",
];

const OUTROS_LABEL = "Outros";

const TRATAMENTOS = [
  "Terapia hormonal (TRH/TH)",
  "Fitoterápicos ou suplementos",
  "Nenhum tratamento",
  "Outros / prefiro não dizer",
];

function buildQuery({ fase, sintomas, incomodo, tratamento }) {
  const faseLabel = FASES.find(f => f.id === fase)?.label ?? fase;
  const sintomasStr = sintomas.join(", ");
  const tratStr = tratamento === "Nenhum tratamento"
    ? "sem tratamento atual"
    : `em uso de ${tratamento}`;
  return `Mulher em fase de ${faseLabel}, com os seguintes sintomas: ${sintomasStr}. Principal incômodo: ${incomodo}. ${tratStr}. Com base nas evidências científicas mais recentes, quais intervenções têm maior eficácia para esses sintomas? Inclua opções hormonais e não-hormonais com seus respectivos níveis de evidência.`;
}

function OutroInput({ value, onChange, placeholder }) {
  return (
    <input
      type="text"
      className="triagem-outro-input"
      placeholder={placeholder}
      value={value}
      onChange={e => onChange(e.target.value)}
      autoFocus
    />
  );
}

function Header({ step, total, label, onBack }) {
  return (
    <header className="header triagem-header">
      <button className="back-btn" onClick={onBack}>← Voltar</button>
      <div>
        <div className="logo">🌸 <span>Triagem Personalizada</span></div>
        {total && (
          <p className="tagline">PASSO {step} DE {total} · {label}</p>
        )}
        {!total && (
          <p className="tagline">BASEADO EM EVIDÊNCIAS · PUBMED</p>
        )}
      </div>
    </header>
  );
}

export default function Triagem({ onBack }) {
  const [step, setStep]           = useState(0);
  const [fase, setFase]           = useState(null);
  const [sintomas, setSintomas]   = useState([]);
  const [sintomaOutroAberto, setSintomaOutroAberto] = useState(false);
  const [sintomaOutroTexto, setSintomaOutroTexto]   = useState("");
  const [incomodo, setIncomodo]   = useState(null);
  const [incomodoOutroAberto, setIncomodoOutroAberto] = useState(false);
  const [incomodoOutroTexto, setIncomodoOutroTexto]   = useState("");
  const [tratamento, setTratamento] = useState(null);
  const [finalResult, setFinalResult] = useState(null);

  const { loading, step: aiStep, result: aiResult, error, submit } = useAsk();

  useEffect(() => {
    if (aiResult) setFinalResult(aiResult);
  }, [aiResult]);

  const toggleSintoma = (s) =>
    setSintomas(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]);

  const toggleOutroSintoma = () => {
    setSintomaOutroAberto(prev => !prev);
    if (sintomaOutroAberto) setSintomaOutroTexto("");
  };

  const selecionarIncomodo = (s) => {
    setIncomodo(s);
    setIncomodoOutroAberto(false);
    setIncomodoOutroTexto("");
  };

  const toggleOutroIncomodo = () => {
    setIncomodoOutroAberto(prev => !prev);
    if (incomodoOutroAberto) setIncomodoOutroTexto("");
    setIncomodo(null);
  };

  const todosSintomas = [
    ...sintomas,
    ...(sintomaOutroAberto && sintomaOutroTexto.trim() ? [sintomaOutroTexto.trim()] : []),
  ];

  const incomodoFinal = incomodoOutroAberto ? incomodoOutroTexto.trim() : incomodo;

  const handleSubmit = (t) => {
    setTratamento(t);
    setStep(4);
    const query = buildQuery({ fase, sintomas: todosSintomas, incomodo: incomodoFinal, tratamento: t });
    submit(query, true);
  };

  if (step === 0) return (
    <div className="page">
      <Header step={1} total={4} label="SUA FASE" onBack={onBack} />
      <main className="triagem-main">
        <div className="triagem-card">
          <h2>Em qual fase você está?</h2>
          <div className="triagem-options">
            {FASES.map(f => (
              <button
                key={f.id}
                className={`triagem-option ${fase === f.id ? "selected" : ""}`}
                onClick={() => setFase(f.id)}
              >
                <span className="option-label">{f.label}</span>
                {f.desc && <span className="option-desc">{f.desc}</span>}
              </button>
            ))}
          </div>
          <button className="triagem-next" disabled={!fase} onClick={() => setStep(1)}>
            Próximo →
          </button>
        </div>
      </main>
    </div>
  );

  if (step === 1) return (
    <div className="page">
      <Header step={2} total={4} label="SEUS SINTOMAS" onBack={() => setStep(0)} />
      <main className="triagem-main">
        <div className="triagem-card">
          <h2>Quais sintomas você tem sentido recentemente?</h2>
          <p className="triagem-subtitle">Selecione todos que se aplicam</p>
          <div className="triagem-options triagem-multi">
            {SINTOMAS.map(s => (
              <button
                key={s}
                className={`triagem-option ${sintomas.includes(s) ? "selected" : ""}`}
                onClick={() => toggleSintoma(s)}
              >
                {sintomas.includes(s) && <span className="check">✓ </span>}{s}
              </button>
            ))}
            <button
              className={`triagem-option ${sintomaOutroAberto ? "selected" : ""}`}
              onClick={toggleOutroSintoma}
            >
              {sintomaOutroAberto && <span className="check">✓ </span>}{OUTROS_LABEL}
            </button>
          </div>
          {sintomaOutroAberto && (
            <OutroInput
              value={sintomaOutroTexto}
              onChange={setSintomaOutroTexto}
              placeholder="Descreva seu sintoma…"
            />
          )}
          <button
            className="triagem-next"
            disabled={todosSintomas.length === 0}
            onClick={() => setStep(2)}
          >
            Próximo →
          </button>
        </div>
      </main>
    </div>
  );

  if (step === 2) return (
    <div className="page">
      <Header step={3} total={4} label="PRINCIPAL INCÔMODO" onBack={() => setStep(1)} />
      <main className="triagem-main">
        <div className="triagem-card">
          <h2>Qual seu principal incômodo hoje?</h2>
          <div className="triagem-options">
            {todosSintomas.map(s => (
              <button
                key={s}
                className={`triagem-option ${incomodo === s ? "selected" : ""}`}
                onClick={() => selecionarIncomodo(s)}
              >
                {s}
              </button>
            ))}
            <button
              className={`triagem-option ${incomodoOutroAberto ? "selected" : ""}`}
              onClick={toggleOutroIncomodo}
            >
              {incomodoOutroAberto && <span className="check">✓ </span>}{OUTROS_LABEL}
            </button>
          </div>
          {incomodoOutroAberto && (
            <OutroInput
              value={incomodoOutroTexto}
              onChange={setIncomodoOutroTexto}
              placeholder="Descreva seu principal incômodo…"
            />
          )}
          <button
            className="triagem-next"
            disabled={!incomodoFinal}
            onClick={() => setStep(3)}
          >
            Próximo →
          </button>
        </div>
      </main>
    </div>
  );

  if (step === 3) return (
    <div className="page">
      <Header step={4} total={4} label="TRATAMENTO ATUAL" onBack={() => setStep(2)} />
      <main className="triagem-main">
        <div className="triagem-card">
          <h2>Você já faz algum tratamento?</h2>
          <div className="triagem-options">
            {TRATAMENTOS.map(t => (
              <button
                key={t}
                className={`triagem-option ${tratamento === t ? "selected" : ""}`}
                onClick={() => handleSubmit(t)}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </main>
    </div>
  );

  return (
    <div className="page">
      <Header onBack={onBack} />
      <main className="triagem-main triagem-result-main">
        {!finalResult && !error && (
          <div className="triagem-profile-summary">
            <h3>Analisando seu perfil…</h3>
            <ul>
              <li><strong>Fase:</strong> {FASES.find(f => f.id === fase)?.label}</li>
              <li><strong>Sintomas:</strong> {todosSintomas.join(", ")}</li>
              <li><strong>Principal incômodo:</strong> {incomodoFinal}</li>
            </ul>
          </div>
        )}
        {loading && aiStep && <StepIndicator step={aiStep} />}
        {error && <p className="error">Erro: {error}</p>}
        {finalResult && (
          <>
            <div className="triagem-profile-chips">
              <span className="profile-chip">{FASES.find(f => f.id === fase)?.label}</span>
              <span className="profile-chip">{incomodoFinal}</span>
              <span className="profile-chip">{tratamento}</span>
            </div>
            <ChatBubble entry={finalResult} />
            <button className="triagem-next triagem-cta-btn" onClick={onBack}>
              Fazer uma pergunta específica →
            </button>
          </>
        )}
        <p className="disclaimer" style={{ marginTop: "1rem" }}>
          Não substitui consulta médica · Fonte: PubMed/NCBI
        </p>
      </main>
    </div>
  );
}
