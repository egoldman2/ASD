# Customer Support cloud bonus evidence — 25 October 2026

These six sections apply to **Ethan Goldman's Customer Support feature**. The
application was demonstrated at `https://dww8d9hiqp0ce.cloudfront.net/support/`
in AWS Sydney (`ap-southeast-2`). Shared infrastructure is discussed only where
it protects Support. Other-feature demonstrations have been retired and are
excluded from these claims. This is evidence for assessment, not confirmation
of awarded marks.

## B1 — Cloud AI-Mode: staff ticket analysis

I enabled AI-Mode for the Customer Support backend and used **Analyse ticket**
in the deployed staff workspace for seeded ticket **#2002**, “Parcel marked
delivered but not received.” The real `qwen2.5:0.5b` model returned a validated
staff review: Delivery category, High priority, Negative sentiment, the summary
“Parcel not received after delivery,” and a suggested next step to verify the
carrier tracking record. The response identified `subject`, `message-1` and
`message-2` as its evidence. Support's Plan → Act → Observe → Adapt handling
accepted the response without a retry. Suggestions remained advisory; I did not
apply classifications or send a reply.

**Figure B1:** [Cloud Support AI analysis](B1-support-ai.jpg). The screenshot
shows the actual model, evidence and advisory controls. [Native AI events and
public route receipts](support-ui-mcp-ai-receipts.json) record the accepted
analysis and HTTP 200 at 08:27:09 UTC. [Activation/source hashes](support-ai-activation.json)
and [model metadata/HTTP receipts](support-model-runtime-final.json) connect the
application to the temporary cloud-hosted Ollama service.

## B2 — Cloud MCP: authenticated ticket context

I enabled MCP for Customer Support and selected **Read support data directly →
Read ticket context** in the same cloud staff workspace. The MCP tool
`ethan_goldman_get_ticket_context` retrieved ticket #2002 and its **three of
three recorded conversation messages**, with Open/Delivery/High fields and the
recorded assignee. The Support integration propagates and revalidates the staff
session at its private tool-data API. This demonstration uses the MCP protocol
and a real tool result; the direct-read control does not generate an AI answer.

**Figure B2:** [Cloud Support MCP ticket context](B2-support-mcp.jpg).
[Native receipts](support-ui-mcp-ai-receipts.json) contain the MCP
`CallToolRequest`, successful `/mcp` exchanges and the application's context
route HTTP 200 at 08:21:33 UTC. [Support MCP activation](support-mcp-activation.json)
and [configuration manifest](configuration-manifest.json) identify the deployed
overlay and accepted application image. Other feature flags remained off.

## B3 — Cloud RAG: grounded support guidance

I asked the cloud **Support knowledge assistant**: “What does unresolved mean
in the support queue? Please cite the guide.” The model `qwen2.5:3b` answered:
**“Unresolved means any ticket whose status is not solved. [1]”** It displayed a
source link to *Customer Support staff assistant guide: Queue totals and ticket
attention*, `staff_assistant_guide.md`, passage 1. The interface recorded four
passages reviewed and one generation attempt for this successful request.
The answer matches the retrieved guide text.

**Figure B3:** [Cloud Support answer with citation](B3-support-rag.jpg).
[Retrieved context](support-rag-retrieved-context.json) records the matching
chunk under scope `ethan_goldman_support`; [browser observations](browser-observations.json)
retain the rendered answer, model and citation. [Successful public route receipt](support-ui-receipts-final.json)
and [Ollama HTTP/model metadata](support-model-runtime-final.json) corroborate
actual cloud generation. Only the two approved Support Markdown guides were
packaged; tickets, customer identities and credentials were not indexed.

Earlier attempts failed citation validation or the cloud response window and
are retained as diagnostics, not successful demonstrations. The 0.5B RAG model
was changed to 3B. I also fixed the cloud application packager, which had
omitted the approved Markdown files needed to validate source links. For the
accepted image, those exact guides were mounted read-only at the canonical
path; [before/after source availability](support-citation-packaging-fix.json)
and [17 passing packaging/cloud tests](support-packaging-tests.xml) document
the repair. Citation and scope validation were preserved.

## B4 — Cloud Multi-Agent: support reply and next-action review

I selected **Propose reply and action** for support ticket **#2002** in the
cloud staff workspace. Workflow **`82d95447-da3f-4684-a5db-c546799393af`**
completed **Planner (`qwen2.5:3b`) → Worker (`qwen2.5:3b`) → Reviewer
(`llama3.1:8b`)** using the same recorded support-ticket snapshot. Native
records identify `feature: customer_support`, evidence `support-ticket-2002`,
source `customer-support-database`, and all three messages. The Planner bound
the work to that evidence; the Worker proposed a follow-up and next action;
the Reviewer returned a risk assessment and recommendation. The chain took
**283.383 seconds** and was saved as **`awaiting_human_review`**, with no human
decision recorded.

**Figure B4:** [Completed Support workflow in the cloud application](B4-support-workflow.jpg).
Separate [Planner](B4-support-planner.jpg), [Worker](B4-support-worker.jpg) and
[Reviewer](B4-support-reviewer.jpg) figures are available for larger report
captions. [Native SSM workflow capture](support-native-workflow-retry.json),
[extracted unchanged record](workflow-record.json) and [matching coordination
audit](workflow-audit.json) establish the workflow identity, stage completion,
models and pending human review. The [browser capture](browser-observations.json)
uses the same workflow ID and models. [Final Ollama receipts](support-model-runtime-completed.json)
record three successful generation calls and no container OOM/restart.

