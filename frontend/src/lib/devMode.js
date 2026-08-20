/**
 * Modo desenvolvedor: permite que testadores usem a própria chave de LLM.
 *
 * A chave fica em sessionStorage (some ao fechar a aba) e viaja em cabeçalho
 * a cada requisição. Nunca é gravada no backend nem no banco.
 */

const KEY = "menopausia.devCreds";
const ANSWERED = "menopausia.devAsked";

export function getDevCreds() {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setDevCreds({ model, apiKey }) {
  sessionStorage.setItem(KEY, JSON.stringify({ model, apiKey }));
  sessionStorage.setItem(ANSWERED, "1");
}

export function clearDevCreds() {
  sessionStorage.removeItem(KEY);
}

/** Marca que a usuária já respondeu ao modal nesta sessão. */
export function markAsked() {
  sessionStorage.setItem(ANSWERED, "1");
}

export function hasAnswered() {
  return sessionStorage.getItem(ANSWERED) === "1";
}

/** Cabeçalhos do modo dev — objeto vazio quando não há chave configurada. */
export function devHeaders() {
  const creds = getDevCreds();
  if (!creds?.apiKey || !creds?.model) return {};
  return {
    "X-LLM-Model": creds.model,
    "X-LLM-Api-Key": creds.apiKey,
  };
}
