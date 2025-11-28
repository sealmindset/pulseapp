import argparse
from argparse import RawTextHelpFormatter
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree

from diagrams import Diagram, Cluster, Edge
from diagrams.azure.network import VirtualNetworks, Subnets, PrivateEndpoint, DNSPrivateZones
from diagrams.azure.ml import AzureOpenAI
from diagrams.azure.storage import StorageAccounts
from diagrams.azure.web import AppServices, AppServicePlans
from diagrams.azure.compute import FunctionApps
from diagrams.azure.monitor import Logs
from diagrams.azure.devops import ApplicationInsights
from diagrams.azure.database import DatabaseForPostgresqlServers


def build_topology():
    with Cluster("Resource Group: rg-PULSE-training-<env>"):
        # Virtual network, subnets, and app hosting
        with Cluster("Virtual Network: vnet-PULSE-training-<env> (10.10.0.0/16)"):
            with Cluster("App Subnet: PULSE-app-subnet (10.10.1.0/24)"):
                app_subnet = Subnets("Subnet: PULSE-app-subnet")
                plan = AppServicePlans("App Service Plan (asp-PULSE-training-<env>)")
                web = AppServices("Web App: app-PULSE-training-ui-<env>")
                func = FunctionApps(
                    "Function App: func-PULSE-training-scenario-<env>\n"
                    "Routes: /session/*, /audio/chunk, /trainer/pulse/step, /admin/*"
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
                pe_web = PrivateEndpoint("Private Endpoint: Web App (optional)")
                pe_subnet - Edge(label="hosts") - pe_openai
                pe_subnet - Edge(label="hosts") - pe_blob
                pe_subnet - Edge(label="hosts") - pe_web

            with Cluster("Analytics Subnet: PULSE-analytics-pg-subnet (10.10.3.0/24)"):
                analytics_subnet = Subnets("Subnet: PULSE-analytics-pg-subnet")
                analytics_pg = DatabaseForPostgresqlServers(
                    "Analytics PostgreSQL Flexible Server\n"
                    "(pg-PULSE-training-analytics-<env>)"
                )
                analytics_subnet - Edge(label="hosts") - analytics_pg

        # Private DNS zones and VNet links
        with Cluster("Private DNS Zones + VNet Links"):
            vnet_node = VirtualNetworks("Virtual Network")
            dns_openai = DNSPrivateZones("Zone: privatelink.openai.azure.com")
            dns_blob = DNSPrivateZones("Zone: privatelink.blob.core.windows.net")
            dns_web = DNSPrivateZones("Zone: privatelink.azurewebsites.net (optional)")
            dns_pg = DNSPrivateZones("Zone: privatelink.postgres.database.azure.com")
            vnet_node - Edge(label="contains") - app_subnet
            vnet_node - Edge(label="contains") - pe_subnet
            vnet_node - Edge(label="contains") - analytics_subnet
            dns_openai - Edge(label="vnet link") - vnet_node
            dns_blob - Edge(label="vnet link") - vnet_node
            dns_web - Edge(label="vnet link (optional)") - vnet_node
            dns_pg - Edge(label="vnet link") - vnet_node

        # Azure OpenAI account and deployments
        with Cluster("Azure OpenAI: Cognitive Account + Deployments"):
            openai_account = AzureOpenAI("Cognitive Account (cog-PULSE-training-<env>)")
            dep_core = AzureOpenAI("Deployment: Persona-Core-Chat")
            dep_high = AzureOpenAI("Deployment: Persona-High-Reasoning")
            dep_audio = AzureOpenAI("Deployment: PULSE-Audio-Realtime")
            dep_visual = AzureOpenAI("Deployment: Persona-Visual-Asset")
            openai_account >> dep_core
            openai_account >> dep_high
            openai_account >> dep_audio
            openai_account >> dep_visual

        # Storage account and key containers
        with Cluster("Storage Account + Containers"):
            storage = StorageAccounts("Storage Account (sa-<name>)")
            container_cert = StorageAccounts("Container: certification-materials")
            container_logs = StorageAccounts("Container: interaction-logs")
            container_prompts = StorageAccounts("Container: prompts")
            container_trainer_logs = StorageAccounts("Container: trainer-change-logs")
            storage >> container_cert
            storage >> container_logs
            storage >> container_prompts
            storage >> container_trainer_logs

        # Observability (Log Analytics + Application Insights)
        with Cluster("Observability"):
            law = Logs("Log Analytics Workspace (law-PULSE-training-<env>)")
            ai = ApplicationInsights("Application Insights (appi-PULSE-training-<env>)")

        # Connectivity: App Services to Private Endpoints and services
        web >> Edge(label="HTTPS via Private Endpoint") >> pe_openai
        func >> Edge(label="HTTPS via Private Endpoint") >> pe_openai
        pe_openai >> Edge(label="account") >> openai_account

        web >> Edge(label="Blob via Private Endpoint") >> pe_blob
        pe_blob >> Edge(label="blob") >> storage

        # Function App talks to Storage using connection string (AzureWebJobsStorage)
        func >> Edge(label="AzureWebJobsStorage") >> storage

        # App Services use analytics PostgreSQL via VNet + private DNS (no public access)
        web >> Edge(label="PULSE_ANALYTICS_DB_HOST") >> analytics_pg
        func >> Edge(label="PULSE_ANALYTICS_DB_HOST") >> analytics_pg

        # Optional Web App Private Endpoint (enable_webapp_private_endpoint)
        web >> Edge(label="Private Endpoint (optional)") >> pe_web
        pe_web >> Edge(label="DNS zone group") >> dns_web

        # App Service VNet integration (Swift connections)
        web >> Edge(label="VNet Swift Integration") >> vnet_node
        func >> Edge(label="VNet Swift Integration") >> vnet_node

        # Diagnostic settings: logs/metrics to Log Analytics
        openai_account >> Edge(label="diag_openai") >> law
        storage >> Edge(label="diag_storage") >> law
        web >> Edge(label="diag_webapp") >> law
        func >> Edge(label="diag_functionapp") >> law

        # Application Insights telemetry
        web >> Edge(label="AppInsights") >> ai
        func >> Edge(label="AppInsights") >> ai
        func >> law


def render_drawio(output_basename: str) -> None:
    """Render the topology as a draw.io (.drawio) XML document.

    This can be imported into Lucidchart via the "Import Diagram" flow
    (choose draw.io) or opened directly in diagrams.net.
    """

    mxfile = Element("mxfile", attrib={"host": "app.diagrams.net"})
    diagram = SubElement(mxfile, "diagram", attrib={"id": "PULSE", "name": "PULSE Azure Network"})
    model = SubElement(
        diagram,
        "mxGraphModel",
        attrib={
            "dx": "1200",
            "dy": "800",
            "grid": "1",
            "gridSize": "10",
            "guides": "1",
            "tooltips": "1",
            "connect": "1",
            "arrows": "1",
            "fold": "1",
            "page": "1",
            "pageScale": "1",
            "pageWidth": "1654",
            "pageHeight": "1169",
        },
    )
    root = SubElement(model, "root")
    SubElement(root, "mxCell", attrib={"id": "0"})
    SubElement(root, "mxCell", attrib={"id": "1", "parent": "0"})

    def add_vertex(cell_id: str, label: str, x: int, y: int, w: int, h: int, parent: str = "1") -> None:
        cell = SubElement(
            root,
            "mxCell",
            attrib={
                "id": cell_id,
                "value": label,
                "style": "rounded=1;whiteSpace=wrap;html=1;",
                "vertex": "1",
                "parent": parent,
            },
        )
        SubElement(
            cell,
            "mxGeometry",
            attrib={"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"},
        )

    def add_edge(cell_id: str, source: str, target: str, label: str = "", parent: str = "1") -> None:
        cell = SubElement(
            root,
            "mxCell",
            attrib={
                "id": cell_id,
                "value": label,
                "style": "endArrow=block;html=1;",
                "edge": "1",
                "parent": parent,
                "source": source,
                "target": target,
            },
        )
        SubElement(cell, "mxGeometry", attrib={"relative": "1", "as": "geometry"})

    # Vertices (simple grid layout)
    add_vertex("rg", "Resource Group: rg-PULSE-training-<env>", 40, 40, 1500, 800)
    add_vertex("vnet", "Virtual Network: vnet-PULSE-training-<env>", 80, 80, 700, 350, parent="rg")
    add_vertex("subnet_app", "Subnet: PULSE-app-subnet", 120, 140, 320, 120, parent="vnet")
    add_vertex("subnet_pe", "Subnet: PULSE-private-endpoints-subnet", 480, 140, 320, 120, parent="vnet")
    add_vertex("subnet_analytics", "Subnet: PULSE-analytics-pg-subnet", 120, 260, 320, 100, parent="vnet")

    add_vertex("plan", "App Service Plan (asp-PULSE-training-<env>)", 140, 300, 220, 60, parent="subnet_app")
    add_vertex("web", "Web App: app-PULSE-training-ui-<env>", 140, 380, 220, 60, parent="subnet_app")
    add_vertex(
        "func",
        "Function App: func-PULSE-training-scenario-<env>\\nRoutes: /session/*, /audio/chunk, /trainer/pulse/step, /admin/*",
        140,
        460,
        260,
        60,
        parent="subnet_app",
    )

    add_vertex("pe_openai", "Private Endpoint: Azure OpenAI", 500, 300, 260, 60, parent="subnet_pe")
    add_vertex("pe_blob", "Private Endpoint: Storage Blob", 500, 380, 260, 60, parent="subnet_pe")
    add_vertex("pe_web", "Private Endpoint: Web App (optional)", 500, 460, 260, 60, parent="subnet_pe")

    add_vertex("dns_openai", "Zone: privatelink.openai.azure.com", 840, 80, 320, 60, parent="rg")
    add_vertex("dns_blob", "Zone: privatelink.blob.core.windows.net", 840, 160, 320, 60, parent="rg")
    add_vertex("dns_web", "Zone: privatelink.azurewebsites.net (optional)", 840, 240, 360, 60, parent="rg")

    add_vertex("openai_account", "Azure OpenAI Account (cog-PULSE-training-<env>)", 840, 340, 360, 80, parent="rg")
    add_vertex("dep_core", "Deployment: Persona-Core-Chat", 860, 440, 280, 40, parent="openai_account")
    add_vertex("dep_high", "Deployment: Persona-High-Reasoning", 860, 490, 280, 40, parent="openai_account")
    add_vertex("dep_audio", "Deployment: PULSE-Audio-Realtime", 860, 540, 280, 40, parent="openai_account")
    add_vertex("dep_visual", "Deployment: Persona-Visual-Asset", 860, 590, 280, 40, parent="openai_account")

    add_vertex("storage", "Storage Account (sa-<name>)", 1240, 340, 260, 80, parent="rg")
    add_vertex("container_cert", "Container: certification-materials", 1260, 440, 260, 40, parent="storage")
    add_vertex("container_logs", "Container: interaction-logs", 1260, 490, 260, 40, parent="storage")
    add_vertex("container_prompts", "Container: prompts", 1260, 540, 260, 40, parent="storage")
    add_vertex("container_trainer_logs", "Container: trainer-change-logs", 1260, 590, 260, 40, parent="storage")

    add_vertex("law", "Log Analytics Workspace (law-PULSE-training-<env>)", 1240, 80, 280, 60, parent="rg")
    add_vertex("ai", "Application Insights (appi-PULSE-training-<env>)", 1240, 160, 280, 60, parent="rg")

    add_vertex(
        "analytics_pg",
        "Analytics PostgreSQL Flexible Server (pg-PULSE-training-analytics-<env>)",
        140,
        620,
        340,
        60,
        parent="subnet_analytics",
    )

    # Edges (relationships)
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

    # Analytics PostgreSQL DNS zone linking to VNet
    add_vertex("dns_pg", "Zone: privatelink.postgres.database.azure.com", 840, 320, 360, 60, parent="rg")
    add_edge("e_dns_pg_vnet", "dns_pg", "vnet", label="vnet link")

    add_edge("e_openai_dep_core", "openai_account", "dep_core")
    add_edge("e_openai_dep_high", "openai_account", "dep_high")
    add_edge("e_openai_dep_audio", "openai_account", "dep_audio")
    add_edge("e_openai_dep_visual", "openai_account", "dep_visual")

    add_edge("e_storage_cert", "storage", "container_cert")
    add_edge("e_storage_logs", "storage", "container_logs")
    add_edge("e_storage_prompts", "storage", "container_prompts")
    add_edge("e_storage_trainer_logs", "storage", "container_trainer_logs")

    add_edge("e_openai_law", "openai_account", "law", label="diag_openai (Audit, RequestResponse)")
    add_edge("e_storage_law", "storage", "law", label="diag_storage (StorageRead/Write/Delete)")
    add_edge("e_web_law", "web", "law", label="diag_webapp (HTTPLogs, ConsoleLogs)")
    add_edge("e_func_law", "func", "law", label="diag_functionapp (FunctionAppLogs, AppServiceHTTPLogs)")

    add_edge("e_web_ai", "web", "ai", label="AppInsights")
    add_edge("e_func_ai", "func", "ai", label="AppInsights")

    # App Services -> Analytics PostgreSQL relationships
    add_edge("e_web_analytics_pg", "web", "analytics_pg", label="PULSE_ANALYTICS_DB_HOST")
    add_edge("e_func_analytics_pg", "func", "analytics_pg", label="PULSE_ANALYTICS_DB_HOST")

    tree = ElementTree(mxfile)
    output_path = Path(f"{output_basename}.drawio")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Render an Azure network diagram (PNG + SVG) for the PULSE/H2 Terraform architecture.\n"
            "\n"
            "Purpose:\n"
            "  Visualize VNet, subnets, Private Endpoints (OpenAI, Storage, Web App),\n"
            "  Azure OpenAI account and its deployments, Storage Account and key\n"
            "  containers, App Service Plan, Web App (UI/API), Function App (Scenario\n"
            "  Orchestrator), Private DNS zones and VNet links, diagnostic settings,\n"
            "  Application Insights, and Log Analytics.\n"
        ),
        formatter_class=RawTextHelpFormatter,
        epilog=(
            "Requirements (macOS):\n"
            "  1) Homebrew Graphviz (provides 'dot'):\n"
            "     brew install graphviz\n"
            "  2) Python 3.9+ and packages:\n"
            "     python3 -m venv .venv && source .venv/bin/activate && \\\n"
            "     pip install --upgrade pip && pip install diagrams graphviz\n"
            "\n"
            "Terraform files expected (in --tf-path):\n"
            "  - main.tf (required for architecture source)\n"
            "  - variables.tf (recommended)\n"
            "  - outputs.tf (recommended)\n"
            "  The script will warn if files are missing but will still render the diagram.\n"
            "\n"
            "Outputs:\n"
            "  - <output-basename>.png\n"
            "  - <output-basename>.svg\n"
            "  - <output-basename>.drawio (when using --drawio)\n"
            "\n"
            "Basic usage (from repo root):\n"
            "  python docs/PULSE_network_diagram.py\n"
            "\n"
            "Specify Terraform path explicitly (when running from docs/):\n"
            "  python PULSE_network_diagram.py --tf-path ..\n"
            "\n"
            "Write outputs into docs/:\n"
            "  python docs/PULSE_network_diagram.py --output-basename docs/PULSE-network-diagram\n"
            "\n"
            "Change layout direction (Top-to-Bottom):\n"
            "  python docs/PULSE_network_diagram.py --direction TB\n"
            "\n"
            "All-in-one setup and render (from repo root):\n"
            "  python3 -m venv .venv && source .venv/bin/activate && pip install --upgrade pip && \\\n"
            "  pip install diagrams graphviz && if ! command -v dot >/dev/null; then brew install graphviz; fi && \\\n"
            "  python docs/PULSE_network_diagram.py --output-basename docs/PULSE-network-diagram\n"
            "\n"
            "Draw.io / Lucidchart import example (from repo root):\n"
            "  python docs/PULSE_network_diagram.py --drawio --output-basename PULSE-az-lucid\n"
        ),
    )
    parser.add_argument(
        "--tf-path",
        type=str,
        default=str(Path(__file__).resolve().parents[1]),
        help="Path to the Terraform project root (used for validation and future auto-labeling).",
    )
    parser.add_argument(
        "--usage",
        "--usuage",
        action="store_true",
        help="Show extended usage/help with requirements and examples, then exit.",
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
        help=(
            "Generate a draw.io XML file (<basename>.drawio) suitable for Lucidchart "
            "or draw.io Import Diagram, and skip PNG/SVG rendering."
        ),
    )
    args = parser.parse_args()

    if args.usage:
        parser.print_help()
        return

    tf_root = Path(args.tf_path).resolve()
    print(f"[info] Using Terraform path: {tf_root}")
    main_tf = tf_root / "main.tf"
    variables_tf = tf_root / "variables.tf"
    outputs_tf = tf_root / "outputs.tf"
    found = {
        "main.tf": main_tf.exists(),
        "variables.tf": variables_tf.exists(),
        "outputs.tf": outputs_tf.exists(),
    }
    for k, v in found.items():
        print(f"[check] {k}: {'OK' if v else 'MISSING'}")

    if args.drawio:
        print("[render] Generating draw.io XML (Lucidchart/draw.io)...")
        render_drawio(args.output_basename)
        print("[done] Outputs written (draw.io mode):")
        print(f" - {args.output_basename}.drawio  [Import into Lucidchart/draw.io]")
        return

    print("[render] Generating PNG...")
    with Diagram(
        "PULSE H2 - Azure Network Architecture",
        filename=args.output_basename,
        outformat="png",
        direction=args.direction,
        show=False,
    ):
        build_topology()

    print("[render] Generating SVG...")
    with Diagram(
        "PULSE H2 - Azure Network Architecture",
        filename=args.output_basename,
        outformat="svg",
        direction=args.direction,
        show=False,
    ):
        build_topology()

    print("[done] Outputs written:")
    print(f" - {args.output_basename}.png")
    print(f" - {args.output_basename}.svg")


if __name__ == "__main__":
    main()
