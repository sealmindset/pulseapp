"use client";

import { createContext, useContext, useMemo, useState } from "react";

export type ScenarioFiltersState = {
  step?: string;
  objection?: string;
  framework?: string;
};

type SessionState = {
  persona: string | null;
  filters: ScenarioFiltersState;
  sessionId: string | null;
  avatarUrl: string | null;
  setPersona: (p: string | null) => void;
  setFilters: (f: ScenarioFiltersState) => void;
  setSessionId: (id: string | null) => void;
  setAvatarUrl: (u: string | null) => void;
};

const SessionContext = createContext<SessionState | undefined>(undefined);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [persona, setPersona] = useState<string | null>(null);
  const [filters, setFilters] = useState<ScenarioFiltersState>({});
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);

  const value = useMemo(
    () => ({ persona, filters, sessionId, avatarUrl, setPersona, setFilters, setSessionId, setAvatarUrl }),
    [persona, filters, sessionId, avatarUrl]
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
}
