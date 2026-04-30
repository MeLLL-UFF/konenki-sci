import { useState } from "react";
import Home from "./pages/Home";
import Triagem from "./pages/Triagem";
import News from "./pages/News";
import NewsPost from "./pages/NewsPost";
import "./index.css";

export default function App() {
  const [view, setView]         = useState("home");
  const [selectedSlug, setSlug] = useState(null);

  if (view === "triagem")
    return <Triagem onBack={() => setView("home")} />;
  if (view === "news")
    return <News onPost={slug => { setSlug(slug); setView("news-post"); }} onBack={() => setView("home")} />;
  if (view === "news-post")
    return <NewsPost slug={selectedSlug} onBack={() => setView("news")} />;
  return <Home onTriagem={() => setView("triagem")} onNews={() => setView("news")} />;
}