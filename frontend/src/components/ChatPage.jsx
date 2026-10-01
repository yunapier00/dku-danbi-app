import { useCallback } from "react";
import { useChat } from "../hooks/useChat";
import { SESSION_EXPIRED_MESSAGE } from "../constants/messages";
import ChatHeader from "./ChatHeader";
import MessageList from "./MessageList";
import ChatInput from "./ChatInput";
import "./ChatPage.css";

function ChatPage({ token, onLogout }) {
  const handleSessionExpired = useCallback(() => onLogout(SESSION_EXPIRED_MESSAGE), [onLogout]);
  const { messages, isTyping, sendMessage } = useChat(token, handleSessionExpired);

  return (
    <div className="chat-page">
      <ChatHeader onLogout={() => onLogout()} />
      <MessageList messages={messages} isTyping={isTyping} />
      <ChatInput onSend={sendMessage} disabled={isTyping} />
    </div>
  );
}

export default ChatPage;
