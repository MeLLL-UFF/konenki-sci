import { useState, useCallback } from "react";
import { askStream, AskRequest, StreamEvent } from "../lib/api";

export interface AskResult extends StreamEvent {
  question: string;
  plainLanguage: boolean;
}

export function useAsk() {
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState("");
  const [result, setResult] = useState<AskResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = useCallback(async (question: string, plainLanguage: boolean) => {
    setLoading(true);
    setStep("");
    setResult(null);
    setError(null);
    try {
      await askStream({
        question,
        plainLanguage,
        onStep: setStep,
        onResult: (r: StreamEvent) => setResult({ ...r, question, plainLanguage }),
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