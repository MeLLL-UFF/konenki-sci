const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";

export async function ask({ question, plainLanguage }) {
  const res = await fetch(`${BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, plain_language: plainLanguage }),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function fetchNews() {
  const res = await fetch(`${BASE}/news`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function fetchNewsPost(slug) {
  const res = await fetch(`${BASE}/news/${slug}`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function fetchTrends() {
  const res = await fetch(`${BASE}/news/trends`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function askStream({ question, plainLanguage, onStep, onResult }) {
  const res = await fetch(`${BASE}/ask/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, plain_language: plainLanguage }),
  });
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop();
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const event = JSON.parse(line.slice(6));
      if (event.type === "step")   onStep?.(event.message);
      if (event.type === "result") onResult?.(event);
      if (event.type === "error")  throw new Error(event.message);
    }
  }
}