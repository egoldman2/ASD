# Release 1 master implementation plan

Baseline inspected: **18 September 2026**, local `main` at **`bccf637`**. Ethan Goldman's latest commit is **`52b3b5a`**, `update README`, 9 September 2026. This plan compares `52b3b5a..bccf637` and reads the current implementation. It is a source/history audit, not a claim that the current stack or CI has been rerun successfully. Remote changes after the local checkout are not covered.

## 1. Instructions for agents using this plan

**The default task is implementing and validating working software. Do not treat the technical report, presentation/slides, showcase video, report diagrams, or contribution-log prose as key implementation requirements or blockers. Work on those only when Ethan explicitly asks.** Capture useful test results and required agentic validation outputs as part of engineering work; do not turn a coding stage into a report-writing exercise. RAG knowledge files are runtime application data and remain in scope.

**On every user prompt handled under this plan, create or update the separate `RELEASE_1_ETHAN_GOLDMAN_WORK_LOG.md` file at the repository root. Append one concise entry summarising the specific work performed for that prompt before the final response.** Keep one running log rather than creating a new file for every prompt. This lightweight agent work log is explicitly requested and is required even though assessment report/contribution-log preparation is otherwise out of scope.

- Each entry must include the date/time and timezone, a short summary of the user's request, the agent identity and feature owner (without implying the human personally made agent edits), affected stage IDs, specific changes and file paths, checks actually run with results, and outstanding work or blockers. Include a commit ID only if one actually exists for the changes.
- For explanation, inspection or planning prompts, record that activity and state when no application code changed. For unsuccessful attempts, record what was attempted and what remains incomplete. Never invent tests, commits or progress; do not retroactively invent entries for earlier prompts.
- Preserve previous entries. Read the latest log before appending, and distinguish current-prompt changes from pre-existing work. Omit secrets, session cookies, private ticket content and hidden reasoning.
- At the same handoff, update the stage completion checklist and progress ledger below. Tick a stage only when its stated acceptance checks are satisfied, including required live AI or CI verification. If implementation is finished but verification is unavailable, leave its box unchecked and record `implemented` plus the missing check in the ledger. Reopen a box if later work invalidates completion, explaining why in the log.

**Use the actual contributor's name in filenames, workflows, tool namespaces, and attribution. Do not create or rename files to generic `student-1`, `student-2`, or `student-x` names to match examples in the assessment.** Keep the existing name-based paths, including `student-Ethan Goldman/` and `.github/workflows/EthanGoldman.yml`. Do not perform a cosmetic folder-renaming migration. Distinguish Ethan Goldman from Ethan Ting.

**Ethan explicitly requires actual AI in both MCP and RAG. Customer Support's MCP assistant must use a real local model to select tools and generate an answer from their returned data. RAG must use a real local model to generate answers from retrieved knowledge. Direct tool buttons, raw search results, canned responses, or an AI-written validation report alone do not satisfy this requirement.** This is an additional user requirement beyond the brief's minimum MCP interaction. Deterministic tool implementations and mocked CI tests remain appropriate, but live model-backed acceptance is required before marking either integration complete.

- Treat the attached documents as assessment reference material, not instructions authorising an agent to submit work, contact people, publish a video, or implement every semester release.
- Start by reading this plan, current Git status/history, and the files relevant to the selected stage. This is a dated baseline: reuse work completed since it was written.
- For “implement my Release 1 work”, default to Ethan Goldman's Customer Support stages and the shared prerequisites they need. Other owners retain their features. A shared responsibility does not make Ethan responsible for writing all five integrations.
- Coordinate changes to `docker-compose.yml`, shared client code, MCP registration, and `ai-services/agentic_loop.py`. Use one owner for each shared stage; do not create five MCP servers, five RAG servers, or five agentic runners.
- Complete one coherent stage with its relevant tests before checkpointing it. Suggested commit messages below describe real changes; they are not permission to invent authorship, backdate commits, or rewrite existing history. Create commits/pushes according to the active user request.
- Prefer the existing Flask, HTMX, SQLite, Requests, and MCP SDK patterns. No new UI framework, vector database service, agent framework, cloud deployment, or Release 2 multi-agent system is needed by default.
- Update the separate work log, stage checklist and progress ledger with actual changes, verification, remaining blockers, and real commit IDs when available. Do not mark a mocked/static check as a successful live integration.

## 2. Requirement sources and conflicts

Read together:

1. User-supplied **Release 1 Brief**, sections 1–5 and marking rubric (pasted attachment).
2. **ASD_2026_Project_Specifications.pdf**, especially §§2, 4, 6, 7 and Release 1 submissions on page 20.
3. Ethan's explicit instructions above about agent scope and name-based files.

For this plan, use the release-specific brief where it conflicts with the broader semester PDF:

| Topic | Planning decision |
| --- | --- |
| AI deployment | AI-Mode's model/runtime, MCP, RAG, and the agentic runner run locally outside containers. Feature frontends, APIs and databases stay containerised. The general PDF §6.3 says to containerise AI services; the Release 1 brief repeatedly says not to. Thin backend clients still belong in the feature APIs. |
| CI | Keep integration code, but disable live AI-Mode, MCP, and RAG during CI. Exercise contracts with deterministic substitutes and prove disabled routes do not contact those services. |
| Deadline | Pasted brief: **4 October 2026, 11:59 PM AEST**. General PDF: **27 September 2026, 11:59 PM AEST**. Use the brief as the planning assumption; the team should verify the current Canvas deadline/timezone. No live Canvas verification was performed. |
| Naming | Existing actual-name workflows/directories satisfy this implementation plan; generic numbered examples are not a renaming task. |
| Assessment artefacts | Still human/team assessment obligations, but outside agents' default implementation scope. |

Release 1 is worth 30 marks across ten equally weighted criteria: setup/architecture, retained microservices, MCP, RAG, agentic loop, CI, Compose, integrated software, technical report/evidence, and demonstration/Q&A. Several software criteria also allocate marks to report evidence. Excluding report preparation from agent work does not remove those assessment obligations.

## 3. What has changed since Ethan's Release 0 work

The local history contains 19 commits after `52b3b5a`, including merges. The diff spans 49 files, with 4,886 insertions and 10 deletions. No Customer Support implementation or Goldman workflow changes appear in that range.

