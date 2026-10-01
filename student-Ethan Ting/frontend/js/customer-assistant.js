/* Shared component for both Ethan Ting admin pages. Dynamic data uses textContent. */
(() => {
const host = document.querySelector("#customerAssistant");
if (!host) return;
host.innerHTML = `
<div class="panelHeading"><div><p class="dashboardEyebrow">Customer support tools</p><h2 id="customerInsightTitle">Customer assistant</h2><p class="panelDescription">Check live loyalty records, ask AI or look up the approved guide.</p></div></div>
<div class="assistantStatusRow"><div id="assistantServiceStatus" class="assistantStatus" role="status" aria-live="polite" hx-get="/api/admin/assistant/service-status" hx-trigger="load, every 30s" hx-request='{"timeout":9000}' hx-swap="innerHTML">Checking MCP and RAG connections...</div><button class="secondaryButton" type="button" hx-get="/api/admin/assistant/service-status" hx-target="#assistantServiceStatus" hx-request='{"timeout":9000}'>Check connections</button></div>
<div class="assistantTabs" role="tablist" aria-label="Assistant task"><button id="assistantTab0" type="button" role="tab" aria-controls="assistantPane0" aria-selected="true" tabindex="0" data-assistant-tab="tools">Customer tools</button><button id="assistantTab1" type="button" role="tab" aria-controls="assistantPane1" aria-selected="false" tabindex="-1" data-assistant-tab="ai">Ask AI</button><button id="assistantTab2" type="button" role="tab" aria-controls="assistantPane2" aria-selected="false" tabindex="-1" data-assistant-tab="guide">Ask the guide</button></div>
<div id="assistantCustomerFields" class="assistantCustomerFields">
  <div class="formField"><label for="assistantCustomerSearch">Find a customer</label><input id="assistantCustomerSearch" class="searchField" type="search" placeholder="Search name, email or ID" maxlength="254"></div>
          <div class="formField">
            <label for="mcpTierCustomer">Customer</label>
            <select id="mcpTierCustomer" class="searchField">
              <option value="">Loading customers...</option>
            </select>
          </div>
  <button id="assistantReloadCustomers" class="secondaryButton" type="button">Reload customers</button>
</div>
<p id="assistantSelectedContext" class="panelDescription" role="status"></p>
<section id="assistantPane0" role="tabpanel" aria-labelledby="assistantTab0">
  <p class="panelDescription">Check loyalty progress or the latest 5 point changes. Both tools are read-only.</p>
  <form id="mcpTierForm" class="assistantQuickActions">
          <button id="mcpTierButton" class="primaryButton" type="submit" disabled>Check progress</button>
          <button id="assistantHistoryButton" class="secondaryButton" type="button" disabled>Point history</button>
        </form>
        <p id="mcpTierMessage" class="dashboardMessage" role="status" aria-live="polite"></p>
        <div id="mcpTierResult" class="mcpTierResult" hidden>
          <span id="mcpTierBadge" class="loyaltyTierBadge"></span>
          <p id="mcpTierDetails"></p>
        </div><button id="assistantToolRetry" class="secondaryButton" type="button" hidden>Try again</button></section>
<section id="assistantPane1" role="tabpanel" aria-labelledby="assistantTab1" hidden><p class="panelDescription">Only edit proposals require confirmation. Include a customer ID or email in typed questions.</p>        <form id="customerInsightForm" class="aiInsightForm">
          <label for="customerInsightQuestion">Question for the assistant</label>
          <textarea
            id="customerInsightQuestion"
            name="question"
            rows="3"
            maxlength="400"
            placeholder="For example: Which active customers are closest to their next loyalty tier?"
            required
          ></textarea>

          <div class="aiPromptSuggestions" aria-label="Example questions">
            <button
              class="aiPromptButton"
              type="button"
              data-customer-prompt="summary"
            >Customer summary</button>
            <button
              class="aiPromptButton"
              type="button"
              data-insight-question="Which active customers are closest to their next loyalty tier?"
            >Next loyalty tier</button>
            <button
              class="aiPromptButton"
              type="button"
              data-insight-question="Summarise the disabled customer accounts in the supplied records."
            >Disabled accounts</button>
            <button
              class="aiPromptButton"
              type="button"
              data-customer-prompt="edit"
            >Prepare an edit</button>
          </div>

          <div class="formActions">
            <button id="askCustomerInsightButton" class="primaryButton" type="submit">
              Ask AI
            </button>
          </div>
        </form>

</section>
<section id="assistantPane2" role="tabpanel" aria-labelledby="assistantTab2" hidden>        <section class="ragGuide assistantGuide" aria-labelledby="ragGuideTitle">
          <div class="panelHeading panelHeading--responsive">
            <div>
              <p class="dashboardEyebrow">Grounded knowledge · RAG</p>
              <h3 id="ragGuideTitle">Accounts and loyalty guide</h3>
              <p class="panelDescription">Ask how the feature works. Answers use the approved guide and show sources. This does not look up live customers or change data.</p>
            </div>
            <button id="refreshRagGuideButton" class="secondaryButton" type="button">Refresh guide</button>
          </div>
          <form id="ragGuideForm" class="aiInsightForm">
            <label for="ragGuideQuestion">Question about account or loyalty rules</label>
            <textarea id="ragGuideQuestion" name="question" rows="2" maxlength="400" placeholder="For example: How many points are needed for Gold?" required></textarea>
            <div class="aiPromptSuggestions" aria-label="Guide examples">
              <button class="aiPromptButton" type="button" data-rag-question="How do loyalty tiers work?">Loyalty tiers</button>
              <button class="aiPromptButton" type="button" data-rag-question="How can a customer change their password, and what are the requirements?">Change password</button>
              <button class="aiPromptButton" type="button" data-rag-question="How can a customer update their profile name and email?">Profile changes</button>
              <button class="aiPromptButton" type="button" data-rag-question="How do customers get loyalty points, and are purchases rewarded automatically?">Getting points</button>
              <button class="aiPromptButton" type="button" data-rag-question="Where can a customer check their loyalty point history?">Viewing history</button>
              <button class="aiPromptButton" type="button" data-rag-question="Can administrators remove points, and what are the limits?">Points adjustments</button>
              <button class="aiPromptButton" type="button" data-rag-question="What is the warranty period for a laptop?">Unknown policy</button>
            </div>
            <div class="formActions"><button id="askRagGuideButton" class="primaryButton" type="submit">Ask guide</button></div>
          </form>
          <p id="ragGuideMessage" class="dashboardMessage" role="status" aria-live="polite"></p>
          <div id="ragGuideResult" class="aiInsightResult" hidden>
            <p id="ragGuideAnswer" class="aiInsightAnswer"></p>
            <p id="ragGuideMeta" class="aiInsightMeta"></p>
            <div id="ragGuideSources" hidden>
              <h4>Sources used</h4>
              <ol id="ragGuideCitationList"></ol>
            </div>
          </div>
        </section></section>
        <p id="customerInsightMessage" class="dashboardMessage" aria-live="polite"></p>

        <div id="customerInsightResult" class="aiInsightResult" aria-live="polite" hidden>
          <div id="customerInsightAnalysis">
            <p id="customerInsightLabel" class="dashboardEyebrow">AI response</p>
            <p id="customerInsightAnswer" class="aiInsightAnswer"></p>
            <p id="customerInsightMeta" class="aiInsightMeta"></p>
            <div id="customerInsightHistory" class="tableWrapper" hidden>
              <table class="dataTable">
                <caption>Recent point changes, newest first</caption>
                <thead><tr><th scope="col">Date</th><th scope="col">Points</th><th scope="col">Reason</th></tr></thead>
                <tbody id="customerInsightHistoryBody"></tbody>
              </table>
            </div>
          </div>

          <section id="customerChangeProposal" class="aiChangeProposal" aria-labelledby="customerChangeProposalTitle" hidden>
            <div class="aiChangeProposalHeading">
              <div>
                <h3 id="customerChangeProposalTitle">Review customer changes</h3>
                <p id="proposalCustomerSummary" class="aiChangeCustomer"></p>
              </div>
              <span class="aiReviewBadge">AI suggestion · Not saved</span>
            </div>

            <div class="aiChangeList" aria-label="Current and proposed customer details">
              <div id="proposalNameRow" class="aiChangeRow">
                <span class="aiChangeLabel">Full name</span>
                <div class="aiChangeTransition">
                  <span id="proposalCurrentName" class="aiChangeCurrent"></span>
                  <span class="aiChangeArrow" aria-hidden="true">→</span>
                  <strong id="proposalNewName" class="aiChangeNew"></strong>
                </div>
              </div>
              <div id="proposalEmailRow" class="aiChangeRow">
                <span class="aiChangeLabel">Email address</span>
                <div class="aiChangeTransition">
                  <span id="proposalCurrentEmail" class="aiChangeCurrent"></span>
                  <span class="aiChangeArrow" aria-hidden="true">→</span>
                  <strong id="proposalNewEmail" class="aiChangeNew"></strong>
                </div>
              </div>
            </div>

            <p class="aiChangeNotice">
              Nothing changes until you select <strong>Save customer changes</strong>.
            </p>

            <details class="aiTechnicalDetails">
              <summary>AI details</summary>
              <p id="proposalAiMeta"></p>
            </details>

            <div class="aiChangeActions">
              <button id="cancelCustomerChangeButton" class="secondaryButton" type="button">
                Cancel
              </button>
              <button id="confirmCustomerChangeButton" class="primaryButton" type="button">
                Save customer changes
              </button>
            </div>
          </section>
        </div>

`;
const AUTH_API_URL = "http://localhost:6002";
const customerInsightForm = document.querySelector("#customerInsightForm");
const customerInsightQuestion = document.querySelector("#customerInsightQuestion");
const askCustomerInsightButton = document.querySelector("#askCustomerInsightButton");
const customerInsightMessage = document.querySelector("#customerInsightMessage");
const customerInsightResult = document.querySelector("#customerInsightResult");
const customerInsightAnalysis = document.querySelector("#customerInsightAnalysis");
const customerInsightAnswer = document.querySelector("#customerInsightAnswer");
const customerInsightMeta = document.querySelector("#customerInsightMeta");
const customerInsightLabel = document.querySelector("#customerInsightLabel");
const customerInsightHistory = document.querySelector("#customerInsightHistory");
const customerInsightHistoryBody = document.querySelector("#customerInsightHistoryBody");
const customerChangeProposal = document.querySelector("#customerChangeProposal");
const confirmCustomerChangeButton = document.querySelector("#confirmCustomerChangeButton");
const cancelCustomerChangeButton = document.querySelector("#cancelCustomerChangeButton");
const ragGuideForm = document.querySelector("#ragGuideForm");
const ragGuideQuestion = document.querySelector("#ragGuideQuestion");
const askRagGuideButton = document.querySelector("#askRagGuideButton");
const refreshRagGuideButton = document.querySelector("#refreshRagGuideButton");
const ragGuideMessage = document.querySelector("#ragGuideMessage");
const ragGuideResult = document.querySelector("#ragGuideResult");
const ragGuideAnswer = document.querySelector("#ragGuideAnswer");
const ragGuideMeta = document.querySelector("#ragGuideMeta");
const ragGuideSources = document.querySelector("#ragGuideSources");
const ragGuideCitationList = document.querySelector("#ragGuideCitationList");
let pendingCustomerChange = null;
async function authRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(`${AUTH_API_URL}${path}`, {
    signal: AbortSignal.timeout(120000),
    ...options,
    credentials: "include",
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
    });
  } catch (error) {
    throw new Error(["TimeoutError", "AbortError"].includes(error.name)
      ? "The request timed out. Try again."
      : "Could not reach the account service. Check it is running and try again.");
  }
  let result;
  try { result = await response.json(); }
  catch (_) { throw new Error("The account service returned an unreadable response. Try again."); }

  if (!response.ok) {
    const error = new Error(result.error || "The request failed.");
    error.status = response.status;
    throw error;
  }

  return result;
}

