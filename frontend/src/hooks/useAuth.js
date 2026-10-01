import { useCallback, useEffect, useState } from "react";
import { googleLoginUrl } from "../api/client";
import { DOMAIN_ERROR_MESSAGE } from "../constants/messages";

const TOKEN_STORAGE_KEY = "danbi_token";

/**
 * 로그인 상태를 관리한다. 토큰은 localStorage에 저장하고, OAuth 콜백이 돌려준
 * ?token= / ?error= 쿼리 파라미터를 최초 1회 읽어 처리한다.
 */
export function useAuth() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_STORAGE_KEY) || "");
  const [loginError, setLoginError] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tokenFromUrl = params.get("token");
    const errorFromUrl = params.get("error");

    if (tokenFromUrl) {
      localStorage.setItem(TOKEN_STORAGE_KEY, tokenFromUrl);
      setToken(tokenFromUrl);
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (errorFromUrl === "invalid_domain") {
      setLoginError(DOMAIN_ERROR_MESSAGE);
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  const login = useCallback(() => {
    window.location.href = googleLoginUrl();
  }, []);

  const logout = useCallback((reason = "") => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken("");
    setLoginError(reason);
  }, []);

  return { token, isLoggedIn: Boolean(token), loginError, login, logout };
}
