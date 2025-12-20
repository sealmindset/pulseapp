#!/usr/bin/env python3
"""
PULSE Azure Network Diagram Generator

Generates architecture diagrams from Terraform state (dynamic) or falls back to
static topology when state is unavailable.

Usage:
    # Dynamic mode (reads from terraform state)
    cd /path/to/terraform && terraform show -json > tfstate.json
    python docs/PULSE_network_diagram.py --state tfstate.json

    # Static mode (hardcoded topology - legacy)
    python docs/PULSE_network_diagram.py

    # Generate draw.io XML for Lucidchart
    python docs/PULSE_network_diagram.py --state tfstate.json --drawio
"""

import argparse
import json
from argparse import RawTextHelpFormatter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.etree.ElementTree import Element, SubElement, ElementTree

from diagrams import Diagram, Cluster, Edge
from diagrams.azure.network import VirtualNetworks, Subnets, PrivateEndpoint, DNSPrivateZones
from diagrams.azure.ml import AzureOpenAI, CognitiveServices
from diagrams.azure.storage import StorageAccounts
from diagrams.azure.web import AppServices, AppServicePlans
from diagrams.azure.compute import FunctionApps
from diagrams.azure.monitor import Logs
from diagrams.azure.devops import ApplicationInsights
from diagrams.azure.database import DatabaseForPostgresqlServers


# =============================================================================
# Terraform State Parser
# =============================================================================

@dataclass
class ParsedInfrastructure:
    """Parsed infrastructure from Terraform state."""
    resource_group: Optional[str] = None
    location: Optional[str] = None
    environment: Optional[str] = None

    # Networking
    vnet_name: Optional[str] = None
    vnet_cidr: Optional[str] = None
    subnets: List[Dict[str, Any]] = field(default_factory=list)
    private_endpoints: List[Dict[str, Any]] = field(default_factory=list)
    dns_zones: List[Dict[str, Any]] = field(default_factory=list)

    # Compute
    app_service_plan: Optional[str] = None
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

    # Observability
    log_analytics: Optional[str] = None
    app_insights: Optional[str] = None


def parse_terraform_state(state_json: Dict[str, Any]) -> ParsedInfrastructure:
    """Parse terraform show -json output into structured infrastructure data."""
    infra = ParsedInfrastructure()

    # Get root module values if available
    values = state_json.get("values", {})
    root_module = values.get("root_module", {})
    resources = root_module.get("resources", [])
    child_modules = root_module.get("child_modules", [])

    # Flatten child module resources
    for child in child_modules:
        resources.extend(child.get("resources", []))
        # Handle nested child modules
        for nested in child.get("child_modules", []):
            resources.extend(nested.get("resources", []))

    for resource in resources:
        rtype = resource.get("type", "")
        rvalues = resource.get("values", {})
        rname = resource.get("name", "")

        # Resource Group
        if rtype == "azurerm_resource_group":
            infra.resource_group = rvalues.get("name")
            infra.location = rvalues.get("location")
            # Try to extract environment from name
            name = rvalues.get("name", "")
            if "-prod" in name:
                infra.environment = "prod"
            elif "-dev" in name:
                infra.environment = "dev"
            elif "-staging" in name:
                infra.environment = "staging"

        # Virtual Network
        elif rtype == "azurerm_virtual_network":
            infra.vnet_name = rvalues.get("name")
            cidrs = rvalues.get("address_space", [])
            infra.vnet_cidr = cidrs[0] if cidrs else None

        # Subnets
        elif rtype == "azurerm_subnet":
            prefixes = rvalues.get("address_prefixes", [])
            infra.subnets.append({
                "name": rvalues.get("name"),
                "cidr": prefixes[0] if prefixes else None,
            })

        # Private Endpoints
        elif rtype == "azurerm_private_endpoint":
            infra.private_endpoints.append({
                "name": rvalues.get("name"),
                "target": rname,  # Use terraform resource name as hint
            })

        # Private DNS Zones
        elif rtype == "azurerm_private_dns_zone":
            infra.dns_zones.append({
                "name": rvalues.get("name"),
            })

        # App Service Plan
        elif rtype == "azurerm_service_plan":
            infra.app_service_plan = rvalues.get("name")

        # Web App (Linux)
        elif rtype == "azurerm_linux_web_app":
            name = rvalues.get("name", "")
            if "ui" in name.lower():
                infra.web_app = name
            elif "func" in name.lower() or "scenario" in name.lower():
                infra.function_app = name

        # Function App
        elif rtype == "azurerm_linux_function_app":
            infra.function_app = rvalues.get("name")
            # Try to extract routes from app settings
            app_settings = rvalues.get("app_settings", {})
            if app_settings.get("TRAINING_ORCHESTRATOR_ENABLED"):
                infra.function_routes = ["/session/*", "/audio/chunk", "/avatar/token", "/admin/*"]

        # Azure OpenAI (Cognitive Account)
        elif rtype == "azurerm_cognitive_account":
            kind = rvalues.get("kind", "")
            name = rvalues.get("name", "")
            if kind == "OpenAI":
                infra.openai_account = name
            elif kind == "SpeechServices":
                infra.speech_account = name
                infra.speech_enabled = True

        # Cognitive Deployments (OpenAI models)
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

        # Storage Account
        elif rtype == "azurerm_storage_account":
            infra.storage_account = rvalues.get("name")

        # Storage Containers
        elif rtype == "azurerm_storage_container":
            infra.storage_containers.append(rvalues.get("name"))

        # PostgreSQL Flexible Server
        elif rtype == "azurerm_postgresql_flexible_server":
            infra.postgres_server = rvalues.get("name")

        # Log Analytics Workspace
        elif rtype == "azurerm_log_analytics_workspace":
            infra.log_analytics = rvalues.get("name")

        # Application Insights
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
# Dynamic Diagram Builder
# =============================================================================