| Work | Evidence in history/current files | Actual status |
| --- | --- | --- |
| Follow-up Release 0 material | `765bf0c` updates README and adds Ethan Ting architecture review evidence | Not a new feature integration. |
| Shared MCP foundation | `29eefbb`, `e44912e`, `0454348`; `ai-services/mcp_server/` | FastMCP Streamable HTTP server at `/mcp`, default port 8765; configuration, health route, structured success/error envelopes and transport host restrictions exist. |
| Catalogue MCP tools | `d6c5ab0`; `tools/chufeng_catalogue.py` | Four read-only tools: product search, product details, stock check, proposed-cart summary. They use the Product Database API. |
| Protocol and tool tests | `d90f0f4`; `ai-services/mcp_server/tests/` | Test code covers protocol, configuration, catalogue operations and boundaries. Presence is not a fresh passing run. |
| Catalogue backend and UI | `2860190`, `ba36bcb`, `ca37b28`, `dc1ae4c` | MCP client with tool allowlist, `/api/chufeng/mcp/*` routes, a dedicated tools page and frontend/client/route tests exist. |
| Host bridge | `d71ca57`; `docker-compose.yml` | Shared backend receives MCP URL/enable/timeout settings and host mapping; Product Database API is published on port 6001 for the host MCP process. Other backends lack MCP/RAG wiring. |
| Chufeng CI | `d6e57c1`; `.github/workflows/Chufeng.yml` | Declares AI/MCP/RAG disabled, runs catalogue/MCP tests, builds frontend/shared backend/database. No RAG implementation accompanies the flag. |
| MCP agentic validation | `3a427a9`, `c99205f`; `ai-services/agentic_loop.py` | MCP mode exists, but imports Chufeng's client and hard-codes Chufeng paths/checks. It is not yet a general five-feature validator. |
| Saved validation | `docs/evidence/agentic/chufeng-product-catalogue-and-shopping-cart-mcp-20260912-201208.md` | Committed evidence records tool discovery and a successful live probe on Chufeng's machine. It does not prove all features or today's environment work. |

### Remaining gaps and inherited issues

- `ethan_goldman_support.py`, `ethan_ting_customer.py`, `howard_orders.py`, and `ryan_inventory.py` under MCP `tools/` are **empty**. The server registers only Chufeng's four tools and hard-codes that count in health output.
- There is **no shared RAG server, retrieval corpus/index, grounded-response flow, frontend RAG integration, or RAG agentic mode** in the current tree.
- Customer Support remains the Release 0 independent frontend/backend/database implementation, with role/ownership checks and advisory Ollama triage. Its existing source references are not a substitute for the shared RAG requirement.
- Compose still defines `ollama` and `ollama-init`; shared backend, support and inventory depend on them. Ethan Ting already points to host Ollama. This mixed deployment must be corrected for Release 1.
- Goldman CI starts Ollama, pulls a model, and checks real AI output. Its agentic configuration also asserts the old containerised Ollama setup. Update both together.
- `AI_MODE_ENABLED` and `RAG_ENABLED` occur as CI settings/checks, but no application Python implementation currently enforces them. Environment declarations alone do not disable a feature.
- Existing architecture/MCP evidence placeholder files are empty. Do not confuse scaffolding with completion or spend implementation stages filling report placeholders.
- The current topology is not five independent service triples: catalogue and orders use the shared backend; inventory uses the shared Product Database API; orders open SQLite in the shared backend. The brief describes per-student frontend/API/database microservices. This is an inherited team architecture gap, not something to silently claim is compliant or rebuild inside Ethan's support task. Howard owns the orders database/API separation; Ryan and Chufeng must resolve the shared inventory/catalogue database ownership against the team's agreed assessment interpretation.
- Howard's workflow builds only the frontend; Ryan's builds frontend and test targets. Their Release 1 workflows must validate the actual backend/database services as well.

## 4. Responsibilities

### Shared group responsibilities

The group delivers one integrated marketplace with all five existing features operational, one host MCP server, one host RAG server, the existing local AI capability, and one shared local agentic runner. Every feature must expose both MCP and RAG through its own frontend and backend/API. At least one successful UI-to-backend MCP interaction and one grounded RAG interaction are required per feature.

The group must agree on shared request/response contracts, source ownership, service configuration, tool boundaries and merge ownership; integrate the feature services through Compose; retain authentication and CRUD; extend the shared loop with MCP and RAG validation; and validate the whole application on one machine. A standalone feature is not sufficient: the brief assigns zero for Working Software if it is not integrated.

No repository evidence establishes who has accepted ownership of the remaining shared RAG/runtime/runner work. **Chufeng's MCP authorship is established; the other shared owners below are proposed roles to allocate, not claimed assignments.** Ethan can implement a shared prerequisite when necessary, but should record it as shared work.

### Individual feature ownership

| Person | Existing feature and path | Release 1 responsibility |
| --- | --- | --- |
| Chufeng Li | Catalogue/cart, `student-Chufeng/`, `Chufeng.yml` | Preserve existing MCP slice; add catalogue RAG sources/API/UI; adapt to shared runner/runtime changes; verify the catalogue workflow. |
| Ryan Nolan | Inventory, `student-Ryan_Nolan/`, `Ryan.yml` | Implement inventory MCP tools/API/UI and RAG sources/API/UI, retain admin protections and stock/supplier operations, validate backend/database deployment. |
| Ethan Ting | Customer accounts/loyalty, `student-Ethan Ting/`, `EthanTing.yml` | Implement customer/loyalty MCP and RAG; retain sessions, role checks and human confirmation for existing AI changes. Keep credentials/account data out of public retrieval. |
| Howard Ong | Orders/returns, `student-Howard/`, `Howard.yml` | Implement order/return MCP and RAG with customer ownership/admin boundaries; resolve existing service separation and workflow coverage gaps. |
| **Ethan Goldman (you)** | Customer Support, `student-Ethan Goldman/`, `EthanGoldman.yml` | Add support MCP tools, backend routes and HTMX UI; add support RAG sources/backend/UI; preserve ticket CRUD, conversations, permissions and existing triage; extend support validation configuration and update your workflow. |

