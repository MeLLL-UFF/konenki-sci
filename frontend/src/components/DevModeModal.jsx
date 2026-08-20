import { useState } from "react";
import { validateDevKey } from "../lib/api";
import { setDevCreds, markAsked } from "../lib/devMode";

/**
 * Pergunta, uma vez por sessão, se quem abriu o app é desenvolvedor.
 * Em caso afirmativo, coleta modelo + chave de API para testar o app com
 * qualquer LLM. Caso contrário, o app segue com o modelo padrão do servidor.
 */
export default function DevModeModal({ onClose }) {
  const [stage, setStage]   = useState("ask");   // "ask" | "form"
  const [model, setModel]   = useState("");
  const [apiKey, setApiKey] = useState("");
  const [error, setError]   = useState("");
  const [testing, setTesting] = useState(false);

  function decline() {
    markAsked();
    onClose();
  }

  async function submit(e) {
    e.preventDefault();
    setError("");

    if (!model.trim())  return setError("Informe o nome do modelo.");
    if (!apiKey.trim()) return setError("Informe a chave de API.");

    setTesting(true);
    try {
      await validateDevKey({ model: model.trim(), apiKey: apiKey.trim() });
      setDevCreds({ model: model.trim(), apiKey: apiKey.trim() });
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="dev-modal-title">
      <div className="modal">
        {stage === "ask" ? (
          <>
            <h2 id="dev-modal-title" className="modal-title">Você é desenvolvedor(a)?</h2>
            <p className="modal-text">
              Testadores podem usar a própria chave de API para avaliar o app com
              diferentes modelos de linguagem.
            </p>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={decline}>
                Não, usar padrão
              </button>
              <button className="btn-primary" onClick={() => setStage("form")}>
                Sim, usar minha chave
              </button>
            </div>
          </>
        ) : (
          <form onSubmit={submit}>
            <h2 id="dev-modal-title" className="modal-title">Configurar modelo</h2>
            <p className="modal-text">
              O provedor é detectado pelo nome do modelo: <code>claude-*</code>,{" "}
              <code>gpt-*</code>, <code>gemini-*</code> ou <code>sabia-*</code>.
            </p>

            <label className="modal-label" htmlFor="dev-model">Modelo</label>
            <input
              id="dev-model"
              className="modal-input"
              placeholder="ex: gpt-4o-mini"
              value={model}
              onChange={e => setModel(e.target.value)}
              autoComplete="off"
            />

            <label className="modal-label" htmlFor="dev-key">Chave de API</label>
            <input
              id="dev-key"
              className="modal-input"
              type="password"
              placeholder="sk-…"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              autoComplete="off"
            />

            <p className="modal-hint">
              A chave fica só nesta aba do navegador e é enviada ao servidor apenas
              para atender às suas perguntas. Não é gravada em banco de dados.
            </p>

            {error && <p className="modal-error">{error}</p>}

            <div className="modal-actions">
              <button type="button" className="btn-secondary" onClick={decline} disabled={testing}>
                Cancelar
              </button>
              <button type="submit" className="btn-primary" disabled={testing}>
                {testing ? "Testando…" : "Testar e salvar"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
