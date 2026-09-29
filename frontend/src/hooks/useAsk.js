import { useState, useCallback, useRef } from "react";
import { askStream, resetConversation as resetOnServer } from "../lib/api";

export function useAsk() {
  const [loading,  setLoading]  = useState(false);
  const [step,     setStep]     = useState("");
  const [result,   setResult]   = useState(null);
  const [error,    setError]    = useState(null);

  // Amarra as perguntas numa conversa só. Fica em ref, não em state, porque
  // precisa estar disponível já na próxima chamada de submit — um state só
  // estaria atualizado depois do re-render.
  const sessionIdRef = useRef(null);

  const submit = useCallback(async (question, plainLanguage) => {
    setLoading(true);
    setStep("");
    setResult(null);
    setError(null);
    try {
      await askStream({
        question,
        plainLanguage,
        sessionId: sessionIdRef.current,
        onStep:   setStep,
        onResult: (r) => {
          // O backend devolve o id (o mesmo que enviamos ou um novo, se era a
          // primeira pergunta ou se a sessão havia expirado no servidor).
          if (r.session_id) sessionIdRef.current = r.session_id;
          setResult({ ...r, question, plainLanguage });
        },
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      setStep("");
    }
  }, []);

  /** Descarta a conversa atual: a próxima pergunta abre uma sessão nova. */
  const resetConversation = useCallback(() => {
    resetOnServer(sessionIdRef.current);   // não precisa de await
    sessionIdRef.current = null;
    setResult(null);
    setError(null);
    setStep("");
  }, []);

  return { loading, step, result, error, submit, resetConversation };
}
