import { useState, useRef, useEffect } from "react";
import React from "react";
import { useAsk } from "../hooks/useAsk";
import ChatMessage from "./ChatMessage";
import StepIndicator from "./StepIndicator";
import SuggestedQuestions from "./SuggestedQuestions";
import ChatInput from "./ChatInput";
import TypingIndicator from "./TypingIndicator";
import { Heart } from "lucide-react";

const SUGGESTIONS = [
  "Quais são os sintomas mais comuns da menopausa?",
  "A terapia hormonal é segura?",
  "Como a menopausa afeta a saúde óssea?",
  "Existem tratamentos naturais para os fogachos?",
  "Como a menopausa influencia o risco cardiovascular?",
  "O que é menopausa precoce?",
];

export default function Home() {
  const [question, setQuestion] = useState("");
  const [plain, setPlain] = useState(false);
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
  const { loading, step, result, error, submit } = useAsk();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (result) {
      setMessages(prev => [
        ...prev,
        { role: "assistant", content: result.answer || "Resposta não disponível" }
      ]);
    }
  }, [result]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = (input: string) => {
    if (!input.trim() || loading) return;
    setMessages(prev => [...prev, { role: "user", content: input.trim() }]);
    submit(input.trim(), plain);
    setQuestion("");
  };

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Header */}
      <header className="flex items-center gap-3 px-6 py-4 border-b border-border bg-card/80 backdrop-blur-sm">
        <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
          <span className="text-xl">🌸</span>
        </div>
        <div>
          <h1 className="text-lg font-display font-semibold text-foreground tracking-tight">
            MenopausIA
          </h1>
          <p className="text-xs text-muted-foreground">
            Respostas baseadas em evidências científicas
          </p>
        </div>
      </header>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto scrollbar-thin px-4 md:px-8 py-6">
        <div className="max-w-2xl mx-auto space-y-4">
          {messages.length === 0 ? (
            <>
              <SuggestedQuestions suggestions={SUGGESTIONS} onSelect={handleSend} disabled={loading} />
              {loading && (step ? <StepIndicator step={step} /> : <TypingIndicator />)}
            </>
          ) : (
            <>
              {messages.map((msg, i) => (
                <ChatMessage key={i} role={msg.role} content={msg.content} />
              ))}
              {loading && step && <StepIndicator step={step} />}
              {loading && !step && <TypingIndicator />}
            </>
          )}
          {error && <p className="error text-destructive">Erro: {error}</p>}
        </div>
      </div>

      {/* Input + Disclaimer */}
      <div className="border-t border-border bg-card/80 backdrop-blur-sm px-4 md:px-8 py-4">
        <div className="max-w-2xl mx-auto space-y-3">
          <ChatInput
            value={question}
            onChange={setQuestion}
            onSend={handleSend}
            disabled={loading}
            plainLanguage={plain}
            onTogglePlain={() => setPlain(v => !v)}
          />
          <p className="text-[11px] text-muted-foreground text-center flex items-center justify-center gap-1">
            <Heart className="w-3 h-3" />
            Não substitui consulta médica · Fonte: Dataset Hugging Face
          </p>
        </div>
      </div>
    </div>
  );
}