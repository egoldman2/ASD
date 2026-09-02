# Agentic Review Evidence

- Feature: Ethan Ting - Customer Accounts and Loyalty
- Mode: endpoints
- Model: llama3.1:8b
- Generated: 2026-08-31T00:46:24
- Prompt: /Users/ethan/Desktop/Uni/Advanced software development/Assessment 1/ASD/student-Ethan Ting/agentic/review_prompt.txt

## Plan

Load the feature-specific prompt, collect read-only endpoints evidence, request an initial
review, evaluate that review, and adapt it when required.

## Evidence

```json
{
  "method": "GET only",
  "endpoints": [
    {
      "name": "Customer service health",
      "url": "http://localhost:6002/health",
      "method": "GET",
      "expected_status": 200,
      "status": 200,
      "content_type": "application/json",
      "response": {
        "status": "healthy"
      }
    },
    {
      "name": "Customer service readiness",
      "url": "http://localhost:6002/ready",
      "method": "GET",
      "expected_status": 200,
      "status": 200,
      "content_type": "application/json",
      "response": {
        "database": "healthy",
        "status": "ready"
      }
    },
    {
      "name": "Signed-out session protection",
      "url": "http://localhost:6002/api/session",
      "method": "GET",
      "expected_status": 401,
      "status": 401,
      "error": "HTTP Error 401: UNAUTHORIZED"
    },
    {
      "name": "Customer profile protection",
      "url": "http://localhost:6002/api/profile",
      "method": "GET",
      "expected_status": 401,
      "status": 401,
      "error": "HTTP Error 401: UNAUTHORIZED"
    },
    {
      "name": "Customer loyalty protection",
      "url": "http://localhost:6002/api/loyalty",
      "method": "GET",
      "expected_status": 401,
      "status": 401,
      "error": "HTTP Error 401: UNAUTHORIZED"
    },
    {
      "name": "Customer loyalty history protection",
      "url": "http://localhost:6002/api/loyalty/history",
      "method": "GET",
      "expected_status": 401,
      "status": 401,
      "error": "HTTP Error 401: UNAUTHORIZED"
    },
    {
      "name": "Administrator customer-list protection",
      "url": "http://localhost:6002/api/admin/customers",
      "method": "GET",
      "expected_status": 401,
      "status": 401,
      "error": "HTTP Error 401: UNAUTHORIZED"
    },
    {
      "name": "Administrator loyalty-list protection",
      "url": "http://localhost:6002/api/admin/loyalty",
      "method": "GET",
      "expected_status": 401,
      "status": 401,
      "error": "HTTP Error 401: UNAUTHORIZED"
    }
  ]
}
```

## Initial Review

**PLAN REVIEWED**
Ethan Ting - Customer Accounts and Loyalty feature for ASD 2026 Release 0.

**OBSERVATIONS**
The collected evidence consists of HTTP GET requests to various endpoints of the Customer Accounts and Loyalty feature. The evidence shows that the feature is deployed and available, with all endpoints returning the expected status codes.

**FINDINGS**
1. **High**: The feature is correctly rejecting unauthenticated requests to protected endpoints. All endpoints with expected status 401 are returning 401, indicating that the authentication mechanism is working as intended. (Evidence: Signed-out session protection, Customer profile protection, Customer loyalty protection, Customer loyalty history protection, Administrator customer-list protection, Administrator loyalty-list protection)
2. **Low**: The feature is deployed and available, with all endpoints returning the expected status codes. This is a positive observation, but it does not necessarily indicate that the feature is functioning correctly. (Evidence: Customer service health, Customer service readiness)

**RECOMMENDATIONS**
None. The collected evidence does not indicate any defects or issues with the feature.

**PROPOSED ADAPTATION**
None. The feature appears to be functioning as intended, and no changes are recommended at this time. However, further testing and review of the feature's functionality is necessary to ensure that it meets the requirements of the ASD 2026 Release 0.

## Reviewer Feedback

DECISION: ADAPT
Deterministic evidence checks found:
- A passing endpoint check should not be labelled as a High- or Medium-severity finding.

Model reviewer feedback:
DECISION: PASS

REVIEW FEEDBACK:
The review is evidence-based, correctly scoped, specific, and useful. It accurately reflects the collected evidence and provides clear findings and recommendations. The review correctly identifies the feature's correct rejection of unauthenticated requests to protected endpoints as a high-priority finding. The review also notes the feature's deployment and availability as a low-priority finding. The recommendations are concise and focused on the specific evidence presented. The proposed adaptation is clear and acknowledges the need for further testing and review of the feature's functionality. Overall, the review is well-written and effectively communicates the findings and recommendations based on the provided evidence.

## Final Review

OBSERVATIONS
- PASS: GET `/health` expected 200 and observed 200.
- PASS: GET `/ready` expected 200 and observed 200.
- PASS: GET `/api/session` expected 401 and observed 401.
- PASS: GET `/api/profile` expected 401 and observed 401.
- PASS: GET `/api/loyalty` expected 401 and observed 401.
- PASS: GET `/api/loyalty/history` expected 401 and observed 401.
- PASS: GET `/api/admin/customers` expected 401 and observed 401.
- PASS: GET `/api/admin/loyalty` expected 401 and observed 401.

FINDINGS
- All configured signed-out GET checks matched their expected statuses.
- 6 protected routes correctly rejected the signed-out request with 401 Unauthorized.
- Evidence limitation: this read-only run used signed-out GET requests only; it did not exercise authenticated CRUD or role-specific mutation requests.

RECOMMENDATIONS
- Keep the current signed-out protection and health-check expectations.
- Use the automated authenticated customer/admin tests as separate evidence for CRUD and role authorisation.

ADAPTATION APPLIED
- Replaced status contradictions with a deterministic comparison of expected and observed HTTP statuses.
- Grounding issues removed: A passing endpoint check should not be labelled as a High- or Medium-severity finding.
