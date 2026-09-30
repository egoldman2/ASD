# Ethan Ting: Release 1 report contribution draft

This section is ready to adapt into the **group** PDF. It covers only my Customer Accounts and Loyalty work. The group must keep the complete report within 3,000 words, excluding diagrams, and add the final repository, video and CI links after publication.

## Feature and requirements

My existing feature lets customers register, sign in, update their own profile and password, and see their loyalty balance and history. Administrators can manage customer accounts and adjust points with an audit reason. For Release 1, I added two administrator-facing extensions. The loyalty page checks a selected customer's current tier through the shared MCP server. The accounts page has a RAG guide for questions about implemented account and loyalty rules. Both use the existing authenticated backend routes; neither grants the model permission to change customer data.

## Architecture and request flow

The browser serves Ethan's frontend from the `ethan-frontend` Docker container. The frontend calls `ethan-backend` on port 6002 using the signed session cookie. The backend reads current records through the `ethan-database` HTTP API, which owns the SQLite file. For MCP, the backend reads the selected customer's points and sends **only the non-negative points integer** to `ethan_ting_calculate_loyalty_tier` on the one shared host MCP service. It checks the tool name, response structure, read-only flag and tier arithmetic before returning the result. At 720 points, the displayed result is Silver with 280 points left to Gold.

For RAG, the backend fixes the scope to `ethan_ting_accounts_loyalty` and sends a validated question to the one shared host RAG service. That service retrieves passages from a curated Markdown guide and, when there is relevant context, asks local Ollama to generate a short cited answer. The backend rejects a wrong scope, invented citation identity or citation number, then the UI shows the answer, source, retrieval confidence and actual model. The guide does not contain live customer records. If retrieval cannot support a question, it returns “Insufficient context to answer this question” without a citation or model call. See the [architecture](../docs/evidence/release1-ethan-ting/architecture.svg) and [request-flow](../docs/evidence/release1-ethan-ting/request-flow.svg) diagrams.

## Measurable quality targets and validation

The intended targets were: all five tier boundaries correct at 0, 499, 500, 999 and 1,000 points; no account mutation during MCP lookup; a Gold-threshold question answered as 1,000 points with a real guide citation; an unrelated question abstaining without invented sources; non-admin callers rejected; and ordinary account operations still usable when AI, MCP and RAG are disabled. Local checks met these targets. The browser showed the 720-point MCP result, a `llama3.1:8b` RAG answer with medium retrieval confidence and approved source, and an unrelated-question abstention. The MCP lookup left the temporary customer's 720-point balance and one setup transaction unchanged. The temporary account was deactivated afterward.

The Python suite had **237 passed, 2 skipped** across Ethan, shared MCP and shared RAG tests. The Docker test image had **137 passed** with live AI services disabled. A separate disabled backend returned 503 for admin MCP, RAG and AI Mode calls while customer login, profile and loyalty endpoints still returned 200. The original administrator Customer Insight AI Mode also returned a live, read-only response with all four workflow fields. When the host RAG service was stopped, the browser showed an unavailable-service error and allowed retry; after restart the same question returned its cited answer. The shared Plan, Act, Observe, Adapt loop ran live MCP and RAG probes and saved both reports. Its review stage rejected unsupported model claims in initial drafts and replaced them with deterministic evidence summaries. Browser captures, reports and exact commands are in the [evidence index](../docs/evidence/release1-ethan-ting/README.md).

## Contribution and limitations

Earlier commits include `4e314c2` for the loyalty MCP integration, `c8520cf` for moving AI services to the host and `efab7fe` for customer password change. The Release 1 RAG, validation, CI and evidence changes in this draft are **not yet committed or pushed**. Add their real commit and GitHub Actions URL after publication.

The RAG guide is static feature documentation, not a live customer lookup. Retrieval confidence measures match strength, not whether every generated sentence is true, so administrators should review the cited passage. Local model availability and response time depend on the host machine. The group must separately verify the other four student features and the final published CI run; this section does not claim those group-wide checks are complete.
