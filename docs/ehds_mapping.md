# EHDS Chapter IV Compliance Mapping

Maps each implemented EHDS article to the exact file and line in System B.

---

| EHDS Article | Requirement | File | Line | Notes |
|-------------|-------------|------|------|-------|
| **Art. 50** | Output checking before release from SPE | `apps/output_airlock/checks.py` | 4 | `run_checks()` — chain of disclosure checks |
| **Art. 50** | Small-cell suppression on all counts | `shared/suppression.py` | 4 | `suppress()` — canonical single implementation |
| **Art. 50** | Small-cell suppression on all counts | `apps/discovery_api/routers/counts.py` | 9 | All count endpoints import from `shared.suppression` |
| **Art. 50** | Human review before output release | `apps/output_airlock/main.py` | 154 | `approve()` — reviewer must approve before download |
| **Art. 50** | Blocked output stays quarantined | `apps/output_airlock/main.py` | 96 | `submit()` — failed checks set `state="blocked"` |
| **Art. 53** | Six permitted purposes only | `shared/models.py` | 28 | `purpose` field: `public_health`, `policy`, `statistics`, `education`, `research`, `innovation` |
| **Art. 53** | Purpose validated at API boundary | `apps/permit_service/routers/permits.py` | 30 | `PermitCreate.purpose: Literal[...]` — invalid values rejected by FastAPI |
| **Art. 67** | Application submission process | `apps/permit_service/routers/permits.py` | 86 | `create_permit()` — draft permit creation |
| **Art. 67** | Permit creation audited | `apps/permit_service/routers/permits.py` | 98 | `log_event("permit.draft", ...)` — every new application is audit-logged |
| **Art. 67** | Application submission process | `apps/permit_service/routers/permits.py` | 142 | `submit()` — draft → submitted transition |
| **Art. 67** | Applicant UI | `apps/permit_service/applicant_ui.py` | 1 | Streamlit application form (calls REST API) |
| **Art. 68** | Permit lifecycle and conditions | `apps/permit_service/state_machine.py` | 26 | `PermitStateMachine` — enforces legal transitions |
| **Art. 68** | State transition table | `shared/models.py` | 6 | `PERMIT_TRANSITIONS` — single source of truth for legal states |
| **Art. 68** | Permit grant with validity dates | `apps/permit_service/state_machine.py` | 55 | `grant()` — sets `valid_from`, `valid_until`; rejects inverted date ranges |
| **Art. 68** | Permit refusal with reason | `apps/permit_service/state_machine.py` | 64 | `refuse()` — records reviewer comment |
| **Art. 68** | Permit expiry | `apps/permit_service/state_machine.py` | 68 | `expire()` — terminal state |
| **Art. 68** | Reviewer UI | `apps/permit_service/reviewer_ui.py` | 1 | Streamlit reviewer queue (calls REST API) |
| **Art. 68** | Public register of granted permits | `apps/permit_service/routers/permits.py` | 120 | `GET /permits/register` — public endpoint |
| **Art. 68** | Data minimisation — permit-scoped views | `apps/spe_provisioner/projection.py` | 56 | `create_projection()` — per-permit Postgres schema with domain-scoped patient subquery |
| **Art. 68** | Data minimisation — dedicated DB user | `apps/spe_provisioner/projection.py` | 100 | `CREATE USER` with SELECT on permit schema only |
| **Art. 68** | SPE isolation — no internet egress | `apps/spe_provisioner/provisioner.py` | 58 | Internal Docker network (`--internal`) |
| **Art. 68** | SPE teardown on permit expiry | `apps/spe_provisioner/provisioner.py` | 116 | `teardown()` — stops container, removes network |
| **Art. 68** | SPE teardown on permit expiry | `apps/spe_provisioner/projection.py` | 143 | `teardown_projection()` — drops schema and DB user |
| **Art. 68** | Automatic permit expiry on valid_until | `apps/permit_service/main.py` | lifespan | Background task runs hourly via `_expiry_loop()`, calls `_expire_due()` |
| **Art. 68** | Manual expiry trigger | `apps/permit_service/routers/permits.py` | POST /permits/expire-due | Returns `{"expired": n}` — also callable via `make expire` |
| **Art. 73** | Audit log — queryable DB record | `shared/audit.py` | 29 | `AuditEvent` SQLAlchemy model — every event written to `audit.event` table |
| **Art. 73** | Audit log — every state transition | `apps/permit_service/state_machine.py` | 31 | `_transition()` calls `log_event()` on every change; audit row commits atomically with state change |
| **Art. 73** | Audit log — container lifecycle | `apps/spe_provisioner/provisioner.py` | 99 | `log_event("spe.started", ...)` |
| **Art. 73** | Audit log — notebook saves | `spe_jupyter_config.py` | 1 | Post-save hook writes audit event to stdout |
| **Art. 73** | Audit log — airlock submissions | `apps/output_airlock/main.py` | 122 | `log_event("airlock.submitted", ...)` |
| **Art. 73** | Audit log — airlock approval | `apps/output_airlock/main.py` | 171 | `log_event("airlock.approved", ...)` |
| **Art. 73** | Audit log — airlock rejection | `apps/output_airlock/main.py` | 193 | `log_event("airlock.rejected", ...)` |
| **Art. 73** | Audit log — file downloads | `apps/output_airlock/main.py` | 206 | `log_event("airlock.downloaded", actor=requester, ...)` — requester identified |
| **Art. 73** | Audit log — LLM tool calls | `apps/llm_gateway/main.py` | 139 | `log_event("llm.tool_call", ...)` |
| **Art. 73** | Audit log — PII rejections | `apps/llm_gateway/main.py` | 157 | `log_event("llm.pii_rejected", ...)` |
| **Art. 73** | Single audit function | `shared/audit.py` | 54 | `log_event()` — all services import this; writes to both Python logger and `audit.event` DB table |

---

## Illegal transition protection (Art. 68)

Attempts to move a permit to a non-permitted state raise `IllegalTransitionError` (`apps/permit_service/state_machine.py:22`). The legal transition table is defined once in `shared/models.py:6` (`PERMIT_TRANSITIONS`) and imported by the state machine. Verified by 16 unit tests in `tests/test_state_machine.py`, including checks that illegal transitions never write an audit event.

## Small-cell suppression integrity (Art. 50)

`suppress()` is the single implementation at `shared/suppression.py:4`. All count-returning API endpoints import from `shared.suppression`. The threshold constant `THRESHOLD = 10` lives in the same file and is also imported by the airlock checks so no threshold value is duplicated. Verified by 5 unit tests in `tests/test_suppression.py` and 5 integration tests in `tests/test_counts_endpoint.py` that exercise the live endpoint layer.

## Concept ID integrity (LLM guardrail)

Concept IDs used in `estimate_count` and `draft_application` must have been returned by `search_concept` or `get_concept_descendants` in the current session. The allowlist (`allowed_concept_ids: set[int]`) is initialised empty at the start of each tool loop (`apps/llm_gateway/main.py:112`), seeded from tool results at line 142–143, and passed to `execute_tool` at line 141. Enforcement is in `apps/llm_gateway/tools.py:164` (`estimate_count`) and line 181 (`draft_application`). Documented in `redteam/adversarial_prompts.md` attacks #12–#13.
