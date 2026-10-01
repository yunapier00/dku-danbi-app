import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const markdownComponents = {
  p: (props) => <p className="bubble__markdown-p" {...props} />,
  ul: (props) => <ul className="bubble__markdown-list" {...props} />,
  ol: (props) => <ol className="bubble__markdown-list" {...props} />,
  a: (props) => <a target="_blank" rel="noreferrer" {...props} />,
  // 백엔드 답변의 취소선 표기는 의미가 없어 일반 텍스트로 보여준다 (기존 동작 유지).
  del: (props) => <span {...props} />,
  s: (props) => <span {...props} />,
};

function MessageBubble({ message }) {
  const isUser = message.sender === "user";

  return (
    <div className={`message-row message-row--${isUser ? "user" : "bot"}`}>
      {!isUser && (
        <span className="message-avatar" aria-hidden="true">
          단
        </span>
      )}
      <div className={`bubble bubble--${isUser ? "user" : "bot"}`}>
        {isUser ? (
          message.message
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {message.message}
          </ReactMarkdown>
        )}
      </div>
    </div>
  );
}

export default MessageBubble;
