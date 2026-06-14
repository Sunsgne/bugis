import React, { createContext, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api/client";

interface User {
  id: number;
  username: string;
  full_name?: string;
  role: string;
}

interface AuthCtx {
  user: User | null;
  ready: boolean;
  loginWithToken: (token: string) => Promise<void>;
  logout: () => void;
}

const Ctx = createContext<AuthCtx>(null as any);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  async function fetchMe() {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch {
      setUser(null);
    } finally {
      setReady(true);
    }
  }

  useEffect(() => {
    if (getToken()) fetchMe();
    else setReady(true);
  }, []);

  async function loginWithToken(token: string) {
    setToken(token);
    await fetchMe();
  }

  function logout() {
    setToken(null);
    setUser(null);
    location.href = "/login";
  }

  return (
    <Ctx.Provider value={{ user, ready, loginWithToken, logout }}>
      {children}
    </Ctx.Provider>
  );
}

export const useAuth = () => useContext(Ctx);