function showCustomerInsightMessage(message, success = false) {
  customerInsightMessage.textContent = message;
  customerInsightMessage.classList.toggle("success", success);
}


function renderCustomerInsight(result) {
  pendingCustomerChange = result.proposal || null;
  customerInsightAnswer.textContent = result.answer;
  customerInsightLabel.textContent = result.source === "mcp" ? "Customer loyalty history" : "AI response";
  customerInsightMeta.textContent = result.source === "mcp" ? (
    result.clarification_required ? "Select one customer · No records changed" : "MCP · Live recorded transactions · Read-only"
  ) : (
    `${result.model} · ${result.customers_analyzed} customer records · Read-only analysis`
  );
  customerInsightHistoryBody.replaceChildren();
  const transactions = result.history?.transactions || [];
  for (const transaction of transactions) {
    const row = document.createElement("tr");
    const timestamp = transaction.created_at.replace(" ", "T");
    const date = new Date(/(?:Z|[+-]\d{2}:\d{2})$/.test(timestamp) ? timestamp : `${timestamp}Z`);
    const values = [
      Number.isNaN(date.getTime()) ? transaction.created_at : date.toLocaleString(),
      `${transaction.points_change > 0 ? "+" : ""}${transaction.points_change}`,
      transaction.reason,
    ];
    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.appendChild(cell);
    }
    customerInsightHistoryBody.appendChild(row);
  }
  customerInsightHistory.hidden = transactions.length === 0;
  customerInsightAnalysis.hidden = Boolean(pendingCustomerChange);
  customerInsightResult.classList.toggle(
    "aiInsightResult--proposal",
    Boolean(pendingCustomerChange)
  );

  if (pendingCustomerChange) {
    const current = pendingCustomerChange.current;
    const changes = pendingCustomerChange.changes;
    document.querySelector("#proposalCustomerSummary").textContent = (
      `${current.full_name} · ${current.email}`
    );
    const nameRow = document.querySelector("#proposalNameRow");
    const emailRow = document.querySelector("#proposalEmailRow");

    nameRow.hidden = !changes.full_name;
    emailRow.hidden = !changes.email;

    if (changes.full_name) {
      document.querySelector("#proposalCurrentName").textContent = current.full_name;
      document.querySelector("#proposalNewName").textContent = changes.full_name;
    }
    if (changes.email) {
      document.querySelector("#proposalCurrentEmail").textContent = current.email;
      document.querySelector("#proposalNewEmail").textContent = changes.email;
    }

    document.querySelector("#proposalAiMeta").textContent = (
      `${result.model} analysed ${result.customers_analyzed} allow-listed customer records. `
      + "The proposal endpoint did not write to the database."
    );
    customerChangeProposal.hidden = false;
  } else {
    customerChangeProposal.hidden = true;
  }

  customerInsightResult.hidden = false;
}


