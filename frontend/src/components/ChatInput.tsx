import { useState, useRef, useEffect } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (message: string) => void;
  disabled?: boolean;
  plainLanguage: boolean;
  onTogglePlain: () => void;
}

const ChatInput = ({ value, onChange, onSend, disabled, plainLanguage, onTogglePlain }: ChatInputProps) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + "px";
    }
  }, [value]);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    onChange("");
  };

  return (
    <div className="space-y-2">
      <div className="flex justify-center">
        <Badge
          variant={plainLanguage ? "default" : "secondary"}
          className="cursor-pointer"
          onClick={onTogglePlain}
        >
          💬 Linguagem simples
        </Badge>
      </div>
      <div className="flex items-end gap-2 bg-card border border-border rounded-2xl px-4 py-2 shadow-sm">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
          placeholder="Faça sua pergunta sobre menopausa..."
          className="flex-1 bg-transparent border-none outline-none resize-none text-sm text-foreground placeholder:text-muted-foreground font-body min-h-[40px] py-2"
          rows={1}
          disabled={disabled}
        />
        <Button
          onClick={handleSubmit}
          disabled={disabled || !value.trim()}
          size="icon"
          className="rounded-full flex-shrink-0 h-9 w-9"
        >
          <Send className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
};

export default ChatInput;