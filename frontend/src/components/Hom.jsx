import { useState, useRef, useEffect } from "react";
import { useAsk } from "../hooks/useAsk";
import ChatBubble from "../components/ChatBubble";
import StepIndicator from "../components/StepIndicator";
import SuggestionChip from "../components/SuggestionChip";

const SUGGESTIONS = [
  "Quais são os sintomas mais comuns da menopausa?",
  "A terapia hormonal é segura?",
  "Como a menopausa afeta a saúde óssea?",
  "Existem tratamentos naturais para os fogachos?",
  "Como a menopausa influencia o risco cardiovascular?",
  "O que é menopausa precoce?",
];

export default function Home() {
  const [question, setQuestion]   = useState("");
  const [plain,    setPlain]      = useState(false);
  const [history,  setHistory]    = useState([]);
  const { loading, step, result, error, submit } = useAsk();
  const bottomRef = useRef(null);
  const textRef   = useRef(null);

  useEffect(() => {
    if (result) setHistory(h => [...h, result]);
  }, [result]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, step]);

  const handleSubmit = () => {
    if (!question.trim() || loading) return;
    submit(question.trim(), plain);
    setQuestion("");
  };

  return (
    <div className="page">
      <header className="header">
        <div className="logo">🌸 <span>MenopausIA</span></div>
        <p className="tagline">RESPOSTAS BASEADAS EM EVIDÊNCIAS · PUBMED</p>
      </header>

      <main className="main">
        {history.length === 0 && !loading && (
          <section className="intro">
            <h1>Suas dúvidas sobre menopausa,<br /><em>respondidas pela ciência.</em></h1>
            <p>Cada resposta é gerada a partir de artigos indexados no <strong>PubMed</strong>.</p>
            <div className="chips">
              {SUGGESTIONS.map(s => (
                <SuggestionChip key={s} text={s} onClick={t => { setQuestion(t); textRef.current?.focus(); }} />
              ))}
            </div>
          </section>
        )}

        {history.map((h, i) => <ChatBubble key={i} entry={h} />)}
        {loading && step && <StepIndicator step={step} />}
        {error && <p className="error">Erro: {error}</p>}
        <div ref={bottomRef} />
      </main>

      <footer className="input-bar">
        <button
          className={`plain-toggle ${plain ? "active" : ""}`}
          onClick={() => setPlain(v => !v)}
        >
          💬 Linguagem simples
        </button>
        <div className="input-row">
          <textarea
            ref={textRef}
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(); } }}
            placeholder="Faça sua pergunta sobre menopausa…"
            disabled={loading}
            rows={1}
          />
          <button className="send-btn" onClick={handleSubmit} disabled={loading || !question.trim()}>
            {loading ? "⋯" : "↑"}
          </button>
        </div>
        <p className="disclaimer">Não substitui consulta médica · Fonte: PubMed/NCBI</p>
      </footer>
    </div>
  );
}