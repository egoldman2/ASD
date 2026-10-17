#!/usr/bin/env bash
# Provision/update only this application stack in the Toolkit project's Region.
set -euo pipefail
region=ap-southeast-2
profile=${AWS_PROFILE:-aws-toolkit}
stack=${ASD_STACK_NAME:-asd-release2}
root=$(cd "$(dirname "$0")/.." && pwd)
instance_type=${ASD_INSTANCE_TYPE:-t3.small}
repository_identity=${GITHUB_OIDC_REPOSITORY_IDENTITY:-egoldman2@200193881/ASD@1326270780}
if [[ ! "$repository_identity" =~ ^[A-Za-z0-9_.-]+@[1-9][0-9]*/[A-Za-z0-9_.-]+@[1-9][0-9]*$ ]]; then
  echo 'Set GITHUB_OIDC_REPOSITORY_IDENTITY to the verified owner@owner-id/repository@repository-id; no AWS requests made.' >&2
  exit 1
fi
plan=$(aws freetier get-account-plan-state --profile "$profile" --region "$region" --query accountPlanType --output text)
eligible=$(aws ec2 describe-instance-types --profile "$profile" --region "$region" --instance-types "$instance_type" --query 'InstanceTypes[0].FreeTierEligible' --output text)
if [ "$plan" = FREE ] && [ "$eligible" != True ]; then
  echo "$instance_type is not eligible for this project's Free plan; no stack changes made." >&2
  exit 1
fi
prefix_list=$(aws ec2 describe-managed-prefix-lists --profile "$profile" --region "$region" --filters Name=prefix-list-name,Values=com.amazonaws.global.cloudfront.origin-facing --query 'PrefixLists[0].PrefixListId' --output text)
test "$prefix_list" != None
aws cloudformation validate-template --profile "$profile" --region "$region" --template-body "file://$root/cloud/infrastructure.yml" >/dev/null
aws cloudformation deploy --profile "$profile" --region "$region" --stack-name "$stack" \
  --template-file "$root/cloud/infrastructure.yml" \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides "CloudFrontPrefixList=$prefix_list" \
    "EnableGitHubOidc=${ENABLE_GITHUB_OIDC:-false}" \
    "GitHubRepository=$repository_identity" \
    "ExistingGitHubProviderArn=${GITHUB_OIDC_PROVIDER_ARN:-}" \
    "InstanceType=$instance_type" \
  --tags Project=ASD Release=2 ManagedBy=CloudFormation \
  --no-fail-on-empty-changeset
aws cloudformation describe-stacks --profile "$profile" --region "$region" --stack-name "$stack" --query 'Stacks[0].Outputs' --output json
