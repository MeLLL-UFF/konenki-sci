import { useState } from "react";
import Home from "./pages/Home";
import Triagem from "./pages/Triagem";
import News from "./pages/News";
import NewsPost from "./pages/NewsPost";
import "./index.css";

export default function App() {
  const [view, setView] = useState("home");
  const [selectedId, setSelectedId] = useState(null);
  const [selectedType, setSelectedType] = useState("article");

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
}