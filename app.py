"""
Switch catalog CLI with configuration snippets.

- Built-in catalog of common switch models across several vendors
- Search and filter by vendor/model/ports/PoE/L2-L3/managed/stackable
- Optional CLI configuration snippets and troubleshooting commands per device family
- Optional JSON catalog input (your own inventory of switch models)

Usage examples:
  python app.py
  python app.py --vendor Cisco --min-ports 24 --poe yes
  python app.py --keyword "campus" --include-cli
  python app.py --ask "48 port PoE Cisco stackable L3"
  python app.py --output json --poe yes
  python app.py --catalog my_switches.json --group-by-vendor --include-cli
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class Switch:
    vendor: str
    model: str
    ports: int
    poe: bool
    layer: str
    managed: bool
    stackable: bool
    uplink: str
    uplink_count: int
    poe_budget: Optional[int]
    cli_sections: Dict[str, List[str]]
    troubleshooting: List[str]
    notes: str

    def matches_keyword(self, keyword: Optional[str]) -> bool:
        if not keyword:
            return True
        keyword = keyword.lower()
        haystack = " ".join(
            [
                self.vendor,
                self.model,
                self.layer,
                self.uplink,
                self.notes,
                " ".join(self.troubleshooting),
                " ".join(" ".join(cmds) for cmds in self.cli_sections.values()),
            ]
        ).lower()
        return keyword in haystack


# ---------- Built-in command templates (kept simple + safe) ----------

CISCO_CLI = {
    "VLAN configuration": [
        "configure terminal",
        "vlan 10",
        "name USERS",
        "interface gig1/0/1",
        "switchport mode access",
        "switchport access vlan 10",
        "spanning-tree portfast",
        "end",
        "write memory",
    ],
    "Uplink trunk (example)": [
        "configure terminal",
        "interface tengig1/1/1",
        "description Uplink-to-core",
        "switchport mode trunk",
        "switchport trunk allowed vlan 10,20,30",
        "end",
        "write memory",
    ],
}

JUNIPER_CLI = {
    "VLAN configuration": [
        "configure",
        "set vlans USERS vlan-id 10",
        "set interfaces ge-0/0/1 unit 0 family ethernet-switching vlan members USERS",
        "commit and-quit",
    ],
    "Uplink trunk (example)": [
        "configure",
        "set interfaces xe-0/1/0 unit 0 family ethernet-switching port-mode trunk",
        "set interfaces xe-0/1/0 unit 0 family ethernet-switching vlan members [ USERS VOICE ]",
        "commit and-quit",
    ],
}

ARUBA_AOSS_CLI = {
    "VLAN configuration (AOS-S/ProCurve style)": [
        "configure terminal",
        "vlan 10",
        "name USERS",
        "untagged 1-12",
        "exit",
        "write memory",
    ],
    "Uplink (tagged VLANs)": [
        "configure terminal",
        "interface 25",
        "name Uplink-to-core",
        "tagged 10,20",
        "exit",
        "write memory",
    ],
}

ARUBA_CX_CLI = {
    "VLAN configuration (AOS-CX style)": [
        "configure terminal",
        "vlan 10",
        "name USERS",
        "interface 1/1/1",
        "no shutdown",
        "vlan access 10",
        "end",
        "write memory",
    ],
    "Uplink trunk (AOS-CX)": [
        "configure terminal",
        "interface 1/1/49",
        "description Uplink-to-core",
        "no shutdown",
        "vlan trunk native 1",
        "vlan trunk allowed 10,20,30",
        "end",
        "write memory",
    ],
}

UNIFI_CLI = {
    "Controller configuration": [
        "Managed via UniFi Network application (GUI/API).",
        "SSH is mostly for diagnostics; config is normally via controller profiles.",
    ],
}

NETGEAR_SMART_CLI = {
    "VLAN configuration (varies by model)": [
        "Many Netgear Smart/Managed switches are configured via web UI.",
        "Some models have a CLI, but commands vary by family.",
        "Best approach: use the UI/API and export config backups regularly.",
    ],
}

UNMANAGED_CLI = {
    "Configuration": [
        "Unmanaged switch; no CLI configuration available.",
    ],
}


def default_catalog() -> List[Switch]:
    """Built-in catalog so the app works out of the box."""
    return [
        # ---------------- Cisco ----------------
        Switch(
            vendor="Cisco",
            model="Catalyst 9200L-24P",
            ports=24,
            poe=True,
            layer="L2",
            managed=True,
            stackable=True,
            uplink="4x10G",
            uplink_count=4,
            poe_budget=370,
            cli_sections=CISCO_CLI,
            troubleshooting=[
                "show interfaces status",
                "show power inline",
                "show spanning-tree summary",
                "show cdp neighbors detail",
            ],
            notes="Campus access (9200L). Good standard edge switch option.",
        ),
        Switch(
            vendor="Cisco",
            model="Catalyst 9300-48P",
            ports=48,
            poe=True,
            layer="L3",
            managed=True,
            stackable=True,
            uplink="4x25G",
            uplink_count=4,
            poe_budget=715,
            cli_sections=CISCO_CLI,
            troubleshooting=[
                "show interfaces status",
                "show power inline",
                "show etherchannel summary",
                "show spanning-tree interface status",
                "show logging | last 50",
            ],
            notes="Enterprise access with L3 capabilities and stacking.",
        ),
        Switch(
            vendor="Cisco",
            model="Catalyst 9500-24Y4C",
            ports=24,
            poe=False,
            layer="L3",
            managed=True,
            stackable=False,
            uplink="40/100G",
            uplink_count=4,
            poe_budget=None,
            cli_sections={
                "Routing (example)": [
                    "configure terminal",
                    "ip routing",
                    "interface vlan 10",
                    "ip address 10.10.10.1 255.255.255.0",
                    "end",
                    "write memory",
                ]
            },
            troubleshooting=[
                "show ip interface brief",
                "show ip route",
                "show platform hardware capacity",
                "show interfaces counters errors",
            ],
            notes="Core/distribution L3 switch (no PoE).",
        ),

        # ---------------- Juniper ----------------
        Switch(
            vendor="Juniper",
            model="EX2300-24P",
            ports=24,
            poe=True,
            layer="L2",
            managed=True,
            stackable=True,
            uplink="4x10G (SFP+)",
            uplink_count=4,
            poe_budget=370,
            cli_sections=JUNIPER_CLI,
            troubleshooting=[
                "show interfaces terse",
                "show poe interface all",
                "show ethernet-switching table",
                "show chassis alarms",
            ],
            notes="Access switch with Virtual Chassis (model dependent).",
        ),
        Switch(
            vendor="Juniper",
            model="EX3400-48P",
            ports=48,
            poe=True,
            layer="L3",
            managed=True,
            stackable=True,
            uplink="4x10G (SFP+)",
            uplink_count=4,
            poe_budget=740,
            cli_sections=JUNIPER_CLI,
            troubleshooting=[
                "show interfaces terse",
                "show spanning-tree interface",
                "show ethernet-switching table",
                "show virtual-chassis",
            ],
            notes="Campus access with stronger performance; VC capable.",
        ),
        Switch(
            vendor="Juniper",
            model="EX4300-48P",
            ports=48,
            poe=True,
            layer="L3",
            managed=True,
            stackable=True,
            uplink="4x40G",
            uplink_count=4,
            poe_budget=715,
            cli_sections=JUNIPER_CLI,
            troubleshooting=[
                "show interfaces terse",
                "show poe interface all",
                "show ethernet-switching table",
                "show chassis hardware",
                "show virtual-chassis",
            ],
            notes="Virtual Chassis capable with PoE+.",
        ),

        # ---------------- Aruba AOS-S / ProCurve style ----------------
        Switch(
            vendor="Aruba",
            model="2530-24G-PoE+",
            ports=24,
            poe=True,
            layer="L2",
            managed=True,
            stackable=False,
            uplink="4xSFP",
            uplink_count=4,
            poe_budget=195,
            cli_sections=ARUBA_AOSS_CLI,
            troubleshooting=[
                "show interfaces brief",
                "show power-over-ethernet brief",
                "show vlan",
                "show trunks",
                "show spanning-tree",
            ],
            notes="AOS-S access switch, simple and reliable edge.",
        ),
        Switch(
            vendor="Aruba",
            model="2930F-48G-PoE+",
            ports=48,
            poe=True,
            layer="L3",
            managed=True,
            stackable=True,
            uplink="4xSFP+ (10G)",
            uplink_count=4,
            poe_budget=740,
            cli_sections=ARUBA_AOSS_CLI,
            troubleshooting=[
                "show interfaces brief",
                "show power-over-ethernet brief",
                "show lacp",
                "show spanning-tree",
                "show logging -r",
            ],
            notes="AOS-S (2930F) often used for campus access; stacking via VSF.",
        ),

        # ---------------- Aruba CX (AOS-CX) ----------------
        Switch(
            vendor="Aruba",
            model="CX 6100 48G",
            ports=48,
            poe=False,
            layer="L2",
            managed=True,
            stackable=True,
            uplink="4xSFP+ (10G)",
            uplink_count=4,
            poe_budget=None,
            cli_sections=ARUBA_CX_CLI,
            troubleshooting=[
                "show interface brief",
                "show vlan",
                "show lacp interfaces",
                "show logging -r",
            ],
            notes="Entry AOS-CX access; modern OS, good for standard edge.",
        ),
        Switch(
            vendor="Aruba",
            model="CX 6200F 48G PoE+",
            ports=48,
            poe=True,
            layer="L3",
            managed=True,
            stackable=True,
            uplink="4xSFP+ (10G)",
            uplink_count=4,
            poe_budget=740,
            cli_sections=ARUBA_CX_CLI,
            troubleshooting=[
                "show interface brief",
                "show power-over-ethernet brief",
                "show vsf",
                "show vlan",
                "show lacp interfaces",
            ],
            notes="AOS-CX access/distribution; common campus standard with VSF.",
        ),
        Switch(
            vendor="Aruba",
            model="CX 6300M 48G PoE+",
            ports=48,
            poe=True,
            layer="L3",
            managed=True,
            stackable=True,
            uplink="4xSFP+/4xSFP56",
            uplink_count=4,
            poe_budget=1440,
            cli_sections=ARUBA_CX_CLI,
            troubleshooting=[
                "show interface brief",
                "show power-over-ethernet brief",
                "show vsx status",
                "show lacp interfaces",
                "show logging -r",
            ],
            notes="Higher-performance CX stack/VSX capable distribution layer.",
        ),

        # ---------------- Ubiquiti (UniFi) ----------------
        Switch(
            vendor="Ubiquiti",
            model="UniFi USW-24",
            ports=24,
            poe=False,
            layer="L2",
            managed=True,
            stackable=False,
            uplink="2xSFP",
            uplink_count=2,
            poe_budget=None,
            cli_sections=UNIFI_CLI,
            troubleshooting=[
                "show interfaces",
                "mca-cli-op info",
                "swctrl poe show",
            ],
            notes="Managed via controller; CLI limited to diagnostics.",
        ),
        Switch(
            vendor="Ubiquiti",
            model="UniFi USW-Pro-48-PoE",
            ports=48,
            poe=True,
            layer="L2",
            managed=True,
            stackable=False,
            uplink="4xSFP+",
            uplink_count=4,
            poe_budget=600,
            cli_sections=UNIFI_CLI,
            troubleshooting=[
                "show interfaces",
                "mca-cli-op info",
                "swctrl poe show",
                "swctrl port show <port>",
            ],
            notes="Controller-managed PoE access; diagnostics via SSH limited.",
        ),

        # ---------------- Netgear ----------------
        Switch(
            vendor="Netgear",
            model="GS108",
            ports=8,
            poe=False,
            layer="L2",
            managed=False,
            stackable=False,
            uplink="None",
            uplink_count=0,
            poe_budget=None,
            cli_sections=UNMANAGED_CLI,
            troubleshooting=[
                "Use link LEDs and cable testing; no CLI available.",
            ],
            notes="Unmanaged desktop switch.",
        ),
        Switch(
            vendor="Netgear",
            model="M4300-52G-PoE+",
            ports=48,
            poe=True,
            layer="L3",
            managed=True,
            stackable=True,
            uplink="2x40G",
            uplink_count=2,
            poe_budget=740,
            cli_sections=NETGEAR_SMART_CLI,
            troubleshooting=[
                "show interface status",
                "show poe status",
                "show spanning-tree",
            ],
            notes="Stackable campus PoE switch (commands vary by firmware).",
        ),

        # ---------------- HPE / ProCurve ----------------
        Switch(
            vendor="HPE",
            model="2920-24G-PoE+",
            ports=24,
            poe=True,
            layer="L3",
            managed=True,
            stackable=True,
            uplink="2xSFP+",
            uplink_count=2,
            poe_budget=370,
            cli_sections=ARUBA_AOSS_CLI,
            troubleshooting=[
                "show interfaces brief",
                "show power-over-ethernet brief",
                "show spanning-tree",
                "show logging -r",
            ],
            notes="ProCurve/ArubaOS-Switch family with stacking support.",
        ),
    ]


def load_catalog(path: Optional[str]) -> List[Switch]:
    if not path:
        return default_catalog()

    data = json.loads(Path(path).read_text())
    catalog = []
    for item in data:
        catalog.append(
            Switch(
                vendor=item["vendor"],
                model=item["model"],
                ports=int(item["ports"]),
                poe=bool(item["poe"]),
                layer=item["layer"],
                managed=bool(item["managed"]),
                stackable=bool(item["stackable"]),
                uplink=item.get("uplink", "N/A"),
                uplink_count=int(item.get("uplink_count", 0)),
                poe_budget=item.get("poe_budget"),
                cli_sections=item.get("cli_sections", {}),
                troubleshooting=item.get("troubleshooting", []),
                notes=item.get("notes", ""),
            )
        )
    return catalog


def filter_catalog(catalog: Iterable[Switch], args: argparse.Namespace) -> List[Switch]:
    def bool_filter(value: bool, selector: Optional[str]) -> bool:
        if selector is None:
            return True
        if selector.lower() == "yes":
            return value
        if selector.lower() == "no":
            return not value
        return True

    results = []
    for item in catalog:
        if args.vendor and item.vendor.lower() != args.vendor.lower():
            continue
        if args.model and args.model.lower() not in item.model.lower():
            continue
        if not item.matches_keyword(args.keyword):
            continue
        if args.min_ports and item.ports < args.min_ports:
            continue
        if args.max_ports and item.ports > args.max_ports:
            continue
        if args.layer and item.layer.lower() != args.layer.lower():
            continue
        if not bool_filter(item.poe, args.poe):
            continue
        if not bool_filter(item.managed, args.managed):
            continue
        if not bool_filter(item.stackable, args.stackable):
            continue
        results.append(item)
    return results


def format_table(items: List[Switch], include_cli: bool, group_by_vendor: bool) -> str:
    if not items:
        return "No switches matched your criteria."

    headers = [
        "Vendor",
        "Model",
        "Ports",
        "PoE",
        "Layer",
        "Managed",
        "Stackable",
        "Uplinks",
        "PoE Budget (W)",
        "Notes",
    ]

    def render_rows(rows: List[List[str]]) -> List[str]:
        col_widths = [max(len(row[i]) for row in rows + [headers]) for i in range(len(headers))]

        def render_row(row: List[str]) -> str:
            return " | ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(row))

        lines = [render_row(headers), "-+-".join("-" * w for w in col_widths)]
        lines.extend(render_row(row) for row in rows)
        return lines

    def render_cli(sw: Switch) -> List[str]:
        if not include_cli:
            return []
        lines: List[str] = [f"[{sw.vendor} {sw.model}]"]
        for section, commands in sw.cli_sections.items():
            lines.append(f"  {section}:")
            for cmd in commands:
                lines.append(f"    {cmd}")
        if sw.troubleshooting:
            lines.append("  Troubleshooting:")
            for cmd in sw.troubleshooting:
                lines.append(f"    {cmd}")
        lines.append("")
        return lines

    lines: List[str] = []
    if group_by_vendor:
        vendors = sorted({sw.vendor for sw in items})
        for vendor in vendors:
            subset = [sw for sw in items if sw.vendor == vendor]
            lines.append(f"== {vendor} ==")
            rows = [
                [
                    sw.vendor,
                    sw.model,
                    str(sw.ports),
                    "Yes" if sw.poe else "No",
                    sw.layer,
                    "Yes" if sw.managed else "No",
                    "Yes" if sw.stackable else "No",
                    f"{sw.uplink_count} @ {sw.uplink}",
                    str(sw.poe_budget) if sw.poe_budget is not None else "-",
                    sw.notes,
                ]
                for sw in subset
            ]
            lines.extend(render_rows(rows))
            if include_cli:
                lines.append("Configuration snippets:")
                for sw in subset:
                    lines.extend(render_cli(sw))
    else:
        rows = [
            [
                sw.vendor,
                sw.model,
                str(sw.ports),
                "Yes" if sw.poe else "No",
                sw.layer,
                "Yes" if sw.managed else "No",
                "Yes" if sw.stackable else "No",
                f"{sw.uplink_count} @ {sw.uplink}",
                str(sw.poe_budget) if sw.poe_budget is not None else "-",
                sw.notes,
            ]
            for sw in items
        ]
        lines.extend(render_rows(rows))
        if include_cli:
            lines.append("Configuration snippets:")
            for sw in items:
                lines.extend(render_cli(sw))

    return "\n".join(lines).rstrip()


def answer_question(question: str, catalog: List[Switch]) -> str:
    """
    Lightweight, rule-based assistant to suggest switches and commands.

    This is intentionally simple (no external AI/LLM calls). It scores switches by
    matching vendor/model keywords and then crafts a short recommendation plus
    next steps.
    """

    def score_switch(sw: Switch, q: str) -> int:
        score = 0
        q_low = q.lower()
        if sw.vendor.lower() in q_low:
            score += 3
        if sw.model.lower() in q_low:
            score += 3
        if "poe" in q_low and sw.poe:
            score += 2
        if "stack" in q_low and sw.stackable:
            score += 2
        if "layer 3" in q_low or "l3" in q_low:
            score += 1 if sw.layer.lower() == "l3" else 0
        if "troubleshoot" in q_low or "diagnose" in q_low:
            score += 1 if sw.troubleshooting else 0
        if "uplink" in q_low:
            score += 1
        return score

    ranked: List[Tuple[int, Switch]] = []
    for sw in catalog:
        ranked.append((score_switch(sw, question), sw))
    ranked.sort(key=lambda x: x[0], reverse=True)

    best_score, best = ranked[0]
    if best_score == 0:
        return (
            "I didn't find a specific match. Try mentioning a vendor or feature "
            "(e.g., 'Cisco PoE 48-port stackable L3 with troubleshooting commands')."
        )

    lines = [
        (
            f"Suggested match: {best.vendor} {best.model} ({best.layer}, {best.ports} ports, "
            f"{'PoE' if best.poe else 'non-PoE'}, "
            f"{'stackable' if best.stackable else 'non-stackable'})."
        ),
        (
            f"Uplinks: {best.uplink_count} @ {best.uplink}. PoE budget: "
            f"{best.poe_budget if best.poe_budget is not None else 'N/A'}."
        ),
        f"Notes: {best.notes}",
    ]

    if best.cli_sections:
        lines.append("Key configuration sections:")
        for section, cmds in best.cli_sections.items():
            preview = "; ".join(cmds[:4])
            if len(cmds) > 4:
                preview += " ..."
            lines.append(f"  - {section}: {preview}")

    if best.troubleshooting:
        preview = "; ".join(best.troubleshooting[:4])
        if len(best.troubleshooting) > 4:
            preview += " ..."
        lines.append(f"Troubleshooting tips: {preview}")

    lines.append("You can see full details with:")
    lines.append(
        f'  python app.py --vendor "{best.vendor}" --model "{best.model}" --include-cli --group-by-vendor'
    )

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search and explore switch models with example CLI configurations."
    )
    parser.add_argument(
        "--catalog",
        help="Path to a JSON catalog (list of switches) to use instead of the built-in sample.",
    )
    parser.add_argument("--vendor", help="Exact vendor match (e.g., Cisco, Juniper).")
    parser.add_argument("--model", help="Substring match on the model name.")
    parser.add_argument(
        "--keyword",
        help="Keyword to search across vendor, model, uplink, and notes (case-insensitive).",
    )
    parser.add_argument("--layer", choices=["L2", "L3"], help="Layer capability filter.")
    parser.add_argument("--min-ports", type=int, help="Minimum copper port count.")
    parser.add_argument("--max-ports", type=int, help="Maximum copper port count.")
    parser.add_argument(
        "--poe",
        choices=["yes", "no"],
        help="Filter by Power-over-Ethernet support.",
    )
    parser.add_argument(
        "--managed",
        choices=["yes", "no"],
        help="Filter by managed vs unmanaged.",
    )
    parser.add_argument(
        "--stackable",
        choices=["yes", "no"],
        help="Filter by stackable capability.",
    )
    parser.add_argument(
        "--output",
        choices=["table", "json"],
        default="table",
        help="Choose output format.",
    )
    parser.add_argument(
        "--include-cli",
        action="store_true",
        help="Include sample CLI configuration snippets in the output.",
    )
    parser.add_argument(
        "--group-by-vendor",
        action="store_true",
        help="Group results by vendor with per-vendor tables and command sections.",
    )
    parser.add_argument(
        "--ask",
        help="Ask a natural-language question (e.g., 'PoE 48-port Cisco with troubleshooting commands').",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of results shown (after filtering).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    catalog = load_catalog(args.catalog)

    if args.ask:
        print(answer_question(args.ask, catalog))
        return

    matches = filter_catalog(catalog, args)

    if args.limit is not None:
        matches = matches[: max(0, args.limit)]

    if args.output == "json":
        json.dump([asdict(sw) for sw in matches], fp=sys.stdout, indent=2)
        print()
    else:
        print(format_table(matches, include_cli=args.include_cli, group_by_vendor=args.group_by_vendor))


if __name__ == "__main__":
    main()
