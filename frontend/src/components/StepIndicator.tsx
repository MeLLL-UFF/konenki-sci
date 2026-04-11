import React from "react";

interface StepIndicatorProps {
  step: string;
}

const StepIndicator = ({ step }: StepIndicatorProps) => (
  <div className="flex gap-3 animate-fade-in">
    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
      <span className="text-sm">🌸</span>
    </div>
    <div className="bg-chat-assistant rounded-2xl rounded-bl-sm px-4 py-3">
      <p className="text-sm text-chat-assistant-foreground italic">{step}</p>
    </div>
  </div>
);

export default StepIndicator;