# Cost comparison

Checked 9 October 2026. Region: Sydney (`ap-southeast-2`). Currency: USD, before tax, credits and usage allowances. This is an estimate, not a bill. Use 730 hours per month. No Paid-plan upgrade was made.

AWS's [public Sydney catalogue](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/ap-southeast-2/index.json), published 8 October 2026, lists Linux shared-tenancy `t3.small` at $0.0264/hour and gp3 storage at $0.096/GB-month. [Public IPv4](https://aws.amazon.com/vpc/pricing/) costs $0.005/hour, including idle Elastic IPs. [Secrets Manager](https://aws.amazon.com/secrets-manager/pricing/) costs $0.40/secret-month plus API requests.

| Resource | Calculation | Monthly estimate |
| --- | --- | --- |
| EC2, continuously running | 730 × $0.0264 | $19.27 |
| 20 GB root + 30 GB data disks | 50 × $0.096 | $4.80 |
| One Elastic IP | 730 × $0.005 | $3.65 |
| Two generated secrets | 2 × $0.40 | $0.80 |
| Fixed running subtotal | Sum above | **$28.52** |

| Option | Monthly estimate | Effect |
| --- | --- | --- |
| Run continuously | $28.52 + variable usage | Public site available |
| Stop EC2 for the whole month | $9.25 + variable usage | Site unavailable, setup and data preserved |
| Run EC2 for 40 hours/month | $10.31 + variable usage | Available only during those sessions |
| Delete stack, preserve retained resources | $3.28 + S3 usage | 30 GB data disk, seed secret and release bucket remain |
| Delete all deployment resources and data | $0 ongoing for this deployment | Data lost; provision again for future sessions |

S3 release storage, S3 requests and Secrets Manager API requests are excluded from the fixed subtotal. [CloudFront pay-as-you-go](https://aws.amazon.com/cloudfront/pricing/pay-as-you-go/) includes 1 TB monthly transfer out and 10 million HTTP(S) requests; higher usage and some transfer categories can incur charges. The estimate assumes a lightly used assessment demo within the main allowances. T3 uses Standard CPU credits, avoiding Unlimited surplus-credit charges but allowing throttling after credits are depleted.

The project API reported an active Free plan with $100 USD remaining credits and expiry 9 April 2027. Usage/credit reporting may lag. At the fixed running subtotal, $100 covers approximately 3.51 months if no other services consume credits. [AWS states](https://aws.amazon.com/free/) that the Free plan does not charge unless upgraded; resources become unavailable when its credits or time allowance expire. Review actual spend in AWS Settings → Billing.
