"""Reviewer UI — approve or refuse pending applications."""

import os
import requests
import streamlit as st
from datetime import date, timedelta
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent.parent / ".env")
REVIEWER_PASSWORD = os.getenv("REVIEWER_PASSWORD")
PERMIT_SERVICE_URL = os.getenv("PERMIT_SERVICE_URL", "http://localhost:8002")

st.set_page_config(page_title="Reviewer Console", layout="wide")

# --- Reviewer login ---
if "reviewer" not in st.session_state:
    st.title("SecureHealth — Reviewer Console")
    password = st.text_input("Reviewer password", type="password")
    if st.button("Log in"):
        if not REVIEWER_PASSWORD:
            st.error("REVIEWER_PASSWORD is not configured. Contact your system administrator.")
        elif password == REVIEWER_PASSWORD:
            st.session_state["reviewer"] = "reviewer"
            st.rerun()
        else:
            st.error("Wrong password.")
    st.stop()

st.title("Reviewer Console")

tab_pending, tab_all = st.tabs(["Pending Review", "All Permits"])

with tab_pending:
    st.subheader("Applications awaiting action")
    try:
        submitted_permits = requests.get(f"{PERMIT_SERVICE_URL}/permits", params={"state": "submitted"}).json()
        under_review_permits = requests.get(f"{PERMIT_SERVICE_URL}/permits", params={"state": "under_review"}).json()
        pending = submitted_permits + under_review_permits
    except Exception as e:
        st.error(f"Cannot reach permit service: {e}")
        pending = []

    if not pending:
        st.info("No pending applications.")
    else:
        for p in pending:
            with st.expander(f"📋 {p['permit_id'][:8]}... | {p['holder']} | {p['purpose']} | {p['state']}"):
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.json(p)
                with col2:
                    if p["state"] == "submitted":
                        if st.button("Start review", key=f"review_{p['permit_id']}"):
                            resp = requests.post(
                                f"{PERMIT_SERVICE_URL}/permits/{p['permit_id']}/review",
                                json={"actor": st.session_state["reviewer"]}
                            )
                            if resp.ok:
                                st.success("Moved to under_review")
                                st.rerun()
                            else:
                                st.error(resp.text)

                    if p["state"] == "under_review":
                        st.write("**Grant**")
                        valid_from = st.date_input("Valid from", value=date.today(),
                                                   key=f"vf_{p['permit_id']}")
                        valid_until = st.date_input("Valid until",
                                                    value=date.today() + timedelta(days=7),
                                                    key=f"vu_{p['permit_id']}")
                        if st.button("✅ Grant", key=f"grant_{p['permit_id']}"):
                            resp = requests.post(
                                f"{PERMIT_SERVICE_URL}/permits/{p['permit_id']}/grant",
                                json={"actor": st.session_state["reviewer"],
                                      "valid_from": str(valid_from),
                                      "valid_until": str(valid_until)}
                            )
                            if resp.ok:
                                st.success("Permit granted.")
                                st.rerun()
                            else:
                                st.error(resp.text)

                        st.write("**Refuse**")
                        comment = st.text_area("Reason for refusal", key=f"comment_{p['permit_id']}")
                        if st.button("❌ Refuse", key=f"refuse_{p['permit_id']}"):
                            if not comment.strip():
                                st.error("Refusal reason is required.")
                            else:
                                resp = requests.post(
                                    f"{PERMIT_SERVICE_URL}/permits/{p['permit_id']}/refuse",
                                    json={"actor": st.session_state["reviewer"], "comment": comment}
                                )
                                if resp.ok:
                                    st.success("Application refused.")
                                    st.rerun()
                                else:
                                    st.error(resp.text)

with tab_all:
    st.subheader("All permits")
    try:
        all_permits = requests.get(f"{PERMIT_SERVICE_URL}/permits").json()
    except Exception as e:
        st.error(f"Cannot reach permit service: {e}")
        all_permits = []

    state_icons = {"granted": "🟢", "refused": "🔴", "submitted": "🟡",
                   "under_review": "🔵", "draft": "⚪", "expired": "⚫"}
    for p in all_permits:
        icon = state_icons.get(p["state"], "")
        st.write(f"{icon} `{p['permit_id'][:8]}` | **{p['holder']}** | {p['purpose']} | {p['state']} | {p['created_at'][:10]}")
