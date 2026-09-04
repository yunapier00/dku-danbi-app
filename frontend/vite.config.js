import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server:{
	host: '0.0.0.0', // 외부 접속 허용
    allowedHosts: [
      'bf77-121-145-126-218.ngrok-free.app', // 🌟 본인의 ngrok 주소에서 'https://'를 뺀 도메인만 입력!
      // 혹은 아예 모든 ngrok 주소를 허용하고 싶다면 아래와 같이 작성할 수도 있습니다:
      // '.ngrok-free.app' 
    ]
  }
})
