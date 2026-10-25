# Customer Support — cloud bonus evidence

**Feature owner: Ethan Goldman.** Use the [six report sections](report-sections.md)
for the individual report. All business demonstrations here concern Customer
Support. Incorrect other-feature demonstrations are preserved only in the
[retired archive](../../retired-other-feature-bonus-20261025/); they are not
renamed or counted as Support evidence.

| Criterion | Actual Customer Support evidence | Status |
| --- | --- | --- |
| B1 AI-Mode | Ticket #2002 analysis, Qwen 0.5B, accepted advisory classification/summary | Cloud demonstrated |
| B2 MCP | `ethan_goldman_get_ticket_context`, ticket #2002, 3/3 messages | Cloud demonstrated |
| B3 RAG | Unresolved = not solved, approved staff-guide citation, Qwen 3B | Cloud demonstrated |
| B4 Multi-Agent | Ticket #2002 Planner → Worker → Reviewer, matching native/UI workflow ID | Cloud demonstrated; human review pending |
| B5 Endpoint security | 10 fresh Support public checks; same-day customer 403/admin 200; origin restrictions | Specific controls evidenced; limits disclosed |
| B6 Data security | Encrypted retained Support storage; secret modes; identical before/after ticket hash | Specific controls and integrity evidenced |

## Figures for the report

- [B1-support-ai.jpg](B1-support-ai.jpg): actual validated staff review and model,
  evidence labels and advisory controls. **Apply** was not clicked.
- [B2-support-mcp.jpg](B2-support-mcp.jpg): direct MCP ticket context, three
  conversation messages, ticket identity and triage fields.
- [B3-support-rag.jpg](B3-support-rag.jpg): successful grounded answer, source
  link, passage, model and generation metadata. The full-page capture records
  the same answer at an intermediate point while B4 was still unconfirmed.
- [B4-support-workflow.jpg](B4-support-workflow.jpg): same Support ticket evidence,
  all three completed model stages and pending human decision. Separate
  [Planner](B4-support-planner.jpg), [Worker](B4-support-worker.jpg) and
  [Reviewer](B4-support-reviewer.jpg) crops retain readable outputs.

The selected ticket and `customer@asd.local` identity are seeded synthetic demo
data. [Browser observations](browser-observations.json) preserve the captured
rendered text and failed RAG attempts. No customer reply or human review decision
was sent and no ticket triage update was applied.

## Native provenance

- [Source archive manifest](source-manifest.json), [S3 version](source-upload.json),
  [CloudFormation create request](stack-create.json), [stack result](stack-status.json),
  [instance](inference-instance.json), [encrypted temporary disk](inference-volume.json).
- [Support activation](support-ai-activation.json), [final deployed configuration](support-active-config-final.json),
  [configuration hashes/models](configuration-manifest.json),
  [private connectivity](private-support-connections.json).
- [B4 native workflow](support-native-workflow-retry.json), [workflow record](workflow-record.json),
  [matching audit](workflow-audit.json), [completed model receipts](support-model-runtime-completed.json),
  [history reload receipt](support-ui-receipts-completed.json).
- [B1/B2 native receipts](support-ui-mcp-ai-receipts.json), [later Support UI receipts](support-ui-receipts-final.json),
  [Ollama model digests and HTTP receipts](support-model-runtime-final.json),
  [Support-only retrieval](support-rag-retrieved-context.json).
- [Fresh Support endpoint checks](support-public-security.json), [earlier same-day Support role subset](support-role-security.json),
  [AWS security configuration](support-aws-security.json), [Support bind/file modes](support-storage-security.json),
  [retained volume mapping](support-volume-mapping.json), [ticket before hash](ticket-before.json), [after hash](ticket-after.json)
  and [unchanged-data comparison](ticket-integrity-comparison.json).

The accepted API image remains the recorded existing image. Only Support flags,
private optional containers and approved public guide configuration were changed.
The inference instance has a public address for bootstrap egress, but its ingress
rules admit only the application security group to ports 11434 and 5003. No
public inference or SSH ingress was added. IAM and metadata captures omit
credentials and origin-header values.

## Repairs, unsuccessful attempts and checks

The first 0.5B RAG attempts omitted citations. A 3B attempt timed out; another
returned a cited abstention and is **not** counted as a grounded success. The
application then rejected otherwise valid source references because the accepted
cloud bundle lacked the approved Support Markdown. [Missing source check](support-rag-client-source-check.json)
and [repair check](support-citation-packaging-fix.json) show the cause and fix.
`cloud/prepare.py` now includes exactly the two approved guide files; the accepted
image received the same files as a read-only mount. Scope/citation validation
was not weakened. The successful queue-definition request returned public
HTTP 200 at 08:39:19 UTC. The RAG HTTP bridge has no implemented audit writer;
no RAG audit file is claimed.

[327 passing regressions / 23 opt-in skips](support-regressions.xml) cover Support,
the shared Multi-Agent client and Multi-Agent server. [17 passing focused checks](support-packaging-tests.xml)
cover cloud packaging and Support activation/rollback; suites overlap.
[Earlier six overlay checks](support-overlay-tests.xml), lint and
[CloudFormation guard](guard.json)/[AWS validation](template-validation.json)
are also retained. The sandbox-only regression attempt was interrupted after
loopback networking was denied; the permitted rerun passed. The initial public
probe incorrectly expected an unauthenticated workspace HTTP 200; the correct
login redirect HTTP 302 was verified by the corrected probe. Neither initial
artifact is presented as a working demo or a security defect.

`support-native-workflow.json` records an initial evidence-collector syntax
error, not an application workflow result. The corrected collector is used for
workflow proof. Native command IDs, script hashes and timestamps remain in each
SSM artifact. An empty warmup is not counted as a multi-agent interaction.
The actual Support chain completed at 08:44:31 UTC after 283.383 seconds;
the initial browser timeout was recovered through recorded history. The Worker
repeated an already-confirmed address check and the Reviewer missed it. The
report preserves that quality limitation and leaves human review pending.

## Cleanup and limits

[Cloud cleanup](cleanup-cloud.json) passed at **08:46:51 UTC**: the temporary
stack is `DELETE_COMPLETE`, instance `i-032c47ee7c2754159` is terminated,
root volume `vol-0148100eaa52f33af` no longer exists, and the exact uploaded
bootstrap object version returns 404. The encrypted Support data volume
`vol-02087b3eeb07eec99` remains attached and in use.

[Application cleanup](cleanup-application.json) restored **Support MCP-only**
mode: Support AI/RAG/Multi-Agent flags are false, MCP is true, and the Multi-Agent
container, disposable workflow files and model connection env are removed.
Other feature flags remain false. A fresh [MCP browser check](B2-support-mcp-after-cleanup.jpg)
after cleanup still returned ticket #2002 and all three messages.
[Before/after hashes](ticket-integrity-comparison.json) confirm no ticket or
conversation changes. Native workflow/audit and all report captures are retained
here; they are no longer served by the removed temporary runtime.

The accepted application, its normal ongoing hosting and persistent Support
data remain. Only the added model/demo infrastructure was removed. Disable the
manual Support MCP overlay before a baseline CI deployment, as documented in the
[runbook](../../../../cloud/support-bonus.md).

Specific security limits are retained in the report: HTTP origin transport,
legacy TLS policy, no demonstrated WAF/HSTS/rotation/restore, and existing
ChromaDB advisory exceptions. The CPU demo is not a sustained-load or production
readiness result. `artifact-hashes.json` records the final retained evidence.
