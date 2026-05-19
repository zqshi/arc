import { useEffect, useRef, useCallback } from 'react';
import { Send } from 'lucide-react';

export function ChatInput({
  value,
  onChange,
  onSend,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled: boolean;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, []);

  useEffect(() => {
    adjustHeight();
  }, [value, adjustHeight]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="relative">
      <textarea
        ref={textareaRef}
        rows={1}
        placeholder="输入消息... (Shift+Enter 换行)"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        className="w-full resize-none rounded-md border border-border bg-bg-input py-2 pl-3 pr-8 text-xs leading-relaxed text-text-primary placeholder:text-text-muted focus:border-border-active focus:outline-none disabled:opacity-50"
      />
      <button
        onClick={onSend}
        disabled={disabled || !value.trim()}
        className="absolute bottom-2 right-2 text-text-muted transition-colors hover:text-accent disabled:opacity-30"
      >
        <Send size={13} />
      </button>
    </div>
  );
}
