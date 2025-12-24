// =============================================================================
// PULSE Authentication Database Operations
// =============================================================================
// This module provides database operations for the auth system.
// In production, these call the orchestrator Function App APIs.
// For development/demo mode, they use localStorage fallback.

import type {
  PulseUser,
  Invitation,
  DomainRule,
  AuditLogEntry,
  AuthSettings,
  UserRole,
  UserStatus,
  InvitationType,
  PRESET_USERS,
} from "@/types/auth";

const FUNCTION_APP_URL = process.env.NEXT_PUBLIC_FUNCTION_APP_URL || process.env.FUNCTION_APP_BASE_URL || "";
const IS_DEV = process.env.NODE_ENV === "development" || process.env.NEXT_PUBLIC_USE_DEV_SESSION === "true";

// Storage keys for localStorage fallback
const STORAGE_KEYS = {
  users: "pulse_auth_users_v2",
  invitations: "pulse_auth_invitations",
  domainRules: "pulse_auth_domain_rules",
  auditLog: "pulse_auth_audit_log",
  settings: "pulse_auth_settings_v2",
};

// =============================================================================
// Default Data
// =============================================================================

const DEFAULT_SETTINGS: AuthSettings = {
  authMode: "demo",
  ssoEnabled: false,
  requireApproval: true,
  sessionTimeoutMinutes: 480,
  entraSyncEnabled: true,
  autoDisableDays: 14,
};

const DEFAULT_DOMAIN_RULES: DomainRule[] = [
  {
    id: "default-sleepnumber",
    domain: "sleepnumber.com",
    defaultRole: "trainee",
    autoApprove: false,
    isActive: true,
    createdAt: new Date().toISOString(),
  },
];

