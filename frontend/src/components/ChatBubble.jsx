import { useState } from "react";
import RefCard from "./RefCard";

export default function ChatBubble({ entry }) {
  const [showRefs, setShowRefs] = useState(false);
  return (
    <div className="bubble-wrap">
      <div className="bubble bubble-user">
        {entry.question}
        {entry.plainLanguage && <span className="badge">linguagem simples</span>}
      </div>
      <div className="bubble bubble-bot">
        {entry.pubmed_query && (
          <p className="query-label">🔬 PubMed: <em>{entry.pubmed_query}</em></p>
        )}
        <div className="answer-text">
          {entry.answer.split("\n\n").map((p, i) => <p key={i}>{p}</p>)}
        </div>
        {entry.articles?.length > 0 && (
          <div className="refs-section">
            <button className="refs-toggle" onClick={() => setShowRefs(v => !v)}>
              {showRefs ? "▾" : "▸"} {entry.articles.length} artigo(s) consultado(s)
            </button>
            {showRefs && entry.articles.map((a, i) => (
              <RefCard key={a.pmid} article={a} index={i} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}