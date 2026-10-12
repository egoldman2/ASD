# Release 2 AWS deployment

The cloud baseline runs the existing five features and their CRUD APIs on one EC2 host in `ap-southeast-2`. The local Release 1 Compose layout remains available. Ollama, MCP, RAG and the future multi-agent service are disabled in the cloud configuration.

```mermaid
flowchart LR
    Browser -->|HTTPS| CloudFront
    CloudFront -->|HTTP, origin verification header| Gateway[EC2: Nginx gateway]
    Gateway --> Frontends[Home and five feature frontends]
    Gateway --> APIs[Four application APIs]
    APIs --> Databases[Three SQLite database APIs]
    APIs --> Orders[Orders SQLite file]
    Databases --> EBS[Encrypted retained EBS volume]
    Orders --> EBS
    S3[Private release bucket] -->|SSM deployment| Gateway
```

## Design choices

- One public HTTPS origin gives all features a shared secure session cookie. Paths are `/catalogue/`, `/inventory/`, `/account/`, `/orders/` and `/support/`.
- `cloud/prepare.py` builds a source-only cloud bundle and rewrites the original browser-local URLs. It excludes existing databases, environment files, Git metadata and local generated files. It refuses to overwrite a build directory.
- Gunicorn serves Flask in the cloud. The gateway is the only published container port. Database APIs and feature APIs communicate through the private Compose network.
- EC2 ingress accepts port 80 only from the AWS-managed CloudFront origin-facing prefix list. A generated secret header rejects requests from other distributions. No SSH port is opened; administration uses Systems Manager.
- The host fetches release files and generated credentials with an instance role. IMDSv2 and a hop limit of one prevent bridge-network application containers from using that role.
- Accounts, products, support and orders databases live under `/srv/asd/data` on encrypted EBS, outside release directories. The generated session key also survives releases. Initial seed passwords come from Secrets Manager; existing database hashes are not replaced.
- The EC2 default is `t3.small`, verified eligible for this project's Free plan. Local idle measurements were approximately 550 MiB across the 14 containers. This is an assessment baseline; load and sustained CPU usage still need measurement.

## Provision and release

Use the AWS Toolkit profile and confirm the selected Region in **AWS Settings → View all projects → Overview → Additional Info → Region**. All Regional resources in this template are in Sydney.

```bash
export AWS_PROFILE=aws-toolkit
bash cloud/provision.sh
python3 cloud/deploy.py --release manual-unique-id --report deployment-report.json
```

Provisioning validates the template and checks the chosen instance type against the project's current plan before changing the stack. It creates the VPC, host, retained storage, private release bucket, secrets and CloudFront distribution. The host installs Docker and a checksum-verified Compose binary.

Deployment creates a source archive, uploads it to S3 and executes installation through SSM. The host verifies the archive hash, builds containers and runs integrated authentication and CRUD checks. Only a passing release becomes `/srv/asd/current`. A failed update attempts to restore the previous containers; database changes are not rolled back. Do not introduce destructive database migrations without a separate backup and recovery plan.

SSM command IDs and sanitized deployment reports provide evidence. Do not paste `cloud.env`, Secrets Manager values, cookies or raw `docker inspect` output into reports. The seed password can be retrieved privately from the stack's `DemoPasswordArn` for `admin@asd.local` and `customer@asd.local`; it is not published in source or stack outputs.

## Stop and resume sessions

The initial environment was stopped after verification at the user's request. Its URL is `https://dww8d9hiqp0ce.cloudfront.net`; it is unavailable while EC2 is stopped. The instance ID is `i-03a217a6a7f61d3ae`. Start it for the next group session:

```bash
aws ec2 start-instances --profile aws-toolkit --region ap-southeast-2 --instance-ids i-03a217a6a7f61d3ae
aws ec2 wait instance-running --profile aws-toolkit --region ap-southeast-2 --instance-ids i-03a217a6a7f61d3ae
```

Allow Docker and the APIs time to become ready, then check the public homepage and sign-in. The Elastic IP keeps the CloudFront origin address stable. Use Systems Manager to investigate startup rather than opening SSH. Stop it after a session:

```bash
aws ec2 stop-instances --profile aws-toolkit --region ap-southeast-2 --instance-ids i-03a217a6a7f61d3ae
aws ec2 wait instance-stopped --profile aws-toolkit --region ap-southeast-2 --instance-ids i-03a217a6a7f61d3ae
```

Stopping saves compute charges but retains both disks, the Elastic IP and secrets. See [cost estimates](../evidence/release2-aws/cost-estimate.md). Deployment reports describe successful checks made while the host was running; they do not imply the stopped website is currently reachable.

## GitHub deployment

`.github/workflows/cloud-deployment.yml` runs six test suites and a cloud container build before deploying a main-branch release. Configure a GitHub environment named `aws-cloud`, with `AWS_DEPLOY_ROLE_ARN` and optionally `AWS_STACK_NAME` environment variables. The AWS role trusts only this repository and that environment using OIDC; no long-lived access keys are needed.

The template's `EnableGitHubOidc` parameter defaults to `false`. This project's managed policies explicitly denied IAM OIDC provider creation, read and list operations during setup. The actual GitHub role and a successful GitHub deployment run remain to be established; preparing a workflow does not verify CI/CD. If the project permits OIDC, enable the template option with `ENABLE_GITHUB_OIDC=true`; supply `GITHUB_OIDC_PROVIDER_ARN` when reusing an existing provider. Project capability changes belong in AWS Settings and require the project owner's decision. AWS documents these restrictions in its [project capability guide](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html).

## Validation and limitations

The initial port passed 677 Python tests with ten optional live-service tests skipped, plus 44 integrated local cloud checks. A request without the gateway's origin verification header was rejected with HTTP 403. The template passed cfn-lint, the repository's targeted cfn-guard rules and AWS `validate-template`. These checks cover this change; they do not establish that all Release 2 assessment requirements are complete.

This baseline has a single host and SQLite databases. It has no automatic failover, scheduled database backups or centralized application-log collection. Container logs rotate on disk; CloudTrail event history is available but no durable trail was configured. CloudFront provides browser HTTPS, while the restricted origin connection currently uses HTTP. An ALB with origin TLS and managed database/backup services are possible next steps if the group decides it needs stronger availability or end-to-end transport encryption.

Retained EBS, the release bucket and seed-password secret survive stack deletion. Deleting a stack does not fully remove storage charges. Before cleanup, identify these resources and decide whether application data must be preserved or exported. The failed initial stack contained no deployed application data; its unused retained resources were removed with explicit user approval before the eligible-instance retry.

## Group decisions still needed

Decide who owns the AWS project and invites team members; whether to keep this shared environment running; the acceptable credit budget; how demo credentials are shared privately; who can approve deployments; whether the current availability, logging and backup limits are sufficient; and how OIDC capability will be enabled. The local multi-agent implementation, student endpoint test assignments, review pages, report and showcase remain separate Release 2 work.
