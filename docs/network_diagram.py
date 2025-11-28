import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch

def draw_rounded_rect(ax, x, y, w, h, color, label=None, fontsize=9, fontweight='normal', fill_color='white', subtitle=None, subtitle_fontsize=8):
    # Draw the box
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.2,rounding_size=0.5",
                         linewidth=1.5, edgecolor=color, facecolor=fill_color, zorder=2)
    ax.add_patch(box)
    
    # Add label centered in the box
    if label:
        ax.text(x + w/2, y + h/2, label, ha='center', va='center', 
                fontsize=fontsize, color=color, fontweight=fontweight, zorder=3)
    
    if subtitle:
        ax.text(x + w/2, y + h/2 - (h*0.25), subtitle, ha='center', va='top',
                fontsize=subtitle_fontsize, color=color, zorder=3)
    
    return box

def draw_connection(ax, x1, y1, x2, y2, color):
    ax.plot([x1, x2], [y1, y2], color=color, linewidth=1, zorder=1)

def draw_elbow_connection(ax, x1, y1, x2, y2, color, elbow_x=None):
    if elbow_x is None:
        elbow_x = (x1 + x2) / 2
    ax.plot([x1, elbow_x, elbow_x, x2], [y1, y1, y2, y2], color=color, linewidth=1, zorder=1)

# Setup Figure
fig, ax = plt.subplots(figsize=(20, 14))
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis('off')

# Style Constants
AZURE_BLUE = '#0078D4'
LIGHT_FILL = '#F5FAFF'
WHITE_FILL = '#FFFFFF'

# ==========================================
# 1. REGION BOUNDARIES (Visual Grouping)
# ==========================================

# Region 1: RG & DNS
draw_rounded_rect(ax, 2, 5, 20, 90, AZURE_BLUE, fill_color=WHITE_FILL)
ax.text(12, 92, "Resource Group\nrg-PULSE-training-env", ha='center', va='bottom', fontsize=12, fontweight='bold', color=AZURE_BLUE)

# Region 2: VNet
draw_rounded_rect(ax, 24, 5, 30, 90, AZURE_BLUE, fill_color=WHITE_FILL)
ax.text(39, 92, "Virtual Network", ha='center', va='bottom', fontsize=12, fontweight='bold', color=AZURE_BLUE)

# Region 3: OpenAI
draw_rounded_rect(ax, 56, 5, 18, 90, AZURE_BLUE, fill_color=WHITE_FILL)
ax.text(65, 92, "Azure OpenAI", ha='center', va='bottom', fontsize=12, fontweight='bold', color=AZURE_BLUE)

# Region 4: Observability
draw_rounded_rect(ax, 76, 5, 22, 90, AZURE_BLUE, fill_color=WHITE_FILL)
ax.text(87, 92, "Observability & Storage", ha='center', va='bottom', fontsize=12, fontweight='bold', color=AZURE_BLUE)

# ==========================================
# 2. REGION 1 CONTENTS (DNS)
# ==========================================

# Container for DNS Zones
draw_rounded_rect(ax, 4, 40, 16, 40, AZURE_BLUE, label="", fill_color=LIGHT_FILL)
ax.text(12, 82, "Private DNS Zones &\nVNet Links", ha='center', va='center', fontsize=10, color=AZURE_BLUE, fontweight='bold')

dns_zones = [
    "privatelink.postgres.\ndatabase.azure.com",
    "privatelink.blob.\ncore.windows.net",
    "privatelink.openai.\nazure.com",
    "privatelink.azurewebsites.net"
]

y_pos = 72
for zone in dns_zones:
    draw_rounded_rect(ax, 5, y_pos, 14, 6, AZURE_BLUE, label=zone, fontsize=8, fill_color=WHITE_FILL)
    y_pos -= 8

# ==========================================
# 3. REGION 2 CONTENTS (VNET)
# ==========================================

