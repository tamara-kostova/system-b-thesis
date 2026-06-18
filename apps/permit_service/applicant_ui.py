"""Applicant UI — submit and track data access applications."""

import os
from datetime import date
import requests
import streamlit as st
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent.parent / ".env")
PERMIT_SERVICE_URL = os.getenv("PERMIT_SERVICE_URL", "http://localhost:8002")

st.set_page_config(page_title="Apply for Data Access", layout="wide")

# --- Simple login ---
if "username" not in st.session_state:
    st.title("SecureHealth — Applicant Portal")
    username = st.text_input("Username")
    if st.button("Log in") and username.strip():
        st.session_state["username"] = username.strip()
        st.rerun()
    st.stop()

st.title(f"Data Access Portal — {st.session_state['username']}")

tab_apply, tab_my = st.tabs(["New Application", "My Applications"])

with tab_apply:
    st.subheader("Submit a Data Access Application")

    # EHDS Article 54 — prohibited use screen
    st.markdown("#### EHDS Article 54 — Prohibited Uses")
    st.caption("Your application may not be used for any of the following purposes:")
    prohibited = [
        "Taking decisions detrimental to individuals based on their health data",
        "Producing advertising or marketing for products targeted at individuals",
        "Developing products or services that may harm individuals or public health",
        "Profiling of individuals for insurance pricing or similar purposes",
        "Using data for purposes not specified in the application",
    ]
    for item in prohibited:
        st.markdown(f"- {item}")
    confirmed = st.checkbox(
        "I confirm that my intended use does **not** include any of the above (EHDS Article 54)",
        key="prohibited_confirm",
    )
    if not confirmed:
        st.warning("You must confirm compliance with EHDS Article 54 before submitting.")
        st.stop()

    with st.form("application_form"):
        access_type = st.radio("Access type", ["request", "permit"],
                               help="Request = aggregated counts only. Permit = full SPE access.")
        purpose = st.selectbox("Purpose (EHDS Article 53)", [
            "public_health", "policy", "statistics", "education", "research", "innovation"
        ])
        domains = st.multiselect("Data domains", ["Condition", "Drug", "Measurement", "Visit"],
                                 default=["Condition"])
        concept_ids_raw = st.text_input("Concept IDs (comma-separated integers)",
                                        placeholder="201826, 316866")
        time_from = st.date_input("Time window from", value=date(2000, 1, 1))
        time_until = st.date_input("Time window until", value=date(2026, 6, 5))
        fmt = st.radio("Data format", ["anonymized", "pseudonymized"])
        pseudo_justification = None
        if fmt == "pseudonymized":
            pseudo_justification = st.text_area("Justification for pseudonymization (required)")
        named_users_raw = st.text_input("Named users (comma-separated usernames)",
                                        placeholder="researcher1, researcher2")
        submitted = st.form_submit_button("Submit Application")

    if submitted:
        try:
            concept_ids = [int(c.strip()) for c in concept_ids_raw.split(",") if c.strip()]
        except ValueError:
            st.error("Concept IDs must be integers separated by commas.")
            st.stop()

        if fmt == "pseudonymized" and not pseudo_justification:
            st.error("Pseudonymization justification is required.")
            st.stop()

        named_users = [u.strip() for u in named_users_raw.split(",") if u.strip()]

        try:
            resp = requests.post(f"{PERMIT_SERVICE_URL}/permits", json={
                "type": access_type,
                "holder": st.session_state["username"],
                "named_users": named_users,
                "purpose": purpose,
                "data_scope": {
                    "domains": domains,
                    "concept_ids": concept_ids,
                    "time_window_from": str(time_from),
                    "time_window_until": str(time_until),
                },
                "format": fmt,
                "pseudonymization_justification": pseudo_justification,
            })
            resp.raise_for_status()
            permit_id = resp.json()["permit_id"]

            sub_resp = requests.post(f"{PERMIT_SERVICE_URL}/permits/{permit_id}/submit", json={
                "actor": st.session_state["username"]
            })
            sub_resp.raise_for_status()
            st.success(f"Application submitted. ID: `{permit_id}`")
        except requests.HTTPError as e:
            st.error(f"Submission failed: {e.response.text}")
        except requests.ConnectionError:
            st.error(f"Cannot reach permit service at {PERMIT_SERVICE_URL}")

with tab_my:
    st.subheader("My Applications")
    try:
        resp = requests.get(f"{PERMIT_SERVICE_URL}/permits", params={"holder": st.session_state["username"]})
        resp.raise_for_status()
        permits = resp.json()
    except Exception as e:
        st.error(f"Cannot load applications: {e}")
        permits = []

    if not permits:
        st.info("No applications yet.")
    else:
        for p in permits:
            state_color = {"granted": "🟢", "refused": "🔴", "submitted": "🟡",
                           "under_review": "🔵", "draft": "⚪", "expired": "⚫"}.get(p["state"], "")
            with st.expander(f"{state_color} {p['permit_id'][:8]}... — {p['purpose']} — {p['state']}"):
                st.json(p)
