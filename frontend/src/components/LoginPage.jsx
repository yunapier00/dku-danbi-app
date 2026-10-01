import GoogleIcon from "./GoogleIcon";
import "./LoginPage.css";

function LoginPage({ onLogin, error }) {
  return (
    <div className="login-page">
      <div className="login-page__decoration" aria-hidden="true" />
      <div className="login-card">
        <div className="login-card__badge" aria-hidden="true">
          단비
        </div>
        <h1 className="login-card__title">단국대학교 AI 어시스턴트</h1>
        <p className="login-card__subtitle">죽전캠퍼스 학사 정보를 단비에게 물어보세요.</p>

        {error && (
          <p className="login-card__error" role="alert">
            {error}
          </p>
        )}

        <button type="button" className="google-button" onClick={onLogin}>
          <GoogleIcon />
          Google로 시작하기
        </button>

        <p className="login-card__footnote">단국대학교 학생을 위한 비공식 서비스입니다.</p>
      </div>
    </div>
  );
}

export default LoginPage;