Each owner integrates their work into the shared repo, supplies relevant tests/runtime outputs, keeps identifiable Release 1 commits, and can explain their contribution. Sharing server infrastructure does not remove individual frontend/backend integration obligations.

### Human assessment obligations, outside default agent work

The team submits one PDF report (maximum 3,000 words plus diagrams) and one video URL (maximum 10 minutes), with repository link, validation evidence and individual contribution logs. One person submits the group report. Each student must attend the Week 9 showcase and explain/defend their work; the pasted brief says non-attendance results in zero. Agents should not draft, record, submit or polish these deliverables unless asked.

## 5. Target implementation decisions

### Runtime and boundaries

```text
Containerised feature frontend
  -> its containerised backend/API (authentication, input validation, allowlist)
       -> existing database service (normal CRUD)
       -> host Ollama selects support tools
          -> backend validates calls -> host MCP /mcp -> authorised data API
          -> tool results return to host Ollama -> grounded support answer
       -> host RAG /query -> scoped retrieval -> host Ollama -> validated answer
       -> host Ollama (existing AI-Mode)

Host agentic_loop.py -> selected feature's MCP/RAG validation -> captured outputs
```

- Keep MCP port 8765 and existing response envelope (`success`, `tool`, `result`, `error`, optional `metadata`). Use genuine MCP tool discovery/calls, not a similarly named REST substitute.
- Proposed RAG service: `ai-services/rag_server/`, HTTP port 8766, `/health` and `/query`. These are plan choices, not existing endpoints. Use Flask and a small local retrieval index; SQLite FTS5 is a reasonable starting point if available. Add embeddings only if measured retrieval quality needs them.
- Use explicit `AI_MODE_ENABLED`, `MCP_ENABLED`, `RAG_ENABLED` switches in the code paths that actually call services. Pass them through Compose. The support MCP assistant requires both AI and MCP enabled; the support RAG assistant requires both AI and RAG enabled. Direct diagnostic MCP calls only require MCP. Disabled assistant routes must return before any model/tool/retrieval call. Offline feature CRUD and health checks must work without host AI services.
- Container clients use configurable `host.docker.internal` URLs and required host-gateway mapping. Host tools use published feature APIs through `127.0.0.1`; never use Docker-only DNS from a host process. Test the real bind/interface configuration. Preserve MCP host restrictions; avoid unnecessarily publishing database APIs on all interfaces.
- Existing clients/tool functions and tests should be reused. A shared protocol client must be included in each consuming Docker image; a repo-only import that fails in Goldman's narrowly copied backend image is not complete.
- Keep MCP extensions read-only initially. **Ethan explicitly requests four Customer Support tools; all four below are required for his implementation.** The assessment's minimum interaction requirement does not reduce that scope or impose four tools on other owners. Do not allow the model to write data or expose arbitrary SQL, file paths or upstream URLs.

### Proposed Customer Support slice

MCP: implement **four distinct, read-only staff tools** on the existing shared server and an **AI support assistant that chooses and uses them**. They support finding tickets, understanding one case, reviewing workload, and deciding which cases need attention. These are planned capabilities, not tools already implemented. The tools themselves use deterministic application logic to return trustworthy support data; the local model chooses the appropriate tools/arguments and explains their results. Keep tool execution independent of RAG so each mode can be demonstrated separately.

| Registered tool | Staff use case | Inputs | Structured result and UI location |
| --- | --- | --- | --- |
| `ethan_goldman_search_tickets` | Find relevant cases, such as unassigned delivery tickets or an existing ticket by its subject/ID. | Optional `search`, `status`, `category`, `priority`, `assigned_to`; bounded `limit` and `offset`. Reuse existing search/filter semantics and enum values. | Matching ticket IDs, redacted subjects, status/category/priority, assignee and update time; total matches and pagination metadata. No conversation bodies. A search action in the staff queue's MCP panel renders selectable ticket rows. |
| `ethan_goldman_get_ticket_context` | Understand the selected case before replying or changing triage. | Positive `ticket_id`; bounded `message_limit`. | Ticket ID, redacted subject, status/category/priority, assignee, timestamps and recent redacted messages with sender role; total message count and truncation metadata. A ticket-detail MCP action renders the context. |
| `ethan_goldman_get_queue_summary` | See the overall workload: how many tickets are open, pending, urgent or unassigned. | Optional `category` and `assigned_to` filters; no date window or historical trend feature initially. | Total tickets, counts by status and priority, unresolved count and unresolved-unassigned count, applied filters and observation time. A queue overview action renders labelled counts. Counts cover the complete filtered set, not just a displayed page. |
| `ethan_goldman_get_tickets_needing_attention` | Find unresolved cases worth reviewing next and explain why they were flagged. | Optional `category` and `assigned_to`; `inactive_hours` (default 48, allowed 1–720); bounded `limit` and `offset`. | Ticket summaries with explicit reason codes/labels, last activity time, priority, total matches and pagination metadata. An attention-list action in the staff queue links to each flagged ticket. |

Shared tool rules:

- Require a verified **admin** session for all four tools, including direct MCP calls. The current staff interface uses the `admin` role. Customer-facing equivalents are outside this four-tool scope; existing customer ownership protections remain unchanged.
- List tools default to 20 results and cap at 50; validate non-negative offsets and reject excessive offsets (proposed maximum 10,000). Ticket context defaults to the latest 20 messages and caps at 50, displayed chronologically. Apply query/message limits at the data API/database layer, not only after fetching all conversations. Return truncation/continuation metadata rather than silently omitting results.
- Reuse existing enums: status `needs_triage`, `open`, `pending`, `solved`; priority `unclassified`, `low`, `medium`, `high`, `urgent`. `assigned_to=unassigned` retains the existing null-assignee meaning. Unsupported filters, invalid enums and malformed pagination return structured input errors.
- Search and attention lists return compact fields; only the context tool returns bounded message text. Redact sensitive content in subjects/messages and omit customer name/email snapshots and credentials. Staff assignee labels can remain visible to authorised staff.
- Queue totals come from aggregate database queries over the full authorised, filtered set. Avoid fetching every ticket and conversation merely to count them. Define unresolved as `status != solved`; the priority breakdown includes all filtered tickets, while unresolved/unassigned metrics are labelled explicitly.
- The attention tool excludes solved tickets and includes an unresolved ticket when **any** of these reasons applies: `needs_triage`; no assignee; priority is `high` or `urgent`; the most recent message is from the customer (`awaiting_staff_reply`); or no activity for at least `inactive_hours`. Define activity as the latest ticket-update or message timestamp. Return every applicable reason. The 48-hour default is a review heuristic, **not an agreed SLA or overdue promise**.
- Sort attention results deterministically: priority (`urgent`, `high`, `medium`, `low`, `unclassified`), then oldest last activity, then ticket ID. Apply this order before pagination. Use UTC comparisons and a controllable clock in tests. The tool reports recorded facts and reasons; it does not infer sentiment, change priorities, assign tickets or send replies.
- Reuse the support backend and database-service structure. Existing list reads currently load all matching conversations; add bounded list/context reads and small summary/attention query operations where needed, with tests. Keep SQL and aggregation in `database_service/`; avoid a new analytics service, background scheduler or duplicated ticket store.

