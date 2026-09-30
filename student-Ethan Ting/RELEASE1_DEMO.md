# Ethan Ting Release 1 demo and Q&A notes

Allow about two minutes for this section of the team's video. Record at readable browser zoom. Open the pages, terminal results and two review reports before recording so time is not spent waiting for the model. Use the real integrated `localhost:8003` pages, not mock slides. Do not include an active test password or cookie in the recording.

## Screen order and natural script

1. **Customer view, about 20 seconds.** Show sign-in/registration, the profile and password sections, and loyalty balance/history. Say: “This is my customer accounts and loyalty feature. Customers manage only their own details and password. The loyalty balance and changes are stored through the database API.”
2. **Admin view, about 20 seconds.** Sign in as admin, show Accounts and the existing Customer Insight AI section. Say: “Admins can manage accounts and points. My original AI Mode can help find customer information or prepare an edit, but it does not save an edit until an admin confirms it.” Do not actually save a customer edit for the video.
3. **MCP, about 25 seconds.** On Loyalty, select the prepared 720-point demo customer and press Check tier. Say: “This new MCP action reads the selected customer's live balance, sends only the number to our shared tool and checks the returned tier. At 720 points, the tool says Silver and 280 more points to Gold. The lookup does not change the account.” If using the deactivated local test account, explain that it is disposable evidence; prepare a fresh active test account for the final group recording if needed.
4. **RAG, about 30 seconds.** On Accounts, ask how many points Gold needs, show the answer, source, confidence and model, then use an unrelated question to show insufficient context. Say: “The guide answers from approved account and loyalty documentation, not private customer records. It cites the passage it used. When the guide has no relevant evidence, it says it cannot answer instead of making up a source.”
5. **Validation, about 25 seconds.** Show the terminal line with `237 passed, 2 skipped`, the Docker test result `137 passed`, and a brief scroll through the MCP and RAG Plan, Act, Observe, Adapt reports. Say: “The shared review loop checked real MCP and RAG probes. Its reviewer caught unsupported claims in the first AI draft and adapted the final evidence summary. CI runs the same feature tests with live AI, MCP and RAG disabled.” Show the actual green GitHub Actions run only after this revision has been pushed and the run has passed.

## Likely Q&A

- **Why MCP?** It gives a named, structured, read-only tool contract. The backend decides which customer to look up and the tool sees only a points number.
- **Why RAG?** The model gets passages from an approved guide rather than relying only on its training. The backend fixes the source scope and checks citations before showing an answer.
- **Does confidence mean the answer is true?** No. It describes retrieval match strength. The user still needs to review the cited source.
- **What is the agentic loop?** A separate engineering review: plan checks, act by collecting read-only evidence, observe the model's review, then adapt if the reviewer finds unsupported claims. It does not train the model or mutate customer data.
- **What happens if a service is unavailable?** The UI shows a retryable error. Admin routes return 503; normal account functions remain available. CI verifies disabled-mode behaviour without needing a live model.
- **What remains outside your part?** Teammates own their feature-specific MCP/RAG integration; the team owns the final combined video, report, repository and CI demonstration.