def build_topology_dynamic(infra: ParsedInfrastructure):
    """Build topology from parsed Terraform state."""
    env = infra.environment or "<env>"
    rg_name = infra.resource_group or f"rg-PULSE-training-{env}"

    with Cluster(f"Resource Group: {rg_name}"):
        vnet_label = infra.vnet_name or f"vnet-PULSE-training-{env}"
        vnet_cidr = infra.vnet_cidr or "10.10.0.0/16"

        with Cluster(f"Virtual Network: {vnet_label} ({vnet_cidr})"):
            # Build subnets dynamically
            subnet_nodes = {}

            # App Subnet
            app_subnet_info = next((s for s in infra.subnets if "app" in s["name"].lower()), None)
            app_cidr = app_subnet_info["cidr"] if app_subnet_info else "10.10.1.0/24"
            app_subnet_name = app_subnet_info["name"] if app_subnet_info else "PULSE-app-subnet"

            with Cluster(f"App Subnet: {app_subnet_name} ({app_cidr})"):
                app_subnet = Subnets(f"Subnet: {app_subnet_name}")
                subnet_nodes["app"] = app_subnet

                plan_name = infra.app_service_plan or f"asp-PULSE-training-{env}"
                plan = AppServicePlans(f"App Service Plan ({plan_name})")

                web_name = infra.web_app or f"app-PULSE-training-ui-{env}"
                web = AppServices(f"Web App: {web_name}")

                func_name = infra.function_app or f"func-PULSE-training-scenario-{env}"
                routes = ", ".join(infra.function_routes) if infra.function_routes else "/session/*, /audio/chunk, /avatar/token, /admin/*"
                func = FunctionApps(f"Function App: {func_name}\nRoutes: {routes}")

                app_subnet - Edge(label="hosts") - plan
                app_subnet - Edge(label="hosts") - web
                app_subnet - Edge(label="hosts") - func
                plan >> web
                plan >> func

            # Private Endpoints Subnet
            pe_subnet_info = next((s for s in infra.subnets if "private" in s["name"].lower() or "endpoint" in s["name"].lower()), None)
            pe_cidr = pe_subnet_info["cidr"] if pe_subnet_info else "10.10.2.0/24"
            pe_subnet_name = pe_subnet_info["name"] if pe_subnet_info else "PULSE-private-endpoints-subnet"

            with Cluster(f"Private Endpoints Subnet: {pe_subnet_name} ({pe_cidr})"):
                pe_subnet = Subnets(f"Subnet: {pe_subnet_name}")
                subnet_nodes["pe"] = pe_subnet

                # Create private endpoints based on what's in state
                pe_nodes = {}
                pe_types = {"openai": False, "blob": False, "speech": False, "web": False}

                for pe in infra.private_endpoints:
                    pe_name = pe["name"].lower()
                    if "openai" in pe_name:
                        pe_types["openai"] = True
                    elif "blob" in pe_name or "storage" in pe_name:
                        pe_types["blob"] = True
                    elif "speech" in pe_name:
                        pe_types["speech"] = True
                    elif "web" in pe_name or "app" in pe_name:
                        pe_types["web"] = True

                if pe_types["openai"] or infra.openai_account:
                    pe_openai = PrivateEndpoint("Private Endpoint: Azure OpenAI")
                    pe_nodes["openai"] = pe_openai
                    pe_subnet - Edge(label="hosts") - pe_openai

                if pe_types["blob"] or infra.storage_account:
                    pe_blob = PrivateEndpoint("Private Endpoint: Storage Blob")
                    pe_nodes["blob"] = pe_blob
                    pe_subnet - Edge(label="hosts") - pe_blob

                if pe_types["speech"] or infra.speech_enabled:
                    pe_speech = PrivateEndpoint("Private Endpoint: Azure Speech")
                    pe_nodes["speech"] = pe_speech
                    pe_subnet - Edge(label="hosts") - pe_speech

                if pe_types["web"]:
                    pe_web = PrivateEndpoint("Private Endpoint: Web App (optional)")
                    pe_nodes["web"] = pe_web
                    pe_subnet - Edge(label="hosts") - pe_web

            # Analytics/PostgreSQL Subnet
            pg_subnet_info = next((s for s in infra.subnets if "analytics" in s["name"].lower() or "pg" in s["name"].lower()), None)
            if pg_subnet_info or infra.postgres_server:
                pg_cidr = pg_subnet_info["cidr"] if pg_subnet_info else "10.10.3.0/24"
                pg_subnet_name = pg_subnet_info["name"] if pg_subnet_info else "PULSE-analytics-pg-subnet"

                with Cluster(f"Analytics Subnet: {pg_subnet_name} ({pg_cidr})"):
                    analytics_subnet = Subnets(f"Subnet: {pg_subnet_name}")
                    subnet_nodes["analytics"] = analytics_subnet

                    pg_name = infra.postgres_server or f"pg-PULSE-training-analytics-{env}"
                    analytics_pg = DatabaseForPostgresqlServers(f"Analytics PostgreSQL Flexible Server\n({pg_name})")
                    analytics_subnet - Edge(label="hosts") - analytics_pg

        # Private DNS Zones
        with Cluster("Private DNS Zones + VNet Links"):
            vnet_node = VirtualNetworks("Virtual Network")
            dns_nodes = {}

            # Determine which DNS zones exist
            dns_types = set()
            for zone in infra.dns_zones:
                zone_name = zone["name"].lower()
                if "openai" in zone_name:
                    dns_types.add("openai")
                elif "blob" in zone_name:
                    dns_types.add("blob")
                elif "cognitiveservices" in zone_name:
                    dns_types.add("speech")
                elif "azurewebsites" in zone_name:
                    dns_types.add("web")
                elif "postgres" in zone_name:
                    dns_types.add("pg")

            # Always show DNS zones for resources that exist
            if infra.openai_account or "openai" in dns_types:
                dns_openai = DNSPrivateZones("Zone: privatelink.openai.azure.com")
                dns_nodes["openai"] = dns_openai
                dns_openai - Edge(label="vnet link") - vnet_node

            if infra.storage_account or "blob" in dns_types:
                dns_blob = DNSPrivateZones("Zone: privatelink.blob.core.windows.net")
                dns_nodes["blob"] = dns_blob
                dns_blob - Edge(label="vnet link") - vnet_node

            if infra.speech_enabled or "speech" in dns_types:
                dns_speech = DNSPrivateZones("Zone: privatelink.cognitiveservices.azure.com")
                dns_nodes["speech"] = dns_speech
                dns_speech - Edge(label="vnet link") - vnet_node

            if "web" in dns_types:
                dns_web = DNSPrivateZones("Zone: privatelink.azurewebsites.net (optional)")
                dns_nodes["web"] = dns_web
                dns_web - Edge(label="vnet link (optional)") - vnet_node

            if infra.postgres_server or "pg" in dns_types:
                dns_pg = DNSPrivateZones("Zone: privatelink.postgres.database.azure.com")
                dns_nodes["pg"] = dns_pg
                dns_pg - Edge(label="vnet link") - vnet_node

            # VNet contains subnets
            for subnet in subnet_nodes.values():
                vnet_node - Edge(label="contains") - subnet

        # Azure OpenAI
        if infra.openai_account or infra.openai_deployments:
            with Cluster("Azure OpenAI: Cognitive Account + Deployments"):
                account_name = infra.openai_account or f"cog-PULSE-training-{env}"
                openai_account = AzureOpenAI(f"Cognitive Account ({account_name})")

                deployment_nodes = []
                if infra.openai_deployments:
                    for dep in infra.openai_deployments:
                        dep_name = dep["name"]
                        capacity = dep.get("capacity", 0)
                        # Mark as disabled if capacity is 0
                        label = f"Deployment: {dep_name}"
                        if capacity == 0:
                            label += " (disabled)"
                        dep_node = AzureOpenAI(label)
                        deployment_nodes.append(dep_node)
                        openai_account >> dep_node
                else:
                    # Default deployments if none found (matches modules/openai/main.tf)
                    default_deps = [
                        ("Persona-Core-Chat", True),
                        ("Persona-High-Reasoning", True),
                        ("PULSE-Audio-Realtime", True),
                        ("Persona-Visual-Asset", False),  # Conditional, often disabled
                    ]
                    for name, enabled in default_deps:
                        label = f"Deployment: {name}"
                        if not enabled:
                            label += " (disabled)"
                        dep_node = AzureOpenAI(label)
                        deployment_nodes.append(dep_node)
                        openai_account >> dep_node

        # Azure Speech Service
        if infra.speech_enabled or infra.speech_account:
            with Cluster("Azure Speech Service"):
                speech_name = infra.speech_account or f"speech-PULSE-training-{env}"
                speech_account = CognitiveServices(f"Speech Account\n({speech_name})")
                avatar_service = CognitiveServices("Avatar Service\n(WebRTC streaming)")
                speech_account >> avatar_service

        # Storage Account
        if infra.storage_account or infra.storage_containers:
            with Cluster("Storage Account + Containers"):
                storage_name = infra.storage_account or "sa-<name>"
                storage = StorageAccounts(f"Storage Account ({storage_name})")

                # Only 2 containers exist in Terraform (main.tf lines 218-228)
                containers = infra.storage_containers if infra.storage_containers else [
                    "certification-materials", "interaction-logs"
                ]
                for container in containers:
                    container_node = StorageAccounts(f"Container: {container}")
                    storage >> container_node

        # Observability
        if infra.log_analytics or infra.app_insights:
            with Cluster("Observability"):
                if infra.log_analytics:
                    law = Logs(f"Log Analytics Workspace ({infra.log_analytics})")
                else:
                    law = Logs(f"Log Analytics Workspace (law-PULSE-training-{env})")

                if infra.app_insights:
                    ai = ApplicationInsights(f"Application Insights ({infra.app_insights})")
                else:
                    ai = ApplicationInsights(f"Application Insights (appi-PULSE-training-{env})")

        # Connectivity edges
        if "openai" in pe_nodes:
            web >> Edge(label="HTTPS via Private Endpoint") >> pe_nodes["openai"]
            func >> Edge(label="HTTPS via Private Endpoint") >> pe_nodes["openai"]
            pe_nodes["openai"] >> Edge(label="account") >> openai_account

        if infra.speech_enabled and "speech" in pe_nodes:
            func >> Edge(label="Avatar Token") >> pe_nodes["speech"]
            pe_nodes["speech"] >> Edge(label="account") >> speech_account
            web >> Edge(label="WebRTC (Avatar Stream)", style="dashed") >> avatar_service

        if "blob" in pe_nodes:
            web >> Edge(label="Blob via Private Endpoint") >> pe_nodes["blob"]
            pe_nodes["blob"] >> Edge(label="blob") >> storage

        func >> Edge(label="AzureWebJobsStorage") >> storage

        if infra.postgres_server:
            web >> Edge(label="PULSE_ANALYTICS_DB_HOST") >> analytics_pg
            func >> Edge(label="PULSE_ANALYTICS_DB_HOST") >> analytics_pg

        if "web" in pe_nodes and "web" in dns_nodes:
            web >> Edge(label="Private Endpoint (optional)") >> pe_nodes["web"]
            pe_nodes["web"] >> Edge(label="DNS zone group") >> dns_nodes["web"]

        web >> Edge(label="VNet Swift Integration") >> vnet_node
        func >> Edge(label="VNet Swift Integration") >> vnet_node

        # Diagnostic edges
        openai_account >> Edge(label="diag_openai") >> law
        storage >> Edge(label="diag_storage") >> law
        web >> Edge(label="diag_webapp") >> law
        func >> Edge(label="diag_functionapp") >> law
        web >> Edge(label="AppInsights") >> ai
        func >> Edge(label="AppInsights") >> ai


