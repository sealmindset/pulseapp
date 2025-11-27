Here’s a concrete Phase 4: Infra & Binary Path Hardening implementation spec for this repo, grounded in the current Terraform + Functions/App Service setup and not making any changes yet.

Phase 4 – Infra & Binary Path Hardening (Spec Only)
0. Current Inventory (what this spec is based on)
From the repo:

Terraform root: 
main.tf
, variables.tf, 
outputs.tf
, modules/app, modules/openai, plus diagnostics and private endpoints.
App module (
modules/app/main.tf
):
azurerm_service_plan.app_plan (Linux, sku_name = var.app_service_sku_name).
azurerm_linux_web_app.PULSE_ui_api:
site_config.linux_fx_version = var.web_app_linux_fx_version.
WEBSITE_RUN_FROM_PACKAGE = "1" in app_settings.
VNet integration via azurerm_app_service_virtual_network_swift_connection.PULSE_ui_api_vnet_integration.
azurerm_linux_function_app.scenario_orchestrator:
site_config.application_stack.python_version = "3.11".
FUNCTIONS_WORKER_RUNTIME = "python".
AzureWebJobsStorage wired to storage connection string.
VNet integration via azurerm_app_service_virtual_network_swift_connection.scenario_orchestrator_vnet_integration.
Root diagnostics (
main.tf
):
azurerm_monitor_diagnostic_setting.diag_openai with Audit, RequestResponse, AllMetrics.
azurerm_monitor_diagnostic_setting.diag_functionapp with FunctionAppLogs, AppServiceHTTPLogs, AllMetrics.
Private endpoints:
Root 
main.tf
 includes optional Web App private endpoint via enable_webapp_private_endpoint and private DNS privatelink.azurewebsites.net.
Other private endpoints (OpenAI, Storage) already handled in earlier phases.
No CI/CD workflow files are currently in this repo (no GitHub Actions / Azure DevOps pipelines found).

1. Objectives & Non‑Goals
Objectives
Pin runtimes & extensions for Linux Web App and Function App to eliminate “surprise” platform upgrades.
Constrain ingress/egress surfaces to only what PULSE needs (App, Function, Storage, OpenAI, monitoring).
Standardize deployment paths so that local, CI, and production use the same, well‑defined binaries.
Improve diagnosability of infra misconfig (clear logs/alerts when private endpoints, DNS, or runtime configs drift).
Non‑Goals for Phase 4
No business‑logic changes in orchestrator or UI.
No API contract changes (those are Phases 3 & 6).
No DB/schema migration changes.
2. Terraform Runtime & Provider Hardening
2.1 Providers & Terraform Version
Tasks
Add/confirm explicit required_version & required_providers in root 
main.tf
:
Pin Terraform to a compatible stable range (e.g. >= 1.5, < 1.9 – choose exact range after checking existing use).
Pin azurerm provider (e.g. ~> 4.x) instead of floating latest.
Document chosen versions in:
README.md (Infra section).
CHANGELOG.md
 under Phase 4 entry.
Acceptance Criteria
terraform init always selects the same provider versions on clean machines.
Infra changes only require planned version bumps, never silent provider upgrades.
2.2 App Service Plan & SKU
Tasks
Confirm var.app_service_sku_name (default in variables.tf) is an approved SKU (currently default "P1v3"):
If any future change is needed (e.g., Premium vs. Isolated), document the allowed set and when to use each.
For Phase 4, do not change SKU unless driven by explicit perf/capacity needs; just codify decision.
Acceptance Criteria
Documented rationale for chosen SKU family.
No ad‑hoc SKU changes directly in Azure Portal; changes flow through Terraform.
3. Web App Runtime & Binary Path Hardening
3.1 Pin linux_fx_version explicitly
Current: linux_fx_version = var.web_app_linux_fx_version on azurerm_linux_web_app.PULSE_ui_api.
Tasks
Decide and set a specific runtime string through web_app_linux_fx_version (e.g. PYTHON|3.11 or a specific Node/Next.js stack; whatever you’re actually using).
Document the mapping:
“Web App runtime = <value>; upgrades require intentional change to web_app_linux_fx_version.”
Ensure no Terraform or Portal config leaves linux_fx_version blank or ambiguous.
Acceptance Criteria
terraform plan shows a stable linux_fx_version.
Portal shows the runtime corresponding exactly to your chosen stack and version.
3.2 Lock build/deploy behavior for Web App
Current: WEBSITE_RUN_FROM_PACKAGE = "1" is set; no explicit SCM_DO_BUILD_DURING_DEPLOYMENT.
Tasks
Decide on the single source of truth for web binaries:
If build is done outside App Service (recommended):
Ensure the zipped package is always built by CI (when CI exists) and WEBSITE_RUN_FROM_PACKAGE=1 is the only deploy path.
Add spec that no Kudu/SCM build hooks are relied on.
Once CI/CD pipeline exists:
Pin Node/PNPM/Yarn versions (if relevant) in pipeline, not just on dev machines.
Acceptance Criteria
No dependency on “run from source” in production.
Production binaries are always from an immutable artifact produced by a known build process.
4. Function App Runtime & Extension Hardening
4.1 Pin Python worker/runtime
Current: python_version = "3.11" in azurerm_linux_function_app.scenario_orchestrator.site_config.application_stack.
Tasks
Treat "3.11" as intentionally pinned:
Document in README.md and aidocs/aiworkflow.md (or infra section) that the orchestrator runs on Python 3.11.
Define a lightweight policy for when/how runtime upgrades occur:
E.g., “Test in staging Function App; roll forward only after smoke & scenario tests pass.”
Acceptance Criteria
No silent drift in Python runtime on the function app.
Any runtime upgrade is explicitly captured in 
CHANGELOG.md
 with associated tests.
