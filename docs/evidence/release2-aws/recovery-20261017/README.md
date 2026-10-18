# S02a: existing AWS host recovery, 17 October 2026

Owner: Ethan Goldman. Captured 12:03–12:25 UTC (23:03–23:25 AEDT).
Repository source: `4cf926874458cf75b509d30b0ec1aff81e350e31`.
Environment: existing `asd-release2`, selected Region `ap-southeast-2`, profile
`aws-toolkit`. [Capture context](capture-context.json) distinguishes repository
source from the **unverified full SHA of the older manual cloud release**.

## Actual recovery and data preservation

Explicit human approval renewed CLI access using Chrome. AWS Settings confirmed
Sydney; CLI confirmed the project is still on the FREE plan. Billing balances,
team emails, auth URLs/codes and credentials are excluded. See
[project context](project-context.json) and [actual stack context](stack-context.json).
The native [Console screenshot](stack-outputs.jpg) displays resource identifiers,
including secret ARNs, but no secret values.

The existing t3.small was stopped following a user-initiated shutdown. CPU credit
mode remained standard. Both existing encrypted gp3 volumes were preserved:

| Volume | Size | Completed encrypted snapshot |
| --- | --- | --- |
| Data `vol-02087b3eeb07eec99` | 30 GiB | `snap-036e64b4a356e8578` |
| Root `vol-0abdeffdf216c8ed3` | 20 GiB | `snap-0e749c8a462661e04` |

Multi-volume snapshots were created while the instance was stopped and completed
before [starting the existing instance](start-instances.json) at 12:10:04 UTC.
[Completed state](snapshot-status.json), [data permissions](snapshot-permissions-data.json)
and [root permissions](snapshot-permissions-root.json) verify encryption and no
sharing grants. No detach, format, reseed, replacement, resize or credit-mode
change occurred. Snapshots consume storage credits while retained; cleanup is
pending an explicit owner decision and must not delete assessment data.

[Host inspection](host-inspection.json) verifies `/srv/asd` is the expected ext4
data volume, the session secret predates recovery and remains mode 0600, and all
14 containers are running. Seven configured API/database health checks are
healthy; seven frontend/gateway containers have no configured health check.
All container restart counts are zero and OOMKilled flags false at capture.
All four AI flags are false on all four application APIs. Memory available was
1,013,756 KiB of 1,955,500 KiB; there is no swap. This snapshot is not a capacity
or sustained-load result.

[Consistent SQLite backups](database-backup-manifest.json) were made with read-only
source connections and SQLite's backup API on the verified encrypted data volume.
The directory `/srv/asd/recovery/release2-20261017T121611Z` is mode 0700; backups
and the privately copied session secret are mode 0600. All four database copies
pass `PRAGMA integrity_check`, with zero foreign-key violations. Source main-file
bytes were unchanged across each backup; no business data was edited.

| Database | Actual table counts |
| --- | --- |
| Accounts | users 15; loyalty_accounts 14; loyalty_transactions 10 |
| Products | suppliers 5; products 13; cart_items 10; customer_cart_items 8 |
| Orders | orders 12; order_items 12; returns 12 |
| Support | support_tickets 12; support_ticket_messages 20 |

The supplier minimum remains an owner dependency. Cloud current-cart count 8
differs from the earlier local fixture's 0; neither was replaced or fabricated.
Database SHA-256 values and exact server paths are in the native manifest. No DB,
customer rows, session key or session-key fingerprint was exported. Same-volume
SQLite copies supplement the snapshots; no restore drill is claimed.

[EC2/system/attached-EBS checks](recovery-readiness-summary.json) are all `ok`,
SSM is Online and [both volumes](recovered-ebs-status.json) report normal IO/status.
[Public HEAD requests](recovery-public-head.json) return 200 for `/`, `/support/`
and `/account/`. This proves unauthenticated reachability only. Accepted path is
still `/srv/asd/releases/manual-20261009-aws2-d8cd072bf503`; source-metadata.json
is absent. No current branch code or new main deployment is claimed.

## Diagnosis and remaining gates

[Historical kernel context](oom-context.json) confirms the 15 October 13:19 UTC
global OOM and its killed Gunicorn process. Other processes and kernel memory
also occupied substantial memory; the victim alone does not establish the cause.
Last pre-stop [CPU credit balance](historical-credit-balance.json) was zero.
There is no evidence here that concurrent builds caused the OOM. A measured S03
repair and a clean deployment with 30 minutes of representative use remain open.

Fresh [OIDC listing](oidc-capability.json) fails with an explicit managed SCP
deny. This is a current List result, not a fresh Create/Get/AssumeRole attempt.
Stack OIDC remains false, with its old name-only repository parameter. S04a's
corrected immutable trust source has not been deployed. No paid/advanced feature
activation, GitHub deployment role creation or main merge occurred.
[AWS service template validation](template-validation.json) now succeeds;
[command/status metadata](post-recovery-checks.json). Template validity does not
prove IAM permission or deployment acceptance. Final S16 Actions/CRUD/persistence
and stability evidence is still missing.

## Reproduction and provenance

[SSM execution metadata](ssm-execution.json) records three successful commands,
response codes and times. Safe scripts are preserved as executed:
[host inspection](inspect-host.sh), [database backup](backup-databases.sh) and
[historical kernel inspection](inspect-historical-oom.sh). Run backups only after
reviewing the script's exact volume/path guards; it creates a fresh server-side
directory and fails on unexpected storage or integrity. No deployment command
is part of this checkpoint. First backup request exceeded the documented Comment
length limit and did not execute; its correction and failed local skeleton
experiment are disclosed in the execution metadata.

Native host outputs, status/validation responses, scripts and image are preserved
byte-for-byte. Other JSON explicitly selects or combines CLI metadata. Full Docker/env,
CloudTrail identities, auth logs, billing screens, DB files and raw kernel JSONL
remain private. [Artifact hashes](artifact-hashes.json) verify this capture set;
the historical kernel's separate hash references the private encrypted server
file. Standard secret hooks exclude evidence; a separate staged-file scan is
required before committing. Stage commit and exact-SHA CI are recorded in the
[progress ledger](../../release2-ethan-goldman/progress.md).

Subsequent [native Chrome browser check](public-browser-chrome.json) confirms the
public homepage renders and Support redirects to sign-in. [Homepage](public-home-chrome.jpg),
[sign-in](public-support-signin-chrome.jpg), [native AX](public-support-signin-chrome-ax.txt).
No credentials were entered; this remains older-release recovery evidence, not
S16 authenticated CRUD or confirmation of the group number printed in the footer.
