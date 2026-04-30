import { useState, useEffect } from "react";
import { fetchNews, fetchTrends } from "../lib/api";

function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("pt-BR", { day: "numeric", month: "long", year: "numeric" });
}

export default function News({ onPost, onBack }) {
  const [posts, setPosts]       = useState([]);
  const [trends, setTrends]     = useState([]);
  const [loading, setLoading]   = useState(true);
  const [loadingTrends, setLoadingTrends] = useState(true);
  const [error, setError]       = useState(null);

  useEffect(() => {
    fetchNews()
      .then(data => setPosts(data.posts ?? []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));

    fetchTrends()
      .then(data => setTrends(data.topics ?? []))
      .catch(() => {})
      .finally(() => setLoadingTrends(false));
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
        {trends.length > 0 && (
          <section className="trends-section">
            <h3 className="section-label">Em alta no PubMed (últimos 30 dias)</h3>
            <div className="trends-list">
              {trends.map(t => (
                <div key={t.pmid} className="trend-card">
                  <span className="trend-title">{t.title}</span>
                  <span className="trend-meta">{t.journal}{t.year ? ` · ${t.year}` : ""}</span>
                </div>
              ))}
            </div>
          </section>
        )}
        {loadingTrends && <p className="section-label">Carregando tópicos em alta…</p>}

        <section>
          <h3 className="section-label">Edições publicadas</h3>
          {loading && <p className="news-loading">Carregando…</p>}
          {error && <p className="error">Erro ao carregar: {error}</p>}
          {!loading && posts.length === 0 && !error && (
            <p className="news-empty">Nenhuma edição publicada ainda.</p>
          )}
          <div className="posts-list">
            {posts.map(post => (
              <button key={post.slug} className="post-card" onClick={() => onPost(post.slug)}>
                <div className="post-card-body">
                  <span className="post-title">{post.title}</span>
                  {post.excerpt && <span className="post-excerpt">{post.excerpt}</span>}
                </div>
                <div className="post-card-footer">
                  {post.date && <span className="post-date">{formatDate(post.date)}</span>}
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
