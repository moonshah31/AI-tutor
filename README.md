# AI Tutor

AI Tutor is an educational web application that will help students understand academic concepts, solve problems step by step, and later learn from their own course materials.

## Phase 3: Tutor MVP

This repository provides a React + Vite frontend, a FastAPI backend, MongoDB lifecycle management, JWT authentication, and the first authenticated Gemini-powered tutor chat.

```
frontend (React + Vite) -> FastAPI `/api/chat` -> TutorService -> AIProvider -> Gemini
```

## Run locally

Prerequisites: Node.js 20+, Python 3.11+, and a MongoDB instance (local or Atlas).

```powershell
Copy-Item backend/.env.example backend/.env
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL (normally `http://localhost:5173`). The landing page verifies `GET /api/health` through the development proxy.

### Frontend API URL

The frontend uses relative `/api` URLs by default, which keeps the Vite development proxy working and supports same-origin production reverse proxies. For a separately hosted backend, set the Vite build-time variable `VITE_API_BASE_URL` to the backend origin, for example `https://api.example.com` (or `https://api.example.com/api`). Leave it unset or empty to use relative paths. This variable is public and must not contain secrets; rebuild the frontend after changing it.

### Containerized development

Docker Compose provides the same stack without installing Python or MongoDB locally:

```powershell
docker compose up --build
```

Open `http://localhost:5173`. The frontend container reverse-proxies `/api` to the backend, while MongoDB remains private to the Compose network. Stop it with `docker compose down`; add `--volumes` only when you explicitly want to remove local development data.

## API behavior

`GET /api/health` responds with a typed, non-sensitive operational status:

```json
{ "status": "ok", "database": "connected" }
```

If MongoDB is unavailable, it responds with HTTP 503 and a safe degraded status. Connection details are never exposed.

## Checks

```powershell
cd backend
pip install -r requirements-dev.txt
pytest
```

The health tests cover both the connected and degraded database responses.

## Structure and security baseline

- `backend/app/routes`: thin HTTP handlers
- `backend/app/schemas`: typed request/response contracts
- `backend/app/services`: business and external-provider logic
- `backend/app/models`: persistence models, added per feature
- `backend/app/prompts`: tutor prompt templates, added in the tutor phase
- Secrets stay in `backend/.env` and are ignored by Git.
- CORS is an explicit environment allowlist.
- MongoDB uses an application-scoped lifecycle-managed client.

Authentication, tutor providers, uploads, and RAG are deferred to their roadmap phases so each can be implemented with correct access control and test coverage.

## Authentication

The API creates users with Argon2 password hashes and issues short-lived JWT bearer tokens. Password hashing is a one-way, salted password-verification process, unlike encryption, which is designed to be reversible; plaintext passwords must therefore never be stored. The frontend keeps the token in `sessionStorage`, which is cleared on logout and browser-session end; this keeps the MVP simple but is susceptible to XSS, so a future production deployment should consider secure HttpOnly cookies with CSRF protection. The token and JWT signing secret are never returned as part of a user object.

Add these values to `backend/.env` (choose a unique long random secret):

```dotenv
JWT_SECRET_KEY=your-long-random-development-secret
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
GEMINI_API_KEY=your-gemini-api-key
# Optional; defaults to gemini-2.5-flash
GEMINI_MODEL=gemini-2.5-flash
```

For Docker Compose, set `JWT_SECRET_KEY` in the shell that runs `docker compose up`; it is intentionally not hard-coded in the compose file.

Endpoints:

- `POST /api/auth/register` creates an account and returns its safe public fields.
- `POST /api/auth/login` returns `{ access_token, token_type, user }`.
- `GET /api/users/me` requires `Authorization: Bearer <access_token>`.
- `POST /api/chat` requires `Authorization: Bearer <access_token>` and accepts a bounded current-session context: `{ "message": "Explain recursion", "messages": [{ "role": "user", "content": "..." }] }`.
- `GET /api/health` remains public.

MongoDB creates a unique index for normalized user email on startup. Future ownership-sensitive endpoints should use `get_current_user`, which loads the identity from the validated JWT rather than trusting a client-supplied user id.

## Tutor architecture and limits

Routes remain thin: `/api/chat` validates the request and derives the user from the JWT, `TutorService` builds the modular `ROLE / CONTEXT / TARGET / CONSTRAINTS` prompt, and an `AIProvider` abstraction calls `GeminiProvider`. Gemini credentials are read only by the backend from `GEMINI_API_KEY`; they are never sent to the browser.

The browser keeps the active conversation in memory and sends at most the ten most recent messages. Each message is limited to 4,000 characters. Conversations are not persisted to MongoDB and RAG/course-material retrieval is not implemented yet.

## Verification

Run backend tests and the frontend production build:

```powershell
cd backend
pip install -r requirements-dev.txt
pytest

cd ..\frontend
npm run build
```

Manual checks: start MongoDB, backend, and frontend; register or log in; open **Tutor**; ask “Explain recursion in simple terms.” and then “Give me a simple example.”; verify the second answer reflects the first topic. Confirm logout returns to login and `/tutor` redirects without a session. In Swagger, call `/api/chat` both with a valid bearer token and without one; repeat with an expired token. To check the safe provider failure path, temporarily remove `GEMINI_API_KEY` and submit a chat request—it should return a generic 503 message without exposing configuration details.
