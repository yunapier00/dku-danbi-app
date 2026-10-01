function TypingIndicator() {
  return (
    <div className="message-row message-row--bot">
      <span className="message-avatar" aria-hidden="true">
        단
      </span>
      <div className="bubble bubble--bot bubble--typing" aria-label="단비가 입력 중입니다">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
      </div>
    </div>
  );
}

export default TypingIndicator;