function cancelCustomerChangeProposal(message = "Change proposal cancelled. Nothing was saved.") {
  pendingCustomerChange = null;
  customerChangeProposal.hidden = true;
  customerInsightResult.hidden = true;
  customerInsightResult.classList.remove("aiInsightResult--proposal");
  showCustomerInsightMessage(message, true);
}

customerInsightForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;

  const question = customerInsightQuestion.value.trim();
  if (!question) {
    customerInsightResult.hidden = true;
    showCustomerInsightMessage("Enter a customer or loyalty question.");
    return;
  }

  setToolBusy(true);
  document.querySelector("#mcpTierResult").hidden = true;
  askCustomerInsightButton.disabled = true;
  askCustomerInsightButton.textContent = "Analysing...";
  pendingCustomerChange = null;
  customerChangeProposal.hidden = true;
  customerInsightResult.hidden = true;
  showCustomerInsightMessage(
    "Checking customer information...",
    true
  );

  try {
    const result = await authRequest("/api/admin/ai/customer-insight", {
      method: "POST",
      body: JSON.stringify({ question }),
    });
    renderCustomerInsight(result);
    showCustomerInsightMessage(
      result.proposal
        ? ""
        : result.source === "mcp"
          ? (result.clarification_required ? "Include one customer in your question." : "History loaded. No customer records were changed.")
        : "Analysis complete. Review the evidence before taking any action.",
      true
    );
  } catch (error) {
    customerInsightResult.hidden = true;
    showCustomerInsightMessage(error.message);
  } finally {
    setToolBusy(false);
    askCustomerInsightButton.disabled = false;
    askCustomerInsightButton.textContent = "Ask AI";
  }
});


