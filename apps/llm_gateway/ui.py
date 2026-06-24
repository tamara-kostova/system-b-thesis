"""
Phase 5 — LLM Gateway Mode A Streamlit chat UI.

Run: streamlit run apps/llm_gateway/ui.py --server.port 8504
"""

import os
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://localhost:8006")

st.set_page_config(page_title="SecureHealth — Data Discovery", layout="wide")
st.title("SecureHealth — Data Discovery Assistant")
st.caption(
    "Ask questions about the dataset, search for concepts, and get help drafting a data access application. "
    "No permit required — all counts are suppressed at < 10."
)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_id" not in st.session_state:
    st.session_state.user_id = "anonymous"

with st.sidebar:
    st.header("Session")
    uid = st.text_input("Your name / researcher ID", value=st.session_state.user_id)
    if uid:
        st.session_state.user_id = uid
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.rerun()
    st.divider()
    try:
        health = requests.get(f"{GATEWAY_URL}/health", timeout=3).json()
        st.success(f"LLM: {health.get('provider', '?')}")
    except Exception:
        st.error("Gateway offline")

# Display history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input
if prompt := st.chat_input("Ask about the dataset…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                resp = requests.post(
                    f"{GATEWAY_URL}/chat",
                    json={
                        "messages": [
                            {"role": m["role"], "content": m["content"]}
                            for m in st.session_state.messages
                        ],
                        "user_id": st.session_state.user_id,
                    },
                    timeout=120,
                )
                if resp.ok:
                    reply = resp.json()["reply"]
                else:
                    detail = resp.json().get("detail", resp.text)
                    reply = f"**Error:** {detail}"
            except Exception as e:
                reply = f"**Could not reach gateway:** {e}"

        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
