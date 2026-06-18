"""Public Permit Register — EHDS Article 68(4). No login required."""

import os
import requests
import streamlit as st
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent.parent / ".env")
PERMIT_SERVICE_URL = os.getenv("PERMIT_SERVICE_URL", "http://localhost:8002")

st.set_page_config(page_title="Permit Register", layout="wide")
st.title("SecureHealth — Public Permit Register")
st.caption("All currently granted data access permits. Published in accordance with EHDS Article 68(4).")

try:
    resp = requests.get(f"{PERMIT_SERVICE_URL}/permits/register")
    resp.raise_for_status()
    permits = resp.json()
except Exception as e:
    st.error(f"Cannot load permit register: {e}")
    permits = []

if not permits:
    st.info("No granted permits at this time.")
else:
    st.write(f"**{len(permits)} active permit(s)**")
    st.divider()
    for p in permits:
        scope = p.get("data_scope", {})
        domains = ", ".join(scope.get("domains", []))
        with st.expander(
            f"Permit `{p['permit_id'][:8]}...` — {p['purpose']} — valid {p['valid_from']} to {p['valid_until']}"
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Permit ID:** `{p['permit_id']}`")
                st.markdown(f"**Type:** {p['type']}")
                st.markdown(f"**Purpose:** {p['purpose']}")
                st.markdown(f"**Format:** {p['format']}")
            with col2:
                st.markdown(f"**Valid from:** {p['valid_from']}")
                st.markdown(f"**Valid until:** {p['valid_until']}")
                st.markdown(f"**Data domains:** {domains or '—'}")
                st.markdown(f"**OMOP snapshot:** {p['omop_snapshot']}")
            if p.get("reviewer_comment"):
                st.markdown(f"**Conditions:** {p['reviewer_comment']}")
