import { useState, useEffect } from "react";
import { fetchNews } from "../lib/api";

function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("pt-BR", { day: "numeric", month: "long", year: "numeric" });
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
        <section>
          <h3 className="section-label">Edições publicadas</h3>
          {loading && <p className="news-loading">Carregando…</p>}
          {error && <p className="error">Erro ao carregar: {error}</p>}
          {!loading && articles.length === 0 && !error && (
            <p className="news-empty">Nenhum artigo salvo ainda.</p>
          )}
          <div className="posts-list">
            {articles.map(article => (
              <button
                key={article.slug}
                className="post-card"
                onClick={() => onOpen("article", article.slug)}
              >
                <div className="post-card-body">
                  <span className="post-title">{article.title}</span>
                  {article.summary && <span className="post-excerpt">{article.summary}</span>}

                </div>
                <div className="post-card-footer">
                  {article.date && <span className="post-date">{formatDate(article.date)}</span>}
                  <span className="post-arrow">→</span>
                </div>
              </button>
            ))}
          </div>
        </section>

        <section>
          <h3 className="section-label">Últimas Notícias</h3>
          {!loading && trends.length === 0 && !error && (
            <p className="news-empty">Nenhuma notícia salva ainda.</p>
          )}
          <div className="posts-list">
            {trends.map(trend => (
              <button
                key={trend.id}
                className="post-card"
                onClick={() => onOpen("trend", trend.id)}
              >
                <div className="post-card-body">
                  <span className="post-title">{trend.keyword}</span>
                  {trend.summary && <span className="post-excerpt">{trend.summary}</span>}

                </div>
                <div className="post-card-footer">
                  {trend.source && <span className="post-date">{trend.source}</span>}
                  <span className="post-arrow">→</span>
                </div>
              </button>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
