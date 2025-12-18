# Switch Catalogue Web App

A Streamlit-based web application for searching and comparing network switches across
multiple vendors, with example CLI configuration snippets and troubleshooting commands.

## Features
- Built-in catalogue of common enterprise switches (Cisco, Aruba, Juniper, etc.)
- Filter by vendor, model, ports, PoE, layer (L2/L3), and stackability
- Optional CLI configuration and troubleshooting examples
- Upload a custom switch catalogue using JSON
- Simple recommendation feature using natural-language queries

## Running the app locally
```bash
pip install -r requirements.txt
streamlit run web_app.py
```
