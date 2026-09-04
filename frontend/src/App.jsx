import { useState, useEffect } from 'react';
import '@chatscope/chat-ui-kit-styles/dist/default/styles.min.css';
import {
  MainContainer, ChatContainer, MessageList, Message, MessageInput, TypingIndicator
} from '@chatscope/chat-ui-kit-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function App() {
  const [token, setToken] = useState(localStorage.getItem("danbi_token") || "");
  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem("danbi_token"));
  const [loginError, setLoginError] = useState("");
  
  // 🌟 앱이 켜질 때 화면이 쪼그라들지 않도록 초기값을 기본 인사말로 세팅합니다.
  const [messages, setMessages] = useState([{
      message: "안녕하세요! 단국대학교 죽전캠퍼스 AI 어시스턴트 단비입니다. 무엇을 도와드릴까요?",
      sender: "Danbi",
      direction: "incoming"
    }]);
  const [isTyping, setIsTyping] = useState(false);

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const tokenFromUrl = urlParams.get('token');
    const errorFromUrl = urlParams.get('error');
    
    let currentToken = localStorage.getItem("danbi_token");
    
    if (tokenFromUrl) {
      currentToken = tokenFromUrl;
      setToken(currentToken);
      setIsLoggedIn(true);
      localStorage.setItem("danbi_token", currentToken);
      window.history.replaceState({}, document.title, window.location.pathname);
    } 
    else if (errorFromUrl === "invalid_domain") {
      setLoginError("단국대학교 이메일(@dankook.ac.kr)로만 로그인할 수 있습니다.");
      window.history.replaceState({}, document.title, window.location.pathname);
    }

    // 🌟 어떤 상황에서도 항상 제일 위에 고정할 기본 인사말
    const defaultGreeting = {
      message: "안녕하세요! 단국대학교 죽전캠퍼스 AI 어시스턴트 단비입니다. 무엇을 도와드릴까요?",
      sender: "Danbi",
      direction: "incoming"
    };

    const fetchHistory = async (validToken) => {
      try {
        const cleanToken = validToken.trim().replace(/[^\x00-\x7F]/g, "");
        const response = await fetch("http://localhost:8000/api/web/history", {
          method: "GET",
          headers: { 
            "Authorization": `Bearer ${cleanToken}` 
          }
        });

        if (response.ok) {
          const data = await response.json();
          // 🌟 핵심 로직: DB 기록이 있으면 [기본인사말 + DB기록] 으로 합쳐서 띄움!
          if (data.history && data.history.length > 0) {
            setMessages([defaultGreeting, ...data.history]);
          } else {
            setMessages([defaultGreeting]);
          }
        }
      } catch (error) {
        console.error("대화 기록 로딩 실패:", error);
      }
    };

    if (currentToken) {
      fetchHistory(currentToken);
    }
  }, []);
  
  const handleLogout = () => {
    localStorage.removeItem("danbi_token");
    setToken("");
    setIsLoggedIn(false);
    setLoginError("");
  };

  const handleSend = async (message) => {
    const newMessage = { message, sender: "user", direction: "outgoing" };
    const newMessages = [...messages, newMessage];
    setMessages(newMessages);
    setIsTyping(true);

    try {
      const cleanToken = token.trim().replace(/[^\x00-\x7F]/g, "");
      const response = await fetch("http://localhost:8000/api/web/chat", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${cleanToken}`
        },
        body: JSON.stringify({ query: message, history: "" }) 
      });

      if (response.status === 401) {
        alert("세션이 만료되었습니다. 다시 로그인해주세요.");
        handleLogout();
        return;
      }

      const data = await response.json();
      setMessages([...newMessages, {
        message: data.answer, 
        sender: "Danbi",
        direction: "incoming"
      }]);
    } catch (error) {
      setMessages([...newMessages, {
        message: "서버와 연결할 수 없습니다. 백엔드를 확인해주세요.",
        sender: "Danbi",
        direction: "incoming"
      }]);
    } finally {
      setIsTyping(false);
    }
  };

  // ==========================================
  // 💅 예쁘게 꾸민 로그인 화면 UI
  // ==========================================
  if (!isLoggedIn) {
    return (
      <div style={{ 
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', 
        height: '100vh', 
        background: 'linear-gradient(135deg, #0055A4 0%, #003366 100%)',
        fontFamily: 'sans-serif' 
      }}>
        <div style={{ 
          backgroundColor: 'white', padding: '50px 40px', borderRadius: '16px', 
          boxShadow: '0 10px 25px rgba(0,0,0,0.2)', textAlign: 'center',
          maxWidth: '350px', width: '100%'
        }}>
          <div style={{ 
            width: '60px', height: '60px', backgroundColor: '#0055A4', color: 'white', 
            borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', 
            margin: '0 auto 20px', fontSize: '24px', fontWeight: 'bold' 
          }}>DKU</div>
          
          <h2 style={{ color: '#333', margin: '0 0 10px 0', fontSize: '20px' }}>단국대학교 죽전캠퍼스 AI 어시스턴트 단비</h2>
          <p style={{ color: '#777', fontSize: '14px', marginBottom: '30px', lineHeight: '1.5' }}>
            학교 이메일 계정으로 로그인해주세요.
          </p>

          {loginError && (
            <div style={{ 
              backgroundColor: '#fee', color: '#c00', padding: '12px', 
              borderRadius: '8px', fontSize: '13px', marginBottom: '20px',
              border: '1px solid #fcc'
            }}>
              🚨 {loginError}
            </div>
          )}
          
          <button 
            onClick={() => window.location.href = "http://localhost:8000/api/auth/login"}
            style={{ 
              display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', 
              padding: '14px 20px', backgroundColor: 'white', border: '1px solid #dadce0', 
              borderRadius: '8px', cursor: 'pointer', fontSize: '15px', fontWeight: '600', 
              color: '#3c4043', transition: 'background-color 0.2s',
              boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
            }}
            onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#f8f9fa'}
            onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'white'}
          >
            <img src="https://developers.google.com/identity/images/g-logo.png" alt="Google" style={{ width: '18px', height: '18px', marginRight: '12px' }}/>
            Google로 시작하기
          </button>
        </div>
      </div>
    );
  }

  // ==========================================
  // 💬 채팅 화면 UI
  // ==========================================
  return (
    <div style={{ 
      display: "flex", 
      flexDirection: "column", 
      height: "100dvh", // 혹은 100vh
      maxWidth: "100%", 
      margin: "0 auto", 
      backgroundColor: "#fff" 
    }}>
      {/* 상단 헤더 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '15px 20px', backgroundColor: '#0055A4', color: 'white', flexShrink: 0 }}>
        <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600' }}>단비 (Danbi)</h3>
        <button onClick={handleLogout} style={{ backgroundColor: 'rgba(255,255,255,0.2)', border: 'none', color: 'white', borderRadius: '6px', padding: '6px 12px', cursor: 'pointer', fontSize: '12px', fontWeight: 'bold' }}>
          로그아웃
        </button>
      </div>

      {/* 🌟 핵심: 남은 공간을 채우고 내부에서 스크롤되도록 설정 */}
      <div style={{ flex: 1, overflow: "hidden", position: "relative" }}>
        <MainContainer>
          <ChatContainer>
            <MessageList typingIndicator={isTyping ? <TypingIndicator content="단비가 생각하고 있어요..." /> : null}>
              {messages.map((msg, i) => (
                <Message key={i} model={{ direction: msg.direction }}>
                  <Message.CustomContent>
                    {msg.sender === "user" ? msg.message : (
                      <ReactMarkdown 
                        remarkPlugins={[remarkGfm]}
                        components={{
                          p: ({node, ...props}) => <span style={{ margin: 0 }} {...props} />,
                          ul: ({node, ...props}) => <ul style={{ margin: '8px 0', paddingLeft: '20px' }} {...props} />,
                          ol: ({node, ...props}) => <ol style={{ margin: '8px 0', paddingLeft: '20px' }} {...props} />,
                          del: ({node, ...props}) => <span style={{ textDecoration: 'none' }} {...props} />,
                          s: ({node, ...props}) => <span style={{ textDecoration: 'none' }} {...props} />
                        }}
                      >
                        {msg.message}
                      </ReactMarkdown>
                    )}
                  </Message.CustomContent>
                </Message>
              ))}
            </MessageList>
            <MessageInput placeholder="질문을 입력해주세요." onSend={handleSend} attachButton={false} />
          </ChatContainer>
        </MainContainer>
      </div>
    </div>
  );
}

export default App;