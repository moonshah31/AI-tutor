import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { clearToken, getCurrentUser, login as loginRequest, saveToken, storedToken, type User } from "../services/auth";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};
const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = storedToken();
    if (!token) { setLoading(false); return; }
    void getCurrentUser(token).then(setUser).catch(clearToken).finally(() => setLoading(false));
  }, []);

  const value = useMemo(() => ({
    user, loading,
    async login(email: string, password: string) {
      const response = await loginRequest(email, password);
      saveToken(response.access_token);
      setUser(response.user);
    },
    logout() { clearToken(); setUser(null); },
  }), [user, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
