import React, { createContext, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api/client";

export interface User {
  id: number;
  username: string;
  full_name?: string;
  email?: string;
  role: string;
  scope?: string;
  tenant_id?: number | null;
  mfa_enabled?: boolean;
  mfa_method?: string;
  locale?: string;
  timezone?: string;
}

interface AuthCtx {
  user: User | null;
  ready: boolean;
  isTenantUser: boolean;
  loginWithToken: (token: string) => Promise<User | null>;
  refreshUser: () => Promise<User | null>;
  logout: () => void;
}

const Ctx = createContext<AuthCtx>(null as any);

export function isTenantAccount(user: User | null | undefined): boolean {
  if (!user) return false;
  return user.scope === "tenant" || user.tenant_id != null;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  async function fetchMe(): Promise<User | null> {
    try {
      const { data } = await api.get<User>("/auth/me");
      setUser(data);
      return data;
    } catch {
      setUser(null);
      return null;
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
    return fetchMe();
  }

  function logout() {
    setToken(null);
    setUser(null);
    location.href = "/login";
  }

  return (
    <Ctx.Provider
      value={{
        user,
        ready,
        isTenantUser: isTenantAccount(user),
        loginWithToken,
        refreshUser: fetchMe,
        logout,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export const useAuth = () => useContext(Ctx);
