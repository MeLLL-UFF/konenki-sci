const TypingIndicator = () => (
  <div className="flex gap-3 animate-fade-in">
    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
      <span className="text-sm">🌸</span>
    </div>
    <div className="bg-chat-assistant rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-2 h-2 bg-muted-foreground rounded-full animate-pulse-dot"
          style={{ animationDelay: `${i * 0.2}s` }}
        />
      ))}
    </div>
  </div>
);

export default TypingIndicator;