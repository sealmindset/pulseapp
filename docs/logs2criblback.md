# PULSE Logs to Cribl Migration Plan

## Overview

This document outlines the comprehensive plan to migrate PULSE's logging infrastructure from Azure Application Insights/Log Analytics to Cribl. The goal is to reduce ongoing logging costs by eliminating dedicated log storage in favor of Cribl's stream-based architecture where collection is free and only consumption incurs costs.

**Target Implementation Date**: Post January 7th, 2026 (after hack-a-thon)

---

## Table of Contents

1. [Current Architecture](#current-architecture)
2. [Target Architecture](#target-architecture)
3. [Cost Analysis](#cost-analysis)
4. [Prerequisites](#prerequisites)
5. [Implementation Phases](#implementation-phases)
6. [Detailed Implementation Steps](#detailed-implementation-steps)
7. [Rollback Plan](#rollback-plan)
8. [Testing Strategy](#testing-strategy)
9. [Risk Assessment](#risk-assessment)

---

## Current Architecture

### Components
```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Current Logging Flow                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐     ┌─────────────────────┐     ┌──────────────────┐  │
│  │  Web App     │────▶│  Application        │────▶│  Log Analytics   │  │
│  │  (Next.js)   │     │  Insights           │     │  Workspace       │  │
│  └──────────────┘     └─────────────────────┘     └──────────────────┘  │
│                                                            │             │
│  ┌──────────────┐     ┌─────────────────────┐              │             │
│  │  Function    │────▶│  Application        │──────────────┘             │
│  │  App         │     │  Insights           │                            │
│  └──────────────┘     └─────────────────────┘                            │
│                                                            │             │
│                                                            ▼             │
│                                                   ┌──────────────────┐   │
│                                                   │  AI Log Search   │   │
│                                                   │  (queries LAW)   │   │
│                                                   └──────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Current Cost Drivers
- **Application Insights**: Data ingestion (~$2.30/GB), retention (90 days free, then $0.10/GB/month)
- **Log Analytics Workspace**: Query costs, data ingestion, long-term retention
- **Continuous storage**: All logs stored regardless of whether they're ever queried

### Files Involved
| File | Purpose |
|------|---------|
| `main.tf` | Creates Log Analytics Workspace, passes workspace ID to modules |
| `modules/app/main.tf` | Configures LOG_ANALYTICS_WORKSPACE_ID env var |
| `modules/app/variables.tf` | Defines log_analytics_workspace_id variable |
| `ui/lib/appInsights.ts` | Queries Application Insights via Azure SDK |
| `ui/app/api/admin/logs/search/route.ts` | AI Log Search API endpoint |
| `ui/components/admin/logs/AILogSearch.tsx` | Log search UI component |

---

## Target Architecture

### Components
```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Target Logging Flow                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐                                                        │
│  │  Web App     │──────────────────────┐                                 │
│  │  (Next.js)   │                      │                                 │
│  └──────────────┘                      │                                 │
│         │                              │                                 │
│         │ (structured logs)            │                                 │
│         ▼                              ▼                                 │
│  ┌──────────────┐              ┌──────────────────┐                      │
│  │  Cribl       │◀─────────────│  Cribl HTTP      │                      │
│  │  Stream      │              │  Collector       │                      │
│  └──────────────┘              └──────────────────┘                      │
│         │                              ▲                                 │
│         │                              │                                 │
│  ┌──────────────┐                      │                                 │
│  │  Function    │──────────────────────┘                                 │
│  │  App         │                                                        │
│  └──────────────┘                                                        │
│         │                                                                │
│         │ (query on demand)                                              │
│         ▼                                                                │
│  ┌──────────────────┐     ┌──────────────────┐                           │
│  │  AI Log Search   │────▶│  Cribl Search    │                           │
│  │  API             │     │  API             │                           │
│  └──────────────────┘     └──────────────────┘                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Benefits
1. **Collection is free**: Cribl doesn't charge for ingesting logs
2. **Pay for consumption only**: Costs only incurred when logs are queried
3. **Reduced infrastructure**: Eliminate Application Insights and Log Analytics Workspace
4. **Unified logging**: Single source of truth for all application logs
5. **Flexible routing**: Cribl can route logs to multiple destinations if needed later

---

## Cost Analysis

### Current Estimated Costs (Monthly)
| Service | Estimated Volume | Cost |
|---------|------------------|------|
| Application Insights Ingestion | ~5 GB/month | ~$11.50 |
| Log Analytics Ingestion | ~5 GB/month | ~$11.50 |
| Log Analytics Retention | ~15 GB stored | ~$1.50 |
| Log Analytics Queries | Variable | ~$5-20 |
| **Total** | | **~$30-45/month** |

### Projected Costs with Cribl
| Service | Estimated Volume | Cost |
|---------|------------------|------|
| Cribl Collection | Unlimited | $0 |
| Cribl Search Queries | On-demand only | Variable (usage-based) |
| **Total** | | **$5-15/month** (estimated) |

*Note: Actual savings depend on query frequency. If logs are rarely queried, savings could be 70-80%.*

---

## Prerequisites

### Before Starting Implementation

1. **Cribl Account & Configuration**
   - [ ] Active Cribl Cloud account or self-hosted Cribl instance
   - [ ] HTTP Event Collector (HEC) endpoint configured
   - [ ] Cribl Search API access and credentials
   - [ ] Network connectivity verified between Azure and Cribl

2. **Documentation**
   - [ ] Cribl Search API documentation reviewed
   - [ ] Cribl HEC endpoint specifications documented
   - [ ] Authentication mechanism decided (API key, OAuth, etc.)

3. **Environment Variables Required**
   ```
   CRIBL_HEC_ENDPOINT=https://your-cribl-instance/services/collector
   CRIBL_HEC_TOKEN=your-hec-token
   CRIBL_SEARCH_ENDPOINT=https://your-cribl-instance/api/v1/search
   CRIBL_SEARCH_API_KEY=your-search-api-key
   ```

4. **Testing Environment**
   - [ ] Non-production Cribl instance for testing
   - [ ] Ability to run parallel logging (to both systems) during transition

---

## Implementation Phases

### Phase 1: Preparation (Week 1)
- Set up Cribl endpoints
- Create new logging library
- Configure environment variables in Terraform

### Phase 2: Dual Logging (Week 2)
- Implement log forwarding to Cribl alongside existing setup
- Verify logs are reaching Cribl correctly
- Monitor for any issues

### Phase 3: Query Migration (Week 3)
- Implement Cribl Search client
- Update AI Log Search to query Cribl
- Test search functionality thoroughly

### Phase 4: Cutover (Week 4)
- Switch AI Log Search to use Cribl as primary source
- Monitor for issues
- Keep Application Insights as fallback temporarily

### Phase 5: Cleanup (Week 5)
- Remove Application Insights dependencies
- Update Terraform to remove Log Analytics resources
- Clean up unused code

---

## Detailed Implementation Steps

### Step 1: Create Cribl Logging Library

**File: `ui/lib/cribl.ts`**

```typescript
/**
 * Cribl Integration Library
 * Handles sending logs to Cribl HEC and querying via Cribl Search API
 */

import { DefaultAzureCredential } from "@azure/identity";

// =============================================================================
// Configuration
// =============================================================================

export interface CriblConfig {
  hecEndpoint: string;
  hecToken: string;
  searchEndpoint: string;
  searchApiKey: string;
}

export function getCriblConfig(): CriblConfig | null {
  const hecEndpoint = process.env.CRIBL_HEC_ENDPOINT;
  const hecToken = process.env.CRIBL_HEC_TOKEN;
  const searchEndpoint = process.env.CRIBL_SEARCH_ENDPOINT;
  const searchApiKey = process.env.CRIBL_SEARCH_API_KEY;

  if (!hecEndpoint || !hecToken || !searchEndpoint || !searchApiKey) {
    return null;
  }

  return { hecEndpoint, hecToken, searchEndpoint, searchApiKey };
}

export function isCriblConfigured(): boolean {
  return getCriblConfig() !== null;
}

// =============================================================================
// Log Entry Types
// =============================================================================

export interface LogEntry {
  id: string;
  timestamp: string;
  level: "error" | "warning" | "info" | "debug" | "trace";
  message: string;
  source: string;
  details?: Record<string, unknown>;
  correlationId?: string;
  userId?: string;
  sessionId?: string;
  duration?: number;
  statusCode?: number;
  requestPath?: string;
  stackTrace?: string;
}

// =============================================================================
// HEC Log Forwarding
// =============================================================================

interface HecEvent {
  time: number;
  host: string;
  source: string;
  sourcetype: string;
  event: Record<string, unknown>;
}

/**
 * Send a single log entry to Cribl HEC
 */
export async function sendLogToCribl(entry: LogEntry): Promise<void> {
  const config = getCriblConfig();
  if (!config) {
    console.warn("Cribl not configured, skipping log forward");
    return;
  }

  const hecEvent: HecEvent = {
    time: new Date(entry.timestamp).getTime() / 1000,
    host: process.env.WEBSITE_HOSTNAME || "pulse-app",
    source: entry.source,
    sourcetype: "pulse:application",
    event: {
      id: entry.id,
      level: entry.level,
      message: entry.message,
      ...entry.details,
      correlationId: entry.correlationId,
      userId: entry.userId,
      sessionId: entry.sessionId,
      duration: entry.duration,
      statusCode: entry.statusCode,
      requestPath: entry.requestPath,
      stackTrace: entry.stackTrace,
    },
  };

  try {
    const response = await fetch(config.hecEndpoint, {
      method: "POST",
      headers: {
        Authorization: `Splunk ${config.hecToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(hecEvent),
    });

    if (!response.ok) {
      console.error("Failed to send log to Cribl:", response.statusText);
    }
  } catch (error) {
    console.error("Error sending log to Cribl:", error);
  }
}

/**
 * Send multiple log entries to Cribl HEC (batch)
 */
export async function sendLogsBatchToCribl(entries: LogEntry[]): Promise<void> {
  const config = getCriblConfig();
  if (!config) {
    console.warn("Cribl not configured, skipping batch log forward");
    return;
  }

  const hecEvents = entries.map((entry) => ({
    time: new Date(entry.timestamp).getTime() / 1000,
    host: process.env.WEBSITE_HOSTNAME || "pulse-app",
    source: entry.source,
    sourcetype: "pulse:application",
    event: {
      id: entry.id,
      level: entry.level,
      message: entry.message,
      ...entry.details,
      correlationId: entry.correlationId,
      userId: entry.userId,
      sessionId: entry.sessionId,
      duration: entry.duration,
      statusCode: entry.statusCode,
      requestPath: entry.requestPath,
      stackTrace: entry.stackTrace,
    },
  }));

  try {
    // HEC accepts newline-delimited JSON for batch
    const body = hecEvents.map((e) => JSON.stringify(e)).join("\n");

    const response = await fetch(config.hecEndpoint, {
      method: "POST",
      headers: {
        Authorization: `Splunk ${config.hecToken}`,
        "Content-Type": "application/json",
      },
      body,
    });

    if (!response.ok) {
      console.error("Failed to send batch logs to Cribl:", response.statusText);
    }
  } catch (error) {
    console.error("Error sending batch logs to Cribl:", error);
  }
}

// =============================================================================
// Cribl Search API
// =============================================================================

export interface CriblSearchQuery {
  timeRange?: {
    start: Date;
    end: Date;
  };
  levels?: string[];
  sources?: string[];
  keywords?: string[];
  limit?: number;
}

interface CriblSearchResponse {
  results: Array<{
    _time: string;
    _raw: string;
    [key: string]: unknown;
  }>;
  metadata: {
    totalResults: number;
    executionTimeMs: number;
  };
}

/**
 * Build Cribl SPL-like search query from structured parameters
 */
function buildSearchQuery(params: CriblSearchQuery): string {
  const clauses: string[] = ['sourcetype="pulse:application"'];

  if (params.levels && params.levels.length > 0) {
    const levelClause = params.levels.map((l) => `level="${l}"`).join(" OR ");
    clauses.push(`(${levelClause})`);
  }

  if (params.sources && params.sources.length > 0) {
    const sourceClause = params.sources.map((s) => `source="${s}"`).join(" OR ");
    clauses.push(`(${sourceClause})`);
  }

  if (params.keywords && params.keywords.length > 0) {
    params.keywords.forEach((kw) => {
      clauses.push(`"${kw}"`);
    });
  }

  return clauses.join(" AND ");
}

/**
 * Query logs from Cribl Search API
 */
export async function queryCribl(params: CriblSearchQuery): Promise<LogEntry[]> {
  const config = getCriblConfig();
  if (!config) {
    throw new Error("Cribl not configured");
  }

  const searchQuery = buildSearchQuery(params);
  const timeRange = params.timeRange || {
    start: new Date(Date.now() - 24 * 60 * 60 * 1000), // Default: last 24 hours
    end: new Date(),
  };

  try {
    const response = await fetch(config.searchEndpoint, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${config.searchApiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: searchQuery,
        earliest: timeRange.start.toISOString(),
        latest: timeRange.end.toISOString(),
        limit: params.limit || 500,
      }),
    });

    if (!response.ok) {
      throw new Error(`Cribl search failed: ${response.statusText}`);
    }

    const data: CriblSearchResponse = await response.json();
    return parseCriblResults(data.results);
  } catch (error) {
    console.error("Failed to query Cribl:", error);
    throw error;
  }
}

/**
 * Parse Cribl search results into LogEntry format
 */
function parseCriblResults(
  results: CriblSearchResponse["results"]
): LogEntry[] {
  return results.map((result, index) => {
    // Parse the event data
    let eventData: Record<string, unknown> = {};
    try {
      if (typeof result._raw === "string") {
        eventData = JSON.parse(result._raw);
      }
    } catch {
      eventData = { message: result._raw };
    }

    return {
      id: (result.id as string) || `cribl-${index}-${Date.now()}`,
      timestamp: result._time || new Date().toISOString(),
      level: (eventData.level as LogEntry["level"]) || "info",
      message: (eventData.message as string) || result._raw,
      source: (result.source as string) || "unknown",
      details: eventData.details as Record<string, unknown>,
      correlationId: eventData.correlationId as string,
      userId: eventData.userId as string,
      sessionId: eventData.sessionId as string,
      duration: eventData.duration as number,
      statusCode: eventData.statusCode as number,
      requestPath: eventData.requestPath as string,
      stackTrace: eventData.stackTrace as string,
    };
  });
}

// =============================================================================
// Specialized Queries (matching appInsights.ts interface)
// =============================================================================

/**
 * Query exception/error logs from Cribl
 */
export async function queryExceptionsFromCribl(
  timeRange?: { start: Date; end: Date },
  limit: number = 100
): Promise<LogEntry[]> {
  return queryCribl({
    timeRange,
    levels: ["error"],
    limit,
  });
}

/**
 * Query slow requests from Cribl
 */
export async function querySlowRequestsFromCribl(
  thresholdMs: number = 1000,
  timeRange?: { start: Date; end: Date },
  limit: number = 100
): Promise<LogEntry[]> {
  const config = getCriblConfig();
  if (!config) {
    throw new Error("Cribl not configured");
  }

  // Use a custom query to filter by duration
  const searchQuery = `sourcetype="pulse:application" duration>${thresholdMs}`;

  const defaultTimeRange = timeRange || {
    start: new Date(Date.now() - 24 * 60 * 60 * 1000),
    end: new Date(),
  };

  try {
    const response = await fetch(config.searchEndpoint, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${config.searchApiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: searchQuery,
        earliest: defaultTimeRange.start.toISOString(),
        latest: defaultTimeRange.end.toISOString(),
        limit,
      }),
    });

    if (!response.ok) {
      throw new Error(`Cribl search failed: ${response.statusText}`);
    }

    const data: CriblSearchResponse = await response.json();
    return parseCriblResults(data.results);
  } catch (error) {
    console.error("Failed to query slow requests from Cribl:", error);
    throw error;
  }
}
```

### Step 2: Create Unified Logging Interface

**File: `ui/lib/logging.ts`**

```typescript
/**
 * Unified Logging Interface
 * Abstracts the underlying log storage (Cribl, App Insights, or sample data)
 */

import {
  isCriblConfigured,
  queryCribl,
  queryExceptionsFromCribl,
  querySlowRequestsFromCribl,
  type LogEntry as CriblLogEntry,
  type CriblSearchQuery,
} from "./cribl";

import {
  isAppInsightsConfigured,
  queryApplicationInsights,
  queryExceptions,
  querySlowRequests,
  type LogEntry as AppInsightsLogEntry,
} from "./appInsights";

// =============================================================================
// Unified Log Entry Type
// =============================================================================

export interface LogEntry {
  id: string;
  timestamp: string;
  level: "error" | "warning" | "info" | "debug" | "trace";
  message: string;
  source: string;
  details?: Record<string, unknown>;
  correlationId?: string;
  userId?: string;
  sessionId?: string;
  duration?: number;
  statusCode?: number;
  requestPath?: string;
  stackTrace?: string;
}

export type DataSource = "cribl" | "app_insights" | "sample";

export interface QueryResult {
  logs: LogEntry[];
  dataSource: DataSource;
}

// =============================================================================
// Query Parameters
// =============================================================================

export interface LogQueryParams {
  timeRange?: {
    start: Date;
    end: Date;
  };
  levels?: string[];
  sources?: string[];
  keywords?: string[];
  limit?: number;
}

// =============================================================================
// Unified Query Functions
// =============================================================================

/**
 * Get the active data source
 */
export function getActiveDataSource(): DataSource {
  if (isCriblConfigured()) return "cribl";
  if (isAppInsightsConfigured()) return "app_insights";
  return "sample";
}

/**
 * Query logs from the best available source
 * Priority: Cribl > App Insights > Sample Data
 */
export async function queryLogs(params: LogQueryParams): Promise<QueryResult> {
  // Try Cribl first
  if (isCriblConfigured()) {
    try {
      const logs = await queryCribl(params as CriblSearchQuery);
      return { logs, dataSource: "cribl" };
    } catch (error) {
      console.error("Cribl query failed, trying fallback:", error);
    }
  }

  // Fallback to App Insights
  if (isAppInsightsConfigured()) {
    try {
      const logs = await queryApplicationInsights(params);
      return { logs, dataSource: "app_insights" };
    } catch (error) {
      console.error("App Insights query failed, using sample data:", error);
    }
  }

  // Final fallback: sample data
  const { generateSampleLogs } = await import(
    "@/app/api/admin/logs/search/route"
  );
  return { logs: generateSampleLogs(), dataSource: "sample" };
}

/**
 * Query exceptions from the best available source
 */
export async function queryExceptionsUnified(
  timeRange?: { start: Date; end: Date },
  limit: number = 100
): Promise<QueryResult> {
  if (isCriblConfigured()) {
    try {
      const logs = await queryExceptionsFromCribl(timeRange, limit);
      return { logs, dataSource: "cribl" };
    } catch (error) {
      console.error("Cribl exceptions query failed:", error);
    }
  }

  if (isAppInsightsConfigured()) {
    try {
      const logs = await queryExceptions(timeRange, limit);
      return { logs, dataSource: "app_insights" };
    } catch (error) {
      console.error("App Insights exceptions query failed:", error);
    }
  }

  return { logs: [], dataSource: "sample" };
}

/**
 * Query slow requests from the best available source
 */
export async function querySlowRequestsUnified(
  thresholdMs: number = 1000,
  timeRange?: { start: Date; end: Date },
  limit: number = 100
): Promise<QueryResult> {
  if (isCriblConfigured()) {
    try {
      const logs = await querySlowRequestsFromCribl(thresholdMs, timeRange, limit);
      return { logs, dataSource: "cribl" };
    } catch (error) {
      console.error("Cribl slow requests query failed:", error);
    }
  }

  if (isAppInsightsConfigured()) {
    try {
      const logs = await querySlowRequests(thresholdMs, timeRange, limit);
      return { logs, dataSource: "app_insights" };
    } catch (error) {
      console.error("App Insights slow requests query failed:", error);
    }
  }

  return { logs: [], dataSource: "sample" };
}
```

### Step 3: Update AI Log Search API

**File: `ui/app/api/admin/logs/search/route.ts`**

Update the imports and query logic:

```typescript
// Replace appInsights imports with unified logging
import {
  queryLogs,
  getActiveDataSource,
  type LogEntry,
  type DataSource,
} from "@/lib/logging";

// ... in the POST handler, replace the Application Insights query section:

    let allLogs: LogEntry[];
    let dataSource: DataSource = "sample";

    // Query from the best available source (Cribl > App Insights > Sample)
    try {
      const result = await queryLogs({
        timeRange: parsedQuery.timeRange || undefined,
        levels: parsedQuery.levels.length > 0 ? parsedQuery.levels : undefined,
        sources: parsedQuery.sources.length > 0 ? parsedQuery.sources : undefined,
        keywords: parsedQuery.keywords.length > 0 ? parsedQuery.keywords : undefined,
        limit: 500,
      });
      allLogs = result.logs;
      dataSource = result.dataSource;
      console.log(`Queried ${allLogs.length} logs from ${dataSource}`);
    } catch (error) {
      console.error("Log query failed, falling back to sample data:", error);
      allLogs = generateSampleLogs();
    }
```

### Step 4: Update Terraform Variables

**File: `modules/app/variables.tf`**

Add Cribl configuration variables:

```hcl
# Cribl Configuration
variable "cribl_hec_endpoint" {
  type        = string
  description = "Cribl HTTP Event Collector endpoint URL."
  default     = ""
}

variable "cribl_hec_token" {
  type        = string
  description = "Cribl HEC authentication token."
  sensitive   = true
  default     = ""
}

variable "cribl_search_endpoint" {
  type        = string
  description = "Cribl Search API endpoint URL."
  default     = ""
}

variable "cribl_search_api_key" {
  type        = string
  description = "Cribl Search API authentication key."
  sensitive   = true
  default     = ""
}
```

**File: `modules/app/main.tf`**

Add to app_settings:

```hcl
    # Cribl Configuration
    "CRIBL_HEC_ENDPOINT"    = var.cribl_hec_endpoint
    "CRIBL_HEC_TOKEN"       = var.cribl_hec_token
    "CRIBL_SEARCH_ENDPOINT" = var.cribl_search_endpoint
    "CRIBL_SEARCH_API_KEY"  = var.cribl_search_api_key
```

**File: `prod.tfvars`**

Add Cribl configuration (values to be filled in):

```hcl
# Cribl Configuration
cribl_hec_endpoint    = "https://your-cribl-instance/services/collector"
cribl_hec_token       = "" # Set via environment variable or Azure Key Vault
cribl_search_endpoint = "https://your-cribl-instance/api/v1/search"
cribl_search_api_key  = "" # Set via environment variable or Azure Key Vault
```

### Step 5: Update UI Component

**File: `ui/components/admin/logs/AILogSearch.tsx`**

Update the data source indicator to support Cribl:

```tsx
{/* Data Source Indicator */}
<span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
  result.dataSource === "cribl"
    ? "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400"
    : result.dataSource === "app_insights"
    ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
    : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
}`}>
  {result.dataSource === "cribl" ? (
    <>
      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
      </svg>
      Cribl Stream
    </>
  ) : result.dataSource === "app_insights" ? (
    <>
      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
      </svg>
      Azure Application Insights
    </>
  ) : (
    <>
      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      Sample Data
    </>
  )}
</span>
```

### Step 6: Implement Application-Level Logging

**File: `ui/lib/logger.ts`**

Create a structured logger that sends to Cribl:

```typescript
/**
 * Structured Application Logger
 * Sends logs to Cribl HEC when configured
 */

import { sendLogToCribl, sendLogsBatchToCribl, isCriblConfigured, type LogEntry } from "./cribl";
import { v4 as uuidv4 } from "uuid";

type LogLevel = "error" | "warning" | "info" | "debug" | "trace";

interface LogContext {
  correlationId?: string;
  userId?: string;
  sessionId?: string;
  requestPath?: string;
  duration?: number;
  statusCode?: number;
  [key: string]: unknown;
}

class Logger {
  private source: string;
  private buffer: LogEntry[] = [];
  private flushInterval: NodeJS.Timeout | null = null;
  private bufferSize = 10;
  private flushIntervalMs = 5000;

  constructor(source: string) {
    this.source = source;
    this.startFlushInterval();
  }

  private startFlushInterval() {
    if (typeof window === "undefined" && !this.flushInterval) {
      this.flushInterval = setInterval(() => this.flush(), this.flushIntervalMs);
    }
  }

  private createEntry(
    level: LogLevel,
    message: string,
    context?: LogContext
  ): LogEntry {
    return {
      id: uuidv4(),
      timestamp: new Date().toISOString(),
      level,
      message,
      source: this.source,
      details: context ? { ...context } : undefined,
      correlationId: context?.correlationId,
      userId: context?.userId,
      sessionId: context?.sessionId,
      requestPath: context?.requestPath,
      duration: context?.duration,
      statusCode: context?.statusCode,
    };
  }

  private async log(level: LogLevel, message: string, context?: LogContext) {
    const entry = this.createEntry(level, message, context);

    // Always log to console
    const consoleMethod = level === "error" ? "error" : level === "warning" ? "warn" : "log";
    console[consoleMethod](`[${this.source}] ${level.toUpperCase()}: ${message}`, context || "");

    // Send to Cribl if configured
    if (isCriblConfigured()) {
      this.buffer.push(entry);
      if (this.buffer.length >= this.bufferSize) {
        await this.flush();
      }
    }
  }

  async flush() {
    if (this.buffer.length === 0) return;

    const entries = [...this.buffer];
    this.buffer = [];

    try {
      await sendLogsBatchToCribl(entries);
    } catch (error) {
      console.error("Failed to flush logs to Cribl:", error);
      // Re-add to buffer for retry (with limit to prevent memory issues)
      if (this.buffer.length < 100) {
        this.buffer.push(...entries);
      }
    }
  }

  error(message: string, context?: LogContext) {
    return this.log("error", message, context);
  }

  warn(message: string, context?: LogContext) {
    return this.log("warning", message, context);
  }

  info(message: string, context?: LogContext) {
    return this.log("info", message, context);
  }

  debug(message: string, context?: LogContext) {
    return this.log("debug", message, context);
  }

  trace(message: string, context?: LogContext) {
    return this.log("trace", message, context);
  }

  // Create a child logger with preset context
  child(childContext: LogContext): Logger {
    const childLogger = new Logger(this.source);
    const originalLog = childLogger.log.bind(childLogger);
    childLogger.log = (level, message, context) => {
      return originalLog(level, message, { ...childContext, ...context });
    };
    return childLogger;
  }
}

// Export singleton loggers for different components
export const apiLogger = new Logger("api");
export const authLogger = new Logger("auth");
export const sessionLogger = new Logger("session");
export const trainingLogger = new Logger("training");
export const orchestratorLogger = new Logger("orchestrator");

// Factory function for custom loggers
export function createLogger(source: string): Logger {
  return new Logger(source);
}
```

### Step 7: Remove Application Insights (Final Phase)

**Terraform changes to remove Application Insights:**

**File: `main.tf`**

Comment out or remove:
```hcl
# REMOVED: Application Insights
# resource "azurerm_application_insights" "app_insights" {
#   ...
# }

# REMOVED: Log Analytics Workspace (if not needed for other purposes)
# resource "azurerm_log_analytics_workspace" "log_analytics" {
#   ...
# }
```

**File: `modules/app/main.tf`**

Remove from app_settings:
```hcl
    # REMOVED: Application Insights settings
    # "APPLICATIONINSIGHTS_CONNECTION_STRING" = var.app_insights_connection_string
    # "LOG_ANALYTICS_WORKSPACE_ID"            = var.log_analytics_workspace_id
```

**File: `modules/app/variables.tf`**

Remove unused variables:
```hcl
# REMOVED
# variable "app_insights_connection_string" { ... }
# variable "log_analytics_workspace_id" { ... }
```

**Files to delete:**
- `ui/lib/appInsights.ts` (after verifying Cribl works)

---

## Rollback Plan

If issues arise during migration:

### Phase 1-2 Rollback (Pre-cutover)
- Simply disable Cribl forwarding
- No changes to existing Application Insights flow

### Phase 3-4 Rollback (Post-cutover)
1. Update `ui/lib/logging.ts` to prioritize App Insights over Cribl:
   ```typescript
   export function getActiveDataSource(): DataSource {
     if (isAppInsightsConfigured()) return "app_insights";
     if (isCriblConfigured()) return "cribl";
     return "sample";
   }
   ```
2. Redeploy the application

### Phase 5 Rollback (After cleanup)
1. Restore Terraform resources from git history
2. Run `terraform apply` to recreate Application Insights
3. Update environment variables
4. Redeploy application

---

## Testing Strategy

### Unit Tests

```typescript
// ui/lib/__tests__/cribl.test.ts
describe("Cribl Integration", () => {
  describe("isCriblConfigured", () => {
    it("returns true when all env vars are set", () => {
      process.env.CRIBL_HEC_ENDPOINT = "https://example.com/hec";
      process.env.CRIBL_HEC_TOKEN = "token";
      process.env.CRIBL_SEARCH_ENDPOINT = "https://example.com/search";
      process.env.CRIBL_SEARCH_API_KEY = "key";
      expect(isCriblConfigured()).toBe(true);
    });

    it("returns false when env vars are missing", () => {
      delete process.env.CRIBL_HEC_ENDPOINT;
      expect(isCriblConfigured()).toBe(false);
    });
  });

  describe("buildSearchQuery", () => {
    it("builds correct query with all parameters", () => {
      const query = buildSearchQuery({
        levels: ["error", "warning"],
        sources: ["api"],
        keywords: ["timeout"],
      });
      expect(query).toContain('level="error"');
      expect(query).toContain('source="api"');
      expect(query).toContain('"timeout"');
    });
  });
});
```

### Integration Tests

1. **HEC Forwarding Test**
   - Send test log entries to Cribl HEC
   - Verify they appear in Cribl Stream
   - Check field mapping is correct

2. **Search API Test**
   - Query logs via Cribl Search API
   - Verify response format matches expected schema
   - Test time range filtering
   - Test level filtering
   - Test keyword search

3. **End-to-End Test**
   - Log an error in the application
   - Query via AI Log Search
   - Verify the error appears in results
   - Verify data source shows "Cribl Stream"

### Load Tests

- Send 1000 logs/minute to HEC
- Verify no logs are dropped
- Measure query response times under load

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Cribl API changes | Low | High | Pin API versions, monitor Cribl release notes |
| Network latency to Cribl | Medium | Medium | Implement buffering, async logging |
| Authentication token expiry | Medium | High | Implement token refresh, monitoring |
| Query performance degradation | Low | Medium | Implement caching, query optimization |
| Data loss during transition | Low | High | Run parallel logging during transition |
| Cribl outage | Low | High | Implement fallback to sample data |

---

## Checklist

### Pre-Implementation
- [ ] Cribl account provisioned and configured
- [ ] HEC endpoint created and tested
- [ ] Search API access verified
- [ ] Network connectivity tested
- [ ] Team trained on Cribl Search interface

### Phase 1: Preparation
- [ ] Create `ui/lib/cribl.ts`
- [ ] Create `ui/lib/logging.ts`
- [ ] Create `ui/lib/logger.ts`
- [ ] Add Terraform variables for Cribl
- [ ] Update `prod.tfvars` with Cribl endpoints

### Phase 2: Dual Logging
- [ ] Deploy with Cribl logging enabled
- [ ] Verify logs appearing in Cribl
- [ ] Monitor for errors or dropped logs
- [ ] Run for 1 week minimum

### Phase 3: Query Migration
- [ ] Update AI Log Search API to use unified logging
- [ ] Update UI to show Cribl data source
- [ ] Test all search functionality
- [ ] Performance testing

### Phase 4: Cutover
- [ ] Switch primary source to Cribl
- [ ] Monitor error rates
- [ ] Verify user experience unchanged
- [ ] Run for 1 week minimum

### Phase 5: Cleanup
- [ ] Remove Application Insights code
- [ ] Remove Terraform resources
- [ ] Update documentation
- [ ] Final cost verification

---

## Appendix: Cribl Search Query Examples

```spl
# All errors in last 24 hours
sourcetype="pulse:application" level="error"

# Authentication failures
sourcetype="pulse:application" source="auth" (level="error" OR level="warning")

# Slow requests (>1000ms)
sourcetype="pulse:application" duration>1000

# Specific user's logs
sourcetype="pulse:application" userId="user-123"

# Training session logs
sourcetype="pulse:application" source="training" sessionId="session-456"

# API errors with status codes
sourcetype="pulse:application" source="api" statusCode>=400

# Full text search
sourcetype="pulse:application" "connection refused"
```

---

*Document created: December 25, 2025*
*Target implementation: Post January 7th, 2026*
