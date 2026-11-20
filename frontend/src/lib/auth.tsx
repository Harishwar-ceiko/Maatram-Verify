import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api, getToken, setToken, type Role, type User } from "./api";

type AuthState = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  user: User | null;
  state: AuthState;
  signIn: (email: string, password: string) => Promise<User>;
  signUp: (
  fullName: string,
  email: string,
  password: string,
  volunteerActivities?: string,
  achievements?: string,
  ) => Promise<User>;

  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [state, setState] = useState<AuthState>(getToken() ? "loading" : "anonymous");

  useEffect(() => {
    if (!getToken()) {
      setState("anonymous");
      return;
    }
    let alive = true;
    api
      .me()
      .then((me) => {
        if (!alive) return;
        setUser(me);
        setState("authenticated");
      })
      .catch(() => {
        if (!alive) return;
        setToken(null);
        setUser(null);
        setState("anonymous");
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null);
      setState("anonymous");
    };
    window.addEventListener("maatram:unauthorized", onUnauthorized);
    return () => window.removeEventListener("maatram:unauthorized", onUnauthorized);
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const result = await api.login(email, password);
    setToken(result.access_token);
    setUser(result.user);
    setState("authenticated");
    return result.user;
  }, []);

  const signUp = useCallback(async (
    fullName: string,
    email: string,
    password: string,
    volunteerActivities?: string,
    achievements?: string,
  ) => {
    const result = await api.register(
      fullName,
      email,
      password,
      volunteerActivities,
      achievements,
    );
    setToken(result.access_token);
    setUser(result.user);
    setState("authenticated");
    return result.user;
  }, []);


  const signOut = useCallback(() => {
    setToken(null);
    setUser(null);
    setState("anonymous");
  }, []);

  const value = useMemo(
    () => ({ user, state, signIn, signUp, signOut }),
    [user, state, signIn, signUp, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}

export function landingFor(role: Role | undefined): string {
  return role === "admin" ? "/admin" : "/overview";
}
