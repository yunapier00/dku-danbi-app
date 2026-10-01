import { useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble";
import TypingIndicator from "./TypingIndicator";
import "./MessageList.css";

function MessageList({ messages, isTyping }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages, isTyping]);

  return (
    <div className="message-list" role="log" aria-live="polite">
      {messages.map((msg, index) => (
        // eslint-disable-next-line react/no-array-index-key -- 메시지는 항상 뒤에 추가될 뿐 재정렬되지 않는다.
        <MessageBubble key={index} message={msg} />
      ))}
      {isTyping && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  );
}

export default MessageList;
