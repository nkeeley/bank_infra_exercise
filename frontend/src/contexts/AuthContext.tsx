import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import { auth as authApi, accountHolders, setToken, clearToken } from "@/lib/api";
import type { UserSignupRequest, UserLoginRequest, AccountHolderResponse } from "@/types/api";

interface AuthState {
  isAuthenticated: boolean;
  userType: string | null; // "member" | "admin"
  email: string | null;
  profile: AccountHolderResponse | null;
  loading: boolean;
}

interface AuthContextType extends AuthState {
  login: (data: UserLoginRequest) => Promise<string>;
  signup: (data: UserSignupRequest) => Promise<void>;
  logout: () => void;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    isAuthenticated: !!localStorage.getItem("bank_token"),
    userType: localStorage.getItem("bank_user_type"),
    email: localStorage.getItem("bank_user_email"),
    profile: null,
    loading: true,
  });

  const refreshProfile = useCallback(async () => {
    try {
      if (state.userType === "admin") {
        setState(s => ({ ...s, loading: false }));
        return;
      }
      const profile = await accountHolders.me();
      setState(s => ({ ...s, profile, loading: false }));
    } catch {
      setState(s => ({ ...s, loading: false }));
    }
  }, [state.userType]);

  useEffect(() => {
    if (state.isAuthenticated) {
      refreshProfile();
    } else {
      setState(s => ({ ...s, loading: false }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.isAuthenticated]);

  const login = useCallback(async (data: UserLoginRequest) => {
    const res = await authApi.login(data);
    setToken(res.token);
    const userType = res.user_type || "member";
    localStorage.setItem("bank_user_type", userType);
    localStorage.setItem("bank_user_email", data.email);
    setState({ isAuthenticated: true, userType, email: data.email, profile: null, loading: true });
    return userType;
  }, []);

  const signup = useCallback(async (data: UserSignupRequest) => {
    const res = await authApi.signup(data);
    setToken(res.token);
    const userType = res.user_type || "member";
    localStorage.setItem("bank_user_type", userType);
    localStorage.setItem("bank_user_email", res.email);
    setState({ isAuthenticated: true, userType, email: res.email, profile: null, loading: true });
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setState({ isAuthenticated: false, userType: null, email: null, profile: null, loading: false });
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, signup, logout, refreshProfile }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
