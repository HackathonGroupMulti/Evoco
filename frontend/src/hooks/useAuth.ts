import { useCallback, useState } from "react";

const TOKEN_KEY = "evoco_token";
const USER_KEY = "evoco_user";

export interface AuthUser {
  user_id: string;
  email: string;
}

interface TokenResponse {
  access_token: string;
  expires_in: number;
  user_id: string;
}

interface UseAuthReturn {
  user: AuthUser | null;
  isAuthenticated: boolean;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

function loadUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

async function authRequest(
  path: string,
  email: string,
  password: string
): Promise<{ user: AuthUser; token: string }> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ?? `Request failed (${res.status})`
    );
  }

  const data = (await res.json()) as TokenResponse;
  return {
    token: data.access_token,
    user: { user_id: data.user_id, email },
  };
}

export function useAuth(): UseAuthReturn {
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem(TOKEN_KEY)
  );
  const [user, setUser] = useState<AuthUser | null>(loadUser);

  const persist = useCallback((t: string, u: AuthUser) => {
    localStorage.setItem(TOKEN_KEY, t);
    localStorage.setItem(USER_KEY, JSON.stringify(u));
    setToken(t);
    setUser(u);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const { token: t, user: u } = await authRequest(
        "/api/auth/login",
        email,
        password
      );
      persist(t, u);
    },
    [persist]
  );

  const register = useCallback(
    async (email: string, password: string) => {
      const { token: t, user: u } = await authRequest(
        "/api/auth/register",
        email,
        password
      );
      persist(t, u);
    },
    [persist]
  );

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
  }, []);

  return {
    user,
    isAuthenticated: token !== null,
    token,
    login,
    register,
    logout,
  };
}
