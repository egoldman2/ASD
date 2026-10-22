# Accounts and Loyalty UI review

22 October 2026, Sydney time. These checks cover a local UI revision on top of
`910a654`; the revision has not been committed or deployed to AWS.

## Improvements

- Account and loyalty management appear before the assistant. A page-header
  shortcut opens the assistant directly.
- Accounts and Loyalty share one pagination helper. Search checks all records,
  resets to the first page, and displays a matching count and empty state.
- Assistant tabs retain their results and the unsaved human-review draft.
  MCP history and AI analysis have separate result panels. Selecting another
  customer clears the previous customer's results.
- Planner, Worker and Reviewer use expandable cards; Reviewer opens initially.
  Human review remains explicit and does not alter customer records.
- Phone tabs form an even two-by-two grid. Forms, customer selection and account
  controls fit narrow screens. Empty status areas no longer create large gaps.
- Sign-in and registration have direct links to each other, preserving the
  return URL. Form errors appear beside the relevant form, and Cancel returns
  focus to its opening button. Account-type tabs support arrow keys.
- Connection-check times use Sydney time. A guide response with insufficient
  context uses neutral feedback rather than a green success message.

## Observed checks

- Browser review: admin Accounts, admin Loyalty, sign-in, registration and the
  signed-in demo customer's Profile, Change password and membership sections.
- Responsive checks: Accounts at 320, 390 and 768 CSS pixels; Loyalty at desktop
  and tablet width plus 390 pixels; registration and customer account at phone width. The tested
  pages had no horizontal page overflow.
- Customer pagination showed 10 of 12 records, then the remaining two. Searching
  from page two reset the result to page one; an unmatched search displayed the
  empty state. Loyalty pagination and filtering behaved the same way.
- Add administrator and Edit customer forms opened correctly; Edit customer
  did not display a password field. Cancel restored focus. The points editor
  showed the existing balance and history and was cancelled without saving.
- A temporary human-review reason survived leaving and returning to the review
  tab. The temporary text was cleared without recording a decision.
- Live MCP history and Ask AI results remained in their respective tabs after
  switching. A different customer selection hid the old results.
- The browser reported no console errors for Accounts, Loyalty or the customer
  account page during the final check.
- Ethan Ting's Python suites plus cloud-bundle tests: **383 passed**. The local
  frontend and backend images rebuilt successfully.

No customer account, password or points mutation was submitted during this UI
review. The local demo customer was used to inspect the customer page; existing
admin sessions were preserved. Screenshots are local evidence, not cloud proof.

## Screenshots

- [Accounts on desktop](accounts-desktop.png)
- [Loyalty on desktop](loyalty-desktop.png)
- [Shared assistant on a phone](assistant-mobile.png)
- [Loyalty on a phone](loyalty-mobile.png)

Temporary viewport overrides were cleared after validation. Accounts and Loyalty
remain open at normal browser size for review.