Private ticket reads require a verified session. Forward the originating session securely as per-request transport context to the host tool, and have the tool call an authenticated Support read endpoint on port 6005. Reuse existing reads or extend them for the bounded/aggregate operations above. Those endpoints revalidate the admin session. Do not accept a caller-supplied `role`, `customer_user_id`, or ticket ID as proof of access, log credentials, publish the internal support database API, or allow unauthenticated direct MCP reads. The callback must use a normal read endpoint, never the MCP route itself. If transport credential forwarding requires SDK-specific handling, verify it against the pinned SDK before implementing. Public catalogue tools can remain public.

All four tools must be discoverable and individually callable from the staff UI through the support backend, using its exact four-tool allowlist. Keep existing queue search and CRUD usable independently. Reuse the current staff queue and ticket-detail layouts, adding an MCP assistant and compact tool controls rather than a separate dashboard application. Direct controls can inspect tool results, but the main MCP demonstration must use the model-backed flow below.

### Required AI use with MCP

The support backend orchestrates a small request-scoped tool-calling loop; the model runs in host Ollama and tools run in the shared host MCP server. No separate model/server per tool, persistent agent system or Release 2 multi-agent framework is needed.

1. Staff submit a natural-language question, optionally with the selected ticket ID. Authenticate the staff session and validate the question first.
2. Discover the four support tools through MCP and pass their descriptions/input schemas, the question and minimal authorised context to the local model. Use an approved Qwen/Llama/DeepSeek model that actually passes a local tool-calling smoke test; do not assume the existing `qwen2.5:0.5b` can reliably select tools. Allow a separate configured assistant model without changing the existing triage model unnecessarily.
3. The **model selects the tool name and arguments**. The backend validates the selection against the four-tool allowlist, schema and request limits, and forwards trusted credentials separately from model content. Reject invented tools/arguments and tool-output instructions. A keyword switch that always chooses the tool in application code is not the planned AI selection.
4. Execute through the real MCP client/server, then send the bounded/redacted result back to the model. Permit a short sequence where useful, such as search -> ticket context, with a maximum of three tool calls and four model requests, plus a total request timeout. Any correction attempt counts toward those bounds.
5. The model produces a staff-facing answer grounded in the observed results, referencing returned ticket IDs or labelled queue counts. Return the actual structured results alongside the explanation so staff can inspect the evidence. Verify reference IDs and structured facts against the results; test representative prose for consistency rather than claiming schema validation proves every sentence true.
6. If required information is missing, ask for clarification or report the limitation. If the model, MCP server or validation fails, show an explicit failure/partial-result state. Do not present canned prose or raw tool output as a successful AI answer. Never let generated advice apply triage, send a reply or otherwise mutate records.

Representative live demonstrations (test each of the four tools through model selection):

| Staff question | Expected tool use | Expected AI contribution |
| --- | --- | --- |
| “Find unassigned delivery tickets.” | `ethan_goldman_search_tickets` with the appropriate filters | Explain the matching cases, referencing returned ticket IDs and respecting pagination. |
| “Summarise the conversation and current state of ticket 2002.” | `ethan_goldman_get_ticket_context` | Summarise the actual redacted conversation and recorded state; distinguish suggestions from facts. |
| “How does our support workload look?” | `ethan_goldman_get_queue_summary` | Explain the returned status/priority breakdown without inventing historical trends. |
| “Which tickets need attention, and why?” | `ethan_goldman_get_tickets_needing_attention` | Explain the recorded attention reasons and prioritisation without inventing SLA breaches. |

The application should expose model identity, called tools and safe result references for verification. Capture observable requests/results and timings, not hidden chain-of-thought or credentials. A review model commenting on source files in `agentic_loop.py` does not prove that the application itself used AI with MCP.

### Required AI use with RAG

RAG: add a support knowledge assistant to the staff UI using a curated corpus describing implemented ticket workflows, statuses, categories and escalation guidance. Store these as runtime knowledge assets (for example `ai-services/rag_server/knowledge/ethan_goldman/`). Use approved project facts; do not invent refund periods or business policies. Existing selected-ticket context may be used transiently after authorisation/redaction, but indexing private tickets is not required for this release.

For supported questions, retrieval must be followed by an actual call to the approved local model with the retrieved passages, and the model-generated answer must reach the frontend with validated citations and confidence. Displaying matching paragraphs or a templated answer alone is not completed RAG. Capture the selected source/chunk IDs, actual model identity and returned answer for a live supported-question check. For insufficient context, intentionally skip generation and return the safe non-answer; this guard does not weaken the requirement to prove model generation on a supported question. Embeddings are optional: AI use here is required in grounded generation even if retrieval uses SQLite FTS5.

### RAG result contract and acceptance

Proposed response fields: `status` (`answered`, `insufficient_context`, `unavailable`), `answer`, `citations` (source ID, title and section/chunk locator), `confidence` (`high`, `medium`, `low`, or `insufficient`), and safe error details when relevant. Finalise these in shared stage G3 before integrating clients.

