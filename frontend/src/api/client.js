// 백엔드 주소. VITE_API_URL 미설정 시 기존 운영 주소를 그대로 사용한다(동작 변화 없음).
const DEFAULT_API_BASE_URL = "https://dku-danbi-app-production.up.railway.app";

export const API_BASE_URL = import.meta.env.VITE_API_URL || DEFAULT_API_BASE_URL;

/**
 * 토큰에 섞여 들어올 수 있는 비-ASCII 문자를 제거한다.
 * HTTP 헤더 값은 ASCII만 허용되므로 Authorization 헤더에 싣기 전 반드시 거쳐야 한다.
 */
export function sanitizeToken(token) {
  // eslint-disable-next-line no-control-regex -- \x00-\x7F 는 ASCII 범위 경계이지 제어문자 매칭이 아니다.
  return (token ?? "").trim().replace(/[^\x00-\x7F]/g, "");
}

function authHeaders(token) {
  return { Authorization: `Bearer ${sanitizeToken(token)}` };
}

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function parseJsonOrThrow(response, fallbackMessage) {
  if (!response.ok) {
    throw new ApiError(`${fallbackMessage} (${response.status})`, response.status);
  }
  return response.json();
}

export async function fetchChatHistory(token) {
  const response = await fetch(`${API_BASE_URL}/api/web/history`, {
    method: "GET",
    headers: authHeaders(token),
  });
  return parseJsonOrThrow(response, "대화 기록을 불러오지 못했습니다.");
}

export async function sendChatMessage(token, query) {
  const response = await fetch(`${API_BASE_URL}/api/web/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ query, history: "" }),
  });
  return parseJsonOrThrow(response, "메시지를 보내지 못했습니다.");
}

export function googleLoginUrl() {
  return `${API_BASE_URL}/api/auth/login`;
}
