"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import type { PulseUser, Invitation, DomainRule, AuditLogEntry, AuthSettings, UserRole } from "@/types/auth";
import { ROLE_DEFINITIONS, getRoleColor } from "@/types/auth";
import {
  getUsers,
  createUser,
  updateUser,
  deleteUser,
  getInvitations,
  createInvitation,
  revokeInvitation,
  getDomainRules,
  createDomainRule,
  updateDomainRule,
  deleteDomainRule,
  getAuthSettings,
  updateAuthSettings,
  getAuditLog,
  generateInviteUrl,
} from "@/lib/auth-db";

// ============================================================================
// TAB TYPES
// ============================================================================
type TabId = "users" | "invitations" | "pending" | "oidc" | "domain-rules" | "audit";

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  {
    id: "users",
    label: "Users",
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
      </svg>
    ),
  },
  {
    id: "invitations",
    label: "Invitations",
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
  },
  {
    id: "pending",
    label: "Pending Approvals",
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    id: "oidc",
    label: "OIDC / SSO",
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
      </svg>
    ),
  },
  {
    id: "domain-rules",
    label: "Domain Rules",
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
      </svg>
    ),
  },
  {
    id: "audit",
    label: "Audit Log",
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
  },
];

// ============================================================================
// MAIN COMPONENT
// ============================================================================
export default function AuthManagementPage() {
  const [activeTab, setActiveTab] = useState<TabId>("users");
  const [isLoading, setIsLoading] = useState(true);

  // Data states
  const [users, setUsers] = useState<PulseUser[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [domainRules, setDomainRules] = useState<DomainRule[]>([]);
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
  const [settings, setSettings] = useState<AuthSettings | null>(null);

  // Modal states
  const [showAddUser, setShowAddUser] = useState(false);
  const [showCreateInvitation, setShowCreateInvitation] = useState(false);
  const [showAddDomainRule, setShowAddDomainRule] = useState(false);
  const [editingUser, setEditingUser] = useState<PulseUser | null>(null);

  const isDev = process.env.NEXT_PUBLIC_USE_DEV_SESSION === "true";

  // Load data
  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [usersData, invitationsData, rulesData, settingsData, auditData] = await Promise.all([
        getUsers(),
        getInvitations(),
        getDomainRules(),
        getAuthSettings(),
        getAuditLog(100),
      ]);
      setUsers(usersData);
      setInvitations(invitationsData);
      setDomainRules(rulesData);
      setSettings(settingsData);
      setAuditLog(auditData);
    } catch (error) {
      console.error("Error loading auth data:", error);
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Computed values
  const pendingUsers = users.filter((u) => u.status === "pending");
  const activeUsers = users.filter((u) => u.status === "active");
  const pendingCount = pendingUsers.length;

  // Stats
  const stats = [
    { label: "Active Users", value: activeUsers.length, color: "blue" },
    { label: "Pending Approvals", value: pendingCount, color: pendingCount > 0 ? "yellow" : "gray" },
    { label: "Active Invitations", value: invitations.filter((i) => i.isActive).length, color: "green" },
    { label: "Domain Rules", value: domainRules.filter((r) => r.isActive).length, color: "purple" },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/admin" className="text-gray-500 hover:text-gray-700">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </Link>
          <div>
            <h1 className="text-2xl font-semibold">Authentication & Authorization</h1>
            <p className="text-sm text-gray-500">Manage users, invitations, SSO, and access control</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {settings?.authMode === "sso" ? (
            <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium">SSO Enabled</span>
          ) : (
            <span className="px-3 py-1 bg-amber-100 text-amber-700 rounded-full text-sm font-medium">Demo Mode</span>
          )}
        </div>
      </div>

      {/* Dev Mode Banner */}
      {isDev && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
              <svg className="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div>
              <h3 className="font-medium text-amber-900">Development Mode Active</h3>
              <p className="text-sm text-amber-700 mt-1">
                Demo credentials (demo/demo) have full Super Admin access. All data is stored in localStorage.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className={`rounded-xl p-4 border ${
              stat.color === "blue" ? "bg-blue-50 border-blue-200" :
              stat.color === "yellow" ? "bg-yellow-50 border-yellow-200" :
              stat.color === "green" ? "bg-green-50 border-green-200" :
              stat.color === "purple" ? "bg-purple-50 border-purple-200" :
              "bg-gray-50 border-gray-200"
            }`}
          >
            <div className="text-xs font-medium text-gray-500 uppercase">{stat.label}</div>
            <div className={`text-2xl font-bold ${
              stat.color === "blue" ? "text-blue-700" :
              stat.color === "yellow" ? "text-yellow-700" :
              stat.color === "green" ? "text-green-700" :
              stat.color === "purple" ? "text-purple-700" :
              "text-gray-700"
            }`}>
              {stat.value}
            </div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-gray-100 rounded-lg overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 whitespace-nowrap ${
              activeTab === tab.id
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            {tab.icon}
            {tab.label}
            {tab.id === "pending" && pendingCount > 0 && (
              <span className="ml-1 px-1.5 py-0.5 bg-yellow-500 text-white text-xs rounded-full">
                {pendingCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-2 border-gray-300 border-t-black rounded-full animate-spin" />
          </div>
        ) : (
          <>
            {activeTab === "users" && (
              <UsersTab
                users={users}
                onRefresh={loadData}
                onAddUser={() => setShowAddUser(true)}
                onEditUser={setEditingUser}
              />
            )}
            {activeTab === "invitations" && (
              <InvitationsTab
                invitations={invitations}
                onRefresh={loadData}
                onCreateInvitation={() => setShowCreateInvitation(true)}
              />
            )}
            {activeTab === "pending" && (
              <PendingApprovalsTab
                users={pendingUsers}
                onRefresh={loadData}
              />
            )}
            {activeTab === "oidc" && (
              <OIDCTab
                settings={settings}
                onRefresh={loadData}
              />
            )}
            {activeTab === "domain-rules" && (
              <DomainRulesTab
                rules={domainRules}
                onRefresh={loadData}
                onAddRule={() => setShowAddDomainRule(true)}
              />
            )}
            {activeTab === "audit" && (
              <AuditLogTab auditLog={auditLog} />
            )}
          </>
        )}
      </div>

      {/* Modals */}
      {showAddUser && (
        <AddUserModal
          onClose={() => setShowAddUser(false)}
          onSave={async (userData) => {
            await createUser(userData);
            await loadData();
            setShowAddUser(false);
          }}
        />
      )}

      {editingUser && (
        <EditUserModal
          user={editingUser}
          onClose={() => setEditingUser(null)}
          onSave={async (updates) => {
            await updateUser(editingUser.id, updates);
            await loadData();
            setEditingUser(null);
          }}
        />
      )}

      {showCreateInvitation && (
        <CreateInvitationModal
          onClose={() => setShowCreateInvitation(false)}
          onSave={async (invitation) => {
            await createInvitation(invitation);
            await loadData();
            setShowCreateInvitation(false);
          }}
        />
      )}

      {showAddDomainRule && (
        <AddDomainRuleModal
          onClose={() => setShowAddDomainRule(false)}
          onSave={async (rule) => {
            await createDomainRule(rule);
            await loadData();
            setShowAddDomainRule(false);
          }}
        />
      )}
    </div>
  );
}

// ============================================================================
// USERS TAB
// ============================================================================
function UsersTab({
  users,
  onRefresh,
  onAddUser,
  onEditUser,
}: {
  users: PulseUser[];
  onRefresh: () => Promise<void>;
  onAddUser: () => void;
  onEditUser: (user: PulseUser) => void;
}) {
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<UserRole | "all">("all");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive" | "pending">("all");

  const filteredUsers = users.filter((user) => {
    const matchesSearch =
      user.name.toLowerCase().includes(search.toLowerCase()) ||
      user.email.toLowerCase().includes(search.toLowerCase());
    const matchesRole = roleFilter === "all" || user.role === roleFilter;
    const matchesStatus = statusFilter === "all" || user.status === statusFilter;
    return matchesSearch && matchesRole && matchesStatus;
  });

  const handleDelete = async (userId: string) => {
    if (confirm("Are you sure you want to delete this user?")) {
      await deleteUser(userId);
      await onRefresh();
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between">
        <div>
          <h2 className="text-lg font-semibold">User Management</h2>
          <p className="text-sm text-gray-500">Manage user accounts and access levels</p>
        </div>
        <button
          onClick={onAddUser}
          className="px-4 py-2 bg-black text-white rounded-lg hover:bg-gray-800 transition-colors flex items-center gap-2 w-fit"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add User
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <input
          type="text"
          placeholder="Search by name or email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm flex-1 min-w-[200px]"
        />
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value as UserRole | "all")}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
        >
          <option value="all">All Roles</option>
          {Object.entries(ROLE_DEFINITIONS).map(([id, def]) => (
            <option key={id} value={id}>{def.name}</option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
        >
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
          <option value="pending">Pending</option>
        </select>
      </div>

      {/* Users Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">User</th>
              <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Role</th>
              <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Status</th>
              <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Auth</th>
              <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Last Login</th>
              <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.map((user) => (
              <tr key={user.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="py-3 px-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-sm font-medium">
                      {user.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div className="font-medium text-gray-900">{user.name}</div>
                      <div className="text-xs text-gray-500">{user.email}</div>
                    </div>
                  </div>
                </td>
                <td className="py-3 px-4">
                  <span className={`text-xs px-2 py-1 rounded-full border ${getRoleColor(user.role)}`}>
                    {ROLE_DEFINITIONS[user.role]?.name || user.role}
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className={`text-xs px-2 py-1 rounded-full ${
                    user.status === "active" ? "bg-green-100 text-green-700" :
                    user.status === "pending" ? "bg-yellow-100 text-yellow-700" :
                    "bg-gray-100 text-gray-700"
                  }`}>
                    {user.status}
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="text-xs text-gray-600">
                    {user.authMethod === "sso" ? "SSO" : "Local"}
                  </span>
                </td>
                <td className="py-3 px-4 text-sm text-gray-500">
                  {user.lastLogin ? new Date(user.lastLogin).toLocaleDateString() : "Never"}
                </td>
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => onEditUser(user)}
                      className="text-blue-600 hover:text-blue-800 text-sm"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(user.id)}
                      className="text-red-600 hover:text-red-800 text-sm"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {filteredUsers.length === 0 && (
              <tr>
                <td colSpan={6} className="py-8 text-center text-gray-500">
                  No users found matching your filters
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================================
// INVITATIONS TAB
// ============================================================================
function InvitationsTab({
  invitations,
  onRefresh,
  onCreateInvitation,
}: {
  invitations: Invitation[];
  onRefresh: () => Promise<void>;
  onCreateInvitation: () => void;
}) {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopyLink = async (invitation: Invitation) => {
    const url = generateInviteUrl(invitation.code);
    await navigator.clipboard.writeText(url);
    setCopiedId(invitation.id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleRevoke = async (id: string) => {
    if (confirm("Are you sure you want to revoke this invitation?")) {
      await revokeInvitation(id);
      await onRefresh();
    }
  };

  const activeInvitations = invitations.filter((i) => i.isActive);
  const expiredInvitations = invitations.filter((i) => !i.isActive);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between">
        <div>
          <h2 className="text-lg font-semibold">Invitations</h2>
          <p className="text-sm text-gray-500">Create email invitations or shareable invite links</p>
        </div>
        <button
          onClick={onCreateInvitation}
          className="px-4 py-2 bg-black text-white rounded-lg hover:bg-gray-800 transition-colors flex items-center gap-2 w-fit"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Create Invitation
        </button>
      </div>

      {/* Active Invitations */}
      {activeInvitations.length > 0 ? (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-gray-700">Active Invitations</h3>
          {activeInvitations.map((invitation) => (
            <div key={invitation.id} className="border border-gray-200 rounded-lg p-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      invitation.type === "email" ? "bg-blue-100 text-blue-700" : "bg-purple-100 text-purple-700"
                    }`}>
                      {invitation.type === "email" ? "Email" : "Link"}
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded-full border ${getRoleColor(invitation.role)}`}>
                      {ROLE_DEFINITIONS[invitation.role]?.name}
                    </span>
                    {invitation.requiresApproval && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-700">
                        Requires Approval
                      </span>
                    )}
                  </div>
                  {invitation.email && (
                    <div className="text-sm font-medium">{invitation.email}</div>
                  )}
                  {invitation.description && (
                    <div className="text-sm text-gray-600">{invitation.description}</div>
                  )}
                  <div className="text-xs text-gray-500">
                    Uses: {invitation.currentUses}/{invitation.maxUses} |
                    Expires: {new Date(invitation.expiresAt).toLocaleDateString()}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {invitation.type === "link" && (
                    <button
                      onClick={() => handleCopyLink(invitation)}
                      className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                        copiedId === invitation.id
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                      }`}
                    >
                      {copiedId === invitation.id ? "Copied!" : "Copy Link"}
                    </button>
                  )}
                  <button
                    onClick={() => handleRevoke(invitation.id)}
                    className="px-3 py-1.5 text-sm rounded-lg bg-red-100 text-red-700 hover:bg-red-200 transition-colors"
                  >
                    Revoke
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500">
          <svg className="w-12 h-12 mx-auto mb-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          <p>No active invitations</p>
          <p className="text-sm mt-1">Create an invitation to invite new users</p>
        </div>
      )}

      {/* Expired/Revoked Invitations */}
      {expiredInvitations.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-gray-500">Expired/Revoked Invitations</h3>
          <div className="opacity-60">
            {expiredInvitations.slice(0, 5).map((invitation) => (
              <div key={invitation.id} className="border border-gray-200 rounded-lg p-3 mb-2">
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <span>{invitation.type === "email" ? invitation.email : "Link invitation"}</span>
                  <span>-</span>
                  <span>{ROLE_DEFINITIONS[invitation.role]?.name}</span>
                  <span>-</span>
                  <span>Created {new Date(invitation.createdAt).toLocaleDateString()}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// PENDING APPROVALS TAB
// ============================================================================
function PendingApprovalsTab({
  users,
  onRefresh,
}: {
  users: PulseUser[];
  onRefresh: () => Promise<void>;
}) {
  const handleApprove = async (userId: string) => {
    await updateUser(userId, { status: "active" });
    await onRefresh();
  };

  const handleReject = async (userId: string) => {
    if (confirm("Are you sure you want to reject this user? They will be marked as inactive.")) {
      await updateUser(userId, { status: "inactive" });
      await onRefresh();
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Pending Approvals</h2>
        <p className="text-sm text-gray-500">Review and approve user access requests</p>
      </div>

      {users.length > 0 ? (
        <div className="space-y-3">
          {users.map((user) => (
            <div key={user.id} className="border border-yellow-200 bg-yellow-50 rounded-lg p-4">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-yellow-200 flex items-center justify-center text-lg font-medium text-yellow-700">
                    {user.name.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div className="font-medium text-gray-900">{user.name}</div>
                    <div className="text-sm text-gray-600">{user.email}</div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      Requested: {new Date(user.createdAt).toLocaleString()} |
                      Role: {ROLE_DEFINITIONS[user.role]?.name}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleApprove(user.id)}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Approve
                  </button>
                  <button
                    onClick={() => handleReject(user.id)}
                    className="px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors flex items-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                    Reject
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-12 text-gray-500">
          <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-lg font-medium">No pending approvals</p>
          <p className="text-sm mt-1">All user requests have been processed</p>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// OIDC TAB
// ============================================================================
interface OIDCDisplayConfig {
  clientId: string;
  tenantId: string;
  issuer: string;
  authorizationUrl: string;
  tokenUrl: string;
  isConfigured: boolean;
  mode: string;
}

function OIDCTab({
  settings,
  onRefresh,
}: {
  settings: AuthSettings | null;
  onRefresh: () => Promise<void>;
}) {
  const [isSaving, setIsSaving] = useState(false);
  const [oidcConfig, setOidcConfig] = useState<OIDCDisplayConfig>({
    clientId: "Loading...",
    tenantId: "Loading...",
    issuer: "Loading...",
    authorizationUrl: "Loading...",
    tokenUrl: "Loading...",
    isConfigured: false,
    mode: "demo",
  });

  // Fetch OIDC config from API at runtime
  useEffect(() => {
    async function fetchOIDCConfig() {
      try {
        const response = await fetch("/api/auth/oidc-config");
        if (response.ok) {
          const config = await response.json();
          setOidcConfig(config);
        }
      } catch (error) {
        console.error("Error fetching OIDC config:", error);
      }
    }
    fetchOIDCConfig();
  }, []);

  const handleToggleSSO = async (enabled: boolean) => {
    setIsSaving(true);
    try {
      await updateAuthSettings({
        authMode: enabled ? "sso" : "demo",
        ssoEnabled: enabled,
      });
      await onRefresh();
    } catch (error) {
      console.error("Error updating SSO settings:", error);
    }
    setIsSaving(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">OIDC / Single Sign-On</h2>
          <p className="text-sm text-gray-500">Configure Microsoft Entra ID (Azure AD) authentication</p>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={settings?.authMode === "sso"}
            onChange={(e) => handleToggleSSO(e.target.checked)}
            disabled={!oidcConfig.isConfigured || isSaving}
            className="sr-only peer"
          />
          <div className={`w-11 h-6 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all ${
            oidcConfig.isConfigured
              ? "bg-gray-200 peer-focus:ring-4 peer-focus:ring-blue-300 peer-checked:bg-blue-600"
              : "bg-gray-100 cursor-not-allowed"
          }`}></div>
          <span className="ml-2 text-sm font-medium">{settings?.authMode === "sso" ? "SSO Enabled" : "Demo Mode"}</span>
        </label>
      </div>

      {/* Configuration Status */}
      <div className={`rounded-xl p-4 border ${
        oidcConfig.isConfigured
          ? "bg-green-50 border-green-200"
          : "bg-amber-50 border-amber-200"
      }`}>
        <div className="flex items-start gap-3">
          <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
            oidcConfig.isConfigured ? "bg-green-100" : "bg-amber-100"
          }`}>
            {oidcConfig.isConfigured ? (
              <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            )}
          </div>
          <div>
            <h3 className={`font-medium ${oidcConfig.isConfigured ? "text-green-900" : "text-amber-900"}`}>
              {oidcConfig.isConfigured ? "OIDC Configured" : "OIDC Not Configured"}
            </h3>
            <p className={`text-sm mt-1 ${oidcConfig.isConfigured ? "text-green-700" : "text-amber-700"}`}>
              {oidcConfig.isConfigured
                ? "Microsoft Entra ID is configured and ready to use."
                : "Set the AZURE_AD_CLIENT_ID, AZURE_AD_CLIENT_SECRET, and AZURE_AD_TENANT_ID environment variables to enable SSO."}
            </p>
          </div>
        </div>
      </div>

      {/* OIDC Configuration Details */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="border border-gray-200 rounded-xl p-4">
          <h3 className="font-medium mb-4 flex items-center gap-2">
            <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Provider Configuration
          </h3>
          <div className="space-y-3 text-sm">
            <div>
              <div className="text-gray-500">Provider</div>
              <div className="font-medium">Microsoft Entra ID (Azure AD)</div>
            </div>
            <div>
              <div className="text-gray-500">Client ID</div>
              <div className="font-mono text-xs bg-gray-100 p-2 rounded">{oidcConfig.clientId}</div>
            </div>
            <div>
              <div className="text-gray-500">Tenant ID</div>
              <div className="font-mono text-xs bg-gray-100 p-2 rounded">{oidcConfig.tenantId}</div>
            </div>
            <div>
              <div className="text-gray-500">Mode</div>
              <div className="font-medium capitalize">{oidcConfig.mode}</div>
            </div>
          </div>
        </div>

        <div className="border border-gray-200 rounded-xl p-4">
          <h3 className="font-medium mb-4 flex items-center gap-2">
            <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
            Endpoints
          </h3>
          <div className="space-y-3 text-sm">
            <div>
              <div className="text-gray-500">Issuer</div>
              <div className="font-mono text-xs bg-gray-100 p-2 rounded break-all">{oidcConfig.issuer}</div>
            </div>
            <div>
              <div className="text-gray-500">Authorization URL</div>
              <div className="font-mono text-xs bg-gray-100 p-2 rounded break-all">{oidcConfig.authorizationUrl}</div>
            </div>
            <div>
              <div className="text-gray-500">Token URL</div>
              <div className="font-mono text-xs bg-gray-100 p-2 rounded break-all">{oidcConfig.tokenUrl}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Session Settings */}
      <div className="border border-gray-200 rounded-xl p-4">
        <h3 className="font-medium mb-4">Session Settings</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <div className="text-sm text-gray-500">Session Timeout</div>
            <div className="font-medium">{settings?.sessionTimeoutMinutes || 480} minutes</div>
          </div>
          <div>
            <div className="text-sm text-gray-500">Entra Sync</div>
            <div className="font-medium">{settings?.entraSyncEnabled ? "Every 24 hours" : "Disabled"}</div>
          </div>
          <div>
            <div className="text-sm text-gray-500">Auto-Disable After</div>
            <div className="font-medium">{settings?.autoDisableDays || 14} days inactive in Entra</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// DOMAIN RULES TAB
// ============================================================================
function DomainRulesTab({
  rules,
  onRefresh,
  onAddRule,
}: {
  rules: DomainRule[];
  onRefresh: () => Promise<void>;
  onAddRule: () => void;
}) {
  const handleToggle = async (id: string, isActive: boolean) => {
    await updateDomainRule(id, { isActive });
    await onRefresh();
  };

  const handleDelete = async (id: string) => {
    if (confirm("Are you sure you want to delete this domain rule?")) {
      await deleteDomainRule(id);
      await onRefresh();
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row gap-4 justify-between">
        <div>
          <h2 className="text-lg font-semibold">Domain Rules</h2>
          <p className="text-sm text-gray-500">Configure automatic provisioning for email domains</p>
        </div>
        <button
          onClick={onAddRule}
          className="px-4 py-2 bg-black text-white rounded-lg hover:bg-gray-800 transition-colors flex items-center gap-2 w-fit"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Domain Rule
        </button>
      </div>

      {rules.length > 0 ? (
        <div className="space-y-3">
          {rules.map((rule) => (
            <div key={rule.id} className={`border rounded-lg p-4 ${rule.isActive ? "border-gray-200" : "border-gray-200 opacity-50"}`}>
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">@{rule.domain}</span>
                    {rule.isActive ? (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">Active</span>
                    ) : (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">Inactive</span>
                    )}
                  </div>
                  <div className="text-sm text-gray-600">
                    Default role: <span className={`px-2 py-0.5 rounded-full text-xs border ${getRoleColor(rule.defaultRole)}`}>{ROLE_DEFINITIONS[rule.defaultRole]?.name}</span>
                    {rule.autoApprove ? (
                      <span className="ml-2 text-green-600">Auto-approve enabled</span>
                    ) : (
                      <span className="ml-2 text-yellow-600">Requires approval</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleToggle(rule.id, !rule.isActive)}
                    className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                      rule.isActive
                        ? "bg-gray-100 text-gray-700 hover:bg-gray-200"
                        : "bg-green-100 text-green-700 hover:bg-green-200"
                    }`}
                  >
                    {rule.isActive ? "Disable" : "Enable"}
                  </button>
                  <button
                    onClick={() => handleDelete(rule.id)}
                    className="px-3 py-1.5 text-sm rounded-lg bg-red-100 text-red-700 hover:bg-red-200 transition-colors"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500">
          <svg className="w-12 h-12 mx-auto mb-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
          </svg>
          <p>No domain rules configured</p>
          <p className="text-sm mt-1">Add a domain rule to automatically provision users from specific email domains</p>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// AUDIT LOG TAB
// ============================================================================
function AuditLogTab({ auditLog }: { auditLog: AuditLogEntry[] }) {
  const getActionColor = (action: string) => {
    switch (action) {
      case "create": return "bg-green-100 text-green-700";
      case "update": return "bg-blue-100 text-blue-700";
      case "delete": return "bg-red-100 text-red-700";
      case "revoke": return "bg-orange-100 text-orange-700";
      default: return "bg-gray-100 text-gray-700";
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Audit Log</h2>
        <p className="text-sm text-gray-500">Track changes to users, invitations, and settings</p>
      </div>

      {auditLog.length > 0 ? (
        <div className="space-y-2">
          {auditLog.map((entry) => (
            <div key={entry.id} className="border border-gray-200 rounded-lg p-3 hover:bg-gray-50">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getActionColor(entry.action)}`}>
                  {entry.action.toUpperCase()}
                </span>
                <span className="text-gray-600">{entry.entityType}</span>
                {entry.entityId && (
                  <span className="text-gray-400 font-mono text-xs">({entry.entityId})</span>
                )}
                <span className="text-gray-400">|</span>
                <span className="text-gray-500">{new Date(entry.performedAt).toLocaleString()}</span>
                {entry.performedByEmail && (
                  <>
                    <span className="text-gray-400">by</span>
                    <span className="text-gray-700">{entry.performedByEmail}</span>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500">
          <svg className="w-12 h-12 mx-auto mb-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p>No audit log entries</p>
          <p className="text-sm mt-1">Changes will be tracked here</p>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// ADD USER MODAL
// ============================================================================
function AddUserModal({
  onClose,
  onSave,
}: {
  onClose: () => void;
  onSave: (user: Omit<PulseUser, "id" | "createdAt" | "updatedAt">) => Promise<void>;
}) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<UserRole>("trainee");
  const [status, setStatus] = useState<"active" | "pending">("active");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await onSave({
        email,
        name,
        role,
        status,
        authMethod: "sso",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl p-6 max-w-md w-full">
        <h3 className="text-lg font-semibold mb-4">Add New User</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              placeholder="user@example.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              placeholder="Full Name"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            >
              {Object.entries(ROLE_DEFINITIONS).map(([id, def]) => (
                <option key={id} value={id}>{def.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Status</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as "active" | "pending")}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value="active">Active (Approved)</option>
              <option value="pending">Pending Approval</option>
            </select>
          </div>
          <div className="flex justify-end gap-2 pt-4">
            <button type="button" onClick={onClose} className="px-4 py-2 text-gray-600 hover:text-gray-800">
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 bg-black text-white rounded-lg hover:bg-gray-800 disabled:opacity-50"
            >
              {isSubmitting ? "Adding..." : "Add User"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============================================================================
// EDIT USER MODAL
// ============================================================================
function EditUserModal({
  user,
  onClose,
  onSave,
}: {
  user: PulseUser;
  onClose: () => void;
  onSave: (updates: Partial<PulseUser>) => Promise<void>;
}) {
  const [name, setName] = useState(user.name);
  const [role, setRole] = useState<UserRole>(user.role);
  const [status, setStatus] = useState(user.status);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await onSave({ name, role, status });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl p-6 max-w-md w-full">
        <h3 className="text-lg font-semibold mb-4">Edit User</h3>
        <div className="text-sm text-gray-500 mb-4">{user.email}</div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            >
              {Object.entries(ROLE_DEFINITIONS).map(([id, def]) => (
                <option key={id} value={id}>{def.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Status</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as PulseUser["status"])}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="pending">Pending</option>
            </select>
          </div>
          <div className="flex justify-end gap-2 pt-4">
            <button type="button" onClick={onClose} className="px-4 py-2 text-gray-600 hover:text-gray-800">
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 bg-black text-white rounded-lg hover:bg-gray-800 disabled:opacity-50"
            >
              {isSubmitting ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============================================================================
// CREATE INVITATION MODAL
// ============================================================================
function CreateInvitationModal({
  onClose,
  onSave,
}: {
  onClose: () => void;
  onSave: (invitation: Omit<Invitation, "id" | "code" | "currentUses" | "createdAt" | "isActive">) => Promise<void>;
}) {
  const [type, setType] = useState<"email" | "link">("email");
  const [email, setEmail] = useState("");
  const [description, setDescription] = useState("");
  const [role, setRole] = useState<UserRole>("trainee");
  const [maxUses, setMaxUses] = useState(1);
  const [expiresInDays, setExpiresInDays] = useState(7);
  const [requiresApproval, setRequiresApproval] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      const expiresAt = new Date();
      expiresAt.setDate(expiresAt.getDate() + expiresInDays);

      await onSave({
        type,
        email: type === "email" ? email : undefined,
        description: type === "link" ? description : undefined,
        role,
        maxUses: type === "link" ? maxUses : 1,
        expiresAt: expiresAt.toISOString(),
        requiresApproval,
        createdByEmail: "admin@pulse.training", // Would come from current user
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl p-6 max-w-md w-full">
        <h3 className="text-lg font-semibold mb-4">Create Invitation</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Type Selection */}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setType("email")}
              className={`flex-1 py-2 px-4 rounded-lg border-2 transition-colors ${
                type === "email" ? "border-blue-500 bg-blue-50" : "border-gray-200"
              }`}
            >
              <div className="font-medium">Email Invite</div>
              <div className="text-xs text-gray-500">Send to specific email</div>
            </button>
            <button
              type="button"
              onClick={() => setType("link")}
              className={`flex-1 py-2 px-4 rounded-lg border-2 transition-colors ${
                type === "link" ? "border-purple-500 bg-purple-50" : "border-gray-200"
              }`}
            >
              <div className="font-medium">Shareable Link</div>
              <div className="text-xs text-gray-500">Multi-use invite link</div>
            </button>
          </div>

          {type === "email" ? (
            <div>
              <label className="block text-sm font-medium mb-1">Email Address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                placeholder="user@example.com"
              />
            </div>
          ) : (
            <>
              <div>
                <label className="block text-sm font-medium mb-1">Description (optional)</label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  placeholder="e.g., Team onboarding link"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Maximum Uses</label>
                <input
                  type="number"
                  value={maxUses}
                  onChange={(e) => setMaxUses(parseInt(e.target.value) || 1)}
                  min={1}
                  max={1000}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
            </>
          )}

          <div>
            <label className="block text-sm font-medium mb-1">Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            >
              {Object.entries(ROLE_DEFINITIONS).map(([id, def]) => (
                <option key={id} value={id}>{def.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Expires In</label>
            <select
              value={expiresInDays}
              onChange={(e) => setExpiresInDays(parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value={1}>1 day</option>
              <option value={3}>3 days</option>
              <option value={7}>7 days</option>
              <option value={14}>14 days</option>
              <option value={30}>30 days</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="requiresApproval"
              checked={requiresApproval}
              onChange={(e) => setRequiresApproval(e.target.checked)}
              className="w-4 h-4"
            />
            <label htmlFor="requiresApproval" className="text-sm">
              Require admin approval before access is granted
            </label>
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <button type="button" onClick={onClose} className="px-4 py-2 text-gray-600 hover:text-gray-800">
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 bg-black text-white rounded-lg hover:bg-gray-800 disabled:opacity-50"
            >
              {isSubmitting ? "Creating..." : "Create Invitation"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============================================================================
// ADD DOMAIN RULE MODAL
// ============================================================================
function AddDomainRuleModal({
  onClose,
  onSave,
}: {
  onClose: () => void;
  onSave: (rule: Omit<DomainRule, "id" | "createdAt">) => Promise<void>;
}) {
  const [domain, setDomain] = useState("");
  const [defaultRole, setDefaultRole] = useState<UserRole>("trainee");
  const [autoApprove, setAutoApprove] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await onSave({
        domain: domain.toLowerCase().replace(/^@/, ""),
        defaultRole,
        autoApprove,
        isActive: true,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl p-6 max-w-md w-full">
        <h3 className="text-lg font-semibold mb-4">Add Domain Rule</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Domain</label>
            <div className="flex items-center">
              <span className="px-3 py-2 bg-gray-100 border border-r-0 border-gray-300 rounded-l-lg text-gray-500">@</span>
              <input
                type="text"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                required
                className="flex-1 px-3 py-2 border border-gray-300 rounded-r-lg"
                placeholder="example.com"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Default Role</label>
            <select
              value={defaultRole}
              onChange={(e) => setDefaultRole(e.target.value as UserRole)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            >
              {Object.entries(ROLE_DEFINITIONS).map(([id, def]) => (
                <option key={id} value={id}>{def.name}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="autoApprove"
              checked={autoApprove}
              onChange={(e) => setAutoApprove(e.target.checked)}
              className="w-4 h-4"
            />
            <label htmlFor="autoApprove" className="text-sm">
              Auto-approve users from this domain (skip admin approval)
            </label>
          </div>
          <div className="flex justify-end gap-2 pt-4">
            <button type="button" onClick={onClose} className="px-4 py-2 text-gray-600 hover:text-gray-800">
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 bg-black text-white rounded-lg hover:bg-gray-800 disabled:opacity-50"
            >
              {isSubmitting ? "Adding..." : "Add Rule"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
