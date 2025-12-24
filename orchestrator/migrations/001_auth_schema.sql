-- PULSE Authentication Schema
-- Migration: 001_auth_schema.sql
-- Created: 2024-12-23
-- Purpose: OIDC/Entra ID authentication with invitation system

-- =============================================================================
-- Auth Settings Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS pulse_auth_settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert default settings
INSERT INTO pulse_auth_settings (key, value, description) VALUES
    ('auth_mode', 'demo', 'Authentication mode: demo, sso'),
    ('sso_enabled', 'false', 'Whether SSO/OIDC is enabled'),
    ('require_approval', 'true', 'Whether new signups require admin approval'),
    ('session_timeout_minutes', '480', 'Session timeout in minutes'),
    ('entra_sync_enabled', 'true', 'Whether to sync with Entra ID'),
    ('auto_disable_days', '14', 'Days after Entra disable to revoke PULSE access')
ON CONFLICT (key) DO NOTHING;

-- =============================================================================
-- Users Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS pulse_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    entra_object_id VARCHAR(255) UNIQUE,
    role VARCHAR(50) NOT NULL DEFAULT 'trainee',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    auth_method VARCHAR(20) NOT NULL DEFAULT 'sso',
    invited_by UUID,
    invitation_id UUID,
    last_login TIMESTAMP,
    entra_last_sync TIMESTAMP,
    entra_account_enabled BOOLEAN DEFAULT TRUE,
    disabled_since TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT valid_role CHECK (role IN ('super_admin', 'admin', 'manager', 'trainer', 'trainee')),
    CONSTRAINT valid_status CHECK (status IN ('active', 'pending', 'inactive', 'disabled'))
);

-- Create index for email lookups
CREATE INDEX IF NOT EXISTS idx_pulse_users_email ON pulse_users(email);
CREATE INDEX IF NOT EXISTS idx_pulse_users_entra_id ON pulse_users(entra_object_id);
CREATE INDEX IF NOT EXISTS idx_pulse_users_status ON pulse_users(status);

-- =============================================================================
-- Invitations Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS pulse_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(64) UNIQUE NOT NULL,
    type VARCHAR(20) NOT NULL,
    email VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'trainee',
    expires_at TIMESTAMP NOT NULL,
    max_uses INTEGER DEFAULT 1,
    current_uses INTEGER DEFAULT 0,
    requires_approval BOOLEAN DEFAULT TRUE,
    allowed_domains TEXT[],
    notes TEXT,
    created_by UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    CONSTRAINT valid_invitation_type CHECK (type IN ('email', 'link')),
    CONSTRAINT valid_invitation_role CHECK (role IN ('super_admin', 'admin', 'manager', 'trainer', 'trainee'))
);

CREATE INDEX IF NOT EXISTS idx_pulse_invitations_code ON pulse_invitations(code);
CREATE INDEX IF NOT EXISTS idx_pulse_invitations_email ON pulse_invitations(email);

-- =============================================================================
-- Domain Rules Table (for auto-provisioning)
-- =============================================================================
CREATE TABLE IF NOT EXISTS pulse_domain_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain VARCHAR(255) UNIQUE NOT NULL,
    default_role VARCHAR(50) NOT NULL DEFAULT 'trainee',
    auto_approve BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_by UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT valid_domain_role CHECK (default_role IN ('super_admin', 'admin', 'manager', 'trainer', 'trainee'))
);

-- Insert default domain rule for sleepnumber.com
INSERT INTO pulse_domain_rules (domain, default_role, auto_approve, is_active) VALUES
    ('sleepnumber.com', 'trainee', FALSE, TRUE)
ON CONFLICT (domain) DO NOTHING;

-- =============================================================================
-- Audit Log Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS pulse_auth_audit (
    id SERIAL PRIMARY KEY,
    action VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID,
    old_value JSONB,
    new_value JSONB,
    performed_by UUID,
    performed_by_email VARCHAR(255),
    ip_address VARCHAR(45),
    user_agent TEXT,
    performed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pulse_auth_audit_entity ON pulse_auth_audit(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_pulse_auth_audit_time ON pulse_auth_audit(performed_at DESC);

-- =============================================================================
-- Seed Preset Users
-- =============================================================================

-- Break Glass Account (Super Admin)
INSERT INTO pulse_users (email, name, role, status, auth_method) VALUES
    ('rob.vance@sleepnumber.com', 'Rob Vance', 'super_admin', 'active', 'sso')
ON CONFLICT (email) DO UPDATE SET
    role = 'super_admin',
    status = 'active',
    updated_at = NOW();

-- Trainees
INSERT INTO pulse_users (email, name, role, status, auth_method) VALUES
    ('joshua.oldham@sleepnumber.com', 'Josh Oldham', 'trainee', 'active', 'sso'),
    ('soumil.deshmukh@sleepnumber.com', 'Soumil Deshmukh', 'trainee', 'active', 'sso'),
    ('mayura.javeri@sleepnumber.com', 'Mayura Javeri', 'trainee', 'active', 'sso'),
    ('Melissa.Barra@sleepnumber.com', 'Melissa Barra', 'trainee', 'active', 'sso'),
    ('Linda.Findley@sleepnumber.com', 'Linda Findley', 'trainee', 'active', 'sso')
ON CONFLICT (email) DO UPDATE SET
    status = 'active',
    updated_at = NOW();

-- Demo user for fallback (local auth)
INSERT INTO pulse_users (email, name, role, status, auth_method) VALUES
    ('demo@pulse.training', 'Demo User', 'super_admin', 'active', 'local')
ON CONFLICT (email) DO NOTHING;

-- =============================================================================
-- Helper Functions
-- =============================================================================

-- Function to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for pulse_users
DROP TRIGGER IF EXISTS update_pulse_users_updated_at ON pulse_users;
CREATE TRIGGER update_pulse_users_updated_at
    BEFORE UPDATE ON pulse_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Views for easier querying
-- =============================================================================

-- Active users view
CREATE OR REPLACE VIEW v_active_users AS
SELECT
    id, email, name, role, status, auth_method,
    last_login, created_at
FROM pulse_users
WHERE status = 'active';

-- Pending approvals view
CREATE OR REPLACE VIEW v_pending_approvals AS
SELECT
    u.id, u.email, u.name, u.role, u.created_at,
    i.code as invitation_code, i.type as invitation_type,
    creator.name as invited_by_name
FROM pulse_users u
LEFT JOIN pulse_invitations i ON u.invitation_id = i.id
LEFT JOIN pulse_users creator ON u.invited_by = creator.id
WHERE u.status = 'pending'
ORDER BY u.created_at DESC;

-- Recent audit log view
CREATE OR REPLACE VIEW v_recent_audit AS
SELECT
    a.id, a.action, a.entity_type, a.entity_id,
    a.old_value, a.new_value,
    a.performed_by_email, a.performed_at
FROM pulse_auth_audit a
ORDER BY a.performed_at DESC
LIMIT 100;

-- =============================================================================
-- Grant permissions (adjust based on your DB user)
-- =============================================================================
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO pulse_analytics_admin;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO pulse_analytics_admin;
