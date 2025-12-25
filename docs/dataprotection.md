# PULSE Data Protection Implementation Guide

**Version:** 1.0
**Last Updated:** 2025-12-25
**Priority:** MEDIUM
**Related Documents:** [securedbydesign.md](securedbydesign.md), [secretsmanage.md](secretsmanage.md)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Data Classification](#data-classification)
3. [Field-Level Encryption](#field-level-encryption)
4. [Data Retention Policies](#data-retention-policies)
5. [Audit Logging](#audit-logging)
6. [Data Masking](#data-masking)
7. [Backup and Recovery](#backup-and-recovery)
8. [Compliance Considerations](#compliance-considerations)
9. [Monitoring and Alerting](#monitoring-and-alerting)
10. [Migration Checklist](#migration-checklist)

---

## Executive Summary

Data protection encompasses multiple security controls to ensure data confidentiality, integrity, and availability:

- **Field-Level Encryption**: Encrypt sensitive fields at rest
- **Data Retention**: Automated policies for data lifecycle
- **Audit Logging**: Complete trail of data access and changes
- **Data Masking**: Protect sensitive data in non-production environments

This guide implements comprehensive data protection for the PULSE application.

---

## Data Classification

### Data Categories

| Classification | Description | Examples | Protection Level |
|----------------|-------------|----------|------------------|
| **Public** | Non-sensitive data | Marketing content, public docs | Standard |
| **Internal** | Business-sensitive | Reports, analytics | Encryption at rest |
| **Confidential** | User-sensitive | PII, user preferences | Field encryption |
| **Restricted** | Highly sensitive | Auth tokens, API keys | Encryption + masking |

### PULSE Data Inventory

| Data Type | Classification | Storage | Encryption |
|-----------|---------------|---------|------------|
| User email | Confidential | PostgreSQL | Field-level |
| User name | Confidential | PostgreSQL | Field-level |
| Chat messages | Confidential | PostgreSQL | Field-level |
| Session tokens | Restricted | Redis | Transit + rest |
| API keys | Restricted | Key Vault | HSM-backed |
| Audit logs | Internal | Log Analytics | Azure-managed |
| Analytics | Internal | Storage | Azure-managed |

---

## Field-Level Encryption

### Azure-Based Encryption

Create `ui/lib/encryption/azure-crypto.ts`:

```typescript
/**
 * PULSE Azure-Based Field Encryption
 * Uses Azure Key Vault for key management
 */

import { KeyClient, CryptographyClient } from '@azure/keyvault-keys';
import { DefaultAzureCredential } from '@azure/identity';
import crypto from 'crypto';

const VAULT_URL = process.env.AZURE_KEY_VAULT_URL!;
const DEK_KEY_NAME = process.env.ENCRYPTION_KEY_NAME || 'pulse-dek';

// Cache for crypto client
let cryptoClient: CryptographyClient | null = null;

/**
 * Get or create the cryptography client
 */
async function getCryptoClient(): Promise<CryptographyClient> {
  if (cryptoClient) {
    return cryptoClient;
  }

  const credential = new DefaultAzureCredential();
  const keyClient = new KeyClient(VAULT_URL, credential);

  // Get or create the data encryption key
  let key;
  try {
    key = await keyClient.getKey(DEK_KEY_NAME);
  } catch (error: any) {
    if (error.statusCode === 404) {
      // Create new key
      key = await keyClient.createKey(DEK_KEY_NAME, 'RSA', {
        keySize: 2048,
        keyOps: ['encrypt', 'decrypt', 'wrapKey', 'unwrapKey'],
      });
    } else {
      throw error;
    }
  }

  cryptoClient = new CryptographyClient(key, credential);
  return cryptoClient;
}

/**
 * Envelope encryption: Generate DEK, encrypt with KEK
 */
async function generateDataKey(): Promise<{
  plaintext: Buffer;
  encrypted: Buffer;
}> {
  const client = await getCryptoClient();

  // Generate random 256-bit key
  const plaintext = crypto.randomBytes(32);

  // Wrap with Key Vault key
  const result = await client.wrapKey('RSA-OAEP', plaintext);

  return {
    plaintext,
    encrypted: Buffer.from(result.result),
  };
}

/**
 * Decrypt a wrapped data key
 */
async function decryptDataKey(encryptedKey: Buffer): Promise<Buffer> {
  const client = await getCryptoClient();
  const result = await client.unwrapKey('RSA-OAEP', encryptedKey);
  return Buffer.from(result.result);
}

/**
 * Encrypt data using AES-256-GCM
 */
function encryptWithKey(
  plaintext: string,
  key: Buffer
): { ciphertext: string; iv: string; tag: string } {
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);

  let encrypted = cipher.update(plaintext, 'utf8', 'base64');
  encrypted += cipher.final('base64');

  const tag = cipher.getAuthTag();

  return {
    ciphertext: encrypted,
    iv: iv.toString('base64'),
    tag: tag.toString('base64'),
  };
}

/**
 * Decrypt data using AES-256-GCM
 */
function decryptWithKey(
  ciphertext: string,
  key: Buffer,
  iv: string,
  tag: string
): string {
  const decipher = crypto.createDecipheriv(
    'aes-256-gcm',
    key,
    Buffer.from(iv, 'base64')
  );

  decipher.setAuthTag(Buffer.from(tag, 'base64'));

  let decrypted = decipher.update(ciphertext, 'base64', 'utf8');
  decrypted += decipher.final('utf8');

  return decrypted;
}

// Cache for data keys (in-memory with TTL)
const dataKeyCache = new Map<
  string,
  { key: Buffer; expiry: number }
>();

/**
 * Get cached data key or generate new one
 */
async function getDataKey(): Promise<{ key: Buffer; keyId: string }> {
  const keyId = 'current';
  const cached = dataKeyCache.get(keyId);

  if (cached && cached.expiry > Date.now()) {
    return { key: cached.key, keyId };
  }

  const { plaintext } = await generateDataKey();

  // Cache for 1 hour
  dataKeyCache.set(keyId, {
    key: plaintext,
    expiry: Date.now() + 60 * 60 * 1000,
  });

  return { key: plaintext, keyId };
}

export interface EncryptedField {
  v: number; // Version
  kid: string; // Key ID
  iv: string; // Initialization vector
  tag: string; // Auth tag
  ct: string; // Ciphertext
}

/**
 * Encrypt a field value
 */
export async function encryptField(value: string): Promise<string> {
  if (!value) return value;

  const { key, keyId } = await getDataKey();
  const { ciphertext, iv, tag } = encryptWithKey(value, key);

  const encrypted: EncryptedField = {
    v: 1,
    kid: keyId,
    iv,
    tag,
    ct: ciphertext,
  };

  return JSON.stringify(encrypted);
}

/**
 * Decrypt a field value
 */
export async function decryptField(encryptedValue: string): Promise<string> {
  if (!encryptedValue) return encryptedValue;

  try {
    const data: EncryptedField = JSON.parse(encryptedValue);

    if (data.v !== 1) {
      throw new Error(`Unsupported encryption version: ${data.v}`);
    }

    // Get the key
    const cached = dataKeyCache.get(data.kid);
    if (!cached) {
      throw new Error('Data key not found - re-encryption may be needed');
    }

    return decryptWithKey(data.ct, cached.key, data.iv, data.tag);
  } catch (error) {
    // Not encrypted or invalid format
    return encryptedValue;
  }
}

/**
 * Check if a value is encrypted
 */
export function isEncrypted(value: string): boolean {
  try {
    const data = JSON.parse(value);
    return data.v && data.kid && data.iv && data.tag && data.ct;
  } catch {
    return false;
  }
}
```

### Database Model with Encryption

Create `ui/lib/models/encrypted-user.ts`:

```typescript
/**
 * PULSE User Model with Field-Level Encryption
 */

import { Pool } from 'pg';
import { encryptField, decryptField } from '../encryption/azure-crypto';

interface User {
  id: string;
  email: string;
  name: string;
  phone?: string;
  createdAt: Date;
  updatedAt: Date;
}

interface EncryptedUser {
  id: string;
  email_encrypted: string;
  name_encrypted: string;
  phone_encrypted?: string;
  email_hash: string; // For lookups
  created_at: Date;
  updated_at: Date;
}

export class UserRepository {
  private pool: Pool;

  constructor(connectionString: string) {
    this.pool = new Pool({ connectionString });
  }

  /**
   * Create SHA-256 hash for lookups
   */
  private hashForLookup(value: string): string {
    const crypto = require('crypto');
    return crypto.createHash('sha256').update(value.toLowerCase()).digest('hex');
  }

  /**
   * Create a new user with encrypted fields
   */
  async create(user: Omit<User, 'id' | 'createdAt' | 'updatedAt'>): Promise<User> {
    const encryptedEmail = await encryptField(user.email);
    const encryptedName = await encryptField(user.name);
    const encryptedPhone = user.phone ? await encryptField(user.phone) : null;
    const emailHash = this.hashForLookup(user.email);

    const result = await this.pool.query(
      `INSERT INTO users (email_encrypted, name_encrypted, phone_encrypted, email_hash)
       VALUES ($1, $2, $3, $4)
       RETURNING id, created_at, updated_at`,
      [encryptedEmail, encryptedName, encryptedPhone, emailHash]
    );

    return {
      id: result.rows[0].id,
      email: user.email,
      name: user.name,
      phone: user.phone,
      createdAt: result.rows[0].created_at,
      updatedAt: result.rows[0].updated_at,
    };
  }

  /**
   * Find user by email (using hash)
   */
  async findByEmail(email: string): Promise<User | null> {
    const emailHash = this.hashForLookup(email);

    const result = await this.pool.query(
      `SELECT * FROM users WHERE email_hash = $1`,
      [emailHash]
    );

    if (!result.rows[0]) return null;

    return this.decryptUser(result.rows[0]);
  }

  /**
   * Find user by ID
   */
  async findById(id: string): Promise<User | null> {
    const result = await this.pool.query(
      `SELECT * FROM users WHERE id = $1`,
      [id]
    );

    if (!result.rows[0]) return null;

    return this.decryptUser(result.rows[0]);
  }

  /**
   * Update user
   */
  async update(id: string, updates: Partial<Omit<User, 'id' | 'createdAt' | 'updatedAt'>>): Promise<User> {
    const fields: string[] = [];
    const values: any[] = [];
    let paramIndex = 1;

    if (updates.email) {
      fields.push(`email_encrypted = $${paramIndex++}`);
      values.push(await encryptField(updates.email));
      fields.push(`email_hash = $${paramIndex++}`);
      values.push(this.hashForLookup(updates.email));
    }

    if (updates.name) {
      fields.push(`name_encrypted = $${paramIndex++}`);
      values.push(await encryptField(updates.name));
    }

    if (updates.phone !== undefined) {
      fields.push(`phone_encrypted = $${paramIndex++}`);
      values.push(updates.phone ? await encryptField(updates.phone) : null);
    }

    fields.push(`updated_at = NOW()`);

    const result = await this.pool.query(
      `UPDATE users SET ${fields.join(', ')} WHERE id = $${paramIndex} RETURNING *`,
      [...values, id]
    );

    return this.decryptUser(result.rows[0]);
  }

  /**
   * Decrypt user record
   */
  private async decryptUser(row: EncryptedUser): Promise<User> {
    return {
      id: row.id,
      email: await decryptField(row.email_encrypted),
      name: await decryptField(row.name_encrypted),
      phone: row.phone_encrypted ? await decryptField(row.phone_encrypted) : undefined,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
    };
  }
}
```

### Database Schema for Encrypted Data

```sql
-- Users table with encrypted fields
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_encrypted TEXT NOT NULL,       -- Encrypted email
    email_hash VARCHAR(64) NOT NULL,     -- SHA-256 hash for lookups
    name_encrypted TEXT NOT NULL,        -- Encrypted name
    phone_encrypted TEXT,                -- Encrypted phone (optional)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT users_email_hash_unique UNIQUE (email_hash)
);

CREATE INDEX idx_users_email_hash ON users(email_hash);

-- Chat messages with encrypted content
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id),
    role VARCHAR(20) NOT NULL,
    content_encrypted TEXT NOT NULL,     -- Encrypted message content
    content_hash VARCHAR(64),            -- Optional hash for dedup
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_conversation FOREIGN KEY (conversation_id)
        REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_messages_user ON messages(user_id);
```

---

## Data Retention Policies

### Retention Configuration

Create `ui/lib/data-retention/config.ts`:

```typescript
/**
 * PULSE Data Retention Configuration
 */

export interface RetentionPolicy {
  table: string;
  retentionDays: number;
  dateColumn: string;
  conditions?: string;
  archiveBeforeDelete?: boolean;
  archiveTable?: string;
}

export const retentionPolicies: RetentionPolicy[] = [
  {
    table: 'messages',
    retentionDays: 90,
    dateColumn: 'created_at',
    archiveBeforeDelete: true,
    archiveTable: 'messages_archive',
  },
  {
    table: 'conversations',
    retentionDays: 90,
    dateColumn: 'updated_at',
    conditions: 'NOT EXISTS (SELECT 1 FROM messages WHERE messages.conversation_id = conversations.id)',
  },
  {
    table: 'sessions',
    retentionDays: 30,
    dateColumn: 'expires_at',
    conditions: "revoked = TRUE OR expires_at < NOW()",
  },
  {
    table: 'session_audit_log',
    retentionDays: 365,
    dateColumn: 'created_at',
  },
  {
    table: 'audit_logs',
    retentionDays: 730, // 2 years
    dateColumn: 'created_at',
    archiveBeforeDelete: true,
    archiveTable: 'audit_logs_archive',
  },
];
```

### Retention Job Implementation

Create `ui/lib/data-retention/retention-job.ts`:

```typescript
/**
 * PULSE Data Retention Job
 * Automated cleanup of expired data
 */

import { Pool } from 'pg';
import { retentionPolicies, RetentionPolicy } from './config';
import { logSecurityEvent } from '../security-logger';

export class RetentionJob {
  private pool: Pool;

  constructor(connectionString: string) {
    this.pool = new Pool({ connectionString });
  }

  /**
   * Run retention for all policies
   */
  async runAll(): Promise<{ policy: string; deleted: number; archived: number }[]> {
    const results: { policy: string; deleted: number; archived: number }[] = [];

    for (const policy of retentionPolicies) {
      try {
        const result = await this.runPolicy(policy);
        results.push({
          policy: policy.table,
          deleted: result.deleted,
          archived: result.archived,
        });

        await logSecurityEvent({
          type: 'DATA_RETENTION_RUN',
          clientId: 'system',
          path: '/jobs/retention',
          timestamp: new Date().toISOString(),
          details: {
            table: policy.table,
            deleted: result.deleted,
            archived: result.archived,
          },
        });
      } catch (error) {
        console.error(`Retention job failed for ${policy.table}:`, error);
        await logSecurityEvent({
          type: 'DATA_RETENTION_ERROR',
          clientId: 'system',
          path: '/jobs/retention',
          timestamp: new Date().toISOString(),
          details: {
            table: policy.table,
            error: String(error),
          },
        });
      }
    }

    return results;
  }

  /**
   * Run retention for a specific policy
   */
  async runPolicy(policy: RetentionPolicy): Promise<{ deleted: number; archived: number }> {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - policy.retentionDays);

    let archived = 0;
    let deleted = 0;

    // Begin transaction
    const client = await this.pool.connect();

    try {
      await client.query('BEGIN');

      // Build WHERE clause
      let whereClause = `${policy.dateColumn} < $1`;
      if (policy.conditions) {
        whereClause += ` AND (${policy.conditions})`;
      }

      // Archive if configured
      if (policy.archiveBeforeDelete && policy.archiveTable) {
        const archiveResult = await client.query(
          `INSERT INTO ${policy.archiveTable}
           SELECT *, NOW() as archived_at FROM ${policy.table}
           WHERE ${whereClause}`,
          [cutoffDate]
        );
        archived = archiveResult.rowCount || 0;
      }

      // Delete expired data
      const deleteResult = await client.query(
        `DELETE FROM ${policy.table} WHERE ${whereClause}`,
        [cutoffDate]
      );
      deleted = deleteResult.rowCount || 0;

      await client.query('COMMIT');
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }

    return { deleted, archived };
  }

  /**
   * Get retention report
   */
  async getReport(): Promise<{
    table: string;
    totalRows: number;
    expiredRows: number;
    oldestRecord: Date | null;
    retentionDays: number;
  }[]> {
    const report: any[] = [];

    for (const policy of retentionPolicies) {
      const cutoffDate = new Date();
      cutoffDate.setDate(cutoffDate.getDate() - policy.retentionDays);

      const totalResult = await this.pool.query(
        `SELECT COUNT(*) as count FROM ${policy.table}`
      );

      let whereClause = `${policy.dateColumn} < $1`;
      if (policy.conditions) {
        whereClause += ` AND (${policy.conditions})`;
      }

      const expiredResult = await this.pool.query(
        `SELECT COUNT(*) as count FROM ${policy.table} WHERE ${whereClause}`,
        [cutoffDate]
      );

      const oldestResult = await this.pool.query(
        `SELECT MIN(${policy.dateColumn}) as oldest FROM ${policy.table}`
      );

      report.push({
        table: policy.table,
        totalRows: parseInt(totalResult.rows[0].count, 10),
        expiredRows: parseInt(expiredResult.rows[0].count, 10),
        oldestRecord: oldestResult.rows[0].oldest,
        retentionDays: policy.retentionDays,
      });
    }

    return report;
  }

  async close(): Promise<void> {
    await this.pool.end();
  }
}
```

### Azure Function for Scheduled Retention

Create `func/retention_job/__init__.py`:

```python
"""
PULSE Data Retention Azure Function
Runs on a schedule to clean up expired data
"""

import azure.functions as func
import logging
import psycopg2
from datetime import datetime, timedelta
from typing import Dict, List, Any
import json

# Retention policies
RETENTION_POLICIES = [
    {
        "table": "messages",
        "retention_days": 90,
        "date_column": "created_at",
        "archive_table": "messages_archive",
    },
    {
        "table": "sessions",
        "retention_days": 30,
        "date_column": "expires_at",
        "conditions": "revoked = TRUE OR expires_at < NOW()",
    },
    {
        "table": "session_audit_log",
        "retention_days": 365,
        "date_column": "created_at",
    },
]


def get_db_connection():
    """Get database connection."""
    import os
    return psycopg2.connect(os.environ["DATABASE_URL"])


def run_retention_policy(conn, policy: Dict[str, Any]) -> Dict[str, int]:
    """Run a single retention policy."""
    cutoff_date = datetime.now() - timedelta(days=policy["retention_days"])

    with conn.cursor() as cur:
        # Build WHERE clause
        where_clause = f"{policy['date_column']} < %s"
        if policy.get("conditions"):
            where_clause += f" AND ({policy['conditions']})"

        archived = 0
        deleted = 0

        # Archive if configured
        if policy.get("archive_table"):
            cur.execute(
                f"""INSERT INTO {policy['archive_table']}
                    SELECT *, NOW() as archived_at FROM {policy['table']}
                    WHERE {where_clause}""",
                (cutoff_date,)
            )
            archived = cur.rowcount

        # Delete expired data
        cur.execute(
            f"DELETE FROM {policy['table']} WHERE {where_clause}",
            (cutoff_date,)
        )
        deleted = cur.rowcount

    return {"archived": archived, "deleted": deleted}


def main(timer: func.TimerRequest) -> None:
    """Timer trigger function for data retention."""
    logging.info("Starting data retention job")

    results = []
    conn = None

    try:
        conn = get_db_connection()

        for policy in RETENTION_POLICIES:
            try:
                result = run_retention_policy(conn, policy)
                conn.commit()

                results.append({
                    "table": policy["table"],
                    "archived": result["archived"],
                    "deleted": result["deleted"],
                    "status": "success"
                })

                logging.info(
                    f"Retention completed for {policy['table']}: "
                    f"archived={result['archived']}, deleted={result['deleted']}"
                )

            except Exception as e:
                conn.rollback()
                results.append({
                    "table": policy["table"],
                    "status": "error",
                    "error": str(e)
                })
                logging.error(f"Retention failed for {policy['table']}: {e}")

    except Exception as e:
        logging.error(f"Database connection failed: {e}")

    finally:
        if conn:
            conn.close()

    logging.info(f"Data retention job completed: {json.dumps(results)}")
```

---

## Audit Logging

### Audit Log Schema

```sql
-- Comprehensive audit log table
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id UUID,
    session_id UUID,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    request_method VARCHAR(10),
    request_path TEXT,
    request_body_hash VARCHAR(64),  -- Hash, not actual content
    response_status INTEGER,
    changes JSONB,  -- Before/after for updates
    metadata JSONB,

    -- Partitioning support
    created_date DATE NOT NULL DEFAULT CURRENT_DATE
) PARTITION BY RANGE (created_date);

-- Create monthly partitions
CREATE TABLE audit_logs_2025_01 PARTITION OF audit_logs
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE audit_logs_2025_02 PARTITION OF audit_logs
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
-- ... continue for each month

-- Indexes for common queries
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
```

### Audit Logger Implementation

Create `ui/lib/audit/audit-logger.ts`:

```typescript
/**
 * PULSE Audit Logger
 * Comprehensive audit trail for all data operations
 */

import { Pool } from 'pg';
import crypto from 'crypto';

export interface AuditEntry {
  userId?: string;
  sessionId?: string;
  action: string;
  resourceType: string;
  resourceId?: string;
  ipAddress?: string;
  userAgent?: string;
  requestMethod?: string;
  requestPath?: string;
  requestBody?: any;
  responseStatus?: number;
  changes?: {
    before?: Record<string, any>;
    after?: Record<string, any>;
  };
  metadata?: Record<string, any>;
}

export class AuditLogger {
  private pool: Pool;
  private batchQueue: AuditEntry[] = [];
  private batchTimeout: NodeJS.Timeout | null = null;
  private readonly BATCH_SIZE = 100;
  private readonly BATCH_TIMEOUT_MS = 1000;

  constructor(connectionString: string) {
    this.pool = new Pool({ connectionString });
  }

  /**
   * Log an audit entry
   */
  async log(entry: AuditEntry): Promise<void> {
    // Add to batch queue
    this.batchQueue.push(entry);

    // Flush if batch is full
    if (this.batchQueue.length >= this.BATCH_SIZE) {
      await this.flush();
    } else if (!this.batchTimeout) {
      // Set timeout to flush
      this.batchTimeout = setTimeout(() => this.flush(), this.BATCH_TIMEOUT_MS);
    }
  }

  /**
   * Flush batch to database
   */
  async flush(): Promise<void> {
    if (this.batchTimeout) {
      clearTimeout(this.batchTimeout);
      this.batchTimeout = null;
    }

    if (this.batchQueue.length === 0) {
      return;
    }

    const batch = this.batchQueue.splice(0, this.BATCH_SIZE);

    try {
      const values: any[] = [];
      const placeholders: string[] = [];

      batch.forEach((entry, index) => {
        const offset = index * 13;
        placeholders.push(
          `($${offset + 1}, $${offset + 2}, $${offset + 3}, $${offset + 4}, $${offset + 5},
            $${offset + 6}, $${offset + 7}, $${offset + 8}, $${offset + 9}, $${offset + 10},
            $${offset + 11}, $${offset + 12}, $${offset + 13})`
        );

        values.push(
          entry.userId || null,
          entry.sessionId || null,
          entry.action,
          entry.resourceType,
          entry.resourceId || null,
          entry.ipAddress || null,
          entry.userAgent || null,
          entry.requestMethod || null,
          entry.requestPath || null,
          entry.requestBody ? this.hashBody(entry.requestBody) : null,
          entry.responseStatus || null,
          entry.changes ? JSON.stringify(entry.changes) : null,
          entry.metadata ? JSON.stringify(entry.metadata) : null
        );
      });

      await this.pool.query(
        `INSERT INTO audit_logs
         (user_id, session_id, action, resource_type, resource_id,
          ip_address, user_agent, request_method, request_path, request_body_hash,
          response_status, changes, metadata)
         VALUES ${placeholders.join(', ')}`,
        values
      );
    } catch (error) {
      console.error('Failed to write audit logs:', error);
      // Re-queue failed entries
      this.batchQueue.unshift(...batch);
    }
  }

  /**
   * Hash request body for audit (don't store actual data)
   */
  private hashBody(body: any): string {
    return crypto.createHash('sha256')
      .update(JSON.stringify(body))
      .digest('hex');
  }

  /**
   * Query audit logs
   */
  async query(filters: {
    userId?: string;
    action?: string;
    resourceType?: string;
    resourceId?: string;
    startDate?: Date;
    endDate?: Date;
    limit?: number;
    offset?: number;
  }): Promise<{
    entries: AuditEntry[];
    total: number;
  }> {
    const conditions: string[] = [];
    const params: any[] = [];
    let paramIndex = 1;

    if (filters.userId) {
      conditions.push(`user_id = $${paramIndex++}`);
      params.push(filters.userId);
    }

    if (filters.action) {
      conditions.push(`action = $${paramIndex++}`);
      params.push(filters.action);
    }

    if (filters.resourceType) {
      conditions.push(`resource_type = $${paramIndex++}`);
      params.push(filters.resourceType);
    }

    if (filters.resourceId) {
      conditions.push(`resource_id = $${paramIndex++}`);
      params.push(filters.resourceId);
    }

    if (filters.startDate) {
      conditions.push(`timestamp >= $${paramIndex++}`);
      params.push(filters.startDate);
    }

    if (filters.endDate) {
      conditions.push(`timestamp <= $${paramIndex++}`);
      params.push(filters.endDate);
    }

    const whereClause = conditions.length > 0
      ? `WHERE ${conditions.join(' AND ')}`
      : '';

    // Get total count
    const countResult = await this.pool.query(
      `SELECT COUNT(*) as count FROM audit_logs ${whereClause}`,
      params
    );

    // Get entries
    const limit = Math.min(filters.limit || 100, 1000);
    const offset = filters.offset || 0;

    const result = await this.pool.query(
      `SELECT * FROM audit_logs ${whereClause}
       ORDER BY timestamp DESC
       LIMIT $${paramIndex++} OFFSET $${paramIndex}`,
      [...params, limit, offset]
    );

    return {
      entries: result.rows,
      total: parseInt(countResult.rows[0].count, 10),
    };
  }

  /**
   * Close connection pool
   */
  async close(): Promise<void> {
    await this.flush();
    await this.pool.end();
  }
}

// Singleton instance
let auditLogger: AuditLogger | null = null;

export function getAuditLogger(): AuditLogger {
  if (!auditLogger) {
    const connectionString = process.env.DATABASE_URL!;
    auditLogger = new AuditLogger(connectionString);
  }
  return auditLogger;
}
```

### Audit Middleware

Create `ui/lib/audit/audit-middleware.ts`:

```typescript
/**
 * PULSE Audit Middleware
 * Automatically log API requests
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAuditLogger, AuditEntry } from './audit-logger';

// Actions that should be audited
const AUDITED_ACTIONS: Record<string, { resourceType: string; action: string }> = {
  'POST /api/chat': { resourceType: 'chat', action: 'CREATE_MESSAGE' },
  'DELETE /api/sessions': { resourceType: 'session', action: 'REVOKE_SESSION' },
  'PATCH /api/profile': { resourceType: 'user', action: 'UPDATE_PROFILE' },
  'POST /api/documents': { resourceType: 'document', action: 'UPLOAD_DOCUMENT' },
  'DELETE /api/documents/:id': { resourceType: 'document', action: 'DELETE_DOCUMENT' },
};

/**
 * Match request to action
 */
function matchAction(method: string, path: string): { resourceType: string; action: string } | null {
  const key = `${method} ${path}`;

  // Exact match
  if (AUDITED_ACTIONS[key]) {
    return AUDITED_ACTIONS[key];
  }

  // Pattern match (simple)
  for (const [pattern, action] of Object.entries(AUDITED_ACTIONS)) {
    const patternRegex = pattern
      .replace(':id', '[^/]+')
      .replace(/\//g, '\\/');

    const regex = new RegExp(`^${patternRegex}$`);
    if (regex.test(key)) {
      return action;
    }
  }

  return null;
}

/**
 * Audit middleware
 */
export async function auditMiddleware(
  request: NextRequest,
  handler: (request: NextRequest) => Promise<NextResponse>
): Promise<NextResponse> {
  const method = request.method;
  const path = request.nextUrl.pathname;
  const action = matchAction(method, path);

  // Only audit specific actions
  if (!action) {
    return handler(request);
  }

  const startTime = Date.now();
  let response: NextResponse;
  let error: Error | null = null;

  try {
    response = await handler(request);
  } catch (e) {
    error = e as Error;
    throw e;
  } finally {
    // Log audit entry
    const auditEntry: AuditEntry = {
      userId: request.headers.get('x-user-id') || undefined,
      sessionId: request.headers.get('x-session-id') || undefined,
      action: action.action,
      resourceType: action.resourceType,
      resourceId: extractResourceId(path),
      ipAddress: request.headers.get('x-forwarded-for')?.split(',')[0] || undefined,
      userAgent: request.headers.get('user-agent') || undefined,
      requestMethod: method,
      requestPath: path,
      responseStatus: error ? 500 : response!.status,
      metadata: {
        duration: Date.now() - startTime,
        error: error?.message,
      },
    };

    const logger = getAuditLogger();
    await logger.log(auditEntry);
  }

  return response!;
}

/**
 * Extract resource ID from path
 */
function extractResourceId(path: string): string | undefined {
  const uuidPattern = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
  const match = path.match(uuidPattern);
  return match?.[0];
}
```

---

## Data Masking

### Create Data Masking Utilities

Create `ui/lib/masking/data-masker.ts`:

```typescript
/**
 * PULSE Data Masking
 * Protect sensitive data in non-production environments
 */

export interface MaskingConfig {
  environment: 'production' | 'staging' | 'development' | 'test';
  maskingRules: MaskingRule[];
}

export interface MaskingRule {
  field: string;
  type: 'email' | 'phone' | 'name' | 'creditCard' | 'ssn' | 'full' | 'partial' | 'custom';
  visibleChars?: number;
  customMask?: (value: string) => string;
}

/**
 * Mask email address
 */
function maskEmail(email: string): string {
  const [local, domain] = email.split('@');
  if (!domain) return '***@***.***';

  const maskedLocal = local.charAt(0) + '*'.repeat(Math.max(local.length - 2, 1)) + local.charAt(local.length - 1);
  const [domainName, tld] = domain.split('.');

  return `${maskedLocal}@${domainName.charAt(0)}***${tld ? '.' + tld : ''}`;
}

/**
 * Mask phone number
 */
function maskPhone(phone: string): string {
  const digits = phone.replace(/\D/g, '');
  if (digits.length < 4) return '***';

  return '***-***-' + digits.slice(-4);
}

/**
 * Mask name
 */
function maskName(name: string): string {
  const parts = name.split(' ');
  return parts.map(part => part.charAt(0) + '*'.repeat(Math.max(part.length - 1, 2))).join(' ');
}

/**
 * Mask credit card number
 */
function maskCreditCard(number: string): string {
  const digits = number.replace(/\D/g, '');
  if (digits.length < 4) return '****';

  return '**** **** **** ' + digits.slice(-4);
}

/**
 * Mask SSN
 */
function maskSSN(ssn: string): string {
  const digits = ssn.replace(/\D/g, '');
  if (digits.length < 4) return '***-**-****';

  return '***-**-' + digits.slice(-4);
}

/**
 * Partial mask (show first and last n chars)
 */
function partialMask(value: string, visibleChars: number = 2): string {
  if (value.length <= visibleChars * 2) {
    return '*'.repeat(value.length);
  }

  const start = value.slice(0, visibleChars);
  const end = value.slice(-visibleChars);
  const middle = '*'.repeat(value.length - visibleChars * 2);

  return start + middle + end;
}

/**
 * Full mask
 */
function fullMask(value: string): string {
  return '*'.repeat(value.length);
}

/**
 * Apply masking rule to value
 */
export function applyMask(value: string, rule: MaskingRule): string {
  if (!value) return value;

  switch (rule.type) {
    case 'email':
      return maskEmail(value);
    case 'phone':
      return maskPhone(value);
    case 'name':
      return maskName(value);
    case 'creditCard':
      return maskCreditCard(value);
    case 'ssn':
      return maskSSN(value);
    case 'full':
      return fullMask(value);
    case 'partial':
      return partialMask(value, rule.visibleChars);
    case 'custom':
      return rule.customMask ? rule.customMask(value) : value;
    default:
      return value;
  }
}

/**
 * Mask object fields based on rules
 */
export function maskObject<T extends Record<string, any>>(
  obj: T,
  rules: MaskingRule[]
): T {
  const result = { ...obj };

  for (const rule of rules) {
    if (result[rule.field] !== undefined && typeof result[rule.field] === 'string') {
      (result as any)[rule.field] = applyMask(result[rule.field], rule);
    }
  }

  return result;
}

/**
 * Create a data masking middleware
 */
export function createMaskingMiddleware(config: MaskingConfig) {
  // Don't mask in production
  if (config.environment === 'production') {
    return <T>(data: T): T => data;
  }

  return function maskData<T extends Record<string, any>>(data: T): T {
    return maskObject(data, config.maskingRules);
  };
}

// Default masking rules for PULSE
export const defaultMaskingRules: MaskingRule[] = [
  { field: 'email', type: 'email' },
  { field: 'name', type: 'name' },
  { field: 'phone', type: 'phone' },
  { field: 'creditCard', type: 'creditCard' },
  { field: 'ssn', type: 'ssn' },
];
```

---

## Migration Checklist

### Phase 1: Encryption Setup

- [ ] Configure Azure Key Vault for key management
- [ ] Create data encryption key (DEK)
- [ ] Implement field encryption utilities
- [ ] Create encrypted database schema

### Phase 2: Data Retention

- [ ] Define retention policies
- [ ] Create archive tables
- [ ] Implement retention job
- [ ] Deploy Azure Function for scheduled cleanup

### Phase 3: Audit Logging

- [ ] Create audit log table with partitioning
- [ ] Implement audit logger
- [ ] Add audit middleware to API routes
- [ ] Configure log retention

### Phase 4: Data Masking

- [ ] Define masking rules
- [ ] Implement masking utilities
- [ ] Apply to non-production environments
- [ ] Test masked data exports

### Phase 5: Monitoring

- [ ] Set up retention job monitoring
- [ ] Configure audit log alerts
- [ ] Create compliance dashboards
- [ ] Document data handling procedures

---

## Best Practices Summary

1. **Encrypt Sensitive Data**: Use field-level encryption for PII
2. **Define Retention**: Establish clear data lifecycle policies
3. **Audit Everything**: Log all data access and changes
4. **Mask in Non-Prod**: Protect data in development environments
5. **Automate Cleanup**: Use scheduled jobs for retention
6. **Monitor Compliance**: Track data handling for regulations

---

## Related Documents

- [securedbydesign.md](securedbydesign.md) - Overall security assessment
- [secretsmanage.md](secretsmanage.md) - Secrets management
- [sessionrevoke.md](sessionrevoke.md) - Session management
