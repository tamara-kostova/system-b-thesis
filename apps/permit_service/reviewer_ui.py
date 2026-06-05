"""Reviewer UI — approve or refuse pending applications."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import streamlit as st
from datetime import date, timedelta
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent.parent / ".env")
REVIEWER_PASSWORD = os.getenv("REVIEWER_PASSWORD", "reviewer123")

from shared.db import SessionLocal
from apps.permit_service.models import PermitDB, create_tables
from apps.permit_service.state_machine import PermitStateMachine, IllegalTransitionError

create_tables()

st.set_page_config(page_title="Reviewer Console", layout="wide")

# --- Reviewer login ---
if "reviewer" not in st.session_state:
    st.title("SecureHealth — Reviewer Console")
    password = st.text_input("Reviewer password", type="password")
    if st.button("Log in"):
        if password == REVIEWER_PASSWORD:
            st.session_state["reviewer"] = "reviewer"
            st.rerun()
        else:
            st.error("Wrong password.")
    st.stop()

st.title("Reviewer Console")

tab_pending, tab_all = st.tabs(["Pending Review", "All Permits"])

def load_permits(state_filter=None):
    db = SessionLocal()
    try:
        q = db.query(PermitDB)
        if state_filter:
            q = q.filter(PermitDB.state.in_(state_filter))
        return q.order_by(PermitDB.created_at.desc()).all(), db
    except Exception:
        db.close()
        raise

with tab_pending:
    st.subheader("Applications awaiting action")
    db = SessionLocal()
    try:
        pending = (
            db.query(PermitDB)
            .filter(PermitDB.state.in_(["submitted", "under_review"]))
            .order_by(PermitDB.created_at)
            .all()
        )

        if not pending:
            st.info("No pending applications.")
        else:
            for p in pending:
                with st.expander(f"📋 {p.permit_id[:8]}... | {p.holder} | {p.purpose} | {p.state}"):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.json({
                            "permit_id": p.permit_id,
                            "holder": p.holder,
                            "type": p.type,
                            "purpose": p.purpose,
                            "named_users": p.named_users,
                            "data_scope": p.data_scope,
                            "format": p.format,
                            "pseudonymization_justification": p.pseudonymization_justification,
                            "submitted": str(p.created_at),
                        })
                    with col2:
                        if p.state == "submitted":
                            if st.button("Start review", key=f"review_{p.permit_id}"):
                                try:
                                    PermitStateMachine(p, db).start_review("reviewer")
                                    st.success("Moved to under_review")
                                    st.rerun()
                                except IllegalTransitionError as e:
                                    st.error(str(e))

                        if p.state == "under_review":
                            st.write("**Grant**")
                            valid_from = st.date_input("Valid from", value=date.today(),
                                                        key=f"vf_{p.permit_id}")
                            valid_until = st.date_input("Valid until",
                                                         value=date.today() + timedelta(days=7),
                                                         key=f"vu_{p.permit_id}")
                            if st.button("✅ Grant", key=f"grant_{p.permit_id}"):
                                try:
                                    PermitStateMachine(p, db).grant("reviewer", valid_from, valid_until)
                                    st.success("Permit granted.")
                                    st.rerun()
                                except IllegalTransitionError as e:
                                    st.error(str(e))

                            st.write("**Refuse**")
                            comment = st.text_area("Reason for refusal", key=f"comment_{p.permit_id}")
                            if st.button("❌ Refuse", key=f"refuse_{p.permit_id}"):
                                if not comment.strip():
                                    st.error("Refusal reason is required.")
                                else:
                                    try:
                                        PermitStateMachine(p, db).refuse("reviewer", comment)
                                        st.success("Application refused.")
                                        st.rerun()
                                    except IllegalTransitionError as e:
                                        st.error(str(e))
    finally:
        db.close()

with tab_all:
    st.subheader("All permits")
    db = SessionLocal()
    try:
        all_permits = db.query(PermitDB).order_by(PermitDB.created_at.desc()).all()
        state_icons = {"granted": "🟢", "refused": "🔴", "submitted": "🟡",
                       "under_review": "🔵", "draft": "⚪", "expired": "⚫"}
        for p in all_permits:
            icon = state_icons.get(p.state, "")
            st.write(f"{icon} `{p.permit_id[:8]}` | **{p.holder}** | {p.purpose} | {p.state} | {str(p.created_at)[:10]}")
    finally:
        db.close()
