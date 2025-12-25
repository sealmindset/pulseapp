# PULSE Web Application Firewall (WAF) Implementation Guide

**Version:** 1.0
**Last Updated:** 2025-12-25
**Priority:** HIGH
**Related Documents:** [securedbydesign.md](securedbydesign.md), [nsgconfig.md](nsgconfig.md), [ratelimiting.md](ratelimiting.md)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [WAF Architecture Overview](#waf-architecture-overview)
3. [Azure Front Door Premium with WAF](#azure-front-door-premium-with-waf)
4. [WAF Policy Configuration](#waf-policy-configuration)
5. [Managed Rule Sets](#managed-rule-sets)
6. [Custom Rules](#custom-rules)
7. [Bot Protection](#bot-protection)
8. [Geo-Filtering](#geo-filtering)
9. [Logging and Monitoring](#logging-and-monitoring)
10. [Terraform Implementation](#terraform-implementation)
11. [Testing and Validation](#testing-and-validation)
12. [Migration Checklist](#migration-checklist)

---

## Executive Summary

A Web Application Firewall (WAF) is essential for protecting the PULSE application from:

- **OWASP Top 10 vulnerabilities** (SQL injection, XSS, etc.)
- **Bot attacks** and automated threats
- **DDoS attacks** at the application layer
- **Zero-day exploits** through managed rule updates
- **Geographic-based threats** through geo-filtering

This guide implements Azure Front Door Premium with WAF for comprehensive Layer 7 protection.

---

## WAF Architecture Overview

### Defense in Depth

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Internet                                        │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │     Azure DDoS Protection  │
                    │      (Network Layer)       │
                    └─────────────┬─────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                        Azure Front Door Premium                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         WAF Policy                                      │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │ │
│  │  │ Managed Rules│  │ Custom Rules │  │Bot Protection│  │ Rate Limit │  │ │
│  │  │  (OWASP)     │  │              │  │              │  │            │  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    Origin Groups & Routing                              │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │        App Service        │
                    │    (Private Endpoint)     │
                    └───────────────────────────┘
```

### WAF Benefits

| Feature | Protection |
|---------|------------|
| OWASP Core Rule Set | SQL injection, XSS, LFI/RFI, command injection |
| Bot Manager | Credential stuffing, scraping, automated attacks |
| Rate Limiting | DDoS, brute force, API abuse |
| Geo-Filtering | Block traffic from high-risk regions |
| Custom Rules | Application-specific protections |

---

## Azure Front Door Premium with WAF

### Why Azure Front Door Premium?

- **Global edge network** for low latency
- **Integrated WAF** with managed rules
- **Private Link support** to origins
- **Advanced analytics** and logging
- **Bot protection** capabilities

### Terraform Configuration

Create `infra/modules/frontdoor/main.tf`:

```hcl
# Azure Front Door Premium with WAF

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "environment" {
  type = string
}

variable "custom_domain" {
  type = string
}

variable "origin_host_name" {
  type = string
}

variable "origin_private_link_resource_id" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

# Front Door Profile
resource "azurerm_cdn_frontdoor_profile" "main" {
  name                = "afd-pulse-${var.environment}"
  resource_group_name = var.resource_group_name
  sku_name            = "Premium_AzureFrontDoor"

  response_timeout_seconds = 120

  tags = merge(var.tags, {
    purpose = "CDN and WAF for PULSE application"
  })
}

# Front Door Endpoint
resource "azurerm_cdn_frontdoor_endpoint" "main" {
  name                     = "fde-pulse-${var.environment}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main.id
  enabled                  = true

  tags = var.tags
}

# Origin Group
resource "azurerm_cdn_frontdoor_origin_group" "webapp" {
  name                     = "og-webapp"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main.id

  load_balancing {
    additional_latency_in_milliseconds = 50
    sample_size                        = 4
    successful_samples_required        = 3
  }

  health_probe {
    path                = "/health"
    protocol            = "Https"
    interval_in_seconds = 30
    request_type        = "HEAD"
  }

  session_affinity_enabled = true
}

# Origin with Private Link
resource "azurerm_cdn_frontdoor_origin" "webapp" {
  name                          = "origin-webapp"
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.webapp.id
  enabled                       = true

  certificate_name_check_enabled = true
  host_name                      = var.origin_host_name
  http_port                      = 80
  https_port                     = 443
  origin_host_header             = var.origin_host_name
  priority                       = 1
  weight                         = 1000

  private_link {
    request_message        = "Please approve this Private Link connection for PULSE Front Door"
    target_type            = "sites"
    location               = var.location
    private_link_target_id = var.origin_private_link_resource_id
  }
}

# Custom Domain
resource "azurerm_cdn_frontdoor_custom_domain" "main" {
  name                     = "domain-pulse"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main.id
  host_name                = var.custom_domain

  tls {
    certificate_type    = "ManagedCertificate"
    minimum_tls_version = "TLS12"
  }
}

# Route
resource "azurerm_cdn_frontdoor_route" "main" {
  name                          = "route-main"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.main.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.webapp.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.webapp.id]

  cdn_frontdoor_custom_domain_ids = [azurerm_cdn_frontdoor_custom_domain.main.id]

  supported_protocols    = ["Https"]
  https_redirect_enabled = true
  patterns_to_match      = ["/*"]
  forwarding_protocol    = "HttpsOnly"

  link_to_default_domain = true

  cache {
    query_string_caching_behavior = "IgnoreQueryString"
    compression_enabled           = true
    content_types_to_compress     = [
      "text/html",
      "text/css",
      "text/javascript",
      "application/javascript",
      "application/json",
    ]
  }
}

# Outputs
output "frontdoor_id" {
  value = azurerm_cdn_frontdoor_profile.main.id
}

output "endpoint_hostname" {
  value = azurerm_cdn_frontdoor_endpoint.main.host_name
}

output "custom_domain_id" {
  value = azurerm_cdn_frontdoor_custom_domain.main.id
}
```

---

## WAF Policy Configuration

### Create WAF Policy

Create `infra/modules/frontdoor/waf.tf`:

```hcl
# Azure Front Door WAF Policy

resource "azurerm_cdn_frontdoor_firewall_policy" "main" {
  name                              = "wafpolicy-pulse-${var.environment}"
  resource_group_name               = var.resource_group_name
  sku_name                          = azurerm_cdn_frontdoor_profile.main.sku_name
  enabled                           = true
  mode                              = var.waf_mode  # "Detection" or "Prevention"
  redirect_url                      = "https://${var.custom_domain}/blocked"
  custom_block_response_status_code = 403
  custom_block_response_body        = base64encode(jsonencode({
    error   = "Request blocked by security policy"
    code    = "WAF_BLOCKED"
    support = "Contact support if you believe this is an error"
  }))

  tags = var.tags
}

variable "waf_mode" {
  type        = string
  default     = "Prevention"
  description = "WAF mode: Detection or Prevention"
}

# Associate WAF with Front Door
resource "azurerm_cdn_frontdoor_security_policy" "main" {
  name                     = "secpolicy-pulse-${var.environment}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main.id

  security_policies {
    firewall {
      cdn_frontdoor_firewall_policy_id = azurerm_cdn_frontdoor_firewall_policy.main.id

      association {
        domain {
          cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_custom_domain.main.id
        }
        patterns_to_match = ["/*"]
      }
    }
  }
}
```

---

## Managed Rule Sets

### OWASP Core Rule Set

```hcl
# Add to waf.tf

# OWASP 3.2 Core Rule Set (DRS 2.1)
resource "azurerm_cdn_frontdoor_firewall_policy" "main" {
  # ... previous configuration ...

  managed_rule {
    type    = "Microsoft_DefaultRuleSet"
    version = "2.1"
    action  = "Block"

    # Rule group overrides for fine-tuning
    override {
      rule_group_name = "SQLI"

      rule {
        rule_id = "942100"
        enabled = true
        action  = "Block"
      }
    }

    override {
      rule_group_name = "XSS"

      rule {
        rule_id = "941100"
        enabled = true
        action  = "Block"
      }
    }

    # Exclude specific rules that cause false positives
    exclusion {
      match_variable = "RequestBodyPostArgNames"
      operator       = "Equals"
      selector       = "message"  # Chat message field

      rule {
        rule_id = "942200"  # SQL injection in request body
        enabled = false
      }
    }

    exclusion {
      match_variable = "RequestBodyJsonArgNames"
      operator       = "Equals"
      selector       = "content"

      rule {
        rule_id = "941100"  # XSS in JSON body
        enabled = false
      }
    }
  }

  # Bot Manager Rule Set
  managed_rule {
    type    = "Microsoft_BotManagerRuleSet"
    version = "1.0"
    action  = "Block"

    override {
      rule_group_name = "BadBots"

      rule {
        rule_id = "Bot100100"
        enabled = true
        action  = "Block"
      }
    }

    override {
      rule_group_name = "GoodBots"

      rule {
        rule_id = "Bot200100"
        enabled = true
        action  = "Allow"
      }
    }
  }
}
```

### Rule Categories

| Rule Group | Purpose | Recommended Action |
|------------|---------|-------------------|
| SQLI | SQL injection attacks | Block |
| XSS | Cross-site scripting | Block |
| LFI | Local file inclusion | Block |
| RFI | Remote file inclusion | Block |
| RCE | Remote code execution | Block |
| PHP | PHP-specific attacks | Block |
| JAVA | Java-specific attacks | Block |
| PROTOCOL | Protocol violations | Block |
| GENERIC | Generic attacks | Block |
| BadBots | Malicious bots | Block |
| GoodBots | Known good bots | Allow |

---

## Custom Rules

### Add Custom Rules

```hcl
# Add to waf.tf

resource "azurerm_cdn_frontdoor_firewall_policy" "main" {
  # ... previous configuration ...

  # Block requests without proper headers
  custom_rule {
    name     = "RequireHostHeader"
    priority = 10
    type     = "MatchRule"
    action   = "Block"
    enabled  = true

    match_condition {
      match_variable     = "RequestHeader"
      selector           = "Host"
      operator           = "Equal"
      match_values       = [""]
      negation_condition = false
    }
  }

  # Block known attack patterns in URL
  custom_rule {
    name     = "BlockMaliciousUrls"
    priority = 20
    type     = "MatchRule"
    action   = "Block"
    enabled  = true

    match_condition {
      match_variable = "RequestUri"
      operator       = "Contains"
      match_values   = [
        "..%2f",
        "..%252f",
        "%00",
        "etc/passwd",
        "etc/shadow",
        "win.ini",
        "boot.ini",
        "php://",
        "data://",
        "expect://",
      ]
      transforms         = ["UrlDecode", "Lowercase"]
      negation_condition = false
    }
  }

  # Block suspicious User-Agents
  custom_rule {
    name     = "BlockSuspiciousAgents"
    priority = 30
    type     = "MatchRule"
    action   = "Block"
    enabled  = true

    match_condition {
      match_variable = "RequestHeader"
      selector       = "User-Agent"
      operator       = "Contains"
      match_values   = [
        "sqlmap",
        "nikto",
        "nessus",
        "nmap",
        "masscan",
        "dirbuster",
        "gobuster",
        "wfuzz",
        "burpsuite",
        "nuclei",
      ]
      transforms         = ["Lowercase"]
      negation_condition = false
    }
  }

  # Rate limiting - General
  custom_rule {
    name     = "RateLimitGeneral"
    priority = 100
    type     = "RateLimitRule"
    action   = "Block"
    enabled  = true

    rate_limit_duration_in_minutes = 1
    rate_limit_threshold           = 100

    match_condition {
      match_variable     = "RemoteAddr"
      operator           = "IPMatch"
      match_values       = ["0.0.0.0/0"]
      negation_condition = false
    }
  }

  # Rate limiting - API endpoints (stricter)
  custom_rule {
    name     = "RateLimitAPI"
    priority = 90
    type     = "RateLimitRule"
    action   = "Block"
    enabled  = true

    rate_limit_duration_in_minutes = 1
    rate_limit_threshold           = 30

    match_condition {
      match_variable     = "RequestUri"
      operator           = "BeginsWith"
      match_values       = ["/api/"]
      negation_condition = false
    }
  }

  # Rate limiting - Auth endpoints (strictest)
  custom_rule {
    name     = "RateLimitAuth"
    priority = 80
    type     = "RateLimitRule"
    action   = "Block"
    enabled  = true

    rate_limit_duration_in_minutes = 1
    rate_limit_threshold           = 10

    match_condition {
      match_variable     = "RequestUri"
      operator           = "Contains"
      match_values       = ["/auth/", "/login", "/signin", "/api/auth"]
      negation_condition = false
    }
  }

  # Block large request bodies (potential DoS)
  custom_rule {
    name     = "BlockLargeRequests"
    priority = 40
    type     = "MatchRule"
    action   = "Block"
    enabled  = true

    match_condition {
      match_variable     = "RequestBody"
      operator           = "GreaterThan"
      match_values       = ["10485760"]  # 10 MB
      negation_condition = false
    }
  }

  # Block requests with too many headers
  custom_rule {
    name     = "BlockExcessiveHeaders"
    priority = 50
    type     = "MatchRule"
    action   = "Block"
    enabled  = true

    match_condition {
      match_variable     = "RequestHeader"
      selector           = "X-Custom-Header-Count"
      operator           = "GreaterThan"
      match_values       = ["50"]
      negation_condition = false
    }
  }

  # Protect admin paths
  custom_rule {
    name     = "ProtectAdminPaths"
    priority = 60
    type     = "MatchRule"
    action   = "Block"
    enabled  = true

    match_condition {
      match_variable = "RequestUri"
      operator       = "Contains"
      match_values   = [
        "/admin",
        "/wp-admin",
        "/wp-login",
        "/phpmyadmin",
        "/adminer",
        "/.env",
        "/.git",
        "/debug",
      ]
      transforms         = ["Lowercase"]
      negation_condition = false
    }
  }
}
```

---

## Bot Protection

### Enhanced Bot Protection Rules

```hcl
# Add to waf.tf

resource "azurerm_cdn_frontdoor_firewall_policy" "main" {
  # ... previous configuration ...

  # Block empty or missing User-Agent
  custom_rule {
    name     = "BlockEmptyUserAgent"
    priority = 70
    type     = "MatchRule"
    action   = "Block"
    enabled  = true

    match_condition {
      match_variable = "RequestHeader"
      selector       = "User-Agent"
      operator       = "Equal"
      match_values   = [""]
    }
  }

  # Block common web scrapers
  custom_rule {
    name     = "BlockScrapers"
    priority = 75
    type     = "MatchRule"
    action   = "Block"
    enabled  = true

    match_condition {
      match_variable = "RequestHeader"
      selector       = "User-Agent"
      operator       = "Contains"
      match_values   = [
        "scrapy",
        "python-requests",
        "python-urllib",
        "libwww",
        "lwp-trivial",
        "curl",
        "wget",
        "httpclient",
        "java/",
        "go-http-client",
      ]
      transforms = ["Lowercase"]
    }
  }

  # Challenge suspicious traffic patterns
  custom_rule {
    name     = "ChallengeNoReferer"
    priority = 110
    type     = "MatchRule"
    action   = "JSChallenge"  # JavaScript challenge
    enabled  = true

    # POST requests without referer to API
    match_condition {
      match_variable = "RequestMethod"
      operator       = "Equal"
      match_values   = ["POST"]
    }

    match_condition {
      match_variable = "RequestUri"
      operator       = "BeginsWith"
      match_values   = ["/api/"]
    }

    match_condition {
      match_variable = "RequestHeader"
      selector       = "Referer"
      operator       = "Equal"
      match_values   = [""]
    }
  }
}
```

---

## Geo-Filtering

### Geographic Access Controls

```hcl
# Add to waf.tf

variable "allowed_countries" {
  type        = list(string)
  default     = ["US", "CA", "GB", "DE", "FR", "AU"]
  description = "Allowed country codes (ISO 3166-1 alpha-2)"
}

variable "blocked_countries" {
  type        = list(string)
  default     = []
  description = "Explicitly blocked country codes"
}

resource "azurerm_cdn_frontdoor_firewall_policy" "main" {
  # ... previous configuration ...

  # Block traffic from specific countries
  dynamic "custom_rule" {
    for_each = length(var.blocked_countries) > 0 ? [1] : []
    content {
      name     = "GeoBlockCountries"
      priority = 5
      type     = "MatchRule"
      action   = "Block"
      enabled  = true

      match_condition {
        match_variable = "RemoteAddr"
        operator       = "GeoMatch"
        match_values   = var.blocked_countries
      }
    }
  }

  # Optional: Only allow specific countries (whitelist)
  dynamic "custom_rule" {
    for_each = length(var.allowed_countries) > 0 && var.enable_geo_whitelist ? [1] : []
    content {
      name     = "GeoAllowCountries"
      priority = 6
      type     = "MatchRule"
      action   = "Block"
      enabled  = true

      match_condition {
        match_variable     = "RemoteAddr"
        operator           = "GeoMatch"
        match_values       = var.allowed_countries
        negation_condition = true  # Block if NOT in allowed list
      }
    }
  }
}

variable "enable_geo_whitelist" {
  type        = bool
  default     = false
  description = "Enable country whitelist mode"
}
```

---

## Logging and Monitoring

### Diagnostic Settings

```hcl
# Add to waf.tf

# Log Analytics Workspace for WAF logs
resource "azurerm_log_analytics_workspace" "waf" {
  name                = "law-waf-pulse-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = var.tags
}

# Diagnostic settings for Front Door
resource "azurerm_monitor_diagnostic_setting" "frontdoor" {
  name                       = "diag-frontdoor-pulse"
  target_resource_id         = azurerm_cdn_frontdoor_profile.main.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.waf.id

  enabled_log {
    category = "FrontDoorAccessLog"
  }

  enabled_log {
    category = "FrontDoorHealthProbeLog"
  }

  enabled_log {
    category = "FrontDoorWebApplicationFirewallLog"
  }

  metric {
    category = "AllMetrics"
  }
}
```

### WAF Log Queries

Create `infra/monitoring/waf-queries.kql`:

```kql
// WAF Log Analysis Queries

// 1. WAF blocks over time
AzureDiagnostics
| where Category == "FrontDoorWebApplicationFirewallLog"
| where action_s == "Block"
| summarize count() by bin(TimeGenerated, 1h)
| render timechart

// 2. Top blocked IPs
AzureDiagnostics
| where Category == "FrontDoorWebApplicationFirewallLog"
| where action_s == "Block"
| summarize
    blocks = count(),
    rules = make_set(ruleName_s)
    by clientIp_s
| order by blocks desc
| take 20

// 3. Most triggered rules
AzureDiagnostics
| where Category == "FrontDoorWebApplicationFirewallLog"
| where action_s == "Block"
| summarize count() by ruleName_s, ruleId_s
| order by count_ desc
| take 20

// 4. Blocked requests by country
AzureDiagnostics
| where Category == "FrontDoorWebApplicationFirewallLog"
| where action_s == "Block"
| extend country = geo_info_country_s
| summarize blocks = count() by country
| order by blocks desc

// 5. Attack patterns
AzureDiagnostics
| where Category == "FrontDoorWebApplicationFirewallLog"
| where action_s == "Block"
| extend attack_type = case(
    ruleName_s contains "SQLI", "SQL Injection",
    ruleName_s contains "XSS", "Cross-Site Scripting",
    ruleName_s contains "LFI", "Local File Inclusion",
    ruleName_s contains "RFI", "Remote File Inclusion",
    ruleName_s contains "RCE", "Remote Code Execution",
    ruleName_s contains "Bot", "Bot Attack",
    ruleName_s contains "RateLimit", "Rate Limiting",
    "Other"
)
| summarize count() by attack_type
| render piechart

// 6. False positive candidates
AzureDiagnostics
| where Category == "FrontDoorWebApplicationFirewallLog"
| where action_s == "Block"
| summarize
    blocks = count(),
    unique_ips = dcount(clientIp_s)
    by ruleName_s, ruleId_s, requestUri_s
| where unique_ips > 10  // Many different IPs suggests false positive
| order by blocks desc

// 7. Blocked API requests
AzureDiagnostics
| where Category == "FrontDoorWebApplicationFirewallLog"
| where action_s == "Block"
| where requestUri_s startswith "/api/"
| summarize count() by requestUri_s, ruleName_s
| order by count_ desc

// 8. Real-time threat monitoring
AzureDiagnostics
| where Category == "FrontDoorWebApplicationFirewallLog"
| where TimeGenerated > ago(15m)
| where action_s == "Block"
| project
    TimeGenerated,
    clientIp_s,
    ruleName_s,
    requestUri_s,
    host_s
| order by TimeGenerated desc
```

### Alert Rules

Create `infra/modules/monitoring/waf-alerts.tf`:

```hcl
# WAF Alert Rules

# High volume of WAF blocks
resource "azurerm_monitor_scheduled_query_rules_alert" "waf_high_blocks" {
  name                = "pulse-waf-high-blocks"
  location            = var.location
  resource_group_name = var.resource_group_name

  action {
    action_group = [var.alert_action_group_id]
  }

  data_source_id = var.log_analytics_workspace_id
  description    = "High volume of WAF blocks detected"
  enabled        = true

  query = <<-QUERY
    AzureDiagnostics
    | where Category == "FrontDoorWebApplicationFirewallLog"
    | where TimeGenerated > ago(15m)
    | where action_s == "Block"
    | summarize count()
  QUERY

  severity    = 2
  frequency   = 5
  time_window = 15

  trigger {
    operator  = "GreaterThan"
    threshold = 100
  }
}

# SQL injection attempts
resource "azurerm_monitor_scheduled_query_rules_alert" "waf_sqli" {
  name                = "pulse-waf-sqli-attack"
  location            = var.location
  resource_group_name = var.resource_group_name

  action {
    action_group = [var.alert_action_group_id]
  }

  data_source_id = var.log_analytics_workspace_id
  description    = "SQL injection attack detected"
  enabled        = true

  query = <<-QUERY
    AzureDiagnostics
    | where Category == "FrontDoorWebApplicationFirewallLog"
    | where TimeGenerated > ago(5m)
    | where action_s == "Block"
    | where ruleName_s contains "SQLI"
    | summarize count()
  QUERY

  severity    = 1
  frequency   = 5
  time_window = 10

  trigger {
    operator  = "GreaterThan"
    threshold = 5
  }
}

# Potential DDoS
resource "azurerm_monitor_scheduled_query_rules_alert" "waf_ddos" {
  name                = "pulse-waf-ddos-detection"
  location            = var.location
  resource_group_name = var.resource_group_name

  action {
    action_group = [var.alert_action_group_id]
  }

  data_source_id = var.log_analytics_workspace_id
  description    = "Potential DDoS attack - rate limit violations"
  enabled        = true

  query = <<-QUERY
    AzureDiagnostics
    | where Category == "FrontDoorWebApplicationFirewallLog"
    | where TimeGenerated > ago(5m)
    | where ruleName_s contains "RateLimit"
    | summarize unique_ips = dcount(clientIp_s)
    | where unique_ips > 50
  QUERY

  severity    = 1
  frequency   = 5
  time_window = 10

  trigger {
    operator  = "GreaterThan"
    threshold = 0
  }
}

# Single IP attacking
resource "azurerm_monitor_scheduled_query_rules_alert" "waf_attacker" {
  name                = "pulse-waf-single-attacker"
  location            = var.location
  resource_group_name = var.resource_group_name

  action {
    action_group = [var.alert_action_group_id]
  }

  data_source_id = var.log_analytics_workspace_id
  description    = "Single IP generating many WAF blocks"
  enabled        = true

  query = <<-QUERY
    AzureDiagnostics
    | where Category == "FrontDoorWebApplicationFirewallLog"
    | where TimeGenerated > ago(15m)
    | where action_s == "Block"
    | summarize blocks = count() by clientIp_s
    | where blocks > 50
  QUERY

  severity    = 2
  frequency   = 5
  time_window = 15

  trigger {
    operator  = "GreaterThan"
    threshold = 0
  }
}
```

---

## Terraform Implementation

### Complete WAF Module

Create `infra/modules/frontdoor/variables.tf`:

```hcl
variable "resource_group_name" {
  type        = string
  description = "Resource group name"
}

variable "location" {
  type        = string
  description = "Azure region"
}

variable "environment" {
  type        = string
  description = "Environment (dev, staging, prod)"
}

variable "custom_domain" {
  type        = string
  description = "Custom domain for the application"
}

variable "origin_host_name" {
  type        = string
  description = "Origin hostname (App Service)"
}

variable "origin_private_link_resource_id" {
  type        = string
  description = "Resource ID for Private Link to origin"
}

variable "waf_mode" {
  type        = string
  default     = "Prevention"
  description = "WAF mode: Detection or Prevention"
}

variable "allowed_countries" {
  type        = list(string)
  default     = []
  description = "Allowed country codes"
}

variable "blocked_countries" {
  type        = list(string)
  default     = []
  description = "Blocked country codes"
}

variable "enable_geo_whitelist" {
  type        = bool
  default     = false
  description = "Enable country whitelist mode"
}

variable "log_analytics_workspace_id" {
  type        = string
  description = "Log Analytics workspace ID"
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Resource tags"
}
```

### Main Module Usage

```hcl
# In main.tf or environments/prod/main.tf

module "frontdoor" {
  source = "../../modules/frontdoor"

  resource_group_name             = azurerm_resource_group.main.name
  location                        = var.location
  environment                     = var.environment
  custom_domain                   = var.custom_domain
  origin_host_name                = module.webapp.hostname
  origin_private_link_resource_id = module.webapp.id
  waf_mode                        = "Prevention"
  blocked_countries               = ["XX", "YY"]  # Add countries to block
  log_analytics_workspace_id      = module.monitoring.workspace_id

  tags = var.tags
}
```

---

## Testing and Validation

### WAF Testing Script

Create `scripts/test-waf.sh`:

```bash
#!/bin/bash
# PULSE WAF Testing Script

set -e

TARGET_URL="${1:-https://pulse.example.com}"
echo "Testing WAF at: $TARGET_URL"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

test_waf() {
    local name="$1"
    local url="$2"
    local expected="$3"  # "block" or "allow"
    local extra_args="${4:-}"

    echo -n "Testing: $name... "

    status=$(curl -s -o /dev/null -w "%{http_code}" $extra_args "$url")

    if [ "$expected" == "block" ]; then
        if [ "$status" == "403" ] || [ "$status" == "429" ]; then
            echo -e "${GREEN}PASS${NC} (blocked with $status)"
            return 0
        else
            echo -e "${RED}FAIL${NC} (expected block, got $status)"
            return 1
        fi
    else
        if [ "$status" == "200" ] || [ "$status" == "301" ] || [ "$status" == "302" ]; then
            echo -e "${GREEN}PASS${NC} (allowed with $status)"
            return 0
        else
            echo -e "${RED}FAIL${NC} (expected allow, got $status)"
            return 1
        fi
    fi
}

echo "=== WAF Rule Tests ==="
echo ""

# Legitimate requests (should be allowed)
echo "--- Legitimate Requests ---"
test_waf "Normal GET request" "$TARGET_URL" "allow"
test_waf "Normal page" "$TARGET_URL/about" "allow"

echo ""
echo "--- SQL Injection Tests ---"
test_waf "SQLI in query" "$TARGET_URL/?id=1' OR '1'='1" "block"
test_waf "SQLI UNION" "$TARGET_URL/?id=1 UNION SELECT * FROM users" "block"
test_waf "SQLI comment" "$TARGET_URL/?id=1--" "block"

echo ""
echo "--- XSS Tests ---"
test_waf "XSS script tag" "$TARGET_URL/?q=<script>alert(1)</script>" "block"
test_waf "XSS event handler" "$TARGET_URL/?q=<img onerror=alert(1)>" "block"
test_waf "XSS encoded" "$TARGET_URL/?q=%3Cscript%3E" "block"

echo ""
echo "--- Path Traversal Tests ---"
test_waf "Path traversal" "$TARGET_URL/../../etc/passwd" "block"
test_waf "Encoded traversal" "$TARGET_URL/%2e%2e%2fetc/passwd" "block"
test_waf "Null byte" "$TARGET_URL/file%00.txt" "block"

echo ""
echo "--- Bot Tests ---"
test_waf "Empty User-Agent" "$TARGET_URL" "block" "-H 'User-Agent:'"
test_waf "SQLMap User-Agent" "$TARGET_URL" "block" "-H 'User-Agent: sqlmap/1.0'"
test_waf "Curl User-Agent" "$TARGET_URL" "block" "-H 'User-Agent: curl/7.0'"

echo ""
echo "--- Admin Path Tests ---"
test_waf "WordPress admin" "$TARGET_URL/wp-admin" "block"
test_waf "PHPMyAdmin" "$TARGET_URL/phpmyadmin" "block"
test_waf ".env file" "$TARGET_URL/.env" "block"
test_waf ".git directory" "$TARGET_URL/.git/config" "block"

echo ""
echo "--- Rate Limiting Tests ---"
echo "Sending 50 rapid requests..."
blocked=0
for i in $(seq 1 50); do
    status=$(curl -s -o /dev/null -w "%{http_code}" "$TARGET_URL/api/health")
    if [ "$status" == "429" ]; then
        ((blocked++))
    fi
done
if [ $blocked -gt 0 ]; then
    echo -e "${GREEN}PASS${NC} (Rate limited after $((50-blocked)) requests)"
else
    echo -e "${YELLOW}WARN${NC} (No rate limiting observed in 50 requests)"
fi

echo ""
echo "=== WAF Testing Complete ==="
```

### Manual Testing Checklist

1. **SQL Injection**
   - `' OR '1'='1`
   - `1; DROP TABLE users--`
   - `UNION SELECT password FROM users`

2. **XSS**
   - `<script>alert('xss')</script>`
   - `<img src=x onerror=alert(1)>`
   - `javascript:alert(1)`

3. **Path Traversal**
   - `../../../etc/passwd`
   - `....//....//etc/passwd`
   - `%2e%2e%2f`

4. **Command Injection**
   - `; ls -la`
   - `| cat /etc/passwd`
   - `` `whoami` ``

5. **Bot Detection**
   - Empty User-Agent
   - Known bad User-Agents
   - Missing headers

---

## Migration Checklist

### Phase 1: Planning

- [ ] Review current traffic patterns
- [ ] Identify legitimate traffic sources
- [ ] Document required exclusions
- [ ] Plan rollback procedure

### Phase 2: Detection Mode

- [ ] Deploy WAF in Detection mode
- [ ] Configure all managed rules
- [ ] Add custom rules
- [ ] Enable logging
- [ ] Monitor for 1-2 weeks
- [ ] Identify false positives

### Phase 3: Tuning

- [ ] Add exclusions for false positives
- [ ] Adjust rate limits based on traffic
- [ ] Configure geo-filtering
- [ ] Update custom rules

### Phase 4: Prevention Mode

- [ ] Switch to Prevention mode
- [ ] Monitor closely for issues
- [ ] Document blocked requests
- [ ] Adjust as needed

### Phase 5: Monitoring

- [ ] Deploy alert rules
- [ ] Create dashboard
- [ ] Configure notifications
- [ ] Document incident response

---

## Best Practices Summary

1. **Start in Detection Mode**: Monitor before blocking
2. **Tune for False Positives**: Add exclusions carefully
3. **Layer with Other Controls**: WAF + rate limiting + validation
4. **Keep Rules Updated**: Enable managed rule updates
5. **Monitor Actively**: Review logs regularly
6. **Document Exceptions**: Justify all exclusions
7. **Test Regularly**: Validate WAF effectiveness

---

## Related Documents

- [securedbydesign.md](securedbydesign.md) - Overall security assessment
- [nsgconfig.md](nsgconfig.md) - Network Security Groups
- [ratelimiting.md](ratelimiting.md) - Rate limiting implementation
- [promptsecurity.md](promptsecurity.md) - Prompt injection protection
