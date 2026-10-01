import "./ChatHeader.css";

function ChatHeader({ onLogout }) {
  return (
    <header className="chat-header">
      <div className="chat-header__identity">
        <span className="chat-header__avatar" aria-hidden="true">
          단
        </span>
        <div className="chat-header__text">
          <p className="chat-header__title">단비</p>
          <p className="chat-header__subtitle">단국대학교 죽전캠퍼스 AI 어시스턴트</p>
        </div>
      </div>
      <button type="button" className="chat-header__logout" onClick={onLogout}>
        로그아웃
      </button>
    </header>
  );
}

export default ChatHeader;