confirmCustomerChangeButton.addEventListener("click", async () => {
  if (!pendingCustomerChange || busy) {
    return;
  }

  setToolBusy(true);
  confirmCustomerChangeButton.disabled = true;
  confirmCustomerChangeButton.textContent = "Saving...";

  try {
    await authRequest(
      `/api/admin/customers/${pendingCustomerChange.customer_id}`,
      {
        method: "PUT",
        body: JSON.stringify(pendingCustomerChange.changes),
      }
    );
    document.dispatchEvent(new Event("customer-assistant:updated"));
    await loadAssistantCustomers();
    pendingCustomerChange = null;
    customerChangeProposal.hidden = true;
    customerInsightResult.hidden = true;
    customerInsightResult.classList.remove("aiInsightResult--proposal");
    showCustomerInsightMessage(
      "Customer changes saved.",
      true
    );

  } catch (error) {
    showCustomerInsightMessage(error.message);
  } finally {
    setToolBusy(false);
    confirmCustomerChangeButton.disabled = false;
    confirmCustomerChangeButton.textContent = "Save customer changes";
  }
});


cancelCustomerChangeButton.addEventListener("click", () => {
  cancelCustomerChangeProposal();
});


for (const promptButton of document.querySelectorAll("[data-insight-question]")) {
  promptButton.addEventListener("click", () => {
    customerInsightQuestion.value = promptButton.dataset.insightQuestion;
    customerInsightQuestion.focus();
  });
}


