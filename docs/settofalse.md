# PULSE Prod PrivateLink Internal Access Plan
*(Target: internal-only access via VPN/core corporate network to `https://app-pulse-training-ui-prod.azurewebsites.net` while keeping Private Link and safely setting public access to `false`.)*

---

## Goal
Make `https://app-pulse-training-ui-prod.azurewebsites.net` reachable **only** from:
- VPN users, and
- core company network (HQ/corp) 
- and **not** reachable from the public internet, while still allowing the app to use **Private Link** to Azure OpenAI/Storage/Postgres.

---

## Phase 0 — Confirm the access pattern
**Recommended pattern:** *App Service Inbound Private Endpoint + Private DNS*
- Users on VPN/corp network hit the same hostname
- DNS resolves to a **private IP** internally
- Public internet cannot reach it once Public Network Access is disabled

---

## Phase 1 — Terraform tasks (add/confirm in IaC)

### 1.1 Web App inbound access: disable public, require Private Endpoint
- Add/confirm a variable and implementation such as:
  - `webapp_public_network_access_enabled = false`
- Ensure your App Service resource actually applies the setting (or equivalent Azure property).

**Also lock down SCM/Kudu** (often forgotten):
- Disable/limit public access to: `https://<app>.scm.azurewebsites.net`
- Prefer: public access disabled
- Otherwise: access restrictions limited to corp/VPN

### 1.2 Ensure Web App Private Endpoint + Private DNS zone exist
You already have:
- `enable_webapp_private_endpoint = true`

Verify Terraform creates all of the following:
- **Private Endpoint** targeting the App Service (`sites`)
- **Private DNS Zone:** `privatelink.azurewebsites.net`
- **DNS zone link** to the VNet
- **A record** for `app-pulse-training-ui-prod` in that zone pointing to the PE private IP

### 1.3 Azure OpenAI PrivateLink + controlled public access flip
Current tfvars:
- `openai_public_network_access_enabled = true` *(temporary for testing)*

Plan:
- Keep `true` until private DNS/routing validation passes
- Then set to `false` and confirm AOAI has:
  - Private Endpoint
  - Private DNS zone: `privatelink.openai.azure.com` (linked to VNet)

---

## Phase 2 — Azure networking tasks (make PE subnets reachable from corp/VPN)

### 2.1 Confirm where corp/VPN lands in Azure
Typical layout:
- Corp/VPN → ExpressRoute/VPN → **Hub VNet** → peering to **Spoke VNet** (Private Endpoints)

### 2.2 Ensure routing to Private Endpoint subnets
Ensure corp networks can route to the subnet(s) that contain Private Endpoints for:
- Web App inbound Private Endpoint
- Azure OpenAI Private Endpoint
- Storage Private Endpoint
- Postgres Private Endpoint (if used)

If you use forced tunneling / NVAs / UDRs:
- Confirm PE traffic is not blackholed or hairpinned incorrectly.

---

## Phase 3 — Corporate DNS tasks (most common root cause)

### 3.1 Required outcome
Inside corp/VPN:
- `app-pulse-training-ui-prod.azurewebsites.net` must resolve to the **Private Endpoint private IP**

### 3.2 Choose a DNS forwarding pattern

**Option A (recommended): Azure DNS Private Resolver**
- Deploy **Azure DNS Private Resolver** in hub VNet
- Create **inbound endpoints**
- Configure forwarding rules for Private Link zones

**Option B: DNS Forwarder VMs**
- Deploy Windows DNS/BIND forwarders in hub VNet
- Corporate DNS uses conditional forwarding to those forwarders

### 3.3 Conditional forwarding zones (minimum + likely set)
Minimum required for the web app:
- `privatelink.azurewebsites.net`

Likely required for your stack:
- `privatelink.openai.azure.com`
- `privatelink.blob.core.windows.net` *(and queue/file/table if used)*
- `privatelink.postgres.database.azure.com` *(Postgres flexible server)*
- Any other `privatelink.*` zones you’ve deployed Private Endpoints for

### 3.4 VPN client DNS
- Ensure VPN clients use corporate DNS (or can reach your resolver/forwarder)
- If VPN clients resolve via public DNS, they will fail once public access is disabled

---

## Phase 4 — Palo Alto / firewall policy tasks
Allow traffic from:
- corp/HQ subnets
- VPN client subnets

To:
- **Private Endpoint IP(s)** on **TCP 443**

Notes:
- If you do TLS inspection, test carefully—SSL interception can break some Private Link flows.

---

## Phase 5 — Validation tasks (before flipping public off)

### 5.1 DNS check (corp + VPN)
Run:
- `nslookup app-pulse-training-ui-prod.azurewebsites.net`

Success:
- Returns an RFC1918 **private IP** (the Web App Private Endpoint IP)

If it returns a public IP:
- Do **not** flip public off yet—DNS is not correct.

### 5.2 Connectivity check
Run:
- `curl -I https://app-pulse-training-ui-prod.azurewebsites.net`

Success:
- 200/302 (or expected auth redirect) with a valid TLS handshake

### 5.3 Public internet test
From a non-corp network (e.g., phone hotspot):
- It should work *until* you flip public off
- After flip: it should fail (timeout/403 depending on Azure behavior)

---

## Phase 6 — Cutover sequence (minimize downtime)

1. Stand up Web App **Private Endpoint + Private DNS**
2. Implement corp DNS forwarding (`privatelink.azurewebsites.net`)
3. Validate from **corp** and **VPN** (DNS + curl)
4. Flip Web App public access off
5. Validate corp/VPN still works; validate public internet fails
6. Flip `openai_public_network_access_enabled = false`
7. Validate app-to-openai still works (from within Azure), and (if needed) corp/VPN direct access tests

---

## Immediate Remediation — Secret Rotation Checklist
- Rotate **Entra app secret** (`azure_ad_client_secret`)
- Rotate **NextAuth secret** (`nextauth_secret`)
- Move secrets into:
  - CI secret store / Key Vault / secure tfvars mechanism
- Confirm tfvars is excluded from git and not printed in CI logs

---
