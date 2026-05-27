export default function RefCard({ article, index }) {
  return (
    <a
      href={`https://pubmed.ncbi.nlm.nih.gov/${article.pmid}/`}
      target="_blank"
      rel="noopener noreferrer"
      className="ref-card"
    >
      <span className="ref-index">[{index + 1}]</span>
      <span className="ref-year">{article.year}</span>
      <span className="ref-journal">{article.journal}</span>
      <p className="ref-title">{article.title}</p>
    </a>
  );
}