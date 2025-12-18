"""
Streamlit web UI for the switch catalog.

Uses the CLI logic from app.py to filter, search, and render switch models with
optional configuration snippets.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from types import SimpleNamespace
from typing import Iterable, List, Optional, Tuple

import streamlit as st

from app import Switch, answer_question, filter_catalog, format_table, load_catalog


def _load_uploaded_catalog(uploaded_file) -> Tuple[List[Switch], Optional[str]]:
    """Load catalog from an uploaded JSON file, falling back to default on errors."""
    if not uploaded_file:
        return load_catalog(None), None

    try:
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp.write(uploaded_file.getvalue())
            temp_path = temp.name
        return load_catalog(temp_path), None
    except Exception as exc:  # pragma: no cover - UI feedback path
        return load_catalog(None), f"Failed to load uploaded catalog: {exc}"


def _build_args(
    vendor: Optional[str],
    model: str,
    keyword: str,
    layer: Optional[str],
    min_ports: Optional[int],
    max_ports: Optional[int],
    poe: Optional[str],
    managed: Optional[str],
    stackable: Optional[str],
    output: str,
    include_cli: bool,
    group_by_vendor: bool,
    limit: Optional[int],
) -> SimpleNamespace:
    """Mimic the argparse.Namespace expected by filter_catalog/format_table."""
    return SimpleNamespace(
        catalog=None,
        vendor=vendor,
        model=model or None,
        keyword=keyword or None,
        layer=layer,
        min_ports=min_ports or None,
        max_ports=max_ports or None,
        poe=poe,
        managed=managed,
        stackable=stackable,
        output=output,
        include_cli=include_cli,
        group_by_vendor=group_by_vendor,
        ask=None,
        limit=limit,
    )


def _display_results(matches: Iterable[Switch], args: SimpleNamespace) -> None:
    matches_list = list(matches)
    if args.limit is not None:
        matches_list = matches_list[: max(0, args.limit)]

    if args.output == "json":
        st.json([asdict(sw) for sw in matches_list])
    else:
        st.text(format_table(matches_list, include_cli=args.include_cli, group_by_vendor=args.group_by_vendor))


def main() -> None:
    st.set_page_config(page_title="Switch Catalog", layout="wide")
    st.title("Switch Catalog")
    st.write("Search, filter, and explore common switch models with optional CLI snippets.")

    uploaded_file = st.file_uploader("Upload a catalog JSON file (optional)", type=["json"])
    catalog, upload_error = _load_uploaded_catalog(uploaded_file)
    if upload_error:
        st.error(upload_error)

    vendors = sorted({sw.vendor for sw in catalog})
    vendor_choice = st.selectbox("Vendor", options=["Any"] + vendors)
    vendor = None if vendor_choice == "Any" else vendor_choice

    col1, col2, col3 = st.columns(3)
    with col1:
        model = st.text_input("Model contains", value="")
        layer = st.selectbox("Layer", options=["Any", "L2", "L3"])
        layer_value = None if layer == "Any" else layer
        poe = st.selectbox("PoE", options=["Any", "yes", "no"])
        poe_value = None if poe == "Any" else poe
    with col2:
        keyword = st.text_input("Keyword", value="")
        min_ports = st.number_input("Minimum ports", min_value=0, step=1, value=0)
        max_ports = st.number_input("Maximum ports", min_value=0, step=1, value=0)
        managed = st.selectbox("Managed", options=["Any", "yes", "no"])
        managed_value = None if managed == "Any" else managed
    with col3:
        stackable = st.selectbox("Stackable", options=["Any", "yes", "no"])
        stackable_value = None if stackable == "Any" else stackable
        include_cli = st.checkbox("Include CLI snippets", value=False)
        group_by_vendor = st.checkbox("Group by vendor", value=False)
        limit = st.number_input("Result limit (0 for no limit)", min_value=0, step=1, value=0)

    output_format = st.radio("Output format", options=["table", "json"], horizontal=True)

    args = _build_args(
        vendor=vendor,
        model=model,
        keyword=keyword,
        layer=layer_value,
        min_ports=min_ports or None,
        max_ports=max_ports or None,
        poe=poe_value,
        managed=managed_value,
        stackable=stackable_value,
        output=output_format,
        include_cli=include_cli,
        group_by_vendor=group_by_vendor,
        limit=limit or None,
    )

    st.subheader("Results")
    matches = filter_catalog(catalog, args)
    _display_results(matches, args)

    st.subheader("Ask a quick question")
    question = st.text_input(
        "Natural-language prompt (e.g., '48-port PoE stackable Cisco with troubleshooting commands')"
    )
    if st.button("Get suggestion"):
        st.info(answer_question(question, catalog))


if __name__ == "__main__":  # pragma: no cover - Streamlit entrypoint
    main()
