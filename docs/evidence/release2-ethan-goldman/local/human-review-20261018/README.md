# Support human review — 18 October 2026

Ethan explicitly chose **Accept — “nothing needed.”** for both existing ticket
#2013 proposals. The decisions were recorded through the existing staff controls
in Chrome at `http://localhost:8005/staff-ticket.html?ticket=2013`.

| Workflow | ID | Saved decision (UTC) |
| --- | --- | --- |
| UI | `3a970ca5-0b90-4e7f-ab84-cd7beb089c28` | Accept, `2026-10-18T09:12:41.420750Z` |
| Terminal HTTP | `67702aa8-4a5f-4cd0-a311-8bd952ed18d5` | Accept, `2026-10-18T09:11:43.993558Z` |

Both reasons are exactly `nothing needed.`; the authenticated demo reviewer is
`user:1`. [UI screenshot](ui-accepted.jpg), [terminal screenshot after restart](terminal-accepted-after-restart.jpg),
[complete history](workflow_history.jsonl), [coordination audit](coordination_audit.jsonl)
and [verification](verification.json) retain the actual results. Each workflow has
one completion event and one matching human-review event. Live GETs match history;
the original request, all three model outputs, ticket fields and two messages are
unchanged. Approval sent no reply and applied no ticket update.

After both decisions, the single host server was stopped gracefully and restarted
with its retained files. Both complete workflows and the existing staff session
still worked; history/audit bytes and ticket data stayed unchanged. Chrome then
reloaded the terminal workflow and displayed its saved acceptance.

The real [selected Support review](../../../agentic/ethan-goldman-customer-support-multi-agent-20261018-201915-878486.md)
used Qwen 2.5 3B. Its [console](agentic-console.txt) and [validation](agentic-validation.json)
verify all three agents, matching history/audit, human approval and complete review
evidence. Model citation/agent-name grounding failed; the existing deterministic
fallback preserved the verified result and rejected unsupported model claims.
The tracked config was restored exactly after temporarily overriding the two
local log paths. The validation records the original/runtime config hashes and
overrides, without duplicating the entire config.

Support regression: **206 passed, 10 opt-in tests skipped**. Existing tests cover
accept, partial accept, reject, duplicate decisions, authorization, escaped output,
restart persistence and unchanged business data. New evidence is separately
scanned because the normal secret hook excludes `docs/evidence/`.

The application remains the isolated local demo at source `37e859a`; the review
and restarted host service use source `d389a49`. Original [17 October captures](../README.md)
remain unchanged and correctly describe their then-pending decisions. These
ticket decisions complete Support's local human-review step; other owners' local
evidence, final S17 group reviews and a separate human release decision remain.
No public AWS deployment or release approval is implied.