# VNet Container
draw_rounded_rect(ax, 26, 7, 26, 86, AZURE_BLUE, label="", fill_color=LIGHT_FILL)
ax.text(39, 89, "vnet-PULSE-training-env\n(10.0.0.0/16)", ha='center', va='bottom', fontsize=10, color=AZURE_BLUE, fontweight='bold')

# Subnet 1: Analytics (Top)
draw_rounded_rect(ax, 28, 65, 22, 18, AZURE_BLUE, fill_color=WHITE_FILL)
ax.text(28.5, 81, "Analytics Subnet\nPULSE-analytics-sg-subnet (10.0.3.0/24)", ha='left', va='top', fontsize=8, color=AZURE_BLUE, fontweight='bold')

# DB
draw_rounded_rect(ax, 32, 68, 14, 8, AZURE_BLUE, label="PostgreSQL Flexible Server\npulse-PULSE-training-env-db", fontsize=8)
ax.text(39, 66, "Env: PULSE_ANALYTICS_DB_HOST", ha='center', va='top', fontsize=7, color=AZURE_BLUE, style='italic')

# Subnet 2: Private Endpoints (Middle)
draw_rounded_rect(ax, 28, 40, 22, 22, AZURE_BLUE, fill_color=WHITE_FILL)
ax.text(28.5, 60, "Private Endpoints Subnet\nPULSE-private-endpoints-subnet (10.0.2.0/24)", ha='left', va='top', fontsize=8, color=AZURE_BLUE, fontweight='bold')

# PEs
draw_rounded_rect(ax, 33, 53, 12, 4, AZURE_BLUE, label="PE: Web App (Opt)", fontsize=7)
draw_rounded_rect(ax, 33, 47, 12, 4, AZURE_BLUE, label="PE: Storage Blob", fontsize=7)
draw_rounded_rect(ax, 33, 41, 12, 4, AZURE_BLUE, label="PE: Azure OpenAI", fontsize=7)

# Subnet 3: App Subnet (Bottom)
draw_rounded_rect(ax, 28, 10, 22, 27, AZURE_BLUE, fill_color=WHITE_FILL)
ax.text(28.5, 35, "App Subnet\nPULSE-app-subnet (10.0.1.0/24)", ha='left', va='top', fontsize=8, color=AZURE_BLUE, fontweight='bold')

# App Service Plan
draw_rounded_rect(ax, 29, 28, 20, 4, AZURE_BLUE, label="App Service Plan: app-PULSE-training-env", fontsize=8, fill_color=LIGHT_FILL)

# Web App
draw_rounded_rect(ax, 29, 20, 9, 6, AZURE_BLUE, label="Web App\napp-PULSE-\ntraining-env", fontsize=7)

# Function App
draw_rounded_rect(ax, 39, 20, 9, 6, AZURE_BLUE, label="Function App\nfunc-PULSE-\ntraining-env", fontsize=7)

# Routes
routes = "/session/*, /audioOrChunk,\n/trainingReview, /blob, /admin"
ax.text(43.5, 18, routes, ha='center', va='top', fontsize=6, color=AZURE_BLUE)


# ==========================================
# 4. REGION 3 CONTENTS (OPENAI)
# ==========================================

# Cog Account
draw_rounded_rect(ax, 58, 70, 14, 8, AZURE_BLUE, label="Cognitive Account\ncog-PULSE-training-\nenv-openai", fontsize=8)

# Deployments
draw_rounded_rect(ax, 58, 60, 14, 5, AZURE_BLUE, label="Persona-CoreChat", fontsize=8)
draw_rounded_rect(ax, 58, 53, 14, 5, AZURE_BLUE, label="Persona-Visual-Asset", fontsize=8)
draw_rounded_rect(ax, 58, 46, 14, 5, AZURE_BLUE, label="Persona-Audio-Realtime", fontsize=8)

# Connect Deployments to Account visually (lines)
draw_connection(ax, 65, 65, 65, 70, AZURE_BLUE)
draw_connection(ax, 65, 58, 65, 60, AZURE_BLUE)
draw_connection(ax, 65, 51, 65, 53, AZURE_BLUE)