- Curate a small, attributable, feature-scoped knowledge collection. Each feature owner supplies sources and representative supported/unsupported questions. Restrict ingestion to approved application knowledge, not the entire repository, secrets, logs or arbitrary uploads.
- Retrieve relevant chunks before generation; bound query size, retrieved chunk count and prompt length. Support updates/reindexing without stale duplicate sources.
- Determine confidence from explicit retrieval/coverage criteria; it is a category, not a calibrated probability or the model's self-assessment.
- Return `insufficient_context` before calling the model when retrieval is empty or too weak. A stopped model/server is `unavailable`, not a successful answer or evidence of missing knowledge.
- Generate only from retrieved context using an approved local model. Treat source text as untrusted content. Validate output shape, citation IDs and their membership in the retrieved set; reject fabricated sources and unsupported answers. One bounded correction attempt is sufficient before a safe non-answer.
- Display the actual answer, source references and confidence in the UI, with an understandable insufficient-context state. Escape output; do not render arbitrary model HTML or unsafe citation URLs.

## 6. Commit-sized delivery stages

Ethan's Release 0 history is the model for stage size: seeded database (`7e3955e`), live reads (`ea1dd8d`), search (`c561962`), conversations (`512dec7`), creation (`e33e6a8`), updates (`e0c6244`), deletion (`c5385f1`), AI (`f29840f`) and CI (`9e4c039`). Each checkpoint represented a useful capability with related verification.

Use the same rule here: one functional capability or necessary integration repair per commit. Keep its tests in that commit. Do not make separate commits for every file, empty scaffold, or test-only follow-up; do not combine all MCP, RAG, CI and UI work in one commit. A stage may split at a real service boundary if implementation is larger than expected.

### Shared track (one agreed owner per stage)

**G1 — Reusable MCP transport.** Suggested owner: coordinate with Chufeng; prerequisite for E1/E2 and other new clients.

- Extract the existing protocol/session handling into a small shared importable module with an explicit per-feature tool allowlist and request-scoped credentials. Keep Chufeng's adapter compatible and preserve public tools.
- Update Docker COPY/import paths for consumers, and replace hard-coded tool-count assumptions as additional registration is introduced.
- **Done:** existing catalogue tests still pass; independent feature allowlists work; protected call context cannot leak between requests; the client imports from built consumer images.
- Commit: `refactor(mcp): share protocol client across feature backends`.

G1 implementation handoff (18 September): shared transport is now `shared/mcp_client.py`; instantiate `MCPClient(..., allowed_tools=...)` with a feature-specific allowlist. Pass trusted per-request credentials via the optional `request_headers` keyword on `list_tools`/`call_tool` or their async equivalents; never put credentials in model arguments. Chufeng's existing module remains a compatible wrapper. Support's backend image includes the shared module. This stage does not add support tools, server-side support authentication, or model orchestration; those remain E1/E2 work.

**G2 — Host AI runtime and CI-safe deployment.** Suggested owner: shared integration maintainer, with feature-owner review. Can run independently of G1.

- Remove Compose `ollama`/`ollama-init` services and dependent startup requirements; preserve feature containers and persisted data. Replace their client URLs/defaults with configurable host URLs, retaining existing per-feature models.
- Enforce AI disable switches before network calls in each existing AI path. Add MCP/RAG host URL, timeout and switch settings to all consuming backends. CRUD startup must not require an AI health check.
- Adapt Goldman CI's old Ollama startup/real-AI expectations immediately so this deployment change does not intentionally leave it broken. Move live checks to explicit local validation; retain deterministic AI tests. Fix relevant Docker defaults and agentic source assertions in the same change.
- **Done:** Compose contains no AI runtime/MCP/RAG/runner services; feature containers start with AI modes disabled; host-enabled existing AI works locally; disabled routes make no external AI calls. If this spans too much code, land per-feature disable guards first, then the Compose/CI cutover as a coherent integration commit.
- Commit: `fix(runtime): run AI services on the host outside Compose`.

**G3 — Shared retrieval service.** Suggested owner: agreed RAG maintainer. Independent of MCP work.

- Implement the local RAG HTTP service, query validation, approved source loading, reproducible local index and bounded feature-scoped retrieval. Finalise the result contract above. Include one real support knowledge fixture and deterministic supported/unsupported queries.
- Return source metadata and retrieval results for validation; do not claim retrieval-only output is a generated answer.
- **Done:** relevant queries find the intended sources, unrelated queries yield no usable context, feature scoping holds, and source updates rebuild correctly. Include health/invalid-input checks.
- Commit: `feat(rag): add shared local knowledge retrieval`.

**G4 — Grounded generation.** Same RAG owner; depends on G3.

- Add bounded host Ollama generation, validated source citations, explicit confidence rules, correction/failure handling and the insufficient-context short circuit.
- **Done:** deterministic tests cover grounded output, invented citations, unrelated context, malformed model output and model unavailability. A live supported query records retrieved chunks, a real model request/response and the resulting answer/citations; an unsupported query produces a non-answer without generation. Stopping the model produces an unavailable state, never a fabricated successful answer.
- Commit: `feat(rag): generate cited answers from retrieved context`.

**G5 — Feature-aware MCP validation mode.** Suggested owner: shared runner maintainer; depends on G1 and at least one non-catalogue MCP slice.

- Replace Chufeng-specific imports, file checks, tool counts and fallback prose with selected-feature configuration. Preserve existing review modes and Chufeng's MCP configuration.
- Collect actual protocol discovery and configured read-only probes, including required authentication for private tools. Support a small list of probes per feature while preserving existing single-probe configuration. Keep static review, disabled/skipped execution, unavailable services and successful live calls distinct.
- Add an optional feature-configured assistant probe alongside direct protocol probes. For Goldman, collect observable evidence that the application asked the model to select tools, executed the selected MCP calls and used the returned data for its final model-generated answer. Report transport success and AI-assistant success separately.
- **Done:** Chufeng and Goldman can each run MCP mode with their own tool allowlist and probes; Goldman can exercise all four tools and record each outcome separately, including live assistant evidence once E2b/E3 exist. Missing/failed probes or AI review prose alone cannot be described as live application AI success. Credentials are redacted from evidence.
- Commit: `feat(agentic): validate MCP integration per feature`.

**G6 — RAG validation mode.** Same runner owner; depends on G4.

