# EHDS Chapter IV Compliance Mapping

Maps each implemented EHDS article to the exact file and line in System B.

---

| EHDS Article | Requirement | File | Line | Notes |
|-------------|-------------|------|------|-------|
| **Art. 50** | Output checking before release from SPE | `apps/output_airlock/checks.py` | 4 | `run_checks()` — chain of disclosure checks |
| **Art. 50** | Small-cell suppression on all counts | `apps/discovery_api/suppression.py` | 4 | `suppress()` — single function, never duplicated |
| **Art. 50** | Small-cell suppression on all counts | `apps/discovery_api/routers/counts.py` | 1 | All count endpoints import and call `suppress()` |
| **Art. 50** | Human review before output release | `apps/output_airlock/main.py` | 143 | `approve()` — reviewer must approve before download |
| **Art. 50** | Blocked output stays quarantined | `apps/output_airlock/main.py` | 85 | `submit()` — failed checks set `state="blocked"` |
| **Art. 53** | Six permitted purposes only | `shared/models.py` | 18 | `purpose` field: `public_health`, `policy`, `statistics`, `education`, `research`, `innovation` |
| **Art. 67** | Application submission process | `apps/permit_service/routers/permits.py` | 84 | `create_permit()` — draft permit creation |
| **Art. 67** | Application submission process | `apps/permit_service/routers/permits.py` | 131 | `submit()` — draft → submitted transition |
| **Art. 67** | Applicant UI | `apps/permit_service/applicant_ui.py` | 1 | Streamlit application form |
| **Art. 68** | Permit lifecycle and conditions | `apps/permit_service/state_machine.py` | 35 | `PermitStateMachine` — enforces legal transitions |
| **Art. 68** | Permit grant with validity dates | `apps/permit_service/state_machine.py` | 63 | `grant()` — sets `valid_from`, `valid_until` |
| **Art. 68** | Permit refusal with reason | `apps/permit_service/state_machine.py` | 68 | `refuse()` — records reviewer comment |
| **Art. 68** | Permit expiry | `apps/permit_service/state_machine.py` | 72 | `expire()` — terminal state |
| **Art. 68** | Reviewer UI | `apps/permit_service/reviewer_ui.py` | 1 | Streamlit reviewer queue |
| **Art. 68** | Public register of granted permits | `apps/permit_service/routers/permits.py` | 109 | `GET /permits/register` — public endpoint |
| **Art. 68** | Data minimisation — permit-scoped views | `apps/spe_provisioner/projection.py` | 56 | `create_projection()` — per-permit Postgres schema |
| **Art. 68** | Data minimisation — dedicated DB user | `apps/spe_provisioner/projection.py` | 86 | `CREATE USER` with SELECT on permit schema only |
| **Art. 68** | SPE isolation — no internet egress | `apps/spe_provisioner/provisioner.py` | 56 | Internal Docker network (`--internal`) |
| **Art. 68** | SPE teardown on permit expiry | `apps/spe_provisioner/provisioner.py` | 114 | `teardown()` — stops container, removes network |
| **Art. 68** | SPE teardown on permit expiry | `apps/spe_provisioner/projection.py` | 127 | `teardown_projection()` — drops schema and DB user |
| **Art. 73** | Audit log — every state transition | `apps/permit_service/state_machine.py` | 40 | `_transition()` calls `log_event()` on every change |
| **Art. 73** | Audit log — container lifecycle | `apps/spe_provisioner/provisioner.py` | 97 | `log_event("spe.started", ...)` |
| **Art. 73** | Audit log — notebook saves | `spe_jupyter_config.py` | 1 | Post-save hook writes audit event to stdout |
| **Art. 73** | Audit log — airlock submissions | `apps/output_airlock/main.py` | 110 | `log_event("airlock.submitted", ...)` |
| **Art. 73** | Audit log — airlock decisions | `apps/output_airlock/main.py` | 157 | `log_event("airlock.approved/rejected", ...)` |
| **Art. 73** | Audit log — file downloads | `apps/output_airlock/main.py` | 198 | `log_event("airlock.downloaded", ...)` |
| **Art. 73** | Audit log — LLM tool calls | `apps/llm_gateway/main.py` | 118 | `log_event("llm.tool_call", ...)` |
| **Art. 73** | Audit log — PII rejections | `apps/llm_gateway/main.py` | 141 | `log_event("llm.pii_rejected", ...)` |
| **Art. 73** | Single audit function | `shared/audit.py` | 9 | `log_event()` — all services import this |

---

## Illegal transition protection (Art. 68)

Attempts to move a permit to a non-permitted state raise `IllegalTransitionError` (`apps/permit_service/state_machine.py:31`). Verified by 11 unit tests in `tests/test_state_machine.py`.

## Small-cell suppression integrity (Art. 50)

`suppress()` is the single implementation at `apps/discovery_api/suppression.py:4`. All count-returning API endpoints call it. Verified by 5 unit tests in `tests/test_suppression.py`. The function is never duplicated elsewhere in the codebase.