// Preset users matching the SQL migration
const PRESET_USERS_DATA: PulseUser[] = [
  {
    id: "user-rob-vance",
    email: "rob.vance@sleepnumber.com",
    name: "Rob Vance",
    role: "super_admin",
    status: "active",
    authMethod: "sso",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
  {
    id: "user-josh-oldham",
    email: "joshua.oldham@sleepnumber.com",
    name: "Josh Oldham",
    role: "trainee",
    status: "active",
    authMethod: "sso",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
  {
    id: "user-soumil-deshmukh",
    email: "soumil.deshmukh@sleepnumber.com",
    name: "Soumil Deshmukh",
    role: "trainee",
    status: "active",
    authMethod: "sso",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
  {
    id: "user-mayura-javeri",
    email: "mayura.javeri@sleepnumber.com",
    name: "Mayura Javeri",
    role: "trainee",
    status: "active",
    authMethod: "sso",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
  {
    id: "user-melissa-barra",
    email: "Melissa.Barra@sleepnumber.com",
    name: "Melissa Barra",
    role: "trainee",
    status: "active",
    authMethod: "sso",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
  {
    id: "user-linda-findley",
    email: "Linda.Findley@sleepnumber.com",
    name: "Linda Findley",
    role: "trainee",
    status: "active",
    authMethod: "sso",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
  {
    id: "user-demo",
    email: "demo@pulse.training",
    name: "Demo User",
    role: "super_admin",
    status: "active",
    authMethod: "local",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
];

// =============================================================================
// LocalStorage Helpers
// =============================================================================

function getFromStorage<T>(key: string, defaultValue: T): T {
  if (typeof window === "undefined") return defaultValue;
  try {
    const stored = localStorage.getItem(key);
    return stored ? JSON.parse(stored) : defaultValue;
  } catch {
    return defaultValue;
  }
}

function saveToStorage<T>(key: string, value: T): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    console.error("Error saving to localStorage:", error);
  }
}

// Initialize with preset users if empty
function initializeUsers(): PulseUser[] {
  const stored = getFromStorage<PulseUser[]>(STORAGE_KEYS.users, []);
  if (stored.length === 0) {
    saveToStorage(STORAGE_KEYS.users, PRESET_USERS_DATA);
    return PRESET_USERS_DATA;
  }
  return stored;
}

// =============================================================================
// User Operations
// =============================================================================

export async function getUsers(): Promise<PulseUser[]> {
  if (IS_DEV || !FUNCTION_APP_URL) {
    return initializeUsers();
  }

  try {
    const response = await fetch(`${FUNCTION_APP_URL}/api/auth/users`);
    if (!response.ok) throw new Error("Failed to fetch users");
    return response.json();
  } catch (error) {
    console.error("Error fetching users:", error);
    return initializeUsers();
  }
}

export async function getUserByEmail(email: string): Promise<PulseUser | null> {
  const users = await getUsers();
  return users.find((u) => u.email.toLowerCase() === email.toLowerCase()) || null;
}

export async function createUser(user: Omit<PulseUser, "id" | "createdAt" | "updatedAt">): Promise<PulseUser> {
  const newUser: PulseUser = {
    ...user,
    id: `user-${Date.now()}`,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };

  if (IS_DEV || !FUNCTION_APP_URL) {
    const users = await getUsers();
    users.push(newUser);
    saveToStorage(STORAGE_KEYS.users, users);
    await logAuditEvent("create", "user", newUser.id, null, newUser);
    return newUser;
  }

  const response = await fetch(`${FUNCTION_APP_URL}/api/auth/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(user),
  });

  if (!response.ok) throw new Error("Failed to create user");
  return response.json();
}

export async function updateUser(id: string, updates: Partial<PulseUser>): Promise<PulseUser> {
  if (IS_DEV || !FUNCTION_APP_URL) {
    const users = await getUsers();
    const index = users.findIndex((u) => u.id === id);
    if (index === -1) throw new Error("User not found");

    const oldUser = { ...users[index] };
    users[index] = { ...users[index], ...updates, updatedAt: new Date().toISOString() };
    saveToStorage(STORAGE_KEYS.users, users);
    await logAuditEvent("update", "user", id, oldUser, users[index]);
    return users[index];
  }

  const response = await fetch(`${FUNCTION_APP_URL}/api/auth/users/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });

  if (!response.ok) throw new Error("Failed to update user");
  return response.json();
}

export async function deleteUser(id: string): Promise<void> {
  if (IS_DEV || !FUNCTION_APP_URL) {
    const users = await getUsers();
    const user = users.find((u) => u.id === id);
    const filtered = users.filter((u) => u.id !== id);
    saveToStorage(STORAGE_KEYS.users, filtered);
    if (user) {
      await logAuditEvent("delete", "user", id, user, null);
    }
    return;
  }

  const response = await fetch(`${FUNCTION_APP_URL}/api/auth/users/${id}`, {
    method: "DELETE",
  });

  if (!response.ok) throw new Error("Failed to delete user");
}

export async function approveUser(id: string): Promise<PulseUser> {
  return updateUser(id, { status: "active" });
}

export async function rejectUser(id: string): Promise<void> {
  await updateUser(id, { status: "inactive" });
}

// =============================================================================
// Invitation Operations
// =============================================================================

function generateInviteCode(): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let code = "";
  for (let i = 0; i < 32; i++) {
    code += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return code;
}

export async function getInvitations(): Promise<Invitation[]> {
  if (IS_DEV || !FUNCTION_APP_URL) {
    return getFromStorage<Invitation[]>(STORAGE_KEYS.invitations, []);
  }

  try {
    const response = await fetch(`${FUNCTION_APP_URL}/api/auth/invitations`);
    if (!response.ok) throw new Error("Failed to fetch invitations");
    return response.json();
  } catch (error) {
    console.error("Error fetching invitations:", error);
    return [];
  }
}

export async function createInvitation(
  invitation: Omit<Invitation, "id" | "code" | "currentUses" | "createdAt" | "isActive">
): Promise<Invitation> {
  const newInvitation: Invitation = {
    ...invitation,
    id: `inv-${Date.now()}`,
    code: generateInviteCode(),
    currentUses: 0,
    createdAt: new Date().toISOString(),
    isActive: true,
  };

  if (IS_DEV || !FUNCTION_APP_URL) {
    const invitations = await getInvitations();
    invitations.push(newInvitation);
    saveToStorage(STORAGE_KEYS.invitations, invitations);
    await logAuditEvent("create", "invitation", newInvitation.id, null, newInvitation);
    return newInvitation;
  }

  const response = await fetch(`${FUNCTION_APP_URL}/api/auth/invitations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(invitation),
  });

  if (!response.ok) throw new Error("Failed to create invitation");
  return response.json();
}

export async function validateInvitation(code: string): Promise<Invitation | null> {
  const invitations = await getInvitations();
  const invitation = invitations.find((i) => i.code === code && i.isActive);

  if (!invitation) return null;

  // Check expiration
  if (new Date(invitation.expiresAt) < new Date()) {
    return null;
  }

  // Check max uses
  if (invitation.currentUses >= invitation.maxUses) {
    return null;
  }

  return invitation;
}

export async function consumeInvitation(code: string): Promise<void> {
  if (IS_DEV || !FUNCTION_APP_URL) {
    const invitations = await getInvitations();
    const index = invitations.findIndex((i) => i.code === code);
    if (index !== -1) {
      invitations[index].currentUses += 1;
      saveToStorage(STORAGE_KEYS.invitations, invitations);
    }
    return;
  }

  await fetch(`${FUNCTION_APP_URL}/api/auth/invitations/${code}/use`, {
    method: "POST",
  });
}

export async function revokeInvitation(id: string): Promise<void> {
  if (IS_DEV || !FUNCTION_APP_URL) {
    const invitations = await getInvitations();
    const index = invitations.findIndex((i) => i.id === id);
    if (index !== -1) {
      invitations[index].isActive = false;
      saveToStorage(STORAGE_KEYS.invitations, invitations);
      await logAuditEvent("revoke", "invitation", id, null, { isActive: false });
    }
    return;
  }

  await fetch(`${FUNCTION_APP_URL}/api/auth/invitations/${id}`, {
    method: "DELETE",
  });
}

// =============================================================================
// Domain Rules Operations
// =============================================================================

export async function getDomainRules(): Promise<DomainRule[]> {
  if (IS_DEV || !FUNCTION_APP_URL) {
    const stored = getFromStorage<DomainRule[]>(STORAGE_KEYS.domainRules, []);
    if (stored.length === 0) {
      saveToStorage(STORAGE_KEYS.domainRules, DEFAULT_DOMAIN_RULES);
      return DEFAULT_DOMAIN_RULES;
    }
    return stored;
  }

  try {
    const response = await fetch(`${FUNCTION_APP_URL}/api/auth/domain-rules`);
    if (!response.ok) throw new Error("Failed to fetch domain rules");
    return response.json();
  } catch (error) {
    console.error("Error fetching domain rules:", error);
    return DEFAULT_DOMAIN_RULES;
  }
}

export async function createDomainRule(
  rule: Omit<DomainRule, "id" | "createdAt">
): Promise<DomainRule> {
  const newRule: DomainRule = {
    ...rule,
    id: `rule-${Date.now()}`,
    createdAt: new Date().toISOString(),
  };

  if (IS_DEV || !FUNCTION_APP_URL) {
    const rules = await getDomainRules();
    rules.push(newRule);
    saveToStorage(STORAGE_KEYS.domainRules, rules);
    return newRule;
  }

  const response = await fetch(`${FUNCTION_APP_URL}/api/auth/domain-rules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(rule),
  });

  if (!response.ok) throw new Error("Failed to create domain rule");
  return response.json();
}

export async function updateDomainRule(id: string, updates: Partial<DomainRule>): Promise<DomainRule> {
  if (IS_DEV || !FUNCTION_APP_URL) {
    const rules = await getDomainRules();
    const index = rules.findIndex((r) => r.id === id);
    if (index === -1) throw new Error("Domain rule not found");
    rules[index] = { ...rules[index], ...updates };
    saveToStorage(STORAGE_KEYS.domainRules, rules);
    return rules[index];
  }

  const response = await fetch(`${FUNCTION_APP_URL}/api/auth/domain-rules/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });

  if (!response.ok) throw new Error("Failed to update domain rule");
  return response.json();
}

export async function deleteDomainRule(id: string): Promise<void> {
  if (IS_DEV || !FUNCTION_APP_URL) {
    const rules = await getDomainRules();
    const filtered = rules.filter((r) => r.id !== id);
    saveToStorage(STORAGE_KEYS.domainRules, filtered);
    return;
  }

  const response = await fetch(`${FUNCTION_APP_URL}/api/auth/domain-rules/${id}`, {
    method: "DELETE",
  });

  if (!response.ok) throw new Error("Failed to delete domain rule");
}

// =============================================================================
// Settings Operations
// =============================================================================

export async function getAuthSettings(): Promise<AuthSettings> {
  // In browser, fetch from our local API which has access to server env vars
  if (typeof window !== "undefined") {
    try {
      const response = await fetch("/api/auth/settings");
      if (response.ok) {
        const settings = await response.json();
        return { ...DEFAULT_SETTINGS, ...settings };
      }
    } catch (error) {
      console.error("Error fetching auth settings:", error);
    }
    // Fallback to localStorage for development
    return getFromStorage<AuthSettings>(STORAGE_KEYS.settings, DEFAULT_SETTINGS);
  }

  // Server-side: read from environment
  const authMode = process.env.AUTH_MODE || "demo";
  return {
    ...DEFAULT_SETTINGS,
    authMode: authMode === "sso" ? "sso" : "demo",
    ssoEnabled: authMode === "sso",
  };
}

export async function updateAuthSettings(updates: Partial<AuthSettings>): Promise<AuthSettings> {
  if (IS_DEV || !FUNCTION_APP_URL) {
    const current = await getAuthSettings();
    const updated = { ...current, ...updates };
    saveToStorage(STORAGE_KEYS.settings, updated);
    await logAuditEvent("update", "settings", "auth_settings", current, updated);
    return updated;
  }

  const response = await fetch(`${FUNCTION_APP_URL}/api/auth/settings`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });

  if (!response.ok) throw new Error("Failed to update settings");
  return response.json();
}

// =============================================================================
// Audit Log Operations
// =============================================================================

export async function logAuditEvent(
  action: string,
  entityType: string,
  entityId: string | null,
  oldValue: unknown,
  newValue: unknown,
  performedByEmail?: string
): Promise<void> {
  const entry: AuditLogEntry = {
    id: Date.now(),
    action,
    entityType,
    entityId: entityId || undefined,
    oldValue: oldValue as Record<string, unknown> | undefined,
    newValue: newValue as Record<string, unknown> | undefined,
    performedByEmail,
    performedAt: new Date().toISOString(),
  };

  if (IS_DEV || !FUNCTION_APP_URL) {
    const log = getFromStorage<AuditLogEntry[]>(STORAGE_KEYS.auditLog, []);
    log.unshift(entry);
    // Keep only last 500 entries
    saveToStorage(STORAGE_KEYS.auditLog, log.slice(0, 500));
    return;
  }

  try {
    await fetch(`${FUNCTION_APP_URL}/api/auth/audit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(entry),
    });
  } catch (error) {
    console.error("Error logging audit event:", error);
  }
}

export async function getAuditLog(limit: number = 100): Promise<AuditLogEntry[]> {
  if (IS_DEV || !FUNCTION_APP_URL) {
    return getFromStorage<AuditLogEntry[]>(STORAGE_KEYS.auditLog, []).slice(0, limit);
  }

  try {
    const response = await fetch(`${FUNCTION_APP_URL}/api/auth/audit?limit=${limit}`);
    if (!response.ok) throw new Error("Failed to fetch audit log");
    return response.json();
  } catch (error) {
    console.error("Error fetching audit log:", error);
    return [];
  }
}

// =============================================================================
// User Check (for SSO sign-in)
// =============================================================================

export async function checkUserAccess(
  email: string,
  name: string,
  entraObjectId?: string
): Promise<{ allowed: boolean; status?: UserStatus; user?: PulseUser; reason?: string }> {
  // Check if user exists
  let user = await getUserByEmail(email);

  if (user) {
    // Update Entra Object ID if provided and not set
    if (entraObjectId && !user.entraObjectId) {
      user = await updateUser(user.id, { entraObjectId });
    }

    // Check status
    if (user.status === "active") {
      return { allowed: true, status: "active", user };
    }
    if (user.status === "pending") {
      return { allowed: false, status: "pending", user, reason: "Awaiting approval" };
    }
    return { allowed: false, status: user.status, reason: "Account not active" };
  }

  // User doesn't exist - check domain rules and invitations
  const domain = email.split("@")[1]?.toLowerCase();
  const rules = await getDomainRules();
  const domainRule = rules.find((r) => r.domain.toLowerCase() === domain && r.isActive);

  if (domainRule) {
    // Create user based on domain rule
    const newUser = await createUser({
      email,
      name,
      entraObjectId,
      role: domainRule.defaultRole,
      status: domainRule.autoApprove ? "active" : "pending",
      authMethod: "sso",
    });

    if (domainRule.autoApprove) {
      return { allowed: true, status: "active", user: newUser };
    }
    return { allowed: false, status: "pending", user: newUser, reason: "Awaiting approval" };
  }

  // No domain rule - check for email-based invitation
  const invitations = await getInvitations();
  const emailInvite = invitations.find(
    (i) =>
      i.type === "email" &&
      i.email?.toLowerCase() === email.toLowerCase() &&
      i.isActive &&
      new Date(i.expiresAt) > new Date() &&
      i.currentUses < i.maxUses
  );

  if (emailInvite) {
    await consumeInvitation(emailInvite.code);
    const newUser = await createUser({
      email,
      name,
      entraObjectId,
      role: emailInvite.role,
      status: emailInvite.requiresApproval ? "pending" : "active",
      authMethod: "sso",
      invitationId: emailInvite.id,
    });

    if (!emailInvite.requiresApproval) {
      return { allowed: true, status: "active", user: newUser };
    }
    return { allowed: false, status: "pending", user: newUser, reason: "Awaiting approval" };
  }

  // No access
  return { allowed: false, reason: "No invitation or domain rule found" };
}

// =============================================================================
// Utility Functions
// =============================================================================

export function generateInviteUrl(code: string): string {
  const baseUrl = typeof window !== "undefined" ? window.location.origin : "";
  return `${baseUrl}/invite/${code}`;
}

export async function getPendingApprovals(): Promise<PulseUser[]> {
  const users = await getUsers();
  return users.filter((u) => u.status === "pending");
}

export async function getActiveUserCount(): Promise<number> {
  const users = await getUsers();
  return users.filter((u) => u.status === "active").length;
}
