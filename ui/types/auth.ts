// =============================================================================
// PULSE Authentication Types
// =============================================================================

export type UserRole = "super_admin" | "admin" | "manager" | "trainer" | "trainee";
export type UserStatus = "active" | "pending" | "inactive" | "disabled";
export type AuthMethod = "sso" | "local";
export type AuthMode = "demo" | "sso";
export type InvitationType = "email" | "link";

export interface PulseUser {
  id: string;
  email: string;
  name: string;
  entraObjectId?: string;
  role: UserRole;
  status: UserStatus;
  authMethod: AuthMethod;
  invitedBy?: string;
  invitationId?: string;
  lastLogin?: string;
  entraLastSync?: string;
  entraAccountEnabled?: boolean;
  disabledSince?: string;
  createdAt: string;
  updatedAt: string;
}

export interface Invitation {
  id: string;
  code: string;
  type: InvitationType;
  email?: string;
  description?: string;
  role: UserRole;
  expiresAt: string;
  maxUses: number;
  currentUses: number;
  requiresApproval: boolean;
  allowedDomains?: string[];
  notes?: string;
  createdBy?: string;
  createdByEmail?: string;
  createdByName?: string;
  createdAt: string;
  isActive: boolean;
}

export interface DomainRule {
  id: string;
  domain: string;
  defaultRole: UserRole;
  autoApprove: boolean;
  isActive: boolean;
  createdBy?: string;
  createdAt: string;
}

export interface AuditLogEntry {
  id: number;
  action: string;
  entityType: string;
  entityId?: string;
  oldValue?: Record<string, unknown>;
  newValue?: Record<string, unknown>;
  performedBy?: string;
  performedByEmail?: string;
  ipAddress?: string;
  userAgent?: string;
  performedAt: string;
}

export interface AuthSettings {
  authMode: AuthMode;
  ssoEnabled: boolean;
  requireApproval: boolean;
  sessionTimeoutMinutes: number;
  entraSyncEnabled: boolean;
  autoDisableDays: number;
}

export interface OIDCConfig {
  clientId: string;
  tenantId: string;
  // clientSecret is never exposed to frontend
  issuer: string;
  authorizationUrl: string;
  tokenUrl: string;
  userInfoUrl: string;
  redirectUri: string;
}

export interface RoleDefinition {
  id: UserRole;
  name: string;
  description: string;
  permissions: string[];
  color: string;
  canAccessAdmin: boolean;
  canManageUsers: boolean;
  canConfigureSystem: boolean;
}

// Default role definitions as a Record for easy lookup
export const ROLE_DEFINITIONS: Record<UserRole, RoleDefinition> = {
  super_admin: {
    id: "super_admin",
    name: "Super Administrator",
    description: "Full system access with all permissions - break glass account",
    permissions: ["*"],
    color: "red",
    canAccessAdmin: true,
    canManageUsers: true,
    canConfigureSystem: true,
  },
  admin: {
    id: "admin",
    name: "Administrator",
    description: "Manage users, settings, and content",
    permissions: ["users:*", "settings:*", "content:*", "reports:view", "training:*", "ai:*"],
    color: "purple",
    canAccessAdmin: true,
    canManageUsers: true,
    canConfigureSystem: false,
  },
  manager: {
    id: "manager",
    name: "Manager",
    description: "Manage trainees and view reports",
    permissions: ["users:view", "trainees:*", "reports:*", "content:view", "training:*", "ai:*"],
    color: "blue",
    canAccessAdmin: true,
    canManageUsers: false,
    canConfigureSystem: false,
  },
  trainer: {
    id: "trainer",
    name: "Trainer",
    description: "Conduct training sessions and provide feedback",
    permissions: ["trainees:view", "sessions:*", "feedback:*", "reports:view", "training:*", "ai:*"],
    color: "green",
    canAccessAdmin: false,
    canManageUsers: false,
    canConfigureSystem: false,
  },
  trainee: {
    id: "trainee",
    name: "Trainee",
    description: "Access training content, AI features, and sessions",
    permissions: ["training:access", "sessions:participate", "feedback:view", "ai:*"],
    color: "gray",
    canAccessAdmin: false,
    canManageUsers: false,
    canConfigureSystem: false,
  },
};

// Preset users for seeding
export const PRESET_USERS: Omit<PulseUser, "id" | "createdAt" | "updatedAt">[] = [
  // Break Glass Account
  {
    email: "rob.vance@sleepnumber.com",
    name: "Rob Vance",
    role: "super_admin",
    status: "active",
    authMethod: "sso",
  },
  // Trainees
  {
    email: "joshua.oldham@sleepnumber.com",
    name: "Josh Oldham",
    role: "trainee",
    status: "active",
    authMethod: "sso",
  },
  {
    email: "soumil.deshmukh@sleepnumber.com",
    name: "Soumil Deshmukh",
    role: "trainee",
    status: "active",
    authMethod: "sso",
  },
  {
    email: "mayura.javeri@sleepnumber.com",
    name: "Mayura Javeri",
    role: "trainee",
    status: "active",
    authMethod: "sso",
  },
  {
    email: "Melissa.Barra@sleepnumber.com",
    name: "Melissa Barra",
    role: "trainee",
    status: "active",
    authMethod: "sso",
  },
  {
    email: "Linda.Findley@sleepnumber.com",
    name: "Linda Findley",
    role: "trainee",
    status: "active",
    authMethod: "sso",
  },
  // Demo user for fallback
  {
    email: "demo@pulse.training",
    name: "Demo User",
    role: "super_admin",
    status: "active",
    authMethod: "local",
  },
];

// Helper functions
export function getRoleDefinition(roleId: UserRole): RoleDefinition {
  return ROLE_DEFINITIONS[roleId] || ROLE_DEFINITIONS.trainee;
}

export function getRoleColor(roleId: UserRole): string {
  const colorMap: Record<string, string> = {
    red: "bg-red-100 text-red-700 border-red-200",
    purple: "bg-purple-100 text-purple-700 border-purple-200",
    blue: "bg-blue-100 text-blue-700 border-blue-200",
    green: "bg-green-100 text-green-700 border-green-200",
    gray: "bg-gray-100 text-gray-700 border-gray-200",
  };
  return colorMap[getRoleDefinition(roleId).color] || colorMap.gray;
}

export function canAccessAdmin(role: UserRole): boolean {
  return getRoleDefinition(role).canAccessAdmin;
}

export function canManageUsers(role: UserRole): boolean {
  return getRoleDefinition(role).canManageUsers;
}

export function canConfigureSystem(role: UserRole): boolean {
  return getRoleDefinition(role).canConfigureSystem;
}

export function getStatusColor(status: UserStatus): string {
  const colorMap: Record<UserStatus, string> = {
    active: "bg-green-100 text-green-700",
    pending: "bg-yellow-100 text-yellow-700",
    inactive: "bg-gray-100 text-gray-700",
    disabled: "bg-red-100 text-red-700",
  };
  return colorMap[status];
}
