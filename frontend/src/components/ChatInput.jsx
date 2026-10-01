import { useRef, useState } from "react";
import "./ChatInput.css";

const MAX_TEXTAREA_HEIGHT = 120;

function ChatInput({ onSend, disabled }) {
  const [value, setValue] = useState("");
  const textareaRef = useRef(null);

  const resize = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT)}px`;
  };

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    requestAnimationFrame(resize);
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <form
      className="chat-input"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <textarea
        ref={textareaRef}
        className="chat-input__textarea"
        rows={1}
        value={value}
        placeholder="질문을 입력해주세요."
        onChange={(event) => {
          setValue(event.target.value);
          resize();
        }}
        onKeyDown={handleKeyDown}
        disabled={disabled}
      />
      <button type="submit" className="chat-input__send" disabled={disabled || !value.trim()} aria-label="전송">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M3.4 20.6 21 12 3.4 3.4 3.39 10l12 2-12 2z" fill="currentColor" />
        </svg>
      </button>
    </form>
  );
}

export default ChatInput;
