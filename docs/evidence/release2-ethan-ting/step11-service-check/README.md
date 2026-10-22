# Required local and AWS service check

22 October 2026, Sydney time. Source checkout: `910a654`, plus the local
frontend Nginx repair and startup documentation changes described here.

The user requested verification of the required assessment setup only. No
AWS-to-laptop tunnel or optional cloud AI configuration was added. The cloud
baseline continues to disable AI-Mode, MCP, RAG and Multi-Agent.

## Observed results

- The local RAG host now uses
  `/Users/ethan/Library/Caches/asd-release2-rag/chroma`, with its audit file in
  the same cache directory. Refreshing the approved `ethan_ting_accounts_loyalty`
  scope indexed 16 guide documents. No tracked Chroma files were modified.
- A live Gold-threshold question returned 1,000 points, two citations, model
  `llama3.1:8b` and low retrieval confidence. The unrelated laptop-warranty
  question returned insufficient context with no citations. Low retrieval
  confidence is retained, not described as factual certainty.
- A live MCP call from the Docker backend returned Silver, Gold next and
  280 points remaining for a 720-point balance.
- Both customer tools also succeeded through the signed-in local browser.
  **Check progress with AI** returned the same Silver/280 result with a
  `llama3.1:8b` calculation checked against MCP rules; **Point history** returned
  the temporary customer's recorded +720 transaction. **Ask AI** successfully
  summarised the same customer's disabled status, balance and tier.
- The local status fragment initially returned HTTP 502 because Nginx retained
  the old Docker backend IP. The frontend now uses Docker DNS with a ten-second
  refresh. After rebuilding only the frontend, `nginx -t` passed; anonymous
  requests returned HTTP 401 and the signed-in browser showed MCP and RAG
  reachable.
- A new Multi-Agent workflow was started through the local admin UI for the
  existing temporary test customer #187. Workflow
  `96b5d71c-bd71-47bc-8fc6-01b15a7b1881` completed Planner (`qwen2.5:0.5b`),
  Worker (`llama3.1:8b`) and Reviewer (`llama3.1:8b`) at 8:18 pm Sydney time.
  Its results correctly described 720 points as Silver and 280 points to Gold.
  The UI displayed the human decision form. No human decision was invented or
  submitted: this workflow remains awaiting human review.
- The public AWS homepage and all five feature frontend paths returned HTTP
  200. The signed-in AWS Accounts page displayed customer records, MCP and RAG
  disabled, and Multi-Agent disabled. These current observations establish
  availability and the visible disabled baseline, not a new full CRUD test or
  fresh AWS deployment acceptance.

## Local regression checks

- MCP, RAG and Multi-Agent backend boundary suites: **108 passed**.
- Assistant-status and cloud-bundle tests: **39 passed**.
- Rebuilt frontend configuration: `nginx -t` passed.

The [guide answer](rag-guide.png), [Multi-Agent result](multi-agent.png),
[point history](mcp-history.png) and [Ask AI answer](ask-ai.png) screenshots
capture local browser results. They do not
prove that AI services run on AWS. Existing shared security findings and the
human decision to defer release approval remain unchanged. Nothing in this step
was pushed or deployed to AWS.
