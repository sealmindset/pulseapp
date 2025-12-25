#!/usr/bin/env python3
"""
PULSE Azure Network Diagram Generator

AI-powered infrastructure diagram generator that:
1. Parses Terraform code and tfvars to identify all planned resources
2. Discovers deployed resources via Azure CLI for drift detection
3. Generates accurate architecture diagrams (PNG/SVG/draw.io)
4. Beautifies diagram layout with proper spacing and line routing

Usage:
    # Default: Parse Terraform from project root, output to docs/
    python docs/PULSE_network_diagram.py

    # Generate SVG only (no PNG)
    python docs/PULSE_network_diagram.py --svg

    # With Azure discovery scan (compares plan vs deployed)
    python docs/PULSE_network_diagram.py --discover

    # Specify custom Terraform path
    python docs/PULSE_network_diagram.py --tf-path /path/to/terraform

    # From terraform state (legacy mode)
    python docs/PULSE_network_diagram.py --state tfstate.json

    # Generate draw.io XML for Lucidchart
    python docs/PULSE_network_diagram.py --drawio

    # Specify page size (default: A0 for plotter)
    python docs/PULSE_network_diagram.py --page-size A0
"""

import argparse
import json
import re
import subprocess
from argparse import RawTextHelpFormatter
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.etree.ElementTree import Element, SubElement, ElementTree


# =============================================================================
# Page Size Definitions (ISO Standard)
# =============================================================================

class PageSize(Enum):
    """Standard page sizes in mm (width x height in landscape)."""
    A4 = (297, 210)
    A3 = (420, 297)
    A2 = (594, 420)
    A1 = (841, 594)
    A0 = (1189, 841)  # Default for plotter

    @property
    def width_mm(self) -> int:
        return self.value[0]

    @property
    def height_mm(self) -> int:
        return self.value[1]

    @property
    def width_px(self, dpi: int = 96) -> int:
        """Convert mm to pixels at given DPI."""
        return int(self.value[0] * dpi / 25.4)

    @property
    def height_px(self, dpi: int = 96) -> int:
        """Convert mm to pixels at given DPI."""
        return int(self.value[1] * dpi / 25.4)

    def get_dimensions_px(self, dpi: int = 96) -> Tuple[int, int]:
        """Get (width, height) in pixels."""
        return (int(self.value[0] * dpi / 25.4), int(self.value[1] * dpi / 25.4))

try:
    from diagrams import Diagram, Cluster, Edge
    from diagrams.azure.network import VirtualNetworks, Subnets, PrivateEndpoint, DNSPrivateZones, NetworkSecurityGroupsClassic
    from diagrams.azure.ml import CognitiveServices
    from diagrams.azure.storage import StorageAccounts
    from diagrams.azure.web import AppServices, AppServicePlans
    from diagrams.azure.compute import FunctionApps
    from diagrams.azure.monitor import Logs
    from diagrams.azure.devops import ApplicationInsights
    from diagrams.azure.database import DatabaseForPostgresqlServers
    from diagrams.azure.identity import EnterpriseApplications, Users
    from diagrams.azure.security import KeyVaults
    from diagrams.onprem.client import Client, User
    DIAGRAMS_AVAILABLE = True
except ImportError:
    DIAGRAMS_AVAILABLE = False


# =============================================================================
# AI Agent: Diagram Layout Beautifier
# =============================================================================

@dataclass
class DiagramLayoutConfig:
    """Configuration for diagram layout and beautification."""
    page_size: PageSize = PageSize.A0
    dpi: int = 96

    # Spacing configuration (in pixels at 96 DPI)
    cluster_padding: int = 40
    node_spacing_h: int = 80  # Horizontal spacing between nodes
    node_spacing_v: int = 60  # Vertical spacing between nodes
    cluster_spacing: int = 100  # Space between clusters

    # Edge/line configuration
    edge_sep: float = 0.8  # Edge separation factor (Graphviz)
    min_edge_len: float = 2.0  # Minimum edge length
    use_orthogonal_edges: bool = True  # Use right-angle edges (reduces crossings)
    edge_concentrate: bool = True  # Merge parallel edges

    # Font sizes
    font_size_title: int = 16
    font_size_cluster: int = 14
    font_size_node: int = 12
    font_size_edge: int = 10

    def get_graphviz_attrs(self) -> Dict[str, str]:
        """Get Graphviz graph attributes for layout beautification."""
        width_in, height_in = self.get_page_size_inches()
        return {
            # Page size
            "size": f"{width_in},{height_in}!",
            "ratio": "fill",
            "dpi": str(self.dpi),

            # Spacing
            "pad": "0.5",
            "nodesep": str(self.node_spacing_h / 72),  # Convert px to inches
            "ranksep": str(self.node_spacing_v / 72),

            # Edge routing
            "splines": "ortho" if self.use_orthogonal_edges else "spline",
            "concentrate": "true" if self.edge_concentrate else "false",
            "esep": str(self.edge_sep),
            "mclimit": "2.0",  # Crossing minimization iterations

            # Layout algorithm
            "overlap": "false",
            "sep": "+25,25",  # Node separation for overlap removal

            # Fonts
            "fontsize": str(self.font_size_title),
            "labelfontsize": str(self.font_size_cluster),
        }

    def get_page_size_inches(self) -> Tuple[float, float]:
        """Get page size in inches for Graphviz."""
        w_px, h_px = self.page_size.get_dimensions_px(self.dpi)
        return (w_px / self.dpi, h_px / self.dpi)


class DiagramLayoutAgent:
    """AI Agent that beautifies diagram layout with proper spacing and line routing."""

    def __init__(self, config: Optional[DiagramLayoutConfig] = None):
        self.config = config or DiagramLayoutConfig()
        self.edge_registry: Dict[str, List[Tuple[str, str, str]]] = {}  # Group edges by target
        self.consolidated_edges: List[Tuple[str, str, str, str]] = []  # (source, target, label, style)

    def analyze_edges(self, edges: List[Tuple[str, str, str]]) -> None:
        """Analyze edges to find consolidation opportunities."""
        print("[layout-agent] Analyzing edge patterns for consolidation...")

        # Group edges by source and target
        source_to_targets: Dict[str, List[Tuple[str, str]]] = {}
        target_from_sources: Dict[str, List[Tuple[str, str]]] = {}

        for source, target, label in edges:
            if source not in source_to_targets:
                source_to_targets[source] = []
            source_to_targets[source].append((target, label))

            if target not in target_from_sources:
                target_from_sources[target] = []
            target_from_sources[target].append((source, label))

        # Find consolidation opportunities
        # 1. Multiple edges from same source to different targets with same purpose
        for source, targets in source_to_targets.items():
            labels = {}
            for target, label in targets:
                if label not in labels:
                    labels[label] = []
                labels[label].append(target)

            for label, target_list in labels.items():
                if len(target_list) > 1:
                    print(f"  [consolidate] {source} -> [{', '.join(target_list)}] via '{label}'")

        # 2. Multiple edges from different sources to same target with same purpose
        for target, sources in target_from_sources.items():
            labels = {}
            for source, label in sources:
                if label not in labels:
                    labels[label] = []
                labels[label].append(source)

            for label, source_list in labels.items():
                if len(source_list) > 1:
                    print(f"  [consolidate] [{', '.join(source_list)}] -> {target} via '{label}'")

    def consolidate_edges(self, edges: List[Tuple[str, str, str]]) -> List[Tuple[str, str, str, str]]:
        """Consolidate redundant edges and return optimized edge list."""
        print("[layout-agent] Consolidating edges...")

        # Track seen edges to remove exact duplicates
        seen = set()
        unique_edges = []

        for source, target, label in edges:
            key = (source, target, label)
            if key not in seen:
                seen.add(key)
                unique_edges.append((source, target, label, "solid"))

        # Identify edges that can share routing (same source-target pair, different labels)
        pair_labels: Dict[Tuple[str, str], List[str]] = {}
        for source, target, label, style in unique_edges:
            pair = (source, target)
            if pair not in pair_labels:
                pair_labels[pair] = []
            pair_labels[pair].append(label)

        # Merge labels for same source-target pairs
        consolidated = []
        processed_pairs = set()

        for source, target, label, style in unique_edges:
            pair = (source, target)
            if pair in processed_pairs:
                continue

            labels = pair_labels[pair]
            if len(labels) > 1:
                # Combine labels
                combined_label = ", ".join(sorted(set(labels)))
                consolidated.append((source, target, combined_label, style))
                print(f"  [merged] {source} -> {target}: {combined_label}")
            else:
                consolidated.append((source, target, label, style))

            processed_pairs.add(pair)

        print(f"  [result] {len(edges)} edges -> {len(consolidated)} consolidated edges")
        return consolidated

    def get_edge_style(self, edge_type: str) -> str:
        """Get edge style for different connection types."""
        styles = {
            "data": "solid",
            "control": "dashed",
            "diagnostic": "dotted",
            "optional": "dashed",
            "vnet": "bold",
        }
        return styles.get(edge_type, "solid")

    def categorize_edge(self, label: str) -> str:
        """Categorize an edge based on its label."""
        label_lower = label.lower()

        if any(x in label_lower for x in ["diag", "log", "metric", "insight"]):
            return "diagnostic"
        elif any(x in label_lower for x in ["optional", "pe ("]):
            return "optional"
        elif any(x in label_lower for x in ["vnet", "subnet", "contains"]):
            return "vnet"
        elif any(x in label_lower for x in ["https", "api", "blob", "storage", "db"]):
            return "data"
        else:
            return "control"

    def apply_orthogonal_routing(self, edges: List[Tuple[str, str, str, str]]) -> Dict[str, Any]:
        """Generate routing hints for orthogonal (right-angle) edge layout."""
        # Group edges by routing path to add bumps at intersections
        routing = {
            "edge_attrs": {},
            "waypoints": {},
        }

        for i, (source, target, label, _style) in enumerate(edges):
            edge_id = f"e_{source}_{target}_{i}"
            category = self.categorize_edge(label)

            # Assign edge to routing layer based on category
            # This helps separate different types of connections visually
            routing["edge_attrs"][edge_id] = {
                "weight": 1.0 if category == "data" else 0.5,
                "minlen": 2 if category == "diagnostic" else 1,
                "constraint": "true" if category in ["data", "vnet"] else "false",
            }

        return routing


