import { useState, useEffect } from "react";
import { fetchNews, subscribeNewsletter } from "../lib/api";

function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("pt-BR", { day: "numeric", month: "long", year: "numeric" });
}

function SubscribeBox() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState(null); // null | "loading" | "ok" | "error"
  const [message, setMessage] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    if (!email.trim()) return;
    setStatus("loading");
    try {
      await subscribeNewsletter(email.trim());
      setStatus("ok");
      setMessage("Inscrição realizada! Você receberá as próximas edições.");
      setEmail("");
    } catch (err) {
      setStatus("error");
      setMessage(err.message || "Erro ao inscrever. Tente novamente.");
    }
  }

  return (
    <div className="subscribe-box">
      <div className="subscribe-box-header">
        <svg className="subscribe-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="2" y="4" width="20" height="16" rx="2" />
          <polyline points="2,4 12,13 22,4" />
        </svg>
        <span className="subscribe-title">ASSINE A NEWSLETTER</span>
      </div>
      <p className="subscribe-subtitle">Receba os artigos mais recentes sobre saúde feminina direto no seu email.</p>
      {status === "ok" ? (
        <p className="subscribe-success">{message}</p>
      ) : (
        <form className="subscribe-form" onSubmit={handleSubmit}>
          <input
            className="subscribe-input"
            type="email"
            placeholder="seu@email.com"
            value={email}
            onChange={e => setEmail(e.target.value)}
            disabled={status === "loading"}
            required
          />
          <button className="subscribe-btn" type="submit" disabled={status === "loading"}>
            {status === "loading" ? "…" : "Inscrever"}
          </button>
        </form>
      )}
      {status === "error" && <p className="subscribe-error">{message}</p>}
    </div>
  );
}

export default function News({ onOpen, onBack }) {
  const [articles, setArticles] = useState([]);
  const [trends, setTrends] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchNews()
      .then(data => {
        setArticles(data.articles ?? []);
        setTrends(data.trends ?? []);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page">
      <header className="header">
        <div className="header-row">
          <button className="back-btn" onClick={onBack}>← Início</button>
          <div className="logo">🌸 <span>Newsletter</span></div>
        </div>
        <p className="tagline">CIÊNCIA TRADUZIDA · CONTEXTO BRASILEIRO</p>
      </header>

      <main className="main news-main">
        <div className="news-container">
          <SubscribeBox />

          <section>
            <div className="section-header">
              <h3 className="section-label">Edições publicadas</h3>
              {articles.length > 0 && (
                <span className="section-count">{articles.length} EDIÇÕES</span>
              )}
            </div>
            {loading && <p className="news-loading">Carregando…</p>}
            {error && <p className="error">Erro ao carregar: {error}</p>}
            {!loading && articles.length === 0 && !error && (
              <p className="news-empty">Nenhum artigo salvo ainda.</p>
            )}
            <div className="posts-grid">
              {articles.map(article => (
                <button
                  key={article.slug}
                  className="post-card"
                  onClick={() => onOpen("article", article.slug)}
                >
                  <div className="post-card-body">
                    <span className="post-title">{article.title}</span>
                    {(article.author || article.date) && (
                      <span className="post-meta">
                        {article.author && <span>{article.author}</span>}
                        {article.author && article.date && <span> · </span>}
                        {article.date && <span>{formatDate(article.date)}</span>}
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </section>

          <section>
            <div className="section-header">
              <h3 className="section-label">Últimas Notícias</h3>
              {trends.length > 0 && (
                <span className="section-count">{trends.length} TENDÊNCIAS</span>
              )}
            </div>
            {!loading && trends.length === 0 && !error && (
              <p className="news-empty">Nenhuma notícia salva ainda.</p>
            )}
            <div className="posts-grid">
              {trends.map(trend => (
                <button
                  key={trend.id}
                  className="post-card"
                  onClick={() => onOpen("trend", trend.id)}
                >
                  <div className="post-card-body">
                    <span className="post-title">{trend.keyword}</span>
                  </div>
                  <div className="post-card-footer">
                    {trend.source && <span className="post-date">{trend.source}</span>}
                  </div>
                </button>
              ))}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