- Add a separate `rag` CLI/interactive mode using feature-specific supported and unsupported queries. Capture retrieval sources, answer/citations/confidence, insufficient-context behaviour and truthful Plan/Act/Observe/Adapt outputs.
- **Done:** tests distinguish real observations from model review claims and cover disabled/unavailable cases; local execution produces outputs for both MCP and RAG modes. Existing modes remain usable.
- Commit: `feat(agentic): add grounded RAG validation mode`.

### Ethan Goldman personal track

**E1 — Four protected support MCP tools, delivered in two checkpoints.** Depends on G1; use the support API on port 6005. E1 means both E1a and E1b are complete.

**E1a — Ticket search and context.**

- Implement `ethan_goldman_search_tickets` and `ethan_goldman_get_ticket_context` in the previously empty `ai-services/mcp_server/tools/ethan_goldman_support.py`; register them and configure their host API connection.
- Reuse authenticated support reads and redaction. Add bounded database/API list and message retrieval so the tools do not fetch every conversation. Preserve existing route behaviour for the Release 0 UI.
- **Done:** protocol/tool tests cover both tools, admin access, anonymous/customer denial, invalid filters and IDs, missing tickets, limits/pagination/truncation, upstream failures and no writes. A real MCP client can discover and call both tools; catalogue tools still work.
- Commit: `feat(customer-support): add MCP ticket search and context tools`.

**E1b — Queue summary and attention list.** Depends on E1a.

- Add `ethan_goldman_get_queue_summary` and `ethan_goldman_get_tickets_needing_attention`, backed by authenticated support read routes and database-owned aggregate/attention queries. Implement the exact counting, reason and sorting rules above.
- **Done:** all four tools are registered. Tests verify summary totals exceed a page correctly, filter consistency, zero-result queues, every attention reason, solved-ticket exclusion, latest customer versus staff message, threshold boundaries, stable sorting/pagination, direct-call access denial and no writes. No model runtime is needed for tool results.
- Commit: `feat(customer-support): add MCP queue summary and attention tools`.

**E2 — Support backend MCP access and AI orchestration, delivered in two checkpoints.** E2 means both E2a and E2b are complete.

**E2a — Support backend MCP access.** Depends on E1a and E1b.

- Add a support-owned adapter and JSON routes in `support_backend/`, using the shared client and an explicit allowlist of the four registered support tools above. Authenticate as admin before calling MCP; pass validated session context; enforce input/body/time limits and map safe errors. These frontend-facing MCP routes are separate from the authenticated read endpoints called by the host tools.
- Wire settings into the support image/Compose without registering support in the shared Flask application. Keep database access in its existing service.
- **Done:** support API tests prove an authorised call for each of the four tools, denial of other tools/customer sessions, and disabled/unavailable behaviour. No disabled-mode network calls; the built support image includes the shared client.
- Commit: `feat(customer-support): expose MCP tools through support API`.

**E2b — Model-driven MCP support assistant.** Depends on E2a and working host Ollama configuration from G2.

- Add a staff-authenticated natural-language assistant endpoint and the bounded model -> validated MCP call -> model answer loop specified above. Reuse existing Ollama HTTP/error/redaction patterns where appropriate; add tool-call handling without changing the Release 0 triage contract.
- Test model-selected names/arguments for all four tools, a short multi-tool sequence, invalid or forbidden calls, prompt injection in ticket content, unavailable dependencies, reference validation, disabled modes and loop/time limits using deterministic model substitutes.
- **Done:** the configured approved local model passes tool-selection testing; a real assistant request executes an MCP tool and returns a model-generated answer based on its result. Raw tool output and canned text cannot pass this check. All four representative questions are exercised during E3/E6 live acceptance.
- Commit: `feat(customer-support): add model-driven MCP assistant`.

**E3 — AI-powered support MCP interface.** Depends on E2a and E2b.

- Add compact HTMX controls for search, queue summary and needs-attention results in the staff queue, plus ticket context in the staff ticket view. Render each tool's distinct result fields with loading, empty, success and safe error states. Make result ticket IDs navigable; display attention reasons, applied thresholds and pagination/truncation information.
- Add a natural-language MCP assistant input and show the model-generated explanation, actual tools used and supporting results. Suggested example questions may prefill the input but must still go through model selection and real MCP execution.
- **Done:** each of the four UI actions goes frontend -> support backend -> shared MCP -> authorised read API and displays the correct result. In addition, the four representative natural-language questions demonstrate actual local-model selection, tool execution and final answers through the UI. Rendering is escaped; failures do not break conversations, editing, existing queue search or AI analysis. Add targeted fragment/rendering checks for results and assistant states.
- Commit: `feat(customer-support): add AI-powered MCP staff interface`.

**E4 — Support RAG knowledge and API.** Depends on G4; can proceed independently of E1–E3.

- Supply attributable support workflow knowledge and representative questions; implement a support backend RAG adapter and staff-authorised query route. Fix the feature scope server-side rather than trusting arbitrary client scopes.
- Reuse shared result semantics; enforce `AI_MODE_ENABLED` and `RAG_ENABLED`, timeouts, bounded inputs and safe errors. Avoid private ticket indexing or unnecessary database schema changes.
- **Done:** backend integration tests exercise a grounded answer, insufficient context, unavailable service, invalid query, forged scope and disabled mode; citations resolve to actual support sources.
- Commit: `feat(customer-support): add grounded support knowledge queries`.

**E5 — Support RAG interface.** Depends on E4.

- Add the question form and answer panel to the staff workspace using existing HTMX patterns. Show citations and confidence explicitly, with distinct insufficient-context and unavailable states.
- **Done:** a supported question works through the real frontend/backend/shared RAG/local model path; an unsupported question visibly declines to answer. Escaping, loading and retry states work; existing AI/MCP/CRUD remain usable.
- Commit: `feat(customer-support): display cited RAG answers`.

**E6 — Goldman MCP/RAG agentic configuration.** Depends on G5, G6, E3 and E5.

