import { useState, useEffect } from "react";
import { fetchNewsPost, fetchNewsTrend } from "../lib/api";

function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("pt-BR", { day: "numeric", month: "long", year: "numeric" });
}

export default function NewsPost({ type, id, onBack }) {
  const [post, setPost] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setPost(null);

    const fetcher = type === "trend" ? fetchNewsTrend : fetchNewsPost;
    fetcher(id)
      .then(setPost)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [type, id]);

  return (
    <div className="page">
      <header className="header">
        <div className="header-row">
          <button className="back-btn" onClick={onBack}>← Newsletter</button>
          <div className="logo">🌸 <span>MenopausIA</span></div>
        </div>
        <p className="tagline">BASEADO EM EVIDÊNCIAS · PUBMED</p>
      </header>

      <main className="main news-post-main">
        {loading && <p className="news-loading">Carregando item…</p>}
        {error && <p className="error">Erro: {error}</p>}
        {post && (
          <article className="news-article">
            <header className="article-header">
              <h1 className="article-title">{post.title}</h1>
              {post.date && <p className="article-date">{formatDate(post.date)}</p>}
              {post.excerpt && <p className="article-excerpt">{post.excerpt}</p>}
              {type === "trend" && post.source && (
                <p className="article-excerpt">Fonte: {post.source}</p>
              )}
            </header>
            <div className="article-body">
              {type === "trend" ? (
                <p>{post.content || post.summary}</p>
              ) : (
                <div dangerouslySetInnerHTML={{ __html: post.html }} />
              )}
            </div>
          </article>
        )}
        <p className="disclaimer" style={{ marginTop: "2rem" }}>
          Não substitui consulta médica · Fonte: PubMed/NCBI
        </p>
      </main>
    </div>
  );
}
