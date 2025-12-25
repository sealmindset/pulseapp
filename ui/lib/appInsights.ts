// =============================================================================
// Application Insights Log Query Service
// Queries real logs from Azure Log Analytics / Application Insights
// =============================================================================

import { LogsQueryClient, LogsTable } from "@azure/monitor-query-logs";
import { DefaultAzureCredential, ManagedIdentityCredential } from "@azure/identity";

export interface LogEntry {
  id: string;
  timestamp: string;
  level: "info" | "warn" | "error" | "debug";
  source: string;
  message: string;
  details?: Record<string, unknown>;
  userId?: string;
  sessionId?: string;
  requestId?: string;
  duration?: number;
  statusCode?: number;
  endpoint?: string;
  ip?: string;
  operationId?: string;
  cloud_RoleName?: string;
}

export interface QueryOptions {
  timeRange?: { start: string; end: string };
  levels?: string[];
  sources?: string[];
  keywords?: string[];
  limit?: number;
}

// Map App Insights severity levels to our log levels
function mapSeverityLevel(severityLevel: number): LogEntry["level"] {
  switch (severityLevel) {
    case 0: return "debug";    // Verbose
    case 1: return "info";     // Information
    case 2: return "warn";     // Warning
    case 3: return "error";    // Error
    case 4: return "error";    // Critical
    default: return "info";
  }
}

// Parse operation name to extract endpoint
function extractEndpoint(operationName: string | undefined): string | undefined {
  if (!operationName) return undefined;
  // Operation names often look like "GET /api/chat" or "POST /api/session/start"
  const match = operationName.match(/(?:GET|POST|PUT|DELETE|PATCH)\s+(\S+)/);
  return match ? match[1] : operationName;
}

/**
 * Query Application Insights logs via Log Analytics
 */
export async function queryApplicationInsights(
  options: QueryOptions = {}
): Promise<LogEntry[]> {
  const workspaceId = process.env.LOG_ANALYTICS_WORKSPACE_ID;

  if (!workspaceId) {
    console.warn("LOG_ANALYTICS_WORKSPACE_ID not configured, using sample data");
    return [];
  }

  try {
    // Use Managed Identity in Azure, DefaultAzureCredential for local dev
    const credential = process.env.AZURE_CLIENT_ID
      ? new ManagedIdentityCredential()
      : new DefaultAzureCredential();

    const client = new LogsQueryClient(credential);

    // Build the KQL query
    const kqlQuery = buildKqlQuery(options);

    // Determine time range
    const timeSpan = options.timeRange
      ? {
          startTime: new Date(options.timeRange.start),
          endTime: new Date(options.timeRange.end),
        }
      : { duration: "P2D" }; // Default to last 2 days

    const result = await client.queryWorkspace(workspaceId, kqlQuery, timeSpan);

    if (result.status === "Success" && result.tables.length > 0) {
      return parseLogsTable(result.tables[0]);
    }

    if (result.status === "PartialFailure") {
      console.warn("Partial query failure:", result.partialError);
      // PartialFailure still has tables in the partialTables property
      const tables = "partialTables" in result ? result.partialTables : [];
      if (tables && tables.length > 0) {
        return parseLogsTable(tables[0]);
      }
    }

    return [];
  } catch (error) {
    console.error("Failed to query Application Insights:", error);
    throw error;
  }
}

/**
 * Build KQL query based on options
 */