4.2 Functions extensions & host configuration
Tasks
Inspect 
orchestrator/host.json
 (or create if missing) and:
Pin extension bundle major/minor versions if using extension bundles.
Set logging levels explicitly for Function.{name}, Host, Microsoft.Azure.WebJobs to align with App Insights logs you enabled.
Ensure FUNCTIONS_WORKER_RUNTIME = "python" remains stable and is not overridden elsewhere.
Acceptance Criteria
host.json
 acts as the authority for function behavior and logging, not defaults.
App Insights shows consistent logs for orchestrator functions across environments.
4.3 Package & dependency hardening
Tasks
Confirm that orchestrator dependencies (e.g. azure-functions, Azure Storage, OpenAI SDK) are pinned in 
requirements.txt
:
Use ~=, == or a narrow range to avoid surprise breaking changes.
Establish a basic dependency update workflow:
“Update deps in a branch, run unit tests + scenario flows, update CHANGELOG and then deploy.”
Acceptance Criteria
Rebuilding the function app on a clean machine yields identical dependency versions.
Dependency upgrades are controlled events, not accidental.
5. Infra Surface / Network Hardening
5.1 Ingress surfaces
Tasks
Enumerate all HTTP ingress points:
Web App public endpoint (and its optional private endpoint in 
main.tf
).
Function App (currently VNet integration; evaluate if private endpoint is desired in future).
Any Storage static website/public endpoints (if enabled).
For each:
Decide if it must be internet‑reachable or should be private‑only.
Where private is desired:
Ensure private endpoint + DNS zone exists (similar to web app pattern).
Ensure all clients (UI, orchestrator, admin tools) resolve through private DNS only.
Acceptance Criteria
A short document listing each ingress with its intended exposure:
Public, Private via PE, or Not exposed.
Terraform accurately enforces that intent (e.g. web app private endpoint toggle used appropriately).
5.2 Egress / outbound paths
Tasks
List all outbound dependencies of orchestrator and web app:
Azure OpenAI, Storage, App Insights, Log Analytics, any future external APIs.
Ensure:
NSG / Firewall rules, if any, allow only required destinations/subnets.
Private endpoints are used where Azure supports them (OpenAI, Storage – already in progress).
Document acceptable outbound network patterns for PULSE (e.g. “No arbitrary internet egress from Function App”).
Acceptance Criteria
Outbound traffic patterns are documented and match NSG/PE design.
Any new external dependency must be explicitly added to this list and to network rules.
6. Tooling & Deployment Path Hardening
(Forward‑looking, since CI/CD is not yet present in this repo.)

Tasks
Define expected toolchain versions for:
terraform CLI.
az (Azure CLI) if used for deploys.
func (Azure Functions Core Tools) for local development.
When CI is introduced (GitHub Actions / Azure DevOps):
Use container images or explicit setup steps that pin these tool versions.
Ensure CI runs terraform fmt, terraform validate, and a minimal orchestrator smoke test.
Acceptance Criteria
Local dev and CI use the same effective tool versions for terraform and deployment.
No reliance on “whatever az CLI version is on the dev’s laptop”.
7. Observability & Verification for Phase 4
Tasks
For every hardening change, add or validate:
App Insights and Log Analytics signal for:
Runtime errors due to mis‑configured PE/DNS.
Function runtime version mismatches.
Logs that clearly indicate when:
Runtime version changes.
Terraform or provider versions are upgraded.
Run a minimal verification suite after Phase 4 changes:
terraform validate and terraform plan.
Orchestrator smoke test: create a simple training scenario and see that all steps complete successfully.
Confirm App Insights logs still show requests, traces, and dependencies for Function App and Web App.
Acceptance Criteria
No unexplained increase in 4xx/5xx rates from runtime changes.
Clear logging for any misconfig related to private endpoints or runtime/host settings.
8. Process & Documentation
Tasks
For each logical batch of Phase 4 changes:
Update 
CHANGELOG.md
 with:
Context: “Phase 4 – infra & binary path hardening”.
Specific resources affected.
Next steps or follow‑up actions.
Keep README.md infra section aligned with:
Terraform version and provider version ranges.
Web App runtime and Function App runtime.
Tie back to PULSE phases:
Explicitly mark this as Phase 4 in aidocs or another planning doc so future work can see the progression.
Acceptance Criteria
A new 
CHANGELOG.md
 section that clearly documents all Phase 4 infra/runtime decisions.
Future contributors can tell at a glance:
Which runtimes and CLI versions are expected.
What surfaces are public vs. private.
Summary / Next Step
This spec does not change code or infra yet; it defines exactly what Phase 4 should do to harden:
Terraform versions and providers.
Web App and Function App runtimes and binary paths.
Ingress/egress and private endpoint usage.
Toolchain consistency and observability.
If you’re happy with this spec, the next step would be to choose a small initial slice to implement (e.g., “pin provider versions + document runtimes + host.json hardening”), and we can then apply concrete Terraform and config changes in a follow‑up Phase 4 implementation pass.