# =============================================================================
# Static Topology (Legacy Fallback)
# =============================================================================

def build_topology_static():
    """Build static topology - legacy fallback when no state file provided."""
    with Cluster("Resource Group: rg-PULSE-training-<env>"):
        with Cluster("Virtual Network: vnet-PULSE-training-<env> (10.10.0.0/16)"):
            with Cluster("App Subnet: PULSE-app-subnet (10.10.1.0/24)"):
                app_subnet = Subnets("Subnet: PULSE-app-subnet")
                plan = AppServicePlans("App Service Plan (asp-PULSE-training-<env>)")
                web = AppServices("Web App: app-PULSE-training-ui-<env>")
                func = FunctionApps(
                    "Function App: func-PULSE-training-scenario-<env>\n"
                    "Routes: /session/*, /audio/chunk, /avatar/token, /admin/*"
                )
                app_subnet - Edge(label="hosts") - plan
                app_subnet - Edge(label="hosts") - web
                app_subnet - Edge(label="hosts") - func
                plan >> web
                plan >> func

            with Cluster("Private Endpoints Subnet: PULSE-private-endpoints-subnet (10.10.2.0/24)"):
                pe_subnet = Subnets("Subnet: PULSE-private-endpoints-subnet")
                pe_openai = PrivateEndpoint("Private Endpoint: Azure OpenAI")
                pe_blob = PrivateEndpoint("Private Endpoint: Storage Blob")
                pe_speech = PrivateEndpoint("Private Endpoint: Azure Speech")
                pe_web = PrivateEndpoint("Private Endpoint: Web App (optional)")
                pe_subnet - Edge(label="hosts") - pe_openai
                pe_subnet - Edge(label="hosts") - pe_blob
                pe_subnet - Edge(label="hosts") - pe_speech
                pe_subnet - Edge(label="hosts") - pe_web

            with Cluster("Analytics Subnet: PULSE-analytics-pg-subnet (10.10.3.0/24)"):
                analytics_subnet = Subnets("Subnet: PULSE-analytics-pg-subnet")
                analytics_pg = DatabaseForPostgresqlServers(
                    "Analytics PostgreSQL Flexible Server\n"
                    "(pg-PULSE-training-analytics-<env>)"
                )
                analytics_subnet - Edge(label="hosts") - analytics_pg

        with Cluster("Private DNS Zones + VNet Links"):
            vnet_node = VirtualNetworks("Virtual Network")
            dns_openai = DNSPrivateZones("Zone: privatelink.openai.azure.com")
            dns_blob = DNSPrivateZones("Zone: privatelink.blob.core.windows.net")
            dns_speech = DNSPrivateZones("Zone: privatelink.cognitiveservices.azure.com")
            dns_web = DNSPrivateZones("Zone: privatelink.azurewebsites.net (optional)")
            dns_pg = DNSPrivateZones("Zone: privatelink.postgres.database.azure.com")
            vnet_node - Edge(label="contains") - app_subnet
            vnet_node - Edge(label="contains") - pe_subnet
            vnet_node - Edge(label="contains") - analytics_subnet
            dns_openai - Edge(label="vnet link") - vnet_node
            dns_blob - Edge(label="vnet link") - vnet_node
            dns_speech - Edge(label="vnet link") - vnet_node
            dns_web - Edge(label="vnet link (optional)") - vnet_node
            dns_pg - Edge(label="vnet link") - vnet_node

        with Cluster("Azure OpenAI: Cognitive Account + Deployments"):
            openai_account = AzureOpenAI("Cognitive Account (cog-PULSE-training-<env>)")
            # Deployments match modules/openai/main.tf
            dep_core = AzureOpenAI("Deployment: Persona-Core-Chat")
            dep_high = AzureOpenAI("Deployment: Persona-High-Reasoning")
            dep_audio = AzureOpenAI("Deployment: PULSE-Audio-Realtime")
            dep_visual = AzureOpenAI("Deployment: Persona-Visual-Asset (disabled)")
            openai_account >> dep_core
            openai_account >> dep_high
            openai_account >> dep_audio
            openai_account >> dep_visual

        with Cluster("Azure Speech Service"):
            speech_account = CognitiveServices("Speech Account\n(speech-PULSE-training-<env>)")
            avatar_service = CognitiveServices("Avatar Service\n(WebRTC streaming)")

        with Cluster("Storage Account + Containers"):
            storage = StorageAccounts("Storage Account (sa-<name>)")
            # Only 2 containers defined in main.tf (lines 218-228)
            container_cert = StorageAccounts("Container: certification-materials")
            container_logs = StorageAccounts("Container: interaction-logs")
            storage >> container_cert
            storage >> container_logs

        with Cluster("Observability"):
            law = Logs("Log Analytics Workspace (law-PULSE-training-<env>)")
            ai = ApplicationInsights("Application Insights (appi-PULSE-training-<env>)")

        # Connectivity
        web >> Edge(label="HTTPS via Private Endpoint") >> pe_openai
        func >> Edge(label="HTTPS via Private Endpoint") >> pe_openai
        pe_openai >> Edge(label="account") >> openai_account

        func >> Edge(label="Avatar Token") >> pe_speech
        pe_speech >> Edge(label="account") >> speech_account
        speech_account >> avatar_service
        web >> Edge(label="WebRTC (Avatar Stream)", style="dashed") >> avatar_service

        web >> Edge(label="Blob via Private Endpoint") >> pe_blob
        pe_blob >> Edge(label="blob") >> storage

        func >> Edge(label="AzureWebJobsStorage") >> storage

        web >> Edge(label="PULSE_ANALYTICS_DB_HOST") >> analytics_pg
        func >> Edge(label="PULSE_ANALYTICS_DB_HOST") >> analytics_pg

        web >> Edge(label="Private Endpoint (optional)") >> pe_web
        pe_web >> Edge(label="DNS zone group") >> dns_web

        web >> Edge(label="VNet Swift Integration") >> vnet_node
        func >> Edge(label="VNet Swift Integration") >> vnet_node

        openai_account >> Edge(label="diag_openai") >> law
        storage >> Edge(label="diag_storage") >> law
        web >> Edge(label="diag_webapp") >> law
        func >> Edge(label="diag_functionapp") >> law

        web >> Edge(label="AppInsights") >> ai
        func >> Edge(label="AppInsights") >> ai
        func >> law


