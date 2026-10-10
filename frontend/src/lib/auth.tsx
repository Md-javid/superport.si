"use client";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, tokenStore } from "./api";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string, remember: boolean) => Promise<void>;
  demoLogin: (persona?: string) => Promise<void>;
  signUp: (body: Parameters<typeof api.register>[0]) => Promise<Awaited<ReturnType<typeof api.register>>>;
  refresh: () => Promise<void>;
  logout: () => void;
}
const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tokenStore.get()) {
      setLoading(false);
      return;
    }
    api.me().then(setUser).catch(() => tokenStore.clear()).finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string, remember: boolean) => {
    const res = await api.login(email, password, remember);
    tokenStore.set(res.token, remember);
    setUser(res.user);
  }, []);
  const demoLogin = useCallback(async (persona = "broker") => {
    const res = await api.demoLogin(persona);
    tokenStore.set(res.token, false);
    setUser(res.user);
  }, []);
  const signUp = useCallback(async (body: Parameters<typeof api.register>[0]) => {
    const res = await api.register(body);
    tokenStore.set(res.token, true);
    setUser(res.user);
    return res;
  }, []);
  const refresh = useCallback(async () => {
    setUser(await api.me());
  }, []);
  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    window.location.href = "/login";
  }, []);

  return <Ctx.Provider value={{ user, loading, login, demoLogin, signUp, refresh, logout }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
