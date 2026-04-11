interface Props {
  suggestions: string[];
  onSelect: (question: string) => void;
  disabled?: boolean;
}

const SuggestedQuestions = ({ suggestions, onSelect, disabled }: Props) => (
  <div className="flex flex-col items-center gap-6 animate-fade-in">
    <div className="text-center space-y-2">
      <div className="w-16 h-16 mx-auto bg-secondary rounded-full flex items-center justify-center mb-4">
        <span className="text-3xl">🌸</span>
      </div>
      <h2 className="text-2xl font-display font-semibold text-foreground">
        Olá! Sou a MenopausIA
      </h2>
      <p className="text-sm text-muted-foreground max-w-md">
        Tiro dúvidas sobre menopausa com base em evidências científicas.
        Como posso ajudar você hoje?
      </p>
    </div>
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
      {suggestions.map((q) => (
        <button
          key={q}
          onClick={() => onSelect(q)}
          disabled={disabled}
          className={`text-left text-sm px-4 py-3 rounded-xl border border-border bg-card transition-colors text-foreground ${
            disabled ? "opacity-50 cursor-not-allowed" : "hover:bg-secondary hover:border-primary/30"
          }`}
        >
          {q}
        </button>
      ))}
    </div>
  </div>
);

export default SuggestedQuestions;