- Extend `student-Ethan Goldman/agentic/review_config.json` and mode prompts with actual support source paths, all four required MCP tool names, an authenticated probe for each tool, and positive/negative RAG queries. Use seeded data with known search/context/summary/attention expectations, including a no-match case; do not treat an unexplained empty list as proof of correct attention detection.
- Remove obsolete static checks for Docker Ollama/CI real-AI calls. Preserve the existing implementation, database, architecture and DevOps modes.
- **Done:** both new modes run for Customer Support and capture truthful bounded outputs. MCP evidence includes all four discovered tools, direct probe results and the four real model-driven question/call/answer traces. RAG evidence includes a supported question with actual retrieved chunks and model generation, plus an insufficient-context case. Tests reject unsupported “passed” claims and distinguish missing runtime prerequisites from success. Do not treat the review runner's own model output as a substitute for either application's AI trace.
- Commit: `feat(agentic): configure Goldman MCP and RAG validation`.

**E7 — Complete Release 1 support CI and regression checks.** Depends on G2 and E1–E6; maintain incremental coverage during earlier stages.

- Update `.github/workflows/EthanGoldman.yml` with AI/MCP/RAG disabled in job and container environments, relevant shared-client/server/runner test coverage, and builds/validation for support frontend/backend/database.
- Retain authentication and database-ownership smoke checks. Check disabled MCP/RAG/AI behaviour without starting servers or pulling models. Keep opt-in live AI/MCP/RAG checks runnable locally.
- **Done:** local equivalents pass and the actual GitHub workflow has a successful run when pushed with authorisation. Save its real URL/log; do not invent remote CI success. Run the affected shared regression tests after shared changes.
- Commit: `ci(customer-support): validate Release 1 without live AI services`.

### Other owners' parallel feature tracks

These are team implementation tracks, not automatic extra tasks for an agent assigned to Ethan.

| Owner | Meaningful checkpoints |
| --- | --- |
| Chufeng | Preserve/adapt existing MCP; add catalogue knowledge and RAG backend route; add cited-answer UI; configure both runner modes and complete CI/live validation. Do not redo existing catalogue MCP stages. |
| Ryan | Add bounded inventory/supplier MCP tools; integrate admin backend routes; add MCP UI; add inventory knowledge/RAG backend; add RAG UI; configure validation and build actual backend/database services in CI. |
| Ethan Ting | Add role-scoped account/loyalty MCP tools; integrate authenticated backend routes; add MCP UI; add non-sensitive account/loyalty knowledge/RAG backend; add RAG UI; configure validation and CI. Preserve login/session integration used by the whole app. |
| Howard | Resolve orders database service/API ownership as its own prerequisite checkpoint; add ownership-aware order/return MCP tools; integrate backend routes and MCP UI in separate useful checkpoints; add order/return knowledge/RAG backend then RAG UI; complete runner configuration and backend/database CI coverage. |

Use the E1–E7 acceptance pattern for each owner, with actual names and feature-specific permissions. Each owner contributes domain knowledge; the shared RAG maintainer owns retrieval/generation infrastructure. Split the inherited inventory/catalogue database architecture repair into a separate owner-agreed checkpoint if separate services are required; do not hide it in a RAG/UI commit.

### G7 — Integrated acceptance (whole team, after all feature tracks)

- Start the approved host model runtime, single MCP server and single RAG server; deploy the feature stack with Compose. Verify navigation/authentication and retained CRUD for all five features.
- Exercise at least one successful MCP and one grounded RAG UI interaction for every feature, plus insufficient-context and service-unavailable handling. Run both shared agentic validation modes and collect actual outputs.
- Check all named workflows and validate their frontend/backend/database coverage. Resolve the inherited microservice-ownership gaps before claiming the brief's architecture requirements are fully met.
- Commit only substantive fixes found by acceptance, with feature-scoped messages such as `fix(customer-support): handle unavailable RAG service`. A verification-only session need not manufacture a code commit. Required runtime output files can form a truthful validation checkpoint.
- **Done:** the software acceptance checklist below is satisfied, with observed results and outstanding limitations recorded. Report/presentation preparation is not an agent completion gate.

### Suggested execution order

1. Record baseline test results and choose shared-stage owners. This is stage preparation, not an empty scaffolding commit.
2. G1 -> E1a -> E1b -> E2a -> E2b -> E3 establishes your usable four-tool AI-powered MCP slice. G2 provides E2b's host model setup; transport and model orchestration are separate meaningful commits.
3. G3 -> G4 -> E4 -> E5 establishes your usable RAG slice. G3/G4 may proceed alongside MCP work if another person owns them.
4. G2 should land early, coordinated with the affected CI checks; do not defer the host-runtime mismatch until the showcase.
5. G5/G6 -> E6 -> E7 completes your validation and CI. Other owners integrate their features on the same contracts.
6. G7 validates the assembled release. Shared work already completed by a teammate should be consumed, not repeated.

## 7. Verification and handoff

Run from the repository root with project dependencies installed. These are existing test entry points; the plan-writing task has not executed them:

```bash
python -m pytest 'student-Ethan Goldman/tests' -q
python -m pytest student-Chufeng/tests ai-services/mcp_server/tests -q
python -m pytest shared/tests/test_integrated_access_control.py -q
docker compose config --quiet
```

The first command includes local HTTP integration tests; `RUN_LIVE_AI=1` opts into the existing real-model check. Run applicable tests with deterministic substitutes in CI. Add the new RAG/client/runner tests to the corresponding stage commands as those files are implemented. Also run each other owner's existing suite when their shared dependencies change; Ryan's current suite is explicitly `student-Ryan_Nolan/tests/inventory_tests.py` and is not discovered by the usual `test_*.py` naming convention.

Existing runner invocation (MCP needs the appropriate feature config and services):

```bash
python ai-services/agentic_loop.py --feature student-Chufeng --mode mcp
```

Planned Goldman invocations, available only after G5/G6/E6:

```bash
python ai-services/agentic_loop.py --feature 'student-Ethan Goldman' --mode mcp
python ai-services/agentic_loop.py --feature 'student-Ethan Goldman' --mode rag
```

Use disposable test databases for destructive CRUD tests. Preserve the user's Docker data volumes; do not copy CI's `down --volumes` cleanup into local validation against their existing data.

### Software acceptance checklist

