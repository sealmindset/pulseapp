You are an expert technical diagram artist.

Your task:

Draw a new, clean Azure architecture diagram as a single PNG image, combining the topology from one diagram with the visual style from another.

You must follow these instructions *exactly*.

==================================================
1. INPUT DIAGRAMS
==================================================

You have two visual references:

1) “PULSE-network-diagram.jpeg”
   - This is the **source of truth for topology and labels**.  
   - It shows:
     - The virtual network, subnets, private endpoints, DNS zones.
     - Azure OpenAI, App Service, Function, PostgreSQL, Storage, Insights, Log Analytics.
     - Connection arrows and route annotations.
   - Treat every box, resource name, and relationship in this diagram as *semantically correct*.

2) “PULSEAZArch.pdf”
   - This is the **source of truth for visual style and layout feel**.  
   - Use this for:
     - Overall grid and alignment.
     - Rounded rectangles and consistent capsule shapes.
     - Clean line weights and spacing.
     - Minimalistic, blueprint-like styling.
   - You are *not* copying its exact content, but you are copying its **visual language**.

Your mission:

- Use **PULSE-network-diagram.jpeg** for *what* to draw and *what connects to what*.
- Use **PULSEAZArch.pdf** for *how it should look* (style, cleanliness, spacing, and readability).

Output: a **single PNG image** in landscape orientation, approximately 3:2 aspect ratio, ~3000 × 2000 px, with a white background and Azure-blue lines and text.

==================================================
2. SCOPE OF THE NEW DIAGRAM
==================================================

The new diagram represents the **PULSE H2 – Azure Network Architecture** for an interactive AI trainer application.

You must include at least these logical regions and components, plus their relationships:

A) Resource Group & DNS
   - Resource Group: `rg-PULSE-training-env`
   - Private DNS Zones & VNet Links:
     - `privatelink.postgres.database.azure.com`
     - `privatelink.blob.core.windows.net`
     - `privatelink.openai.azure.com`
     - `privatelink.azurewebsites.net`

B) Virtual Network & Subnets
   - VNet: `vnet-PULSE-training-env (10.0.0.0/16)`
   - Subnets:
     1. Analytics Subnet: `PULSE-analytics-sg-subnet (10.0.3.0/24)`
        - Hosts:
          - Azure Database for PostgreSQL Flexible Server  
            Name: `pulse-PULSE-training-env-db`
        - Environment variable label: `PULSE_ANALYTICS_DB_HOST`
     2. Private Endpoints Subnet: `PULSE-private-endpoints-subnet (10.0.2.0/24)`
        - Private Endpoint: Web App (optional)
        - Private Endpoint: Storage Blob
        - Private Endpoint: Azure OpenAI
     3. App Subnet: `PULSE-app-subnet (10.0.1.0/24)`
        - App Service Plan: `app-PULSE-training-env`
        - Web App: `app-PULSE-training-env`
        - Function App: `func-PULSE-training-env`
          - Key routes (show as small text below or near Function App):
            - `/session/*`
            - `/audioOrChunk`
            - `/trainingReview`
            - `/blob`
            - `/admin`

C) Azure OpenAI
   - Cognitive Account: `cog-PULSE-training-env-openai`
   - Deployments:
     - `Persona-CoreChat`
     - `Persona-Visual-Asset`
     - `Persona-Audio-Realtime`

D) Observability & Storage
   - Application Insights: `apps-PULSE-training-env`
   - Log Analytics Workspace: `law-PULSE-training-env`
   - Storage Account (generic name; do not invent a specific one):
     - Container: `diag_openai`
     - Container: `certification-materials`
     - Container: `trainer-change-logs`
     - Container: `prompts`
     - Container: `interaction-logs`

You must also show the key high-level relationships:

- Web App and Function App connect to:
  - Azure Database for PostgreSQL (via `PULSE_ANALYTICS_DB_HOST`).
  - Azure OpenAI (through the VNet and private endpoint).
  - Storage Account (for blobs such as prompts, certification materials, and interaction logs).
  - Application Insights (for telemetry).
- Application Insights sends data to Log Analytics Workspace.
- DNS Private Zones integrate with the VNet and private endpoints.

If any connection or relationship exists in PULSE-network-diagram.jpeg, you must represent it *somewhere* in the new diagram, but you are allowed to simplify or route lines in a cleaner way as long as the semantics are preserved.

==================================================
3. VISUAL STYLE REQUIREMENTS
==================================================

You must emulate the visual style of PULSEAZArch.pdf, even though you are not directly copying its content.

Follow these style rules:

1. Overall Composition
   - Orientation: **Landscape**.
   - Aspect ratio: about **3:2** (e.g., 3000 × 2000 px).
   - Background: **pure white**.
   - Color scheme: primarily **Azure blue** (#0078D4 or very similar) for:
     - Box outlines
     - Text
     - Connectors/arrows
   - No dark background, no gradients, no drop-shadows.

2. Regions & Grouping
   - Divide the diagram into **four vertical regions**, left-to-right:
     1. Resource Group & Private DNS Zones / VNet Links  
     2. Virtual Network & Subnets (App, Private Endpoints, Analytics)  
     3. Azure OpenAI  
     4. Observability & Storage (App Insights, Log Analytics, Storage Account)
   - Each region must be enclosed in a **rounded rectangle** with a thin Azure-blue outline.
   - Place the region titles at the top inside each region, in bold Azure-blue text.

3. Boxes and Shapes
   - Use **rounded rectangles** for:
     - Subnets
     - Resources (Web App, Function App, DB, Cognitive Account, etc.)
     - Storage containers (may be smaller)
   - Maintain consistent corner radius and stroke thickness across the diagram.
   - Use light interior fill (either white or very subtle tint) and a clear blue border.
   - Do **not** use 3D effects, shadows, or multi-color gradients.

4. Icons
   - You may suggest the resource type (App, DB, Storage, OpenAI, etc.) using:
     - Simple, flat glyphs, or
     - Just text labels if icons would clutter the diagram.
   - Icons are optional. Clarity and label readability is more important than fancy visuals.

5. Text
   - Use a clean, sans-serif font (e.g., Segoe UI–style).
   - Region titles slightly larger and bold.
   - Resource and subnet labels medium-sized.
   - Route details (like `/session/*`) in smaller text near the Function App.
   - All text should be Azure-blue.
   - Do **not** let text overlap borders, connectors, or other boxes.

6. Connectors & Arrows
   - Connectors should be **simple, clean lines**, primarily horizontal/vertical with minimal crossings.
   - Use arrowheads where directionality matters.
   - Avoid clutter: route connectors so they don’t obscure labels or stack directly on top of each other.
   - If necessary, merge related flows into a single connector with a clear fan-out.

==================================================
4. LAYOUT GUIDANCE (VERY IMPORTANT)
==================================================

You must prioritize **readability** and **clean composition** above drawing every tiny arrow from the original network diagram.

Use this layout strategy:

Leftmost region:
- Title: “Resource Group rg-PULSE-training-env”
- Inside, place:
  - A container/group labeled “Private DNS Zones & VNet Links”.
  - Inside that, list the four DNS zones as vertically stacked rounded rectangles, each with its FQDN label.
- Show a simple “contains” relationship from the resource group to this DNS group.
- Show a clean connection from this region to the Virtual Network region (to indicate those DNS zones are used with that VNet).

Second region (Virtual Network):
- Title: “Virtual Network”
- Inside:
  - A bounded box for `vnet-PULSE-training-env (10.0.0.0/16)`.
  - Within that VNet box, stack the three subnets vertically:
    1. Analytics Subnet at top.
    2. Private Endpoints Subnet in the middle.
    3. App Subnet at the bottom.
- Each subnet is its own rounded rectangle with:
  - Subnet name
  - Address range in parentheses.
- Place their contents:
  - Analytics Subnet: DB icon/box + name + DB host label.
  - Private Endpoints Subnet: three small boxes stacked: Web App PE, Storage Blob PE, Azure OpenAI PE.
  - App Subnet: App Service Plan, Web App, Function App (laid out horizontally or vertically, but clearly grouped together).

Third region (Azure OpenAI):
- Title: “Azure OpenAI”
- Place the Cognitive Account at the top or center, with its name.
- Below or beside it, list its three deployments as separate boxes:
  - Persona-CoreChat
  - Persona-Visual-Asset
  - Persona-Audio-Realtime
- Show the connectivity:
  - From the Private Endpoint: Azure OpenAI (in the Private Endpoints subnet) to the Cognitive Account.
  - From the Web App and Function App to the Cognitive Account (optionally via a shared connector if that is cleaner).

Fourth region (Observability & Storage):
- Title: “Observability & Storage”
- Top: Application Insights box (`apps-PULSE-training-env`).
- Under that: Log Analytics Workspace box (`law-PULSE-training-env`).
- Below that: Storage Account box with nested container boxes listed vertically:
  - diag_openai
  - certification-materials
  - trainer-change-logs
  - prompts
  - interaction-logs
- Show the flows:
  - From Web App and Function App to Application Insights.
  - From Application Insights to Log Analytics Workspace.
  - From Web App and Function App to the Storage Account.
  - From the Private Endpoint: Storage Blob to the Storage Account.

==================================================
5. CONTENT FIDELITY RULES
==================================================

You must:

- Preserve all core names exactly as given (case-sensitive, with hyphens):
  - `app-PULSE-training-env`
  - `func-PULSE-training-env`
  - `pulse-PULSE-training-env-db`
  - `cog-PULSE-training-env-openai`
  - `apps-PULSE-training-env`
  - `law-PULSE-training-env`
  - All subnet names and address ranges.
- Reflect all major connections from the PULSE-network-diagram.jpeg, but you may:
  - Combine multiple parallel arrows into a single, labeled connector if that keeps the diagram cleaner.
  - Omit low-level, internal arrows that do not add architectural clarity (e.g., repetitive directional arrows inside the same subnet) as long as the high-level meaning is preserved.
- Keep Environment variables or route labels as small descriptive text:
  - `PULSE_ANALYTICS_DB_HOST` near the DB or near Web/Function App connectors to the DB.
  - Function App routes listed near the Function App.

You must NOT:

- Invent new resource names.
- Change any of the given names.
- Add services that are not implied or shown in the source diagrams.
- Rearrange regions in a different left-to-right order.

==================================================
6. OUTPUT FORMAT
==================================================

Your final answer must be:

- A **single PNG image**, landscape, ~3:2 aspect ratio (around 3000 × 2000 px).
- Clean, minimal “Azure architecture blueprint”