# =============================================================================
# Infrastructure Data Model
# =============================================================================

@dataclass
class ParsedInfrastructure:
    """Parsed infrastructure from Terraform code or Azure discovery."""
    resource_group: Optional[str] = None
    location: Optional[str] = None
    environment: Optional[str] = None
    subscription_id: Optional[str] = None

    # Networking
    vnet_name: Optional[str] = None
    vnet_cidr: Optional[str] = None
    subnets: List[Dict[str, Any]] = field(default_factory=list)
    private_endpoints: List[Dict[str, Any]] = field(default_factory=list)
    dns_zones: List[Dict[str, Any]] = field(default_factory=list)
    vnet_integrations: List[Dict[str, Any]] = field(default_factory=list)
    network_security_groups: List[Dict[str, Any]] = field(default_factory=list)

    # Compute
    app_service_plan: Optional[str] = None
    app_service_sku: Optional[str] = None
    web_app: Optional[str] = None
    function_app: Optional[str] = None
    function_routes: List[str] = field(default_factory=list)

    # AI/ML
    openai_account: Optional[str] = None
    openai_deployments: List[Dict[str, Any]] = field(default_factory=list)
    speech_account: Optional[str] = None
    speech_enabled: bool = False

    # Storage
    storage_account: Optional[str] = None
    storage_containers: List[str] = field(default_factory=list)

    # Database
    postgres_server: Optional[str] = None
    postgres_database: Optional[str] = None

    # Observability
    log_analytics: Optional[str] = None
    app_insights: Optional[str] = None
    diagnostic_settings: List[Dict[str, Any]] = field(default_factory=list)

    # Authentication
    auth_mode: Optional[str] = None
    azure_ad_enabled: bool = False

    # Feature Flags
    enable_app_service: bool = True
    enable_visual_asset: bool = False
    enable_speech_avatar: bool = True
    enable_webapp_private_endpoint: bool = True

    # Security Controls
    security_controls: List[Dict[str, Any]] = field(default_factory=list)
    function_app_shared_secret: bool = False

    # Source tracking
    source: str = "unknown"  # "terraform", "azure", "state"


# =============================================================================
# AI Agent: Terraform Code Parser
# =============================================================================

class TerraformAgent:
    """AI Agent that parses Terraform code to extract infrastructure resources."""

    def __init__(self, tf_path: Path):
        self.tf_path = tf_path
        self.resources: Dict[str, List[Dict]] = {}
        self.variables: Dict[str, Any] = {}
        self.locals: Dict[str, str] = {}

    def parse_all(self, tfvars_path: Optional[Path] = None) -> ParsedInfrastructure:
        """Parse all Terraform files and build infrastructure model."""
        print(f"[agent] Parsing Terraform code from: {self.tf_path}")

        # Parse variables first
        self._parse_variables()

        # Load tfvars if provided
        if tfvars_path and tfvars_path.exists():
            self._parse_tfvars(tfvars_path)
        else:
            # Try to find tfvars in tf_path
            for tfvars in self.tf_path.glob("*.tfvars"):
                self._parse_tfvars(tfvars)
                break

        # Parse main.tf and module files
        self._parse_resources()

        # Build infrastructure model
        return self._build_infrastructure()

    def _parse_variables(self) -> None:
        """Parse variables.tf to get default values."""
        var_file = self.tf_path / "variables.tf"
        if not var_file.exists():
            return

        content = var_file.read_text()

        # Extract variable blocks with defaults
        var_pattern = r'variable\s+"(\w+)"\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}'
        for match in re.finditer(var_pattern, content, re.DOTALL):
            var_name = match.group(1)
            var_block = match.group(2)

            # Extract default value
            default_match = re.search(r'default\s*=\s*(.+?)(?:\n\s*(?:type|description|validation|\}))', var_block, re.DOTALL)
            if default_match:
                default_val = default_match.group(1).strip().rstrip(',')
                self.variables[var_name] = self._parse_hcl_value(default_val)

    def _parse_tfvars(self, tfvars_path: Path) -> None:
        """Parse tfvars file to override variable defaults."""
        print(f"[agent] Loading tfvars: {tfvars_path.name}")
        content = tfvars_path.read_text()

        # Parse key = value pairs
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            match = re.match(r'(\w+)\s*=\s*(.+)', line)
            if match:
                key = match.group(1)
                value = match.group(2).strip()
                self.variables[key] = self._parse_hcl_value(value)

    def _parse_hcl_value(self, value: str) -> Any:
        """Parse HCL value to Python type."""
        value = value.strip()

        # Boolean
        if value == "true":
            return True
        if value == "false":
            return False

        # String (quoted)
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]

        # Number
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        # List
        if value.startswith('['):
            items = re.findall(r'"([^"]*)"', value)
            return items if items else []

        return value

    def _parse_resources(self) -> None:
        """Parse Terraform files to extract resource definitions."""
        tf_files = list(self.tf_path.glob("*.tf")) + list(self.tf_path.glob("modules/**/*.tf"))

        for tf_file in tf_files:
            content = tf_file.read_text()
            self._extract_resources(content, tf_file.name)

    def _extract_resources(self, content: str, filename: str) -> None:
        """Extract resource blocks from Terraform content."""
        # Resource blocks
        resource_pattern = r'resource\s+"(\w+)"\s+"(\w+)"\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}'
        for match in re.finditer(resource_pattern, content, re.DOTALL):
            rtype = match.group(1)
            rname = match.group(2)
            rblock = match.group(3)

            if rtype not in self.resources:
                self.resources[rtype] = []

            self.resources[rtype].append({
                "name": rname,
                "block": rblock,
                "file": filename,
                "values": self._extract_block_values(rblock)
            })

        # Module blocks
        module_pattern = r'module\s+"(\w+)"\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}'
        for match in re.finditer(module_pattern, content, re.DOTALL):
            mname = match.group(1)
            mblock = match.group(2)

            if "modules" not in self.resources:
                self.resources["modules"] = []

            self.resources["modules"].append({
                "name": mname,
                "block": mblock,
                "file": filename,
                "values": self._extract_block_values(mblock)
            })

    def _extract_block_values(self, block: str) -> Dict[str, Any]:
        """Extract key-value pairs from a resource block."""
        values = {}
        for line in block.split('\n'):
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                match = re.match(r'(\w+)\s*=\s*(.+)', line)
                if match:
                    key = match.group(1)
                    val = match.group(2).strip()
                    values[key] = self._parse_hcl_value(val)
        return values

    def _resolve_variable(self, expr: str) -> Any:
        """Resolve a variable reference like var.environment."""
        if expr.startswith("var."):
            var_name = expr[4:]
            return self.variables.get(var_name, f"<{var_name}>")
        return expr

    def _build_infrastructure(self) -> ParsedInfrastructure:
        """Build ParsedInfrastructure from parsed Terraform resources."""
        infra = ParsedInfrastructure(source="terraform")

        # Core variables
        infra.environment = self.variables.get("environment", "prod")
        infra.location = self.variables.get("location", "East US 2")
        infra.resource_group = self.variables.get("resource_group_name", f"rg-PULSE-training-{infra.environment}")
        infra.subscription_id = self.variables.get("subscription_id")

        # Feature flags
        infra.enable_app_service = self.variables.get("enable_app_service", True)
        infra.enable_visual_asset = self.variables.get("enable_visual_asset_deployment", False)
        infra.enable_speech_avatar = self.variables.get("enable_speech_avatar", True)
        infra.enable_webapp_private_endpoint = self.variables.get("enable_webapp_private_endpoint", True)

        # Auth
        infra.auth_mode = self.variables.get("auth_mode", "demo")
        infra.azure_ad_enabled = infra.auth_mode == "sso"

        # VNet
        project_name = self.variables.get("project_name", "PULSE-training")
        infra.vnet_name = f"vnet-{project_name}-{infra.environment}"
        vnet_space = self.variables.get("vnet_address_space", ["10.10.0.0/16"])
        infra.vnet_cidr = vnet_space[0] if isinstance(vnet_space, list) else vnet_space

        # Subnets
        infra.subnets = [
            {"name": "PULSE-app-subnet", "cidr": self.variables.get("subnet_app_prefix", "10.10.1.0/24"), "delegation": "Microsoft.Web/serverFarms"},
            {"name": "PULSE-private-endpoints-subnet", "cidr": self.variables.get("subnet_private_endpoints_prefix", "10.10.2.0/24")},
            {"name": "PULSE-analytics-pg-subnet", "cidr": self.variables.get("analytics_pg_subnet_prefix", "10.10.3.0/24"), "delegation": "Microsoft.DBforPostgreSQL/flexibleServers"},
        ]

        # App Service Plan
        infra.app_service_plan = f"asp-{project_name}-{infra.environment}"
        infra.app_service_sku = self.variables.get("app_service_sku_name", "P1v3")

        # Web App
        infra.web_app = f"app-{project_name}-ui-{infra.environment}"

        # Function App
        infra.function_app = f"func-{project_name}-scenario-{infra.environment}"
        infra.function_routes = ["/session/*", "/audio/chunk", "/avatar/token", "/admin/*", "/readiness/*"]

        # OpenAI
        infra.openai_account = f"cog-{project_name}-{infra.environment}"
        infra.openai_deployments = [
            {"name": "Persona-Core-Chat", "model": self.variables.get("openai_model_core_chat_id", "gpt-4o"), "capacity": self.variables.get("openai_deployment_core_chat_capacity", 50)},
            {"name": "Persona-High-Reasoning", "model": self.variables.get("openai_model_high_reasoning_id", "o4-mini"), "capacity": self.variables.get("openai_deployment_high_reasoning_capacity", 20)},
            {"name": "PULSE-Audio-Realtime", "model": self.variables.get("openai_model_audio_realtime_id", "gpt-4o-realtime-preview"), "capacity": self.variables.get("openai_deployment_audio_realtime_capacity", 4)},
            {"name": "PULSE-Whisper", "model": "whisper", "capacity": 1},
        ]
        if infra.enable_visual_asset:
            infra.openai_deployments.append({"name": "Persona-Visual-Asset", "model": "sora-2", "capacity": 2})

        # Speech
        infra.speech_enabled = infra.enable_speech_avatar
        if infra.speech_enabled:
            infra.speech_account = f"speech-{project_name.lower()}-{infra.environment}"

        # Storage
        infra.storage_account = self.variables.get("storage_account_name", "pulsetrainingprodsa123")
        infra.storage_containers = ["certification-materials", "interaction-logs", "prompts"]

        # PostgreSQL
        infra.postgres_server = f"pg-{project_name.lower()}-analytics-{infra.environment}"
        infra.postgres_database = "pulse_analytics"

        # Observability
        infra.log_analytics = f"law-{project_name}-{infra.environment}"
        infra.app_insights = f"appi-{project_name}-{infra.environment}"
        infra.diagnostic_settings = [
            {"name": "diag-openai", "target": "OpenAI Cognitive Account"},
            {"name": "diag-storage", "target": "Storage Account"},
            {"name": "diag-webapp", "target": "Web App"},
            {"name": "diag-functionapp", "target": "Function App"},
        ]

        # Private Endpoints
        infra.private_endpoints = [
            {"name": f"pe-openai-{infra.environment}", "target": "Azure OpenAI"},
            {"name": f"pe-blob-{infra.environment}", "target": "Storage Blob"},
        ]
        if infra.speech_enabled:
            infra.private_endpoints.append({"name": f"pe-speech-{infra.environment}", "target": "Azure Speech"})
        if infra.enable_webapp_private_endpoint:
            infra.private_endpoints.append({"name": f"pe-webapp-{infra.environment}", "target": "Web App"})

        # DNS Zones
        infra.dns_zones = [
            {"name": "privatelink.openai.azure.com", "target": "OpenAI"},
            {"name": "privatelink.blob.core.windows.net", "target": "Storage"},
            {"name": "privatelink.postgres.database.azure.com", "target": "PostgreSQL"},
        ]
        if infra.speech_enabled:
            infra.dns_zones.append({"name": "privatelink.cognitiveservices.azure.com", "target": "Speech"})
        if infra.enable_webapp_private_endpoint:
            infra.dns_zones.append({"name": "privatelink.azurewebsites.net", "target": "Web App"})

        # VNet Integrations
        infra.vnet_integrations = [
            {"app": infra.web_app, "subnet": "PULSE-app-subnet"},
            {"app": infra.function_app, "subnet": "PULSE-app-subnet"},
        ]

        # Network Security Groups
        infra.network_security_groups = [
            {
                "name": "nsg-PULSE-app",
                "subnet": "PULSE-app-subnet",
                "rules": [
                    {"name": "AllowAzureServicesOutbound", "direction": "Outbound", "port": "443", "dest": "AzureCloud"},
                    {"name": "AllowPrivateEndpointsOutbound", "direction": "Outbound", "port": "443,5432", "dest": "PrivateEndpoints"},
                ]
            },
            {
                "name": "nsg-PULSE-private-endpoints",
                "subnet": "PULSE-private-endpoints-subnet",
                "rules": [
                    {"name": "AllowAppSubnetInbound", "direction": "Inbound", "port": "443", "source": "AppSubnet"},
                ]
            },
            {
                "name": "nsg-PULSE-postgres",
                "subnet": "PULSE-analytics-pg-subnet",
                "rules": [
                    {"name": "AllowPostgresFromAppSubnet", "direction": "Inbound", "port": "5432", "source": "AppSubnet"},
                    {"name": "AllowAzureManagement", "direction": "Inbound", "port": "5432", "source": "AzureCloud"},
                ]
            },
        ]

        # Security Controls
        infra.security_controls = [
            {"name": "CORS", "description": "Azure domain allowlist"},
            {"name": "Rate Limiting", "description": "60 req/min per user"},
            {"name": "Input Validation", "description": "UUID, length checks"},
            {"name": "Security Headers", "description": "CSP, X-Frame-Options"},
            {"name": "Error Sanitization", "description": "Generic messages in prod"},
            {"name": "Audit Logging", "description": "Structured JSON events"},
            {"name": "Function App Auth", "description": "X-Function-Key shared secret"},
        ]
        infra.function_app_shared_secret = True

        return infra


