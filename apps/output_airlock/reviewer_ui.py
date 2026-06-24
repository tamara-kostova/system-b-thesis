"""
Phase 4 — Output Airlock reviewer Streamlit UI.

Run: cd apps/output_airlock && streamlit run reviewer_ui.py --server.port 8503
"""

import os
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

AIRLOCK_URL = os.getenv("AIRLOCK_URL", "http://localhost:8005")
REVIEWER_PASSWORD = os.getenv("REVIEWER_PASSWORD", "reviewer123")

st.set_page_config(page_title="Output Airlock — Reviewer", layout="wide")
st.title("Output Airlock — Reviewer")

# ── Auth ──────────────────────────────────────────────────────────────────────
if "reviewer" not in st.session_state:
    st.session_state.reviewer = None

if not st.session_state.reviewer:
    with st.form("login"):
        name = st.text_input("Reviewer name")
        pwd = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            if pwd == REVIEWER_PASSWORD and name.strip():
                st.session_state.reviewer = name.strip()
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop()

st.caption(f"Logged in as **{st.session_state.reviewer}**")
if st.button("Logout"):
    st.session_state.reviewer = None
    st.rerun()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_pending, tab_all = st.tabs(["Pending Review", "All Submissions"])


def _check_badge(passed: bool) -> str:
    return "✅" if passed else "❌"


def _render_submission(s: dict, show_actions: bool = False):
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"**{s['filename']}** — permit `{s['permit_id']}`")
        st.caption(f"Submitted: {s['submitted_at']}  |  State: `{s['state']}`")
        if s.get("justification"):
            st.markdown(f"*Justification:* {s['justification']}")
    with col2:
        overall = "✅ All passed" if s["all_checks_passed"] else "❌ Checks failed"
        st.markdown(overall)

    with st.expander("Automated check results"):
        for c in s["automated_checks"]:
            st.markdown(f"{_check_badge(c['passed'])} **{c['name']}** — {c['reason']}")

    if s.get("reviewer_comment"):
        st.info(f"Reviewer note: {s['reviewer_comment']}")

    if show_actions and s["state"] == "pending_review":
        with st.form(f"review_{s['submission_id']}"):
            comment = st.text_area("Comment (required for rejection)")
            c1, c2 = st.columns(2)
            approve = c1.form_submit_button("Approve", type="primary")
            reject = c2.form_submit_button("Reject")

            if approve or reject:
                endpoint = "approve" if approve else "reject"
                resp = requests.post(
                    f"{AIRLOCK_URL}/submissions/{s['submission_id']}/{endpoint}",
                    json={
                        "reviewer": st.session_state.reviewer,
                        "password": REVIEWER_PASSWORD,
                        "comment": comment,
                    },
                )
                if resp.ok:
                    st.success(f"Submission {endpoint}d.")
                    st.rerun()
                else:
                    st.error(resp.json().get("detail", "Error"))


with tab_pending:
    try:
        resp = requests.get(f"{AIRLOCK_URL}/submissions?state=pending_review")
        subs = resp.json() if resp.ok else []
        if not isinstance(subs, list):
            st.error(f"Airlock service error: {subs}")
            subs = []
    except Exception as e:
        st.error(f"Cannot reach airlock service: {e}")
        subs = []

    if not subs:
        st.info("No submissions pending review.")
    else:
        st.markdown(f"**{len(subs)} submission(s) waiting.**")
        for s in subs:
            with st.container(border=True):
                _render_submission(s, show_actions=True)

    if st.button("Refresh", key="refresh_pending"):
        st.rerun()


with tab_all:
    try:
        resp = requests.get(f"{AIRLOCK_URL}/submissions")
        all_subs = resp.json() if resp.ok else []
        if not isinstance(all_subs, list):
            st.error(f"Airlock service error: {all_subs}")
            all_subs = []
    except Exception as e:
        st.error(f"Cannot reach airlock service: {e}")
        all_subs = []

    state_filter = st.selectbox(
        "Filter by state", ["all", "pending_review", "approved", "rejected", "blocked"]
    )
    filtered = (
        all_subs if state_filter == "all" else [s for s in all_subs if s["state"] == state_filter]
    )

    st.markdown(f"**{len(filtered)} submission(s)**")
    for s in filtered:
        with st.container(border=True):
            _render_submission(s, show_actions=False)
            if s["state"] == "approved":
                st.markdown(f"[Download]({AIRLOCK_URL}/submissions/{s['submission_id']}/download)")

    if st.button("Refresh", key="refresh_all"):
        st.rerun()
