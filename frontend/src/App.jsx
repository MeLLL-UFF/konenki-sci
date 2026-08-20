import { useState } from "react";
import Home from "./pages/Home";
import Triagem from "./pages/Triagem";
import News from "./pages/News";
import NewsPost from "./pages/NewsPost";
import DevModeModal from "./components/DevModeModal";
import { hasAnswered, getDevCreds, clearDevCreds } from "./lib/devMode";
import "./index.css";

export default function App() {
  const [view, setView] = useState("home");
  const [selectedId, setSelectedId] = useState(null);
  const [selectedType, setSelectedType] = useState("article");
  const [showDevModal, setShowDevModal] = useState(() => !hasAnswered());
  const [devCreds, setDevCredsState] = useState(() => getDevCreds());

  function closeDevModal() {
    setShowDevModal(false);
    setDevCredsState(getDevCreds());
  }

  function disableDevMode() {
    clearDevCreds();
    setDevCredsState(null);
  }

  const page = (() => {
    if (view === "triagem")
      return <Triagem onBack={() => setView("home")} />;
    if (view === "news")
      return (
        <News
          onOpen={(type, id) => {
            setSelectedType(type);
            setSelectedId(id);
            setView("news-post");
          }}
          onBack={() => setView("home")}
        />
      );
    if (view === "news-post")
      return <NewsPost type={selectedType} id={selectedId} onBack={() => setView("news")} />;
    return <Home onTriagem={() => setView("triagem")} onNews={() => setView("news")} />;
  })();

  return (
    <>
      {page}
      {showDevModal && <DevModeModal onClose={closeDevModal} />}
      {devCreds && (
        <button
          className="dev-badge"
          onClick={disableDevMode}
          title="Clique para voltar ao modelo padrão"
        >
          modo dev: {devCreds.model} ✕
        </button>
      )}
    </>
  );
}
