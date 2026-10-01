import { useAuth } from "./hooks/useAuth";
import LoginPage from "./components/LoginPage";
import ChatPage from "./components/ChatPage";

function App() {
  const auth = useAuth();

  if (!auth.isLoggedIn) {
    return <LoginPage onLogin={auth.login} error={auth.loginError} />;
  }

  return <ChatPage token={auth.token} onLogout={auth.logout} />;
}

export default App;
