const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";

export interface AskRequest {
  question: string;
  plainLanguage: boolean;
}

export interface AskResponse {
  answer: string;
  sources?: any[];
}

export interface StreamEvent {
  type: "step" | "result";
  message?: string;
  [key: string]: any;
}

export async function ask({ question, plainLanguage }: AskRequest): Promise<AskResponse> {
  const res = await fetch(`${BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, plain_language: plainLanguage }),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function askStream({
  question,
  plainLanguage,
  onStep,
  onResult
}: AskRequest & {
  onStep?: (message: string) => void;
  onResult?: (event: StreamEvent) => void;
}): Promise<void> {
  const res = await fetch(`${BASE}/ask/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, plain_language: plainLanguage }),
  });
  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const event: StreamEvent = JSON.parse(line.slice(6));
      if (event.type === "step" && onStep) onStep(event.message || "");
      if (event.type === "result" && onResult) onResult(event);
    }
  }
}