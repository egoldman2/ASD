# S03a: measured idle probe overhead and source repair

Owner: Ethan Goldman, 17 October 2026 UTC/AEDT. Diagnosis repository base:
`7b64a0cdb19208f5259ba1da71b48e95f0542fd0`. All AWS samples describe the older
manual accepted release, whose full SHA remains unverified. No branch source or
new health configuration was deployed to AWS. Final S03 acceptance is pending.

## Measurements

- [Host memory/process sample](pressure.json): 995,112 KiB available of 1,955,500
  KiB, no swap and zero current-boot kernel OOM messages at 12:28 UTC. Historical
  [global OOM evidence](../recovery-20261017/oom-context.json) remains distinct.
- [CloudWatch CPU](current-CPUUtilization.json) stays near 20%; [credits](current-CPUCreditBalance.json)
  remain near zero in standard mode. AWS lists t3.small's baseline as 20% on
  each of two vCPUs; depleted standard credits restrict bursting. [AWS reference](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-credits-baseline-concepts.html).
- [15-second process sample](cpu-profile.json) shows low CPU in persistent
  Gunicorn/daemon processes and substantial steal time. It excludes processes
  that exited between samples. Actual deployed readiness/health functions and
  seven five-second Python probes were inspected; no speculative teammate fix.
- [30-second cgroup sample](cgroup-profile.json): seven API/database containers
  consume 12.231853 CPU-seconds in 30.024331 seconds, approximately 20.37% of two
  vCPUs. Each runs three or four execs; frontend/gateway cgroups show zero CPU.
  Cgroup CPU includes API requests and health children. Attribution to recurring
  probes is an inference supported by the process and direct probe measurements.
- [Six actual localhost probes](probe-benchmark.json) all return 200. Normal
  Python median CPU is 0.4845 seconds; skipping site initialization gives
  0.543725 seconds. That experiment showed no consistent benefit, so `-S` was
  not added. Wall time includes docker exec and host throttling.

[Analysis and calculated limits](analysis.json) preserves the arithmetic. Four
successful read-only [SSM commands](ssm-execution.json) and their safe scripts are
retained: [memory](inspect-pressure.sh), [CPU/source](profile-cpu.sh),
[cgroups/events](profile-cgroups.sh), [probe comparison](benchmark-probe.sh).
No raw event attributes, full Docker environment or application rows were exported.

## Small source change

`cloud/compose.yml` spaces steady probes from five to 30 seconds, while retaining
five-second startup checks during the existing 30-second grace period. Five
failures at 30-second intervals keep the former 150-second configured interval
budget (30 failures at five seconds). Probe execution adds time, so this is not
a promise of identical wall-clock failure latency. All seven HTTP commands,
two-second HTTP timeouts, three-second container timeouts, dependency health
conditions and installer acceptance checks remain intact.

Configured periodic frequency is reduced sixfold; this is **not** a measured
sixfold reduction in overall AWS CPU. It needs a clean main deployment and new
measurements. The change requires Compose's `start_interval` support, introduced
in 2.20.2; provisioning pins 2.39.4. [Docker reference](https://docs.docker.com/reference/compose-file/services/#healthcheck).
No instance resize, unlimited credits, paid feature or healthcheck removal.

## Verification and remaining acceptance

[Before change, native compressed log](before-schedule-tests.txt.gz): one schedule failure and 14 passing
actual HTTP cases. [After change](focused-tests.txt): 15 pass, including all seven
actual command bodies against a real local HTTP server for both 200 and 503.
[Shared/cloud](shared-cloud-tests.txt): 302 pass. The generated cloud bundle's
[rendered Compose checks](rendered-compose-health.json) resolve the new schedule
on all seven services. [Support regression](support-tests.txt): 206 pass, 10 opt-in skips.
[Isolated Linux timing](linux-health-timing.json): healthy at 6.170 seconds;
a synthetic 503 fault became unhealthy at 157.388 seconds with five failures.
Only the created disposable container was removed; no network/volumes/credentials
were used. The fixture uses Docker's shell-form health command for timing; actual
Compose keeps its existing CMD form. [Commands and source hashes](verification.json).

[Final old-host observation](pressure-end.json) at 12:40 UTC has 989,420 KiB
available, zero new kernel OOM messages and zero container restarts/OOMKilled.
Its uptime exceeds 30 minutes. [EC2/SSM](final-host-readiness.json) and
[public HEAD](final-public-head.json) remain healthy; [CPU](final-CPUUtilization.json)
and [credits](final-CPUCreditBalance.json) retain the idle constraint. This is
read-only observation, not the required representative CRUD/load acceptance.

Historical OOM involved application, runtime and kernel memory; this CPU repair
does not establish that event's complete cause or guarantee long-term memory
stability. S03 still needs an authorized clean main deployment, 30 minutes of
representative login/browsing/support CRUD, fresh memory/restart/OOM/credit trends
and public acceptance. Read-only observation of the old release cannot satisfy
that gate. S04 OIDC remains explicitly SCP-denied; the [owner capability decision](../../../architecture/aws-deployment.md#concrete-capability-decision-for-the-project-owner)
is separate from a paid upgrade and from PR merge authorization. Human ticket
and final release decisions remain pending.
