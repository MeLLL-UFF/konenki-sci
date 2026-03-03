import { useState, useCallback } from "react";
import { askStream } from "../lib/api";

export function useAsk() {
  const [loading,  setLoading]  = useState(false);
  const [step,     setStep]     = useState("");
  const [result,   setResult]   = useState(null);
  const [error,    setError]    = useState(null);

  const submit = useCallback(async (question, plainLanguage) => {
    setLoading(true);
    setStep("");
    setResult(null);
    setError(null);
    try {
      await askStream({
        question,
        plainLanguage,
        onStep:   setStep,
        onResult: (r) => setResult({ ...r, question, plainLanguage }),
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      setStep("");
    }
  }, []);

  return { loading, step, result, error, submit };
}