function buildKqlQuery(options: QueryOptions): string {
  const limit = options.limit || 500;

  // Union multiple tables to get comprehensive logs
  let query = `
union AppTraces, AppRequests, AppExceptions, AppDependencies
| extend
    LogLevel = case(
        SeverityLevel == 0, "debug",
        SeverityLevel == 1, "info",
        SeverityLevel == 2, "warn",
        SeverityLevel == 3 or SeverityLevel == 4, "error",
        "info"
    ),
    Source = coalesce(AppRoleName, Cloud_RoleName, "unknown"),
    LogMessage = coalesce(Message, ExceptionType, Name, ""),
    Endpoint = coalesce(Url, Target, ""),
    Duration = DurationMs,
    StatusCode = ResultCode
`;

  // Apply level filters
  if (options.levels && options.levels.length > 0) {
    const levelConditions = options.levels.map(l => `LogLevel == "${l}"`).join(" or ");
    query += `| where ${levelConditions}\n`;
  }

  // Apply source filters
  if (options.sources && options.sources.length > 0) {
    const sourceConditions = options.sources.map(s =>
      `Source contains "${s}" or Endpoint contains "${s}"`
    ).join(" or ");
    query += `| where ${sourceConditions}\n`;
  }

  // Apply keyword filters
  if (options.keywords && options.keywords.length > 0) {
    const keywordConditions = options.keywords.map(k =>
      `LogMessage contains "${k}" or Endpoint contains "${k}"`
    ).join(" or ");
    query += `| where ${keywordConditions}\n`;
  }

  // Project final columns and limit
  query += `
| project
    TimeGenerated,
    LogLevel,
    Source,
    LogMessage,
    Endpoint,
    Duration,
    StatusCode,
    OperationId,
    SessionId,
    UserId,
    ClientIP,
    Properties
| order by TimeGenerated desc
| take ${limit}
`;

  return query;
}

/**
 * Parse Log Analytics table response into LogEntry objects
 */
function parseLogsTable(table: LogsTable): LogEntry[] {
  const entries: LogEntry[] = [];

  // Get column indices - property is columnDescriptors in the new SDK
  const columns = table.columnDescriptors.reduce((acc, col, idx) => {
    acc[col.name || ""] = idx;
    return acc;
  }, {} as Record<string, number>);

  for (const row of table.rows) {
    const getValue = (colName: string): unknown => {
      const idx = columns[colName];
      return idx !== undefined ? row[idx] : undefined;
    };

    const timestamp = getValue("TimeGenerated") as string;
    const level = getValue("LogLevel") as LogEntry["level"];
    const message = getValue("LogMessage") as string;
    const source = getValue("Source") as string;
    const endpoint = getValue("Endpoint") as string;
    const duration = getValue("Duration") as number;
    const statusCode = getValue("StatusCode") as number;
    const operationId = getValue("OperationId") as string;
    const sessionId = getValue("SessionId") as string;
    const userId = getValue("UserId") as string;
    const clientIP = getValue("ClientIP") as string;
    const properties = getValue("Properties") as Record<string, unknown>;

    entries.push({
      id: operationId || `log-${Date.now()}-${Math.random().toString(36).substring(7)}`,
      timestamp: new Date(timestamp).toISOString(),
      level: level || "info",
      source: source || "unknown",
      message: message || "",
      endpoint: endpoint || undefined,
      duration: duration || undefined,
      statusCode: typeof statusCode === "number" ? statusCode : undefined,
      operationId: operationId || undefined,
      sessionId: sessionId || undefined,
      userId: userId || undefined,
      ip: clientIP || undefined,
      details: properties || undefined,
    });
  }

  return entries;
}

/**
 * Query specific error traces with stack traces
 */
export async function queryExceptions(
  timeRange?: { start: string; end: string },
  limit = 100
): Promise<LogEntry[]> {
  const workspaceId = process.env.LOG_ANALYTICS_WORKSPACE_ID;

  if (!workspaceId) {
    return [];
  }

  try {
    const credential = process.env.AZURE_CLIENT_ID
      ? new ManagedIdentityCredential()
      : new DefaultAzureCredential();

    const client = new LogsQueryClient(credential);

    const query = `
AppExceptions
| project
    TimeGenerated,
    ExceptionType,
    OuterMessage,
    InnermostMessage,
    Details,
    OperationId,
    SessionId,
    UserId,
    AppRoleName,
    ClientIP
| order by TimeGenerated desc
| take ${limit}
`;

    const timeSpan = timeRange
      ? { startTime: new Date(timeRange.start), endTime: new Date(timeRange.end) }
      : { duration: "P2D" };

    const result = await client.queryWorkspace(workspaceId, query, timeSpan);

    if (result.status === "Success" && result.tables.length > 0) {
      return parseExceptionsTable(result.tables[0]);
    }

    return [];
  } catch (error) {
    console.error("Failed to query exceptions:", error);
    return [];
  }
}

