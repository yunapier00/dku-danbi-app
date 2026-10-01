import { useCallback, useEffect, useState } from "react";
import { fetchChatHistory, sendChatMessage } from "../api/client";
import { GREETING_MESSAGE, NETWORK_ERROR_MESSAGE } from "../constants/messages";

/**
 * 대화 메시지 상태와 전송/이력 로딩을 담당한다.
 * @param {string} token
 * @param {() => void} onSessionExpired 토큰이 더 이상 유효하지 않을 때(401) 호출된다.
 */
export function useChat(token, onSessionExpired) {
  const [messages, setMessages] = useState([GREETING_MESSAGE]);
  const [isTyping, setIsTyping] = useState(false);

  useEffect(() => {
    if (!token) return undefined;
    let cancelled = false;

    fetchChatHistory(token)
      .then((data) => {
        if (cancelled) return;
        setMessages(data.history?.length ? [GREETING_MESSAGE, ...data.history] : [GREETING_MESSAGE]);
      })
      .catch((error) => {
        if (cancelled) return;
        if (error.status === 401) {
          onSessionExpired();
          return;
        }
        console.error("대화 기록 로딩 실패:", error);
      });

    return () => {
      cancelled = true;
    };
  }, [token, onSessionExpired]);

  const sendMessage = useCallback(
    async (text) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      setMessages((prev) => [...prev, { message: trimmed, sender: "user", direction: "outgoing" }]);
      setIsTyping(true);

      try {
        const data = await sendChatMessage(token, trimmed);
        setMessages((prev) => [...prev, { message: data.answer, sender: "Danbi", direction: "incoming" }]);
      } catch (error) {
        if (error.status === 401) {
          onSessionExpired();
          return;
        }
        setMessages((prev) => [
          ...prev,
          { message: NETWORK_ERROR_MESSAGE, sender: "Danbi", direction: "incoming" },
        ]);
      } finally {
        setIsTyping(false);
      }
    },
    [token, onSessionExpired]
  );

  return { messages, isTyping, sendMessage };
}