function showRagGuideMessage(message, success = false) {
  ragGuideMessage.textContent = message;
  ragGuideMessage.classList.toggle("success", success);
}


ragGuideForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  const question = ragGuideQuestion.value.trim();
  if (!question) {
    showRagGuideMessage("Enter a question about the feature guide.");
    return;
  }
  setToolBusy(true);
  askRagGuideButton.disabled = true;
  askRagGuideButton.textContent = "Checking sources...";
  ragGuideResult.hidden = true;
  showRagGuideMessage("Looking for approved account and loyalty guidance...", true);
  try {
    const result = await authRequest("/api/admin/rag/answer", {
      method: "POST",
      body: JSON.stringify({ question }),
    });
    ragGuideAnswer.textContent = result.answer;
    ragGuideMeta.textContent = result.insufficient_context
      ? "Insufficient context · No sources used"
      : `${result.model} · ${result.confidence} retrieval confidence`;
    ragGuideCitationList.replaceChildren();
    for (const citation of result.citations) {
      const item = document.createElement("li");
      item.textContent = `[${citation.rank}] ${citation.label} (${citation.source_id})`;
      ragGuideCitationList.append(item);
    }
    ragGuideSources.hidden = result.citations.length === 0;
    ragGuideResult.hidden = false;
    showRagGuideMessage(result.insufficient_context
      ? "The approved guide does not contain enough evidence to answer."
      : "Answer includes citations from the approved guide. Review the sources before acting.", true);
  } catch (error) {
    showRagGuideMessage(error.message);
  } finally {
    setToolBusy(false);
    askRagGuideButton.disabled = false;
    askRagGuideButton.textContent = "Ask guide";
  }
});


refreshRagGuideButton.addEventListener("click", async () => {
  if (busy) return;
  setToolBusy(true);
  refreshRagGuideButton.disabled = true;
  refreshRagGuideButton.textContent = "Refreshing...";
  try {
    const result = await authRequest("/api/admin/rag/refresh", { method: "POST" });
    showRagGuideMessage(`${result.message} ${result.document_count} knowledge sections indexed.`, true);
  } catch (error) {
    showRagGuideMessage(error.message);
  } finally {
    setToolBusy(false);
    refreshRagGuideButton.disabled = false;
    refreshRagGuideButton.textContent = "Refresh guide";
  }
});


for (const promptButton of document.querySelectorAll("[data-rag-question]")) {
  promptButton.addEventListener("click", () => {
    ragGuideQuestion.value = promptButton.dataset.ragQuestion;
    ragGuideQuestion.focus();
  });
}

const customerSelect = document.querySelector("#mcpTierCustomer");
const customerFilter = document.querySelector("#assistantCustomerSearch");
const tierButton = document.querySelector("#mcpTierButton");
const historyButton = document.querySelector("#assistantHistoryButton");
const toolMessage = document.querySelector("#mcpTierMessage");
const toolRetry = document.querySelector("#assistantToolRetry");
const tierResult = document.querySelector("#mcpTierResult");
const tabs = [...host.querySelectorAll("[data-assistant-tab]")];
let assistantCustomers = [];
let selectedId = "";
let busy = false;
let lastTool = "tier";
let customerLoadVersion = 0;
try { selectedId = sessionStorage.getItem("ethan.assistant.customer") || ""; } catch (_) {}

function clearCustomerResults() {
  tierResult.hidden = true;
  toolRetry.hidden = true;
  toolMessage.textContent = "";
  pendingCustomerChange = null;
  customerChangeProposal.hidden = true;
  customerInsightResult.hidden = true;
  customerInsightMessage.textContent = "";
}