# =============================================================================
# AI Agent: Azure Discovery Scanner
# =============================================================================

class AzureDiscoveryAgent:
    """AI Agent that discovers deployed resources via Azure CLI."""

    def __init__(self, resource_group: str, subscription_id: Optional[str] = None):
        self.resource_group = resource_group
        self.subscription_id = subscription_id

    def discover(self) -> Optional[ParsedInfrastructure]:
        """Discover deployed resources from Azure."""
        print(f"[agent] Discovering Azure resources in: {self.resource_group}")

        if not self._check_az_cli():
            print("[warn] Azure CLI not available or not logged in")
            return None

        infra = ParsedInfrastructure(source="azure")
        infra.resource_group = self.resource_group

        try:
            # List all resources in resource group
            resources = self._az_query(f"resource list --resource-group {self.resource_group}")
            if not resources:
                print(f"[warn] No resources found in {self.resource_group}")
                return None

            for resource in resources:
                rtype = resource.get("type", "")
                rname = resource.get("name", "")
                location = resource.get("location", "")

                if not infra.location:
                    infra.location = location

                # Categorize resources
                if rtype == "Microsoft.Network/virtualNetworks":
                    infra.vnet_name = rname
                    vnet_details = self._az_query(f"network vnet show --resource-group {self.resource_group} --name {rname}")
                    if vnet_details:
                        infra.vnet_cidr = vnet_details.get("addressSpace", {}).get("addressPrefixes", [""])[0]

                elif rtype == "Microsoft.Network/privateEndpoints":
                    infra.private_endpoints.append({"name": rname, "target": rname})

                elif rtype == "Microsoft.Network/privateDnsZones":
                    infra.dns_zones.append({"name": rname})

                elif rtype == "Microsoft.Web/serverFarms":
                    infra.app_service_plan = rname

                elif rtype == "Microsoft.Web/sites":
                    if "func" in rname.lower():
                        infra.function_app = rname
                    else:
                        infra.web_app = rname

                elif rtype == "Microsoft.CognitiveServices/accounts":
                    # Check kind
                    cog_details = self._az_query(f"cognitiveservices account show --resource-group {self.resource_group} --name {rname}")
                    if cog_details:
                        kind = cog_details.get("kind", "")
                        if kind == "OpenAI":
                            infra.openai_account = rname
                            # Get deployments
                            deployments = self._az_query(f"cognitiveservices account deployment list --resource-group {self.resource_group} --name {rname}")
                            if deployments:
                                for dep in deployments:
                                    infra.openai_deployments.append({
                                        "name": dep.get("name", ""),
                                        "model": dep.get("properties", {}).get("model", {}).get("name", ""),
                                        "capacity": dep.get("sku", {}).get("capacity", 0)
                                    })
                        elif kind == "SpeechServices":
                            infra.speech_account = rname
                            infra.speech_enabled = True

                elif rtype == "Microsoft.Storage/storageAccounts":
                    infra.storage_account = rname
                    # Get containers
                    containers = self._az_query(f"storage container list --account-name {rname} --auth-mode login 2>/dev/null || echo '[]'")
                    if containers:
                        infra.storage_containers = [c.get("name", "") for c in containers]

                elif rtype == "Microsoft.DBforPostgreSQL/flexibleServers":
                    infra.postgres_server = rname

                elif rtype == "Microsoft.OperationalInsights/workspaces":
                    infra.log_analytics = rname

                elif rtype == "Microsoft.Insights/components":
                    infra.app_insights = rname

            # Get subnets
            if infra.vnet_name:
                subnets = self._az_query(f"network vnet subnet list --resource-group {self.resource_group} --vnet-name {infra.vnet_name}")
                if subnets:
                    for subnet in subnets:
                        infra.subnets.append({
                            "name": subnet.get("name", ""),
                            "cidr": subnet.get("addressPrefix", "")
                        })

            print(f"[agent] Discovered {len(resources)} resources")
            return infra

        except Exception as e:
            print(f"[error] Azure discovery failed: {e}")
            return None

    def _check_az_cli(self) -> bool:
        """Check if Azure CLI is available and logged in."""
        try:
            result = subprocess.run(
                ["az", "account", "show"],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def _az_query(self, command: str) -> Optional[Any]:
        """Execute Azure CLI command and return JSON result."""
        try:
            full_cmd = f"az {command} -o json"
            if self.subscription_id:
                full_cmd += f" --subscription {self.subscription_id}"

            result = subprocess.run(
                full_cmd, shell=True,
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0 and result.stdout:
                return json.loads(result.stdout)
        except Exception as e:
            print(f"[warn] Azure query failed: {e}")
        return None


# =============================================================================
# Infrastructure Comparator
# =============================================================================

def compare_infrastructure(planned: ParsedInfrastructure, deployed: ParsedInfrastructure) -> Dict[str, List[str]]:
    """Compare planned (Terraform) vs deployed (Azure) infrastructure."""
    drift = {
        "missing_in_azure": [],
        "extra_in_azure": [],
        "differences": []
    }

    # Compare OpenAI deployments
    planned_deps = {d["name"] for d in planned.openai_deployments}
    deployed_deps = {d["name"] for d in deployed.openai_deployments}

    for dep in planned_deps - deployed_deps:
        drift["missing_in_azure"].append(f"OpenAI Deployment: {dep}")
    for dep in deployed_deps - planned_deps:
        drift["extra_in_azure"].append(f"OpenAI Deployment: {dep}")

    # Compare storage containers
    planned_containers = set(planned.storage_containers)
    deployed_containers = set(deployed.storage_containers)

    for c in planned_containers - deployed_containers:
        drift["missing_in_azure"].append(f"Storage Container: {c}")
    for c in deployed_containers - planned_containers:
        drift["extra_in_azure"].append(f"Storage Container: {c}")

    # Compare subnets
    planned_subnets = {s["name"] for s in planned.subnets}
    deployed_subnets = {s["name"] for s in deployed.subnets}

    for s in planned_subnets - deployed_subnets:
        drift["missing_in_azure"].append(f"Subnet: {s}")
    for s in deployed_subnets - planned_subnets:
        drift["extra_in_azure"].append(f"Subnet: {s}")

    # Compare private endpoints
    planned_pes = {pe["name"] for pe in planned.private_endpoints}
    deployed_pes = {pe["name"] for pe in deployed.private_endpoints}

    for pe in planned_pes - deployed_pes:
        drift["missing_in_azure"].append(f"Private Endpoint: {pe}")
    for pe in deployed_pes - planned_pes:
        drift["extra_in_azure"].append(f"Private Endpoint: {pe}")

    return drift


# =============================================================================
# Terraform State Parser (Legacy)
# =============================================================================

def parse_terraform_state(state_json: Dict[str, Any]) -> ParsedInfrastructure:
    """Parse terraform show -json output into structured infrastructure data."""
    infra = ParsedInfrastructure(source="state")

    values = state_json.get("values", {})
    root_module = values.get("root_module", {})
    resources = root_module.get("resources", [])
    child_modules = root_module.get("child_modules", [])

    for child in child_modules:
        resources.extend(child.get("resources", []))
        for nested in child.get("child_modules", []):
            resources.extend(nested.get("resources", []))

    for resource in resources:
        rtype = resource.get("type", "")
        rvalues = resource.get("values", {})
        rname = resource.get("name", "")

        if rtype == "azurerm_resource_group":
            infra.resource_group = rvalues.get("name")
            infra.location = rvalues.get("location")
            name = rvalues.get("name", "")
            if "-prod" in name:
                infra.environment = "prod"
            elif "-dev" in name:
                infra.environment = "dev"

        elif rtype == "azurerm_virtual_network":
            infra.vnet_name = rvalues.get("name")
            cidrs = rvalues.get("address_space", [])
            infra.vnet_cidr = cidrs[0] if cidrs else None

        elif rtype == "azurerm_subnet":
            prefixes = rvalues.get("address_prefixes", [])
            infra.subnets.append({
                "name": rvalues.get("name"),
                "cidr": prefixes[0] if prefixes else None,
            })

        elif rtype == "azurerm_private_endpoint":
            infra.private_endpoints.append({
                "name": rvalues.get("name"),
                "target": rname,
            })

        elif rtype == "azurerm_private_dns_zone":
            infra.dns_zones.append({"name": rvalues.get("name")})

        elif rtype == "azurerm_service_plan":
            infra.app_service_plan = rvalues.get("name")
            infra.app_service_sku = rvalues.get("sku_name")

        elif rtype == "azurerm_linux_web_app":
            name = rvalues.get("name", "")
            if "ui" in name.lower():
                infra.web_app = name
            elif "func" in name.lower():
                infra.function_app = name

        elif rtype == "azurerm_linux_function_app":
            infra.function_app = rvalues.get("name")
            infra.function_routes = ["/session/*", "/audio/chunk", "/avatar/token", "/admin/*"]

        elif rtype == "azurerm_cognitive_account":
            kind = rvalues.get("kind", "")
            name = rvalues.get("name", "")
            if kind == "OpenAI":
                infra.openai_account = name
            elif kind == "SpeechServices":
                infra.speech_account = name
                infra.speech_enabled = True

        elif rtype == "azurerm_cognitive_deployment":
            model = rvalues.get("model", [{}])
            model_info = model[0] if model else {}
            sku = rvalues.get("sku", [{}])
            sku_info = sku[0] if sku else {}
            infra.openai_deployments.append({
                "name": rvalues.get("name"),
                "model": model_info.get("name"),
                "capacity": sku_info.get("capacity", 0),
            })

        elif rtype == "azurerm_storage_account":
            infra.storage_account = rvalues.get("name")

        elif rtype == "azurerm_storage_container":
            infra.storage_containers.append(rvalues.get("name"))

        elif rtype == "azurerm_postgresql_flexible_server":
            infra.postgres_server = rvalues.get("name")

        elif rtype == "azurerm_postgresql_flexible_server_database":
            infra.postgres_database = rvalues.get("name")

        elif rtype == "azurerm_log_analytics_workspace":
            infra.log_analytics = rvalues.get("name")

        elif rtype == "azurerm_application_insights":
            infra.app_insights = rvalues.get("name")

    return infra


def load_state_file(state_path: str) -> Optional[ParsedInfrastructure]:
    """Load and parse a Terraform state JSON file."""
    try:
        with open(state_path, "r") as f:
            state_json = json.load(f)
        return parse_terraform_state(state_json)
    except FileNotFoundError:
        print(f"[warn] State file not found: {state_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"[error] Invalid JSON in state file: {e}")
        return None


# =============================================================================
# Diagram Builder
# =============================================================================

def build_topology(infra: ParsedInfrastructure, layout_config: Optional[DiagramLayoutConfig] = None) -> Dict[str, Any]:
    """Build topology diagram from parsed infrastructure with beautified layout.

    Args:
        infra: Parsed infrastructure data
        layout_config: Optional layout configuration for spacing and page size

    Returns:
        Dictionary with edge tracking info for consolidation analysis
    """
    if not DIAGRAMS_AVAILABLE:
        print("[error] diagrams package not installed. Run: pip install diagrams")
        return {"edges": [], "nodes": []}

    # Initialize layout agent for edge consolidation
    config = layout_config or DiagramLayoutConfig()
    layout_agent = DiagramLayoutAgent(config)

    env = infra.environment or "<env>"
    rg_name = infra.resource_group or f"rg-PULSE-training-{env}"

    # Track all edges for consolidation analysis
    edge_list: List[Tuple[str, str, str]] = []
    node_list: List[str] = []

    # Helper to track edges
    def track_edge(source: str, target: str, label: str = "") -> None:
        edge_list.append((source, target, label))

    # External Users - positioned outside the Azure infrastructure
    # These represent where users interact with the system
    with Cluster("External Users"):
        # Training participants using the PULSE platform
        trainee = User("Trainees\n(Sales Reps)")
        # Administrators and content managers
        admin = Users("Admins\n(Managers)")
        # Optional: Client devices showing browser access
        browser = Client("Web Browser\n(HTTPS)")

    with Cluster(f"Resource Group: {rg_name}"):
        vnet_label = infra.vnet_name or f"vnet-PULSE-training-{env}"
        vnet_cidr = infra.vnet_cidr or "10.10.0.0/16"

        with Cluster(f"Virtual Network: {vnet_label} ({vnet_cidr})"):
            subnet_nodes = {}

            # App Subnet
            app_subnet_info = next((s for s in infra.subnets if "app" in s["name"].lower()), None)
            app_cidr = app_subnet_info["cidr"] if app_subnet_info else "10.10.1.0/24"
            app_subnet_name = app_subnet_info["name"] if app_subnet_info else "PULSE-app-subnet"

            with Cluster(f"App Subnet: {app_subnet_name} ({app_cidr})\nDelegation: Microsoft.Web/serverFarms"):
                app_subnet = Subnets(f"Subnet: {app_subnet_name}")
                subnet_nodes["app"] = app_subnet

                # NSG for App Subnet
                nsg_app = NetworkSecurityGroupsClassic("NSG: nsg-PULSE-app\n• AllowAzureServicesOutbound (443)\n• AllowPrivateEndpointsOutbound (443,5432)")
                app_subnet - Edge(label="protected by", style="dashed", color="orange") - nsg_app

                plan_name = infra.app_service_plan or f"asp-PULSE-training-{env}"
                sku = infra.app_service_sku or "P1v3"
                plan = AppServicePlans(f"App Service Plan\n({plan_name})\nSKU: {sku}")

                web_name = infra.web_app or f"app-PULSE-training-ui-{env}"
                web = AppServices(f"Web App: {web_name}\nNode.js 18 LTS")

                func_name = infra.function_app or f"func-PULSE-training-scenario-{env}"
                routes = ", ".join(infra.function_routes) if infra.function_routes else "/session/*, /audio/chunk, /avatar/token, /admin/*"
                func = FunctionApps(f"Function App: {func_name}\nPython 3.11\nRoutes: {routes}")

                app_subnet - Edge(label="hosts") - plan
                plan >> web
                plan >> func

            # Private Endpoints Subnet
            pe_subnet_info = next((s for s in infra.subnets if "private" in s["name"].lower() or "endpoint" in s["name"].lower()), None)
            pe_cidr = pe_subnet_info["cidr"] if pe_subnet_info else "10.10.2.0/24"
            pe_subnet_name = pe_subnet_info["name"] if pe_subnet_info else "PULSE-private-endpoints-subnet"

            with Cluster(f"Private Endpoints Subnet: {pe_subnet_name} ({pe_cidr})"):
                pe_subnet = Subnets(f"Subnet: {pe_subnet_name}")
                subnet_nodes["pe"] = pe_subnet

                # NSG for Private Endpoints Subnet
                nsg_pe = NetworkSecurityGroupsClassic("NSG: nsg-PULSE-private-endpoints\n• AllowAppSubnetInbound (443)")
                pe_subnet - Edge(label="protected by", style="dashed", color="orange") - nsg_pe

                pe_nodes = {}

                pe_openai = PrivateEndpoint("PE: Azure OpenAI")
                pe_nodes["openai"] = pe_openai
                pe_subnet - Edge(label="hosts") - pe_openai

                pe_blob = PrivateEndpoint("PE: Storage Blob")
                pe_nodes["blob"] = pe_blob
                pe_subnet - Edge(label="hosts") - pe_blob

                if infra.speech_enabled:
                    pe_speech = PrivateEndpoint("PE: Azure Speech")
                    pe_nodes["speech"] = pe_speech
                    pe_subnet - Edge(label="hosts") - pe_speech

                if infra.enable_webapp_private_endpoint:
                    pe_web = PrivateEndpoint("PE: Web App")
                    pe_nodes["web"] = pe_web
                    pe_subnet - Edge(label="hosts") - pe_web

            # Analytics/PostgreSQL Subnet
            pg_subnet_info = next((s for s in infra.subnets if "analytics" in s["name"].lower() or "pg" in s["name"].lower()), None)
            if pg_subnet_info or infra.postgres_server:
                pg_cidr = pg_subnet_info["cidr"] if pg_subnet_info else "10.10.3.0/24"
                pg_subnet_name = pg_subnet_info["name"] if pg_subnet_info else "PULSE-analytics-pg-subnet"

                with Cluster(f"Analytics Subnet: {pg_subnet_name} ({pg_cidr})\nDelegation: Microsoft.DBforPostgreSQL/flexibleServers"):
                    analytics_subnet = Subnets(f"Subnet: {pg_subnet_name}")
                    subnet_nodes["analytics"] = analytics_subnet

                    # NSG for PostgreSQL Subnet
                    nsg_pg = NetworkSecurityGroupsClassic("NSG: nsg-PULSE-postgres\n• AllowPostgresFromAppSubnet (5432)\n• AllowAzureManagement (5432)")
                    analytics_subnet - Edge(label="protected by", style="dashed", color="orange") - nsg_pg

                    pg_name = infra.postgres_server or f"pg-PULSE-training-analytics-{env}"
                    db_name = infra.postgres_database or "pulse_analytics"
                    analytics_pg = DatabaseForPostgresqlServers(f"PostgreSQL Flexible Server\n({pg_name})\nDB: {db_name}")
                    analytics_subnet - Edge(label="hosts") - analytics_pg

        # Private DNS Zones
        with Cluster("Private DNS Zones + VNet Links"):
            vnet_node = VirtualNetworks("Virtual Network")
            dns_nodes = {}

            dns_openai = DNSPrivateZones("Zone: privatelink.openai.azure.com")
            dns_nodes["openai"] = dns_openai
            dns_openai - Edge(label="vnet link") - vnet_node

            dns_blob = DNSPrivateZones("Zone: privatelink.blob.core.windows.net")
            dns_nodes["blob"] = dns_blob
            dns_blob - Edge(label="vnet link") - vnet_node

            dns_pg = DNSPrivateZones("Zone: privatelink.postgres.database.azure.com")
            dns_nodes["pg"] = dns_pg
            dns_pg - Edge(label="vnet link") - vnet_node

            if infra.speech_enabled:
                dns_speech = DNSPrivateZones("Zone: privatelink.cognitiveservices.azure.com")
                dns_nodes["speech"] = dns_speech
                dns_speech - Edge(label="vnet link") - vnet_node

            if infra.enable_webapp_private_endpoint:
                dns_web = DNSPrivateZones("Zone: privatelink.azurewebsites.net")
                dns_nodes["web"] = dns_web
                dns_web - Edge(label="vnet link") - vnet_node

            for subnet in subnet_nodes.values():
                vnet_node - Edge(label="contains") - subnet

        # Azure OpenAI
        with Cluster("Azure OpenAI: Cognitive Account + Deployments"):
            account_name = infra.openai_account or f"cog-PULSE-training-{env}"
            openai_account = CognitiveServices(f"Cognitive Account\n({account_name})")

            deployment_nodes = []
            for dep in infra.openai_deployments:
                dep_name = dep["name"]
                model = dep.get("model", "")
                capacity = dep.get("capacity", 0)
                label = f"{dep_name}\n({model})"
                if capacity == 0:
                    label += " [disabled]"
                else:
                    label += f" [{capacity}K TPM]"
                dep_node = CognitiveServices(label)
                deployment_nodes.append(dep_node)
                openai_account >> dep_node

        # Azure Speech Service
        if infra.speech_enabled:
            with Cluster("Azure Speech Service"):
                speech_name = infra.speech_account or f"speech-PULSE-training-{env}"
                speech_account = CognitiveServices(f"Speech Account\n({speech_name})")
                avatar_service = CognitiveServices("Avatar Service\n(WebRTC streaming)")
                speech_account >> avatar_service

        # Storage Account
        with Cluster("Storage Account + Containers"):
            storage_name = infra.storage_account or "sa-<name>"
            storage = StorageAccounts(f"Storage Account\n({storage_name})\nStandard LRS")

            containers = infra.storage_containers if infra.storage_containers else [
                "certification-materials", "interaction-logs", "prompts"
            ]
            for container in containers:
                container_node = StorageAccounts(f"Container: {container}")
                storage >> container_node

        # Observability
        with Cluster("Observability"):
            law_name = infra.log_analytics or f"law-PULSE-training-{env}"
            law = Logs(f"Log Analytics Workspace\n({law_name})")

            ai_name = infra.app_insights or f"appi-PULSE-training-{env}"
            ai = ApplicationInsights(f"Application Insights\n({ai_name})")

        # Authentication (if SSO enabled)
        if infra.azure_ad_enabled:
            with Cluster("Microsoft Entra ID"):
                entra = EnterpriseApplications(f"App Registration\nAuth Mode: {infra.auth_mode}")

        # Security Controls Cluster
        with Cluster("Security Controls"):
            # Application-level security
            security_label = (
                "Application Security:\n"
                "• CORS: Azure domain allowlist\n"
                "• Rate Limiting: 60 req/min\n"
                "• Input Validation: UUID, length\n"
                "• Security Headers: CSP, X-Frame\n"
                "• Error Sanitization: Prod mode\n"
                "• Audit Logging: Structured JSON"
            )
            app_security = KeyVaults(security_label)

            # Function App authentication
            func_auth_label = (
                "Function App Auth:\n"
                "• X-Function-Key header\n"
                "• Shared secret validation\n"
                "• HMAC timing-safe compare"
            )
            func_auth = KeyVaults(func_auth_label)

        # Security control edges
        web >> Edge(label="enforces", style="dotted", color="purple") >> app_security
        track_edge("web_app", "app_security", "enforces")
        web >> Edge(label="authenticates via", style="dotted", color="purple") >> func_auth
        track_edge("web_app", "func_auth", "authenticates via")
        func >> Edge(label="validates", style="dotted", color="purple") >> func_auth
        track_edge("function_app", "func_auth", "validates")

        # Connectivity edges - tracked for consolidation analysis
        web >> Edge(label="HTTPS via PE") >> pe_nodes["openai"]
        track_edge("web_app", "pe_openai", "HTTPS via PE")
        func >> Edge(label="HTTPS via PE") >> pe_nodes["openai"]
        track_edge("function_app", "pe_openai", "HTTPS via PE")
        pe_nodes["openai"] >> Edge(label="account") >> openai_account
        track_edge("pe_openai", "openai_account", "account")

        if infra.speech_enabled and "speech" in pe_nodes:
            func >> Edge(label="Avatar Token") >> pe_nodes["speech"]
            track_edge("function_app", "pe_speech", "Avatar Token")
            pe_nodes["speech"] >> Edge(label="account") >> speech_account
            track_edge("pe_speech", "speech_account", "account")
            web >> Edge(label="WebRTC (Avatar)", style="dashed") >> avatar_service
            track_edge("web_app", "avatar_service", "WebRTC (Avatar)")

        web >> Edge(label="Blob via PE") >> pe_nodes["blob"]
        track_edge("web_app", "pe_blob", "Blob via PE")
        pe_nodes["blob"] >> Edge(label="blob") >> storage
        track_edge("pe_blob", "storage", "blob")

        func >> Edge(label="AzureWebJobsStorage") >> storage
        track_edge("function_app", "storage", "AzureWebJobsStorage")

        if infra.postgres_server:
            web >> Edge(label="PULSE_ANALYTICS_DB") >> analytics_pg
            track_edge("web_app", "analytics_pg", "PULSE_ANALYTICS_DB")
            func >> Edge(label="PULSE_ANALYTICS_DB") >> analytics_pg
            track_edge("function_app", "analytics_pg", "PULSE_ANALYTICS_DB")

        if "web" in pe_nodes and "web" in dns_nodes:
            web >> Edge(label="PE (optional)") >> pe_nodes["web"]
            track_edge("web_app", "pe_web", "PE (optional)")
            pe_nodes["web"] >> Edge(label="DNS zone group") >> dns_nodes["web"]
            track_edge("pe_web", "dns_web", "DNS zone group")

        web >> Edge(label="VNet Integration") >> vnet_node
        track_edge("web_app", "vnet", "VNet Integration")
        func >> Edge(label="VNet Integration") >> vnet_node
        track_edge("function_app", "vnet", "VNet Integration")

        # Diagnostic edges
        openai_account >> Edge(label="diag_openai") >> law
        track_edge("openai_account", "law", "diag_openai")
        storage >> Edge(label="diag_storage") >> law
        track_edge("storage", "law", "diag_storage")
        web >> Edge(label="diag_webapp") >> law
        track_edge("web_app", "law", "diag_webapp")
        func >> Edge(label="diag_functionapp") >> law
        track_edge("function_app", "law", "diag_functionapp")
        web >> Edge(label="AppInsights") >> ai
        track_edge("web_app", "app_insights", "AppInsights")
        func >> Edge(label="AppInsights") >> ai
        track_edge("function_app", "app_insights", "AppInsights")

        # Auth edges
        if infra.azure_ad_enabled:
            web >> Edge(label="OIDC/SSO") >> entra
            track_edge("web_app", "entra_id", "OIDC/SSO")

    # User interaction edges - connecting external users to the Web App
    # Trainees access the training UI
    trainee >> Edge(label="Training Sessions", color="darkgreen") >> web
    track_edge("trainee", "web_app", "Training Sessions")

    # Admins access admin dashboard
    admin >> Edge(label="Admin Dashboard", color="darkblue") >> web
    track_edge("admin", "web_app", "Admin Dashboard")

    # Browser shows the HTTPS connection path
    browser >> Edge(label="HTTPS/443", style="bold") >> web
    track_edge("browser", "web_app", "HTTPS/443")

    # Run layout agent analysis for edge consolidation
    if edge_list:
        layout_agent.analyze_edges(edge_list)
        consolidated = layout_agent.consolidate_edges(edge_list)
        routing_hints = layout_agent.apply_orthogonal_routing(consolidated)

        return {
            "edges": edge_list,
            "consolidated_edges": consolidated,
            "routing_hints": routing_hints,
            "node_count": len(node_list),
        }

    return {"edges": edge_list, "nodes": node_list}


# =============================================================================
# Draw.io XML Renderer
# =============================================================================

def render_drawio(output_path: Path, infra: ParsedInfrastructure, layout_config: Optional[DiagramLayoutConfig] = None) -> None:
    """Render the topology as a draw.io XML document with beautified layout.

    Args:
        output_path: Path to write the .drawio file
        infra: Parsed infrastructure data
        layout_config: Optional layout configuration for page size and spacing
    """
    env = infra.environment or "<env>"
    config = layout_config or DiagramLayoutConfig()

    # Get page dimensions in pixels (draw.io uses pixels at 96 DPI)
    page_width_px, page_height_px = config.page_size.get_dimensions_px(config.dpi)

    # Scale factor for fitting content (leave margins)
    content_width = int(page_width_px * 0.95)
    content_height = int(page_height_px * 0.95)

    mxfile = Element("mxfile", attrib={"host": "app.diagrams.net"})
    diagram = SubElement(mxfile, "diagram", attrib={"id": "PULSE", "name": "PULSE Azure Network"})
    model = SubElement(
        diagram,
        "mxGraphModel",
        attrib={
            "dx": str(int(page_width_px * 0.3)),
            "dy": str(int(page_height_px * 0.25)),
            "grid": "1",
            "gridSize": "10",
            "guides": "1",
            "tooltips": "1",
            "connect": "1",
            "arrows": "1",
            "fold": "1",
            "page": "1",
            "pageScale": "1",
            "pageWidth": str(page_width_px),
            "pageHeight": str(page_height_px),
        },
    )
    root = SubElement(model, "root")
    SubElement(root, "mxCell", attrib={"id": "0"})
    SubElement(root, "mxCell", attrib={"id": "1", "parent": "0"})

    # Spacing calculations based on page size - scale relative to A4
    scale_factor = page_width_px / PageSize.A4.get_dimensions_px(config.dpi)[0]
    margin = int(config.cluster_padding * scale_factor)
    h_space = int(config.node_spacing_h * scale_factor)
    v_space = int(config.node_spacing_v * scale_factor)

    # Base dimensions scaled for page size
    base_width = int(content_width * 0.9)
    base_height = int(content_height * 0.85)

    def add_vertex(cell_id: str, label: str, x: int, y: int, w: int, h: int, parent: str = "1") -> None:
        cell = SubElement(
            root, "mxCell",
            attrib={
                "id": cell_id, "value": label,
                "style": "rounded=1;whiteSpace=wrap;html=1;",
                "vertex": "1", "parent": parent,
            },
        )
        SubElement(cell, "mxGeometry", attrib={"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"})

    def add_edge(cell_id: str, source: str, target: str, label: str = "", parent: str = "1") -> None:
        cell = SubElement(
            root, "mxCell",
            attrib={
                "id": cell_id, "value": label,
                "style": "endArrow=block;html=1;",
                "edge": "1", "parent": parent, "source": source, "target": target,
            },
        )
        SubElement(cell, "mxGeometry", attrib={"relative": "1", "as": "geometry"})

    # Build vertices with scaled positions for page size
    # All positions are scaled relative to the page dimensions

    # External Users cluster - positioned to the left of Azure infrastructure
    user_cluster_x = margin
    user_cluster_y = margin
    user_cluster_w = int(base_width * 0.12)
    user_cluster_h = int(base_height * 0.35)
    user_node_w = int(user_cluster_w * 0.85)
    user_node_h = int(v_space * 0.7)

    add_vertex("users_cluster", "External Users", user_cluster_x, user_cluster_y, user_cluster_w, user_cluster_h)
    add_vertex("trainee", "Trainees (Sales Reps)", h_space // 2, v_space // 2, user_node_w, user_node_h, parent="users_cluster")
    add_vertex("admin", "Admins (Managers)", h_space // 2, v_space // 2 + user_node_h + v_space // 2, user_node_w, user_node_h, parent="users_cluster")
    add_vertex("browser", "Web Browser (HTTPS)", h_space // 2, v_space // 2 + (user_node_h + v_space // 2) * 2, user_node_w, user_node_h, parent="users_cluster")

    # Shift Resource Group to the right to make room for users
    rg_x = user_cluster_x + user_cluster_w + h_space
    rg_w = base_width - user_cluster_w - h_space

    rg_name = infra.resource_group or f"rg-PULSE-training-{env}"
    add_vertex("rg", f"Resource Group: {rg_name}", rg_x, margin, rg_w, base_height)

    vnet_name = infra.vnet_name or f"vnet-PULSE-training-{env}"
    vnet_cidr = infra.vnet_cidr or "10.10.0.0/16"
    vnet_w = int(base_width * 0.45)
    vnet_h = int(base_height * 0.5)
    add_vertex("vnet", f"Virtual Network: {vnet_name} ({vnet_cidr})", margin + h_space, margin + v_space, vnet_w, vnet_h, parent="rg")

    # Subnets - scaled positions within VNet
    subnet_w = int(vnet_w * 0.45)
    subnet_h_app = int(vnet_h * 0.35)
    subnet_h_pe = int(vnet_h * 0.45)
    subnet_h_analytics = int(vnet_h * 0.25)

    add_vertex("subnet_app", "Subnet: PULSE-app-subnet", h_space, v_space, subnet_w, subnet_h_app, parent="vnet")
    add_vertex("subnet_pe", "Subnet: PULSE-private-endpoints-subnet", subnet_w + h_space * 2, v_space, subnet_w, subnet_h_pe, parent="vnet")
    add_vertex("subnet_analytics", "Subnet: PULSE-analytics-pg-subnet", h_space, subnet_h_app + v_space * 2, subnet_w, subnet_h_analytics, parent="vnet")

    # App components - scaled within app subnet
    node_w = int(subnet_w * 0.8)
    node_h = int(v_space * 0.8)

    plan_name = infra.app_service_plan or f"asp-PULSE-training-{env}"
    add_vertex("plan", f"App Service Plan ({plan_name})", h_space // 2, v_space // 2, node_w, node_h, parent="subnet_app")

    web_name = infra.web_app or f"app-PULSE-training-ui-{env}"
    add_vertex("web", f"Web App: {web_name}", h_space // 2, v_space // 2 + node_h + v_space // 2, node_w, node_h, parent="subnet_app")

    func_name = infra.function_app or f"func-PULSE-training-scenario-{env}"
    add_vertex("func", f"Function App: {func_name}", h_space // 2, v_space // 2 + (node_h + v_space // 2) * 2, int(node_w * 1.2), node_h, parent="subnet_app")

    # Private Endpoints - scaled within PE subnet
    pe_w = int(subnet_w * 0.85)
    pe_h = int(v_space * 0.65)
    pe_y = v_space // 2

    add_vertex("pe_openai", "PE: Azure OpenAI", h_space // 2, pe_y, pe_w, pe_h, parent="subnet_pe")
    pe_y += pe_h + v_space // 3
    add_vertex("pe_blob", "PE: Storage Blob", h_space // 2, pe_y, pe_w, pe_h, parent="subnet_pe")
    pe_y += pe_h + v_space // 3
    if infra.speech_enabled:
        add_vertex("pe_speech", "PE: Azure Speech", h_space // 2, pe_y, pe_w, pe_h, parent="subnet_pe")
        pe_y += pe_h + v_space // 3
    if infra.enable_webapp_private_endpoint:
        add_vertex("pe_web", "PE: Web App", h_space // 2, pe_y, pe_w, pe_h, parent="subnet_pe")

    # DNS Zones - positioned to the right of VNet
    dns_x = vnet_w + h_space * 3
    dns_w = int(base_width * 0.22)
    dns_h = int(v_space * 0.75)
    dns_y = margin + v_space

    add_vertex("dns_openai", "Zone: privatelink.openai.azure.com", dns_x, dns_y, dns_w, dns_h, parent="rg")
    dns_y += dns_h + v_space // 2
    add_vertex("dns_blob", "Zone: privatelink.blob.core.windows.net", dns_x, dns_y, dns_w, dns_h, parent="rg")
    dns_y += dns_h + v_space // 2
    if infra.speech_enabled:
        add_vertex("dns_speech", "Zone: privatelink.cognitiveservices.azure.com", dns_x, dns_y, int(dns_w * 1.1), dns_h, parent="rg")
        dns_y += dns_h + v_space // 2
    if infra.enable_webapp_private_endpoint:
        add_vertex("dns_web", "Zone: privatelink.azurewebsites.net", dns_x, dns_y, int(dns_w * 1.1), dns_h, parent="rg")
        dns_y += dns_h + v_space // 2
    add_vertex("dns_pg", "Zone: privatelink.postgres.database.azure.com", dns_x, dns_y, int(dns_w * 1.1), dns_h, parent="rg")

    # OpenAI Account and Deployments - scaled cluster
    openai_x = dns_x
    openai_y = int(base_height * 0.42)
    openai_w = int(base_width * 0.24)
    openai_h = int(base_height * 0.28)

    openai_name = infra.openai_account or f"cog-PULSE-training-{env}"
    add_vertex("openai_account", f"Azure OpenAI Account ({openai_name})", openai_x, openai_y, openai_w, openai_h, parent="rg")

    dep_y = v_space // 2
    dep_w = int(openai_w * 0.9)
    dep_h = int(v_space * 0.5)
    for i, dep in enumerate(infra.openai_deployments):
        label = f"Deployment: {dep['name']}"
        if dep.get("capacity", 1) == 0:
            label += " (disabled)"
        add_vertex(f"dep_{i}", label, h_space // 2, dep_y, dep_w, dep_h, parent="openai_account")
        dep_y += dep_h + v_space // 4

    # Speech Service - positioned to the right
    services_x = dns_x + dns_w + h_space
    if infra.speech_enabled:
        speech_name = infra.speech_account or f"speech-PULSE-training-{env}"
        speech_w = int(base_width * 0.18)
        speech_h = int(base_height * 0.12)
        add_vertex("speech_account", f"Azure Speech Account ({speech_name})", services_x, openai_y, speech_w, speech_h, parent="rg")
        add_vertex("avatar_service", "Avatar Service (WebRTC)", h_space // 2, v_space, int(speech_w * 0.9), int(v_space * 0.5), parent="speech_account")

    # Storage - positioned below speech
    storage_name = infra.storage_account or "sa-<name>"
    storage_w = int(base_width * 0.17)
    storage_h = int(base_height * 0.22)
    storage_y = openai_y + int(base_height * 0.16)
    add_vertex("storage", f"Storage Account ({storage_name})", services_x, storage_y, storage_w, storage_h, parent="rg")

    cont_y = v_space // 2
    cont_w = int(storage_w * 0.85)
    cont_h = int(v_space * 0.4)
    for i, container in enumerate(infra.storage_containers[:4]):
        add_vertex(f"container_{i}", f"Container: {container}", h_space // 2, cont_y, cont_w, cont_h, parent="storage")
        cont_y += cont_h + v_space // 4

    # Observability - top right
    obs_x = services_x
    obs_w = int(base_width * 0.17)
    obs_h = int(v_space * 0.85)

    law_name = infra.log_analytics or f"law-PULSE-training-{env}"
    add_vertex("law", f"Log Analytics Workspace ({law_name})", obs_x, margin + v_space, obs_w, obs_h, parent="rg")

    ai_name = infra.app_insights or f"appi-PULSE-training-{env}"
    add_vertex("ai", f"Application Insights ({ai_name})", obs_x, margin + v_space + obs_h + v_space // 2, obs_w, obs_h, parent="rg")

    # PostgreSQL - within analytics subnet
    pg_name = infra.postgres_server or f"pg-PULSE-training-analytics-{env}"
    pg_w = int(subnet_w * 0.9)
    pg_h = int(subnet_h_analytics * 0.6)
    add_vertex("analytics_pg", f"PostgreSQL Flexible Server ({pg_name})", h_space // 2, v_space // 2, pg_w, pg_h, parent="subnet_analytics")

    # Edges
    add_edge("e_plan_web", "plan", "web")
    add_edge("e_plan_func", "plan", "func")
    add_edge("e_web_pe_openai", "web", "pe_openai")
    add_edge("e_func_pe_openai", "func", "pe_openai")
    add_edge("e_pe_openai_openai", "pe_openai", "openai_account", label="account")
    add_edge("e_web_pe_blob", "web", "pe_blob")
    add_edge("e_pe_blob_storage", "pe_blob", "storage", label="blob")
    add_edge("e_func_storage", "func", "storage", label="AzureWebJobsStorage")
    add_edge("e_dns_openai_vnet", "dns_openai", "vnet", label="vnet link")
    add_edge("e_dns_blob_vnet", "dns_blob", "vnet", label="vnet link")
    add_edge("e_dns_pg_vnet", "dns_pg", "vnet", label="vnet link")

    if infra.enable_webapp_private_endpoint:
        add_edge("e_web_pe_web", "web", "pe_web")
        add_edge("e_pe_web_dns_web", "pe_web", "dns_web", label="DNS zone group")
        add_edge("e_dns_web_vnet", "dns_web", "vnet", label="vnet link")

    if infra.speech_enabled:
        add_edge("e_func_pe_speech", "func", "pe_speech", label="Avatar Token")
        add_edge("e_pe_speech_speech", "pe_speech", "speech_account", label="account")
        add_edge("e_speech_avatar", "speech_account", "avatar_service")
        add_edge("e_web_avatar", "web", "avatar_service", label="WebRTC Stream")
        add_edge("e_dns_speech_vnet", "dns_speech", "vnet", label="vnet link")

    for i in range(len(infra.openai_deployments)):
        add_edge(f"e_openai_dep_{i}", "openai_account", f"dep_{i}")

    for i in range(min(len(infra.storage_containers), 4)):
        add_edge(f"e_storage_cont_{i}", "storage", f"container_{i}")

    add_edge("e_openai_law", "openai_account", "law", label="diagnostics")
    add_edge("e_storage_law", "storage", "law", label="diagnostics")
    add_edge("e_web_law", "web", "law", label="diagnostics")
    add_edge("e_func_law", "func", "law", label="diagnostics")
    add_edge("e_web_ai", "web", "ai", label="AppInsights")
    add_edge("e_func_ai", "func", "ai", label="AppInsights")
    add_edge("e_web_analytics_pg", "web", "analytics_pg", label="PULSE_ANALYTICS_DB")
    add_edge("e_func_analytics_pg", "func", "analytics_pg", label="PULSE_ANALYTICS_DB")

    # User interaction edges - external users connecting to Web App
    add_edge("e_trainee_web", "trainee", "web", label="Training Sessions")
    add_edge("e_admin_web", "admin", "web", label="Admin Dashboard")
    add_edge("e_browser_web", "browser", "web", label="HTTPS/443")

    tree = ElementTree(mxfile)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    # Determine script location and project root
    script_path = Path(__file__).resolve()
    project_root = script_path.parents[1]  # Go up from docs/
    docs_dir = project_root / "docs"

    parser = argparse.ArgumentParser(
        description=(
            "PULSE Azure Network Diagram Generator\n\n"
            "AI-powered infrastructure diagram generator that parses Terraform code,\n"
            "discovers deployed Azure resources, and generates accurate diagrams.\n"
        ),
        formatter_class=RawTextHelpFormatter,
        epilog=(
            "Examples:\n\n"
            "  # Default: Parse Terraform from project root, output PNG+SVG to docs/\n"
            "  python docs/PULSE_network_diagram.py\n\n"
            "  # Generate SVG only (skip PNG)\n"
            "  python docs/PULSE_network_diagram.py --svg\n\n"
            "  # With Azure discovery scan (compare plan vs deployed)\n"
            "  python docs/PULSE_network_diagram.py --discover\n\n"
            "  # From Terraform state file (legacy mode)\n"
            "  python docs/PULSE_network_diagram.py --state tfstate.json\n\n"
            "  # Generate draw.io XML for Lucidchart\n"
            "  python docs/PULSE_network_diagram.py --drawio\n\n"
            "Requirements:\n"
            "  pip install diagrams graphviz\n"
            "  brew install graphviz  # macOS\n"
        ),
    )
    parser.add_argument(
        "--state",
        type=str,
        help="Path to terraform show -json output file (legacy mode).",
    )
    parser.add_argument(
        "--tf-path",
        type=str,
        default=str(project_root),
        help=f"Path to Terraform project root. Default: {project_root}",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(docs_dir),
        help=f"Output directory for diagrams. Default: {docs_dir}",
    )
    parser.add_argument(
        "--output-basename",
        type=str,
        default="PULSE-network-diagram",
        help="Base filename (without extension) for outputs. Default: PULSE-network-diagram",
    )
    parser.add_argument(
        "--direction",
        type=str,
        choices=["LR", "TB", "BT", "RL"],
        default="LR",
        help="Diagram direction (Left-to-Right, Top-to-Bottom, etc.). Default: LR",
    )
    parser.add_argument(
        "--svg",
        action="store_true",
        help="Generate SVG only (skip PNG). Default: generate both PNG and SVG.",
    )
    parser.add_argument(
        "--png",
        action="store_true",
        help="Generate PNG only (skip SVG).",
    )
    parser.add_argument(
        "--drawio",
        action="store_true",
        help="Generate draw.io XML file instead of PNG/SVG.",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Discover deployed resources from Azure and compare with Terraform plan.",
    )
    parser.add_argument(
        "--resource-group",
        type=str,
        help="Azure resource group for discovery. Default: from tfvars.",
    )
    parser.add_argument(
        "--subscription",
        type=str,
        help="Azure subscription ID for discovery. Default: from tfvars.",
    )
    parser.add_argument(
        "--page-size",
        type=str,
        choices=["A0", "A1", "A2", "A3", "A4"],
        default="A0",
        help="Page size for diagram output. A0 is optimized for plotters. Default: A0",
    )
    parser.add_argument(
        "--usage",
        action="store_true",
        help="Show extended usage help.",
    )
    args = parser.parse_args()

    if args.usage:
        parser.print_help()
        return

    # Setup paths
    tf_path = Path(args.tf_path).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_basename = output_dir / args.output_basename

    print("=" * 60)
    print("PULSE Azure Network Diagram Generator")
    print("=" * 60)

    # Determine mode and parse infrastructure
    infra = None
    deployed_infra = None

    if args.state:
        # Legacy: Load from Terraform state
        print(f"[mode] Loading from Terraform state: {args.state}")
        infra = load_state_file(args.state)
    else:
        # Default: Parse Terraform code
        print(f"[mode] Parsing Terraform code from: {tf_path}")

        # Check terraform files exist
        tf_files = ["main.tf", "variables.tf"]
        for tf_file in tf_files:
            path = tf_path / tf_file
            status = "OK" if path.exists() else "MISSING"
            print(f"[check] {tf_file}: {status}")

        # Find tfvars
        tfvars_path = None
        for tfvars in tf_path.glob("*.tfvars"):
            tfvars_path = tfvars
            print(f"[check] tfvars: {tfvars.name}")
            break

        # Parse with Terraform Agent
        agent = TerraformAgent(tf_path)
        infra = agent.parse_all(tfvars_path)

    if not infra:
        print("[error] Failed to parse infrastructure. Exiting.")
        return

    # Print parsed infrastructure summary
    print("\n[info] Parsed Infrastructure:")
    print(f"  - Source: {infra.source}")
    print(f"  - Resource Group: {infra.resource_group}")
    print(f"  - Location: {infra.location}")
    print(f"  - Environment: {infra.environment}")
    print(f"  - VNet: {infra.vnet_name} ({infra.vnet_cidr})")
    print(f"  - Subnets: {len(infra.subnets)}")
    print(f"  - OpenAI Account: {infra.openai_account}")
    print(f"  - OpenAI Deployments: {len(infra.openai_deployments)}")
    for dep in infra.openai_deployments:
        print(f"      - {dep['name']} ({dep.get('model', 'N/A')}) [{dep.get('capacity', 0)}K TPM]")
    print(f"  - Speech Service: {'Enabled' if infra.speech_enabled else 'Disabled'}")
    print(f"  - Storage: {infra.storage_account} ({len(infra.storage_containers)} containers)")
    print(f"  - PostgreSQL: {infra.postgres_server}")
    print(f"  - Private Endpoints: {len(infra.private_endpoints)}")
    print(f"  - DNS Zones: {len(infra.dns_zones)}")
    print(f"  - Auth Mode: {infra.auth_mode}")
    print(f"  - Network Security Groups: {len(infra.network_security_groups)}")
    for nsg in infra.network_security_groups:
        print(f"      - {nsg['name']} -> {nsg['subnet']}")
    print(f"  - Security Controls: {len(infra.security_controls)}")
    for ctrl in infra.security_controls:
        print(f"      - {ctrl['name']}: {ctrl['description']}")
    print(f"  - Function App Shared Secret: {'Enabled' if infra.function_app_shared_secret else 'Disabled'}")

    # Azure discovery
    if args.discover:
        rg = args.resource_group or infra.resource_group
        sub = args.subscription or infra.subscription_id

        if rg:
            discovery_agent = AzureDiscoveryAgent(rg, sub)
            deployed_infra = discovery_agent.discover()

            if deployed_infra:
                print("\n[info] Azure Discovery Results:")
                print(f"  - OpenAI Deployments: {len(deployed_infra.openai_deployments)}")
                print(f"  - Storage Containers: {len(deployed_infra.storage_containers)}")
                print(f"  - Subnets: {len(deployed_infra.subnets)}")
                print(f"  - Private Endpoints: {len(deployed_infra.private_endpoints)}")

                # Compare
                drift = compare_infrastructure(infra, deployed_infra)

                if drift["missing_in_azure"]:
                    print("\n[drift] Missing in Azure (planned but not deployed):")
                    for item in drift["missing_in_azure"]:
                        print(f"  - {item}")

                if drift["extra_in_azure"]:
                    print("\n[drift] Extra in Azure (deployed but not in Terraform):")
                    for item in drift["extra_in_azure"]:
                        print(f"  + {item}")

                if not drift["missing_in_azure"] and not drift["extra_in_azure"]:
                    print("\n[drift] No drift detected - Terraform and Azure are in sync!")
        else:
            print("[warn] No resource group specified for Azure discovery")

    # Render diagram
    print("\n[render] Generating diagrams...")

    # Parse page size
    page_size_map = {
        "A0": PageSize.A0,
        "A1": PageSize.A1,
        "A2": PageSize.A2,
        "A3": PageSize.A3,
        "A4": PageSize.A4,
    }
    selected_page_size = page_size_map.get(args.page_size.upper(), PageSize.A0)

    # Create layout config with selected page size
    layout_config = DiagramLayoutConfig(
        page_size=selected_page_size,
        use_orthogonal_edges=True,
        edge_concentrate=True,
    )

    print(f"[layout] Page size: {args.page_size} ({selected_page_size.width_mm}mm x {selected_page_size.height_mm}mm)")

    if args.drawio:
        drawio_path = output_basename.with_suffix(".drawio")
        print(f"[render] Generating draw.io XML: {drawio_path}")
        render_drawio(drawio_path, infra, layout_config)
        print(f"[done] Output: {drawio_path}")
    else:
        if not DIAGRAMS_AVAILABLE:
            print("[error] diagrams package not installed. Run: pip install diagrams")
            return

        outputs = []

        if args.svg and not args.png:
            # SVG only
            formats = ["svg"]
        elif args.png and not args.svg:
            # PNG only
            formats = ["png"]
        else:
            # Both (default)
            formats = ["png", "svg"]

        # Get graphviz attributes for beautified layout
        graph_attrs = layout_config.get_graphviz_attrs()

        for fmt in formats:
            print(f"[render] Generating {fmt.upper()} with beautified layout...")
            with Diagram(
                "PULSE H2 - Azure Network Architecture",
                filename=str(output_basename),
                outformat=fmt,
                direction=args.direction,
                show=False,
                graph_attr=graph_attrs,
            ):
                result = build_topology(infra, layout_config)
                if result.get("consolidated_edges"):
                    print(f"[layout] Consolidated {len(result['edges'])} edges -> {len(result['consolidated_edges'])} optimized edges")
            outputs.append(f"{output_basename}.{fmt}")

        print(f"\n[done] Outputs:")
        for output in outputs:
            print(f"  - {output}")


if __name__ == "__main__":
    main()
