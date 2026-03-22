import React from "react";

export default function SuggestionChip({ text, onClick }) {
  return (
    <button className="chip" onClick={() => onClick(text)}>
      {text}
    </button>
  );
}