function switchAssistantTab(name) {
  if (busy) return;
  clearCustomerResults();
  document.querySelector("#assistantCustomerFields").hidden = name === "guide";
  document.querySelector("#assistantSelectedContext").hidden = name === "guide";
  for (const tab of tabs) {
    const active = tab.dataset.assistantTab === name;
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
    document.getElementById(tab.getAttribute("aria-controls")).hidden = !active;
  }
}
tabs.forEach((tab, index) => {
  tab.addEventListener("click", () => switchAssistantTab(tab.dataset.assistantTab));
  tab.addEventListener("keydown", event => {
    const next = event.key === "ArrowRight" ? (index + 1) % tabs.length
      : event.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length
      : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : null;
    if (next !== null && !busy) { event.preventDefault(); tabs[next].click(); tabs[next].focus(); }
  });
});

function setToolBusy(value) {
  busy = value;
  for (const button of [tierButton, historyButton]) button.disabled = busy || !selectedId;
  for (const control of [customerSelect, customerFilter, customerInsightQuestion, ragGuideQuestion,
    confirmCustomerChangeButton, cancelCustomerChangeButton, askCustomerInsightButton, askRagGuideButton,
    refreshRagGuideButton, toolRetry, document.querySelector("#assistantReloadCustomers"),
    ...tabs, ...host.querySelectorAll("[data-insight-question], [data-customer-prompt], [data-rag-question]")]) {
    control.disabled = busy;
  }
  host.setAttribute("aria-busy", String(busy));
}

function rememberCustomer() {
  try {
    if (selectedId) sessionStorage.setItem("ethan.assistant.customer", selectedId);
    else sessionStorage.removeItem("ethan.assistant.customer");
  } catch (_) {}
}

function renderCustomerOptions() {
  const term = customerFilter.value.trim().toLowerCase();
  const matches = assistantCustomers.filter(item =>
    [item.full_name, item.email, String(item.user_id)].some(value => value.toLowerCase().includes(term)));
  customerSelect.replaceChildren();
  const prompt = document.createElement("option");
  prompt.value = "";
  prompt.textContent = matches.length ? "Select a customer" : "No matching customers";
  customerSelect.append(prompt);
  for (const item of matches) {
    const option = document.createElement("option");
    option.value = String(item.user_id);
    option.textContent = `${item.full_name} · ${item.email} · #${item.user_id}`;
    customerSelect.append(option);
  }
  // Never call a tool for a selected customer hidden by the current search.
  if (!matches.some(item => String(item.user_id) === selectedId)) {
    selectedId = ""; rememberCustomer(); clearCustomerResults();
  }
  customerSelect.value = selectedId;
  const selected = assistantCustomers.find(item => String(item.user_id) === selectedId);
  document.querySelector("#assistantSelectedContext").textContent = selected
    ? `Selected: ${selected.full_name} (Customer #${selected.user_id}).`
    : "Select a customer for the quick actions.";
  setToolBusy(busy);
}

async function loadAssistantCustomers() {
  const version = ++customerLoadVersion;
  try {
    const result = await authRequest("/api/admin/loyalty");
    if (version !== customerLoadVersion) return;
    if (!Array.isArray(result.loyalty_accounts)) throw new Error("Customer list is unavailable.");
    assistantCustomers = result.loyalty_accounts.filter(item => Number.isSafeInteger(item.user_id)
      && item.user_id > 0 && typeof item.full_name === "string" && typeof item.email === "string");
    renderCustomerOptions();
  } catch (error) {
    if (version !== customerLoadVersion) return;
    assistantCustomers = []; selectedId = ""; renderCustomerOptions();
    toolMessage.textContent = `${error.message} Use Reload customers to retry.`;
  }
}
customerFilter.addEventListener("input", renderCustomerOptions);
customerSelect.addEventListener("change", () => {
  selectedId = customerSelect.value; rememberCustomer(); clearCustomerResults(); renderCustomerOptions();
});
document.querySelector("#assistantReloadCustomers").addEventListener("click", () => {
  clearCustomerResults(); loadAssistantCustomers();
});
document.addEventListener("customer-accounts:updated", () => {
  clearCustomerResults(); loadAssistantCustomers();
});
for (const button of host.querySelectorAll("[data-customer-prompt]")) {
  button.addEventListener("click", () => {
    if (!selectedId) { showCustomerInsightMessage("Select a customer in Customer tools first."); return; }
    const selected = assistantCustomers.find(item => String(item.user_id) === selectedId);
    if (!selected) { showCustomerInsightMessage("Reload customers and select an account."); return; }
    customerInsightQuestion.value = button.dataset.customerPrompt === "edit"
      ? `Change the full name for Customer #${selectedId} to `
      : `Find the customer with email ${selected.email} and summarise their account status and loyalty.`;
    showCustomerInsightMessage(button.dataset.customerPrompt === "edit"
      ? "Enter the new name before asking AI. Nothing is saved until you confirm." : "");
    customerInsightQuestion.focus();
  });
}