# ==========================================
# 5. REGION 4 CONTENTS (OBSERVABILITY)
# ==========================================

# App Insights
draw_rounded_rect(ax, 78, 80, 18, 6, AZURE_BLUE, label="App Insights\napps-PULSE-training-env", fontsize=8)

# Log Analytics
draw_rounded_rect(ax, 78, 68, 18, 8, AZURE_BLUE, label="Log Analytics Workspace\nlaw-PULSE-training-env", fontsize=8)

# Storage Account
draw_rounded_rect(ax, 78, 10, 18, 50, AZURE_BLUE, fill_color=LIGHT_FILL)
ax.text(87, 57, "Storage Account\n(Standard)", ha='center', va='bottom', fontsize=9, color=AZURE_BLUE, fontweight='bold')

# Containers
containers = [
    "diag_openai",
    "certification-materials",
    "trainer-change-logs",
    "prompts",
    "interaction-logs"
]
c_y = 48
for c in containers:
    draw_rounded_rect(ax, 80, c_y, 14, 5, AZURE_BLUE, label=f"Container:\n{c}", fontsize=7, fill_color=WHITE_FILL)
    c_y -= 7


# ==========================================
# 6. CONNECTIONS
# ==========================================

# 1. DNS to VNet
draw_connection(ax, 20, 60, 24, 60, AZURE_BLUE)
ax.arrow(24, 60, 1, 0, head_width=1, head_length=1, fc=AZURE_BLUE, ec=AZURE_BLUE, zorder=5)

# 2. Web/Func App to DB
# From App Subnet (approx y=23) to Analytics Subnet (approx y=68)
draw_elbow_connection(ax, 39, 26, 39, 68, AZURE_BLUE, elbow_x=53) # Route via right side of vnet to avoid crossing PEs messily
# Actually let's go straight up through Vnet logic
ax.plot([36, 36], [26, 68], color=AZURE_BLUE, linestyle='--', linewidth=0.8, alpha=0.6) # Internal Vnet flow

# 3. Web/Func to App Insights
draw_elbow_connection(ax, 48, 23, 78, 83, AZURE_BLUE, elbow_x=54)
ax.arrow(78, 83, 1, 0, head_width=1, head_length=1, fc=AZURE_BLUE, ec=AZURE_BLUE, zorder=5)

# 4. App Insights to Log Analytics
draw_connection(ax, 87, 80, 87, 76, AZURE_BLUE)
ax.arrow(87, 76, 0, -1, head_width=1, head_length=1, fc=AZURE_BLUE, ec=AZURE_BLUE, zorder=5)

# 5. PE OpenAI to OpenAI Account
draw_connection(ax, 45, 43, 58, 74, AZURE_BLUE) # Diagonal approximation for clarity
# Better: Elbow
draw_elbow_connection(ax, 45, 43, 58, 74, AZURE_BLUE, elbow_x=52)
ax.arrow(58, 74, 1, 0, head_width=1, head_length=1, fc=AZURE_BLUE, ec=AZURE_BLUE, zorder=5)

# 6. PE Storage to Storage Account
draw_connection(ax, 45, 49, 78, 35, AZURE_BLUE)
ax.arrow(78, 35, 1, 0, head_width=1, head_length=1, fc=AZURE_BLUE, ec=AZURE_BLUE, zorder=5)

# 7. Web/Func to Storage (Public/Service endpoint flow or just logical association)
draw_elbow_connection(ax, 48, 20, 78, 30, AZURE_BLUE, elbow_x=54)
ax.arrow(78, 30, 1, 0, head_width=1, head_length=1, fc=AZURE_BLUE, ec=AZURE_BLUE, zorder=5)

# Save
plt.tight_layout()
plt.savefig('pulse_architecture.png', dpi=300, bbox_inches='tight')
plt.close()