# =============================================================================
# Draw.io XML Renderer (Dynamic)
# =============================================================================

def render_drawio_dynamic(output_basename: str, infra: ParsedInfrastructure) -> None:
    """Render the topology as a draw.io XML document from parsed state."""
    env = infra.environment or "<env>"

    mxfile = Element("mxfile", attrib={"host": "app.diagrams.net"})
    diagram = SubElement(mxfile, "diagram", attrib={"id": "PULSE", "name": "PULSE Azure Network"})
    model = SubElement(
        diagram,
        "mxGraphModel",
        attrib={
            "dx": "1200", "dy": "800", "grid": "1", "gridSize": "10",
            "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1",
            "fold": "1", "page": "1", "pageScale": "1",
            "pageWidth": "1654", "pageHeight": "1169",
        },
    )
    root = SubElement(model, "root")
    SubElement(root, "mxCell", attrib={"id": "0"})
    SubElement(root, "mxCell", attrib={"id": "1", "parent": "0"})

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

    # Build vertices dynamically
    rg_name = infra.resource_group or f"rg-PULSE-training-{env}"
    add_vertex("rg", f"Resource Group: {rg_name}", 40, 40, 1600, 900)

    vnet_name = infra.vnet_name or f"vnet-PULSE-training-{env}"
    vnet_cidr = infra.vnet_cidr or "10.10.0.0/16"
    add_vertex("vnet", f"Virtual Network: {vnet_name} ({vnet_cidr})", 80, 80, 700, 400, parent="rg")

    # Subnets
    add_vertex("subnet_app", "Subnet: PULSE-app-subnet", 120, 140, 320, 140, parent="vnet")
    add_vertex("subnet_pe", "Subnet: PULSE-private-endpoints-subnet", 480, 140, 320, 180, parent="vnet")
    add_vertex("subnet_analytics", "Subnet: PULSE-analytics-pg-subnet", 120, 300, 320, 100, parent="vnet")

    # App components
    plan_name = infra.app_service_plan or f"asp-PULSE-training-{env}"
    add_vertex("plan", f"App Service Plan ({plan_name})", 140, 160, 220, 50, parent="subnet_app")

    web_name = infra.web_app or f"app-PULSE-training-ui-{env}"
    add_vertex("web", f"Web App: {web_name}", 140, 220, 220, 50, parent="subnet_app")

    func_name = infra.function_app or f"func-PULSE-training-scenario-{env}"
    routes = ", ".join(infra.function_routes) if infra.function_routes else "/session/*, /audio/chunk, /avatar/token, /admin/*"
    add_vertex("func", f"Function App: {func_name}\\nRoutes: {routes}", 140, 280, 280, 50, parent="subnet_app")

    # Private Endpoints
    add_vertex("pe_openai", "Private Endpoint: Azure OpenAI", 500, 160, 260, 40, parent="subnet_pe")
    add_vertex("pe_blob", "Private Endpoint: Storage Blob", 500, 210, 260, 40, parent="subnet_pe")
    if infra.speech_enabled:
        add_vertex("pe_speech", "Private Endpoint: Azure Speech", 500, 260, 260, 40, parent="subnet_pe")
    add_vertex("pe_web", "Private Endpoint: Web App (optional)", 500, 310, 260, 40, parent="subnet_pe")

    # DNS Zones
    y_offset = 80
    add_vertex("dns_openai", "Zone: privatelink.openai.azure.com", 840, y_offset, 320, 45, parent="rg")
    y_offset += 55
    add_vertex("dns_blob", "Zone: privatelink.blob.core.windows.net", 840, y_offset, 320, 45, parent="rg")
    y_offset += 55
    if infra.speech_enabled:
        add_vertex("dns_speech", "Zone: privatelink.cognitiveservices.azure.com", 840, y_offset, 360, 45, parent="rg")
        y_offset += 55
    add_vertex("dns_web", "Zone: privatelink.azurewebsites.net (optional)", 840, y_offset, 360, 45, parent="rg")
    y_offset += 55
    add_vertex("dns_pg", "Zone: privatelink.postgres.database.azure.com", 840, y_offset, 360, 45, parent="rg")

    # OpenAI Account and Deployments
    openai_name = infra.openai_account or f"cog-PULSE-training-{env}"
    add_vertex("openai_account", f"Azure OpenAI Account ({openai_name})", 840, 380, 380, 220, parent="rg")

    dep_y = 420
    # Default deployments match modules/openai/main.tf
    for i, dep in enumerate(infra.openai_deployments if infra.openai_deployments else [
        {"name": "Persona-Core-Chat", "capacity": 50},
        {"name": "Persona-High-Reasoning", "capacity": 20},
        {"name": "PULSE-Audio-Realtime", "capacity": 4},
        {"name": "Persona-Visual-Asset", "capacity": 0},  # Conditional, often disabled
    ]):
        label = f"Deployment: {dep['name']}"
        if dep.get("capacity", 1) == 0:
            label += " (disabled)"
        add_vertex(f"dep_{i}", label, 860, dep_y, 340, 30, parent="openai_account")
        dep_y += 35

    # Speech Service
    if infra.speech_enabled:
        speech_name = infra.speech_account or f"speech-PULSE-training-{env}"
        add_vertex("speech_account", f"Azure Speech Account ({speech_name})", 1260, 380, 300, 100, parent="rg")
        add_vertex("avatar_service", "Avatar Service (WebRTC)", 1280, 440, 260, 30, parent="speech_account")

    # Storage
    storage_name = infra.storage_account or "sa-<name>"
    add_vertex("storage", f"Storage Account ({storage_name})", 1260, 520, 280, 180, parent="rg")

    # Only 2 containers defined in main.tf (lines 218-228)
    containers = infra.storage_containers if infra.storage_containers else [
        "certification-materials", "interaction-logs"
    ]
    cont_y = 560
    for i, container in enumerate(containers[:4]):  # Limit to 4
        add_vertex(f"container_{i}", f"Container: {container}", 1280, cont_y, 240, 25, parent="storage")
        cont_y += 30

    # Observability
    law_name = infra.log_analytics or f"law-PULSE-training-{env}"
    add_vertex("law", f"Log Analytics Workspace ({law_name})", 1260, 80, 280, 50, parent="rg")

    ai_name = infra.app_insights or f"appi-PULSE-training-{env}"
    add_vertex("ai", f"Application Insights ({ai_name})", 1260, 140, 280, 50, parent="rg")

    # PostgreSQL
    pg_name = infra.postgres_server or f"pg-PULSE-training-analytics-{env}"
    add_vertex("analytics_pg", f"PostgreSQL Flexible Server ({pg_name})", 140, 320, 300, 50, parent="subnet_analytics")

    # Edges
    add_edge("e_plan_web", "plan", "web")
    add_edge("e_plan_func", "plan", "func")
    add_edge("e_web_pe_openai", "web", "pe_openai")
    add_edge("e_func_pe_openai", "func", "pe_openai")
    add_edge("e_pe_openai_openai", "pe_openai", "openai_account", label="account")
    add_edge("e_web_pe_blob", "web", "pe_blob")
    add_edge("e_pe_blob_storage", "pe_blob", "storage", label="blob")
    add_edge("e_func_storage", "func", "storage", label="AzureWebJobsStorage")
    add_edge("e_web_pe_web", "web", "pe_web")
    add_edge("e_pe_web_dns_web", "pe_web", "dns_web", label="DNS zone group")
    add_edge("e_dns_openai_vnet", "dns_openai", "vnet", label="vnet link")
    add_edge("e_dns_blob_vnet", "dns_blob", "vnet", label="vnet link")
    add_edge("e_dns_web_vnet", "dns_web", "vnet", label="vnet link (optional)")
    add_edge("e_dns_pg_vnet", "dns_pg", "vnet", label="vnet link")

    if infra.speech_enabled:
        add_edge("e_func_pe_speech", "func", "pe_speech", label="Avatar Token")
        add_edge("e_pe_speech_speech", "pe_speech", "speech_account", label="account")
        add_edge("e_speech_avatar", "speech_account", "avatar_service")
        add_edge("e_web_avatar", "web", "avatar_service", label="WebRTC Stream")
        add_edge("e_dns_speech_vnet", "dns_speech", "vnet", label="vnet link")

    for i in range(len(infra.openai_deployments) if infra.openai_deployments else 5):
        add_edge(f"e_openai_dep_{i}", "openai_account", f"dep_{i}")

    for i in range(min(len(containers), 4)):
        add_edge(f"e_storage_cont_{i}", "storage", f"container_{i}")

    add_edge("e_openai_law", "openai_account", "law", label="diagnostics")
    add_edge("e_storage_law", "storage", "law", label="diagnostics")
    add_edge("e_web_law", "web", "law", label="diagnostics")
    add_edge("e_func_law", "func", "law", label="diagnostics")
    add_edge("e_web_ai", "web", "ai", label="AppInsights")
    add_edge("e_func_ai", "func", "ai", label="AppInsights")
    add_edge("e_web_analytics_pg", "web", "analytics_pg", label="PULSE_ANALYTICS_DB_HOST")
    add_edge("e_func_analytics_pg", "func", "analytics_pg", label="PULSE_ANALYTICS_DB_HOST")

    tree = ElementTree(mxfile)
    output_path = Path(f"{output_basename}.drawio")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