function parseExceptionsTable(table: LogsTable): LogEntry[] {
  const entries: LogEntry[] = [];

  const columns = table.columnDescriptors.reduce((acc, col, idx) => {
    acc[col.name || ""] = idx;
    return acc;
  }, {} as Record<string, number>);

  for (const row of table.rows) {
    const getValue = (colName: string): unknown => {
      const idx = columns[colName];
      return idx !== undefined ? row[idx] : undefined;
    };

    const timestamp = getValue("TimeGenerated") as string;
    const exceptionType = getValue("ExceptionType") as string;
    const outerMessage = getValue("OuterMessage") as string;
    const innermostMessage = getValue("InnermostMessage") as string;
    const details = getValue("Details") as string;
    const operationId = getValue("OperationId") as string;
    const sessionId = getValue("SessionId") as string;
    const userId = getValue("UserId") as string;
    const roleName = getValue("AppRoleName") as string;
    const clientIP = getValue("ClientIP") as string;

    entries.push({
      id: operationId || `exc-${Date.now()}-${Math.random().toString(36).substring(7)}`,
      timestamp: new Date(timestamp).toISOString(),
      level: "error",
      source: roleName || "unknown",
      message: `${exceptionType}: ${outerMessage || innermostMessage || "Unknown error"}`,
      operationId: operationId || undefined,
      sessionId: sessionId || undefined,
      userId: userId || undefined,
      ip: clientIP || undefined,
      details: details ? { stackTrace: details } : undefined,
    });
  }

  return entries;
}

/**
 * Query request performance data
 */
export async function querySlowRequests(
  thresholdMs = 2000,
  timeRange?: { start: string; end: string },
  limit = 100
): Promise<LogEntry[]> {
  const workspaceId = process.env.LOG_ANALYTICS_WORKSPACE_ID;

  if (!workspaceId) {
    return [];
  }

  try {
    const credential = process.env.AZURE_CLIENT_ID
      ? new ManagedIdentityCredential()
      : new DefaultAzureCredential();

    const client = new LogsQueryClient(credential);

    const query = `
AppRequests
| where DurationMs > ${thresholdMs}
| project
    TimeGenerated,
    Name,
    Url,
    DurationMs,
    ResultCode,
    Success,
    OperationId,
    SessionId,
    UserId,
    AppRoleName,
    ClientIP
| order by DurationMs desc
| take ${limit}
`;

    const timeSpan = timeRange
      ? { startTime: new Date(timeRange.start), endTime: new Date(timeRange.end) }
      : { duration: "P2D" };

    const result = await client.queryWorkspace(workspaceId, query, timeSpan);

    if (result.status === "Success" && result.tables.length > 0) {
      return parseRequestsTable(result.tables[0]);
    }

    return [];
  } catch (error) {
    console.error("Failed to query slow requests:", error);
    return [];
  }
}

function parseRequestsTable(table: LogsTable): LogEntry[] {
  const entries: LogEntry[] = [];

  const columns = table.columnDescriptors.reduce((acc, col, idx) => {
    acc[col.name || ""] = idx;
    return acc;
  }, {} as Record<string, number>);

  for (const row of table.rows) {
    const getValue = (colName: string): unknown => {
      const idx = columns[colName];
      return idx !== undefined ? row[idx] : undefined;
    };

    const timestamp = getValue("TimeGenerated") as string;
    const name = getValue("Name") as string;
    const url = getValue("Url") as string;
    const durationMs = getValue("DurationMs") as number;
    const resultCode = getValue("ResultCode") as string;
    const success = getValue("Success") as boolean;
    const operationId = getValue("OperationId") as string;
    const sessionId = getValue("SessionId") as string;
    const userId = getValue("UserId") as string;
    const roleName = getValue("AppRoleName") as string;
    const clientIP = getValue("ClientIP") as string;

    entries.push({
      id: operationId || `req-${Date.now()}-${Math.random().toString(36).substring(7)}`,
      timestamp: new Date(timestamp).toISOString(),
      level: success ? "warn" : "error",
      source: roleName || "unknown",
      message: `Slow request: ${name} (${Math.round(durationMs)}ms)`,
      endpoint: url || name || undefined,
      duration: durationMs,
      statusCode: parseInt(resultCode) || undefined,
      operationId: operationId || undefined,
      sessionId: sessionId || undefined,
      userId: userId || undefined,
      ip: clientIP || undefined,
    });
  }

  return entries;
}

/**
 * Check if Application Insights is configured
 */
export function isAppInsightsConfigured(): boolean {
  return !!process.env.LOG_ANALYTICS_WORKSPACE_ID;
}