The initial browser request exceeded the cloud response window; the server
continued and completed the workflow. **Reload recorded history** retrieved it
through the application with HTTP 200, as shown by the
[Support route receipts](support-ui-receipts-completed.json). No synthetic
output or model warmup is counted as workflow proof.

**Quality limit:** The Worker proposed rechecking an address the customer had
already confirmed, and the Reviewer recommended acceptance without identifying
that repetition. The output is a next-action proposal, rather than a polished
customer-facing reply. This proves the three-agent cloud workflow runs; it does
not prove the advice is correct or ready to send. I left human review pending
and sent no reply or ticket update.

## B5 — Cloud endpoint security for Support

The deployed Support frontend and APIs use the shared CloudFront HTTPS entry
point. Fresh [Support-only public checks](support-public-security.json) passed
**10 checks**: HTTP redirects to HTTPS; the anonymous staff workspace redirects
to sign-in; customer/staff ticket APIs, tool-data, AI analysis, MCP, RAG and
workflow creation reject anonymous access with HTTP 401; an explicitly forged
session is rejected. Support responses include `no-store`, `nosniff`,
`SAMEORIGIN` and `Referrer-Policy: same-origin`.

The [Support role checks](support-role-security.json), captured earlier the
same day at 06:39 UTC, record HTTP **403 for a signed-in customer** and **200 for
an administrator** on `/api/support/admin/tickets`. These are an explicitly
identified subset of the original shared capture, not a new login during the
corrected demo. The same session evidence records Secure, HttpOnly and
SameSite=Lax cookie attributes. Local Support regressions additionally cover
ownership and role enforcement; local tests are distinct from cloud checks.

[Current AWS configuration](support-aws-security.json) restricts the application
origin's security group to port 80 from the CloudFront managed prefix list,
with no public SSH, API or database ingress. CloudFront supplies an
`X-Origin-Verify` header, whose value is omitted from evidence. Temporary
Support Ollama/RAG ingress accepted only the application's security group;
MCP/Multi-Agent had no published host ports. These controls protect Support's
staff-only ticket and AI/tool endpoints.

**Limits:** CloudFront-to-origin traffic uses HTTP, and the captured minimum
TLS policy is `TLSv1`. WAF and HSTS are not demonstrated. These results establish
specific endpoint controls, not comprehensive security or end-to-end TLS.

## B6 — Cloud data security for Support

Support ticket/message records are stored in the dedicated database container
at `/data/support_tickets.db`, bound from `/srv/asd/data/support`.
[Runtime mapping/file modes](support-storage-security.json) and [device mapping](support-volume-mapping.json)
connect this directory to encrypted **30 GiB EBS volume
`vol-02087b3eeb07eec99`**, with DeleteOnTermination=false
([AWS configuration](support-aws-security.json)). Support's backend has no
database bind mount; it accesses the dedicated database service. The temporary
public-guide bind mount contains only approved documentation.

The session-secret and release environment files are mode **0600**; their
contents were not read for this evidence. The Support SQLite file is **0644
inside its dedicated container**, so a blanket “all data files are 0600” claim
would be inaccurate. Shared sign-in password hashing protects the credentials
used to access Support. [Earlier shared security configuration](../../bonus-b5-b6/20261025/README.md)
also records the private encrypted release bucket, host role scope, secret-store
metadata and private encrypted snapshots. Those are infrastructure controls for
this Support deployment, not separate Support-specific services or proof of
password rotation or backup restoration.

Support analysis and workflow code redact identities and bound conversation
context. RAG indexes only public Support guides. The selected synthetic ticket
was inspected read-only before the demonstrations
([before](ticket-before.json), [after](ticket-after.json)). The ticket/message
SHA-256 remained exactly `399b6f4c29cb7e140204d9c515611a0ed649f01f7358560779152d57d22aeb2a`,
with three messages, SQLite integrity `ok`, and zero foreign-key errors
([comparison](ticket-integrity-comparison.json)). No suggested reply,
classification or human acceptance was applied during these cloud demos.

## Validation and scope of the evidence

The Support/shared-client/Multi-Agent regression run passed **327 tests**, with
**23 opt-in skips** ([JUnit](support-regressions.xml)). A later focused
packaging/cloud run passed **17 tests** ([JUnit](support-packaging-tests.xml));
these suites overlap and are not added into a misleading unique-test total.
CloudFormation lint, security guard checks and AWS validation are retained in
this pack. The project remained on the active FREE plan; no plan upgrade was
performed. This demonstration does not establish sustained load capacity.

At **08:46:51 UTC**, [cloud cleanup](cleanup-cloud.json) confirmed the temporary
inference/RAG stack deleted, model instance terminated, disposable disk absent
and the exact bootstrap object version deleted. [Application cleanup](cleanup-application.json)
removed the Multi-Agent container and disposable state, restored Support to
MCP-only mode, and preserved the accepted application and encrypted Support
data volume. A [post-cleanup browser read](B2-support-mcp-after-cleanup.jpg)
verified Support MCP still returns ticket #2002 and its three messages. The
normal application host remains running; temporary AI hosting does not. Historical other-feature captures remain under
`docs/evidence/retired-other-feature-bonus-20261025/` solely for provenance.
