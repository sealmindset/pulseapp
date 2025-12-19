"use client";

import { createContext, useContext, useMemo, useState } from "react";

export type ScenarioFiltersState = {
  step?: string;
  objection?: string;
  framework?: string;
};

export type AvatarState = "idle" | "speaking" | "listening" | "thinking";

export type PersonaInfo = {
  type: string;
  displayName: string;
};

type SessionState = {
  persona: string | null;
  personaInfo: PersonaInfo | null;
  filters: ScenarioFiltersState;
  sessionId: string | null;
  avatarUrl: string | null;
  avatarVideoUrl: string | null;
  avatarState: AvatarState;
  setPersona: (p: string | null) => void;
  setPersonaInfo: (info: PersonaInfo | null) => void;
  setFilters: (f: ScenarioFiltersState) => void;
  setSessionId: (id: string | null) => void;
  setAvatarUrl: (u: string | null) => void;
  setAvatarVideoUrl: (u: string | null) => void;
  setAvatarState: (s: AvatarState) => void;
};

const SessionContext = createContext<SessionState | undefined>(undefined);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [persona, setPersona] = useState<string | null>(null);
  const [personaInfo, setPersonaInfo] = useState<PersonaInfo | null>(null);
  const [filters, setFilters] = useState<ScenarioFiltersState>({});
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [avatarVideoUrl, setAvatarVideoUrl] = useState<string | null>(null);
  const [avatarState, setAvatarState] = useState<AvatarState>("idle");

  const value = useMemo(
    () => ({
      persona,
      personaInfo,
      filters,
      sessionId,
      avatarUrl,
      avatarVideoUrl,
      avatarState,
      setPersona,
      setPersonaInfo,
      setFilters,
      setSessionId,
      setAvatarUrl,
      setAvatarVideoUrl,
      setAvatarState,
    }),
    [persona, personaInfo, filters, sessionId, avatarUrl, avatarVideoUrl, avatarState]
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
}