def render_drawio_static(output_basename: str) -> None:
    """Render static draw.io XML - legacy fallback."""
    # Create a default infrastructure for static rendering
    # Matches actual Terraform resources in modules/openai/main.tf and main.tf
    infra = ParsedInfrastructure(
        speech_enabled=True,
        openai_deployments=[
            {"name": "Persona-Core-Chat", "capacity": 50},
            {"name": "Persona-High-Reasoning", "capacity": 20},
            {"name": "PULSE-Audio-Realtime", "capacity": 4},
            {"name": "Persona-Visual-Asset", "capacity": 0},  # Conditional, often disabled
        ],
        storage_containers=["certification-materials", "interaction-logs"],
    )
    render_drawio_dynamic(output_basename, infra)


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Render Azure network diagrams for PULSE infrastructure.\n\n"
            "DYNAMIC MODE (recommended):\n"
            "  Reads from terraform show -json output for accurate diagrams.\n\n"
            "STATIC MODE (legacy):\n"
            "  Uses hardcoded topology when no state file provided.\n"
        ),
        formatter_class=RawTextHelpFormatter,
        epilog=(
            "Examples:\n\n"
            "  # Generate state file and render diagram (recommended)\n"
            "  cd /path/to/terraform\n"
            "  terraform show -json > tfstate.json\n"
            "  python docs/PULSE_network_diagram.py --state tfstate.json\n\n"
            "  # Static mode (legacy, hardcoded topology)\n"
            "  python docs/PULSE_network_diagram.py\n\n"
            "  # Generate draw.io XML for Lucidchart\n"
            "  python docs/PULSE_network_diagram.py --state tfstate.json --drawio\n\n"
            "Requirements:\n"
            "  pip install diagrams graphviz\n"
            "  brew install graphviz  # macOS\n"
        ),
    )
    parser.add_argument(
        "--state",
        type=str,
        help="Path to terraform show -json output file. If not provided, uses static topology.",
    )
    parser.add_argument(
        "--tf-path",
        type=str,
        default=str(Path(__file__).resolve().parents[1]),
        help="Path to Terraform project root (for file existence checks).",
    )
    parser.add_argument(
        "--output-basename",
        type=str,
        default="PULSE-network-diagram",
        help="Base filename (without extension) for outputs.",
    )
    parser.add_argument(
        "--direction",
        type=str,
        choices=["LR", "TB", "BT", "RL"],
        default="LR",
        help="Diagram direction (Left-to-Right, Top-to-Bottom, etc.)",
    )
    parser.add_argument(
        "--drawio",
        action="store_true",
        help="Generate draw.io XML file instead of PNG/SVG.",
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

    # Determine mode
    infra = None
    if args.state:
        print(f"[info] Loading Terraform state from: {args.state}")
        infra = load_state_file(args.state)
        if infra:
            print(f"[info] Parsed state successfully")
            print(f"  - Resource Group: {infra.resource_group}")
            print(f"  - VNet: {infra.vnet_name} ({infra.vnet_cidr})")
            print(f"  - Subnets: {len(infra.subnets)}")
            print(f"  - OpenAI Deployments: {len(infra.openai_deployments)}")
            print(f"  - Speech Service: {'Enabled' if infra.speech_enabled else 'Disabled'}")
            print(f"  - Storage Containers: {len(infra.storage_containers)}")
        else:
            print("[warn] Failed to parse state, falling back to static mode")
    else:
        print("[info] No state file provided, using static topology")

    # Check terraform files exist
    tf_root = Path(args.tf_path).resolve()
    for tf_file in ["main.tf", "variables.tf", "outputs.tf"]:
        path = tf_root / tf_file
        status = "OK" if path.exists() else "MISSING"
        print(f"[check] {tf_file}: {status}")

    # Render
    if args.drawio:
        print("[render] Generating draw.io XML...")
        if infra:
            render_drawio_dynamic(args.output_basename, infra)
        else:
            render_drawio_static(args.output_basename)
        print(f"[done] Output: {args.output_basename}.drawio")
    else:
        print("[render] Generating PNG...")
        with Diagram(
            "PULSE H2 - Azure Network Architecture",
            filename=args.output_basename,
            outformat="png",
            direction=args.direction,
            show=False,
        ):
            if infra:
                build_topology_dynamic(infra)
            else:
                build_topology_static()

        print("[render] Generating SVG...")
        with Diagram(
            "PULSE H2 - Azure Network Architecture",
            filename=args.output_basename,
            outformat="svg",
            direction=args.direction,
            show=False,
        ):
            if infra:
                build_topology_dynamic(infra)
            else:
                build_topology_static()

        print(f"[done] Outputs:")
        print(f"  - {args.output_basename}.png")
        print(f"  - {args.output_basename}.svg")


if __name__ == "__main__":
    main()