- [ ] All five feature frontends are reachable through the integrated application; existing CRUD, authentication, ownership and AI-Mode still work.
- [ ] One host MCP server exposes tools for every feature; each feature has a successful real UI -> backend -> MCP call and displays the result.
- [ ] Customer Support exposes exactly the four planned support tools alongside other owners' tools: search, ticket context, queue summary and needs attention. All four have successful staff UI/backend/MCP interactions, independent validation results, and tested access/limit/error boundaries. Queue totals and attention reasons match the underlying records.
- [ ] Customer Support's live MCP assistant uses an approved local model to choose tools/arguments and generate answers from actual MCP results. All four example questions have observed model/call/answer evidence; direct buttons, mocked model output and source-review prose do not satisfy this gate.
- [ ] Protected MCP tools reject unauthenticated/forged access even when called directly; errors, limits and read-only boundaries are tested.
- [ ] One host RAG server retrieves approved sources for every feature, uses the local model, and returns answers with valid citations and confidence.
- [ ] Customer Support's live RAG UI displays an actual model-generated answer using retrieved support knowledge, with traceable citations and confidence. A model outage cannot silently become a canned successful answer; insufficient context safely skips generation.
- [ ] Every feature visibly handles insufficient context; unsupported queries do not generate fabricated answers. Service failures are distinguishable.
- [ ] Both shared agentic validation modes produce actual outputs; old modes still operate; static/mocked/disabled/live statuses are honest.
- [ ] Compose contains only the application services, has working host connections, and retains required database isolation/persistence. Inherited topology gaps are resolved rather than silently waived.
- [ ] Each actual-name workflow builds/validates its frontend/backend/database with live AI/MCP/RAG disabled, and successful execution evidence exists.
- [ ] Feature and shared tests pass; the same integrated checkout has been exercised locally. Missing model, Docker, credentials or network prerequisites are reported as unverified checks rather than passing results.

### Stage completion checklist

Agents must maintain these boxes as work progresses. All planned implementation stages start unchecked; writing this plan or creating a log does not complete an implementation stage. The ledger below records partial progress and verification evidence. E1 is complete only when E1a/E1b are checked; E2 is complete only when E2a/E2b are checked. Do not tick another owner's work based on an assumption; reference actual changes and verification.

Shared stages:

- [x] **G1** — Reusable MCP transport and consumer image integration.
- [ ] **G2** — Host AI runtime, enforced disable switches and CI-safe deployment.
- [ ] **G3** — Shared scoped knowledge retrieval service.
- [ ] **G4** — Grounded RAG generation with real local-model verification.
- [ ] **G5** — Feature-aware MCP validation, including application AI evidence.
- [ ] **G6** — RAG validation mode and truthful runtime outputs.

Ethan Goldman stages:

- [ ] **E1a** — Protected MCP ticket search and context tools.
- [ ] **E1b** — Protected MCP queue summary and attention tools.
- [ ] **E2a** — Support backend access with the four-tool allowlist.
- [ ] **E2b** — Model-driven MCP assistant with bounded tool execution.
- [ ] **E3** — Staff MCP interface and live AI demonstrations of all four tools.
- [ ] **E4** — Support RAG knowledge sources and authenticated backend access.
- [ ] **E5** — RAG interface with real generated answers, citations and confidence.
- [ ] **E6** — Goldman MCP/RAG agentic configuration and live validation outputs.
- [ ] **E7** — Release 1 support CI, regression checks and successful workflow evidence.

Team feature completion and final integration:

- [ ] **Chufeng Li** — Retained catalogue MCP, completed RAG, validation and CI.
- [ ] **Ryan Nolan** — Inventory MCP/RAG, service ownership, validation and CI.
- [ ] **Ethan Ting** — Customer/loyalty MCP/RAG, access protections, validation and CI.
- [ ] **Howard Ong** — Order/return service separation, MCP/RAG, validation and CI.
- [ ] **G7** — Integrated acceptance for all five features and the software checklist above.

### Progress ledger

Status values: `pending`, `in progress`, `implemented`, `validated`, `blocked`. A stage can be implemented before a required live environment is available; say precisely what is unverified.

| Stage | Owner | Current status | Commit / verification / next action |
| --- | --- | --- | --- |
| Existing catalogue MCP slice | Chufeng Li | Implemented; historical validation committed | Through `bccf637`; rerun after shared changes. |
| G1 shared MCP client | Ethan Goldman (agent implementation) | Validated | 114 tests passed, 1 opt-in real-AI test skipped; support/shared backend Docker builds and isolated import checks passed. See prompt entry in the work log. Changes uncommitted; next E1a. |
| G2 host runtime | To allocate | Pending | Coordinate Compose, feature guards and Goldman CI. |
| G3 retrieval | To allocate | Pending | Agree source/response contract. |
| G4 grounded generation | Same RAG owner | Pending | Depends on G3. |
| G5 generic MCP validation | To allocate | Pending | Remove Chufeng-specific assumptions. |
| G6 RAG validation | Same runner owner | Pending | Depends on G4. |
| E1a MCP search/context tools | Ethan Goldman | Pending | Depends on G1; bounded authenticated reads. |
| E1b MCP summary/attention tools | Ethan Goldman | Pending | Depends on E1a; aggregate/attention rules. |
| E2a support MCP API | Ethan Goldman | Pending | Depends on E1a/E1b; four-tool allowlist. |
| E2b model-driven MCP assistant | Ethan Goldman | Pending | Depends on E2a/G2; real model selection and grounded answer. |
| E3 support MCP UI | Ethan Goldman | Pending | Depends on E2a/E2b; four staff actions plus live AI assistant. |
| E4 support RAG API/sources | Ethan Goldman | Pending | Depends on G4. |
| E5 support RAG UI | Ethan Goldman | Pending | Depends on E4. |
| E6 support runner config | Ethan Goldman | Pending | Depends on G5/G6 and feature slices. |
| E7 support CI | Ethan Goldman | Pending | Final coverage after G2 and E1–E6. |
| Other feature integrations | Respective owners | Pending except catalogue MCP | Apply the owner-specific tracks above. |
| G7 integrated acceptance | Whole team | Pending | All five feature slices required. |

At each handoff, append the prompt's specific changes to `RELEASE_1_ETHAN_GOLDMAN_WORK_LOG.md`, synchronise the stage checklist and ledger, and state the selected stage, changed files, real checks/results, commit if created, shared-interface changes and the next dependency. Keep this plan useful to the next agent without requiring it to reconstruct the conversation.