async function runCustomerTool(kind) {
  if (busy) return;
  const account = assistantCustomers.find(item => String(item.user_id) === selectedId);
  if (!account) { toolMessage.textContent = "Select a customer first."; return; }
  lastTool = kind; clearCustomerResults(); setToolBusy(true);
  toolMessage.classList.remove("success");
  toolMessage.textContent = kind === "tier" ? "Checking current points through MCP..." : "Loading recorded point changes through MCP...";
  try {
    if (kind === "tier") {
      const response = await authRequest("/api/admin/mcp/loyalty-tier", {
        method: "POST", body: JSON.stringify({user_id: account.user_id}),
      });
      const tier = response.result;
      const expected = tier?.points_balance >= 1000 ? ["Gold", null, 0]
        : tier?.points_balance >= 500 ? ["Silver", "Gold", 1000 - tier.points_balance]
        : ["Bronze", "Silver", 500 - tier?.points_balance];
      if (response.success !== true || response.tool !== "ethan_ting_calculate_loyalty_tier"
        || response.metadata?.read_only !== true || !Number.isSafeInteger(tier?.points_balance)
        || tier.points_balance < 0 || tier.tier !== expected[0] || tier.next_tier !== expected[1]
        || tier.points_to_next_tier !== expected[2]) throw new Error("Invalid progress result. Try again.");
      const badge = document.querySelector("#mcpTierBadge");
      badge.textContent = tier.tier; badge.dataset.tier = tier.tier.toLowerCase();
      document.querySelector("#mcpTierDetails").textContent = `${account.full_name}: ` + (tier.next_tier
        ? `${tier.points_balance.toLocaleString("en-AU")} points. ${tier.points_to_next_tier.toLocaleString("en-AU")} more to reach ${tier.next_tier}.`
        : `${tier.points_balance.toLocaleString("en-AU")} points. Highest tier reached.`);
      tierResult.hidden = false;
    } else {
      const result = await authRequest("/api/admin/mcp/loyalty-history", {
        method: "POST", body: JSON.stringify({user_id: account.user_id, limit: 5}),
      });
      if (result.history?.customer_id !== account.user_id || result.history?.limit !== 5
        || result.source !== "mcp" || result.read_only !== true) throw new Error("History could not be matched to this customer. Try again.");
      renderCustomerInsight(result);
    }
    toolMessage.textContent = "Loaded through MCP. Nothing was changed.";
    toolMessage.classList.add("success");
  } catch (error) {
    toolMessage.textContent = error.message;
    toolRetry.hidden = false;
  } finally { setToolBusy(false); }
}
document.querySelector("#mcpTierForm").addEventListener("submit", event => { event.preventDefault(); runCustomerTool("tier"); });
historyButton.addEventListener("click", () => runCustomerTool("history"));
toolRetry.addEventListener("click", () => runCustomerTool(lastTool));

const status = document.querySelector("#assistantServiceStatus");
function statusFailure(event) {
  if (event.detail.target !== status && event.detail.elt !== status
    && event.detail.elt?.getAttribute("hx-target") !== "#assistantServiceStatus") return;
  status.textContent = [401, 403].includes(event.detail.xhr?.status)
    ? "Sign in as an administrator to check connections."
    : "Connection status could not be checked. Use Check connections to retry.";
}
for (const event of ["htmx:responseError", "htmx:sendError", "htmx:timeout"]) document.addEventListener(event, statusFailure);
document.addEventListener("htmx:beforeRequest", event => {
  if (event.detail.elt === status && document.hidden) event.preventDefault();
  else if (event.detail.elt === status || event.detail.elt?.getAttribute("hx-target") === "#assistantServiceStatus") {
    status.textContent = "Checking MCP and RAG connections...";
  }
});
loadAssistantCustomers();
})();
