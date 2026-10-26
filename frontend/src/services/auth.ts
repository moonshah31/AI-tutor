import { apiUrl } from "./api";

const TOKEN_KEY = "ai_tutor_access_token";

export type User = { id: string; name: string; email: string };
type AuthResponse = { access_token: string; token_type: "bearer"; user: User };

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: string | Array<{
        type?: string;
        loc?: Array<string | number>;
        msg?: string;
      }>;
    } | null;

    let message = "The server could not complete your request. Please try again.";

    if (typeof body?.detail === "string") {
      message = body.detail;
    } else if (Array.isArray(body?.detail)) {
      message = body.detail
        .map((error) => error.msg)
        .filter(Boolean)
        .join(". ");
    }

    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export async function register(name: string, email: string, password: string): Promise<User> {
  return request<User>("/api/auth/register", { method: "POST", body: JSON.stringify({ name, email, password }) });
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
}

export async function getCurrentUser(token: string): Promise<User> {
  return request<User>("/api/users/me", { headers: { Authorization: `Bearer ${token}` } });
}

export function storedToken(): string | null { return sessionStorage.getItem(TOKEN_KEY); }
export function saveToken(token: string): void { sessionStorage.setItem(TOKEN_KEY, token); }
export function clearToken(): void { sessionStorage.removeItem(TOKEN_KEY); }
