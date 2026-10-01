import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 개발 중 ngrok 등으로 터널링할 때 허용할 호스트. .env.local 에
// VITE_DEV_ALLOWED_HOSTS=foo.ngrok-free.app,bar.ngrok-free.app 형태로 설정한다.
const devAllowedHosts = (process.env.VITE_DEV_ALLOWED_HOSTS || "")
  .split(",")
  .map((host) => host.trim())
  .filter(Boolean);

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0", // 외부 접속 허용 (로컬 네트워크, 터널링 도구 등)
    allowedHosts: devAllowedHosts,
  },
});
