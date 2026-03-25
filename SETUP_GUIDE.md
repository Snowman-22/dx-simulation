# 프로젝트 설치 및 실행 가이드

## 사전 준비

### 필수 설치
- **Python 3.10 이상** — https://www.python.org/downloads/
- **Node.js 18 이상** — https://nodejs.org/
- **Git** (선택)

### 필요한 파일
- `simulation/` 폴더 (FastAPI 백엔드)
- `frontend/` 폴더 (React 프론트엔드)
- `snowman-pemkey.pem` (SSH 터널용 PEM 키)

---

## 1. FastAPI 백엔드 (simulation)

### 1-1. 폴더 배치

```
C:\Users\{사용자}\Desktop\DX_go\simulation\   ← 백엔드
C:\Users\{사용자}\Desktop\DX_go\snowman-pemkey.pem  ← PEM 키 (simulation과 같은 레벨)
```

> **중요**: `snowman-pemkey.pem` 파일은 `Desktop\DX_go\` 폴더 바로 아래에 있어야 합니다.
> 경로가 다르면 `db.py`의 `SSH_KEY` 값을 수정해주세요.

### 1-2. 가상환경 생성 및 패키지 설치

```bash
cd C:\Users\{사용자}\Desktop\DX_go\simulation

# 가상환경 생성 (권장)
python -m venv venv

# 가상환경 활성화
# Windows CMD:
venv\Scripts\activate
# Windows PowerShell:
venv\Scripts\Activate.ps1
# Mac/Linux:
source venv/bin/activate

# 패키지 설치
pip install -r requirements.txt
```

### 1-3. 환경변수 설정

`simulation/` 폴더에 `.env` 파일을 생성하거나, 시스템 환경변수로 설정:

```bash
# Windows CMD (임시):
set OPENAI_API_KEY=your-openai-api-key

# Windows PowerShell (임시):
$env:OPENAI_API_KEY="your-openai-api-key"

# Mac/Linux:
export OPENAI_API_KEY="your-openai-api-key"
```

> **또는** `services/ai_explanation.py` 파일에 직접 API 키가 하드코딩되어 있으므로,
> 해당 키가 유효하면 환경변수 설정 없이도 동작합니다.

### 1-4. 서버 실행

```bash
cd C:\Users\{사용자}\Desktop\DX_go\simulation
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

정상 실행 시 다음 메시지가 출력됩니다:
```
[db] SSH tunnel started -> localhost:15432
[startup] PostgreSQL connected - product 3294 rows
[startup] floor_plan 14 rows
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 1-5. 동작 확인

브라우저에서 접속:
```
http://localhost:8000/api/floor-plans
```
JSON 형태의 도면 목록이 나오면 성공입니다.

---

## 2. React 프론트엔드 (frontend)

### 2-1. 폴더 배치

```
C:\Users\{사용자}\Desktop\DX_test\frontend\   ← 프론트엔드
```

### 2-2. 패키지 설치

```bash
cd C:\Users\{사용자}\Desktop\DX_test\frontend
npm install
```

### 2-3. 프록시 설정 확인

`vite.config.ts` 파일에서 백엔드 주소를 확인합니다:

```ts
// Spring Boot 백엔드 (EC2)
"/api": {
  target: "http://54.116.93.66:8080",
},
// STOMP WebSocket
"/ws": {
  target: "http://54.116.93.66:8080",
},
// FastAPI 시뮬레이션 (로컬)
"/sim-api": {
  target: "http://localhost:8000",   ← 위에서 실행한 FastAPI
},
```

> **다른 PC에서 FastAPI를 실행하는 경우**, `localhost:8000` 대신 해당 PC의 IP 주소로 변경해주세요.

### 2-4. 서버 실행

```bash
cd C:\Users\{사용자}\Desktop\DX_test\frontend
npm run dev
```

정상 실행 시:
```
VITE v7.x.x  ready in xxx ms
➜  Local:   http://localhost:5173/
```

### 2-5. 접속

브라우저에서:
```
http://localhost:5173
```

---

## 3. 실행 순서 (중요!)

1. **FastAPI 백엔드 먼저** 실행 (port 8000)
2. **React 프론트엔드** 실행 (port 5173)
3. 브라우저에서 `http://localhost:5173` 접속

---

## 4. 주요 기능별 접속 경로

| 기능 | URL |
|------|-----|
| 메인 페이지 | http://localhost:5173 |
| 추천 시작 | http://localhost:5173/recommend |
| 챗봇 | http://localhost:5173/chatbot |
| 추천 결과 | http://localhost:5173/recommendchatbot |
| 시뮬레이션 | http://localhost:5173/simulation |
| 로그인 | http://localhost:5173/login |
| 회원가입 | http://localhost:5173/signup |
| 마이페이지 | http://localhost:5173/mypage |

---

## 5. 트러블슈팅

### PEM 키 권한 오류 (Mac/Linux)
```bash
chmod 400 snowman-pemkey.pem
```

### 포트 충돌 (8000 또는 5173)
```bash
# Windows - 사용 중인 프로세스 확인
netstat -ano | findstr :8000

# 프로세스 종료
taskkill /F /PID {PID번호}
```

### SSH 터널 연결 실패
- EC2 인스턴스(54.116.93.66)가 켜져있는지 확인
- PEM 키 경로가 올바른지 확인
- 보안그룹에서 SSH(22번 포트) 접근이 허용되어 있는지 확인

### npm install 오류
```bash
# node_modules 삭제 후 재설치
rm -rf node_modules package-lock.json
npm install
```

### STOMP 연결 실패
- Spring Boot EC2(54.116.93.66:8080)가 켜져있는지 확인
- 로그인이 되어있는지 확인 (JWT 토큰 필요)

---

## 6. 기술 스택 요약

| 구분 | 기술 |
|------|------|
| 프론트엔드 | React 19 + TypeScript + Vite 7 |
| 상태관리 | TanStack React Query |
| HTTP 클라이언트 | Axios |
| 실시간 통신 | SockJS + @stomp/stompjs |
| 시뮬레이션 백엔드 | FastAPI (Python) |
| 메인 백엔드 | Spring Boot (EC2) |
| DB | PostgreSQL (AWS RDS) |
| AI | OpenAI GPT-4o / gpt-image-1 |
