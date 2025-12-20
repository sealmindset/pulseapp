"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";

const AUTH_KEY = "pulse_auth";

interface AuthContextType {
  isAuthenticated: boolean;
  user: { username: string } | null;
  login: (username: string, password: string) => boolean;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<{ username: string } | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load auth state from localStorage on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem(AUTH_KEY);
      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          if (parsed.isAuthenticated && parsed.user) {
            setIsAuthenticated(true);
            setUser(parsed.user);
          }
        } catch {
          // Invalid stored data, ignore
        }
      }
      setIsLoading(false);
    }
  }, []);

  // Mock login - accepts demo/demo credentials
  const login = (username: string, password: string): boolean => {
    // Dev mode: accept demo/demo
    if (username === "demo" && password === "demo") {
      const userData = { username };
      setIsAuthenticated(true);
      setUser(userData);
      if (typeof window !== "undefined") {
        localStorage.setItem(AUTH_KEY, JSON.stringify({ isAuthenticated: true, user: userData }));
      }
      return true;
    }
    return false;
  };

  const logout = () => {
    setIsAuthenticated(false);
    setUser(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem(AUTH_KEY);
    }
  };

  // Show nothing while loading to prevent flash
  if (isLoading) {
    return null;
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
