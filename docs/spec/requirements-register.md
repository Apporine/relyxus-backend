# Relyxus Requirements Register (Step 1 — extraction)

Status: DRAFT for review · Extracted 2026-10-14 · Nothing below is an assumption; anything unclear is in the Open Questions section at the end.

## How to read this

**ID format** `<DOC>-<section>.<n>` — the ID itself is the source tag. Page numbers are added for the PDF.

| Prefix | Source document | Location format |
|---|---|---|
| `MPS` | Relyxus_Master_Product_Specification_v2.3_FINAL (1).pdf | § + PDF page (p.N) |
| `TSD` | Relyxus_Enterprise_Technology_Stack_Decision_v1.3_FINAL (1).docx | § |
| `DEP` | Relyxus_Enterprise_Deployment_Installation_Infrastructure_Specification_v1.2_FINAL.docx | § |
| `MP`  | cursor master prompt - after adding these 3 files.txt | § |
| `LIC` | Apporine_Licensing_Entitlement_Architecture_Specification_v1.0_FINAL.docx (added 2026-10-14) | § |

**Scope tags** (classification only — no requirement is dropped because of its tag):

- `BE` backend product behaviour (code in a Relyxus service)
- `UI` frontend/console behaviour (backend must expose what it needs)
- `OPS` packaging, deployment, infrastructure, CI/CD, release
- `XS` cross-cutting engineering standard that applies to all code
- `ORG` organisational / commercial / legal — not software, listed so nothing is lost
- `Ph0`–`Ph5` build phase **as stated in the source**; absent = source gives no phase

Duplicates across documents are kept as separate IDs and cross-referenced with `≡`; step 3 maps each to exactly one feature.

---

# A. Master Product Specification v2.3 (MPS)

## §1 The product in one page (p.1–2)
- **MPS-1.01** `BE` Relyxus is an AI incident responder for regulated companies: runs inside the customer's own network, finds the cause of an outage with evidence, fixes only within the approvals customer governance demands, drafts the regulator's report while the clock runs. (p.1)
- **MPS-1.02** `BE` Capabilities: detect, diagnose, act behind gates, communicate, report to regulators, learn. (p.1)
- **MPS-1.03** `BE` `OPS` Four deployment modes: Apporine cloud (SaaS), dedicated single-tenant cloud, customer's own cloud or data centre, fully air-gapped. (p.1) ≡ MPS-6.03
- **MPS-1.04** `BE` Watches Kubernetes (EKS, AKS, GKE, OpenShift), servers, AWS, Azure, Google Cloud, on-premise — through the customer's existing monitoring. (p.1)
- **MPS-1.05** `ORG` Price: target $50,000/yr per enterprise customer; minimum first-year deal $15,000; paid pilots credited towards the licence. (p.2)
- **MPS-1.06** `ORG` First markets UAE, Saudi Arabia, UK, EU; then Singapore and Australia. (p.2)
- **MPS-1.07** `BE` North-star: time to first correct hypothesis, median < 3 min from alert. (p.2)
- **MPS-1.08** `BE` North-star: diagnosis accuracy 70% correct-first, 85% top-three, measured by Replay. (p.2)
- **MPS-1.09** `BE` North-star: unapproved production changes — zero, always. (p.2)
- **MPS-1.10** `BE` North-star: verified downtime avoided, confirmed against customer's own history, reported to every customer monthly. (p.2)
- **MPS-1.11** `BE` North-star: regulator draft time < 15 min from "major incident" classification to complete first draft. (p.2)
- **MPS-1.12** `BE` Not built in v1: own metrics or log database (read the customer's); a security-operations product; full paging telephony stack before Phase 3. (p.2)

## §2 Pre-build analyses (p.2–4)
- **MPS-2.01** `ORG` 14 analyses with owner/output/status: discovery interviews; incident archaeology (200 incidents); competitor teardown; bank procurement journey; regulation-to-feature traceability; willingness-to-pay; unit economics; threat model (STRIDE + OWASP LLM); data-flow diagrams per deployment mode; model evaluation benchmark; usability tests (5 on-call engineers per phase); partner/channel map; win/loss log; fundraising narrative. (p.3–4)
- **MPS-2.02** `ORG` Weekly founder graphs: benchmark diagnosis accuracy, time to first value for new installs, design-partner usage; if any is flat for a month, stop adding features and fix it. (p.4)

## §3 Who we build for (p.4–6)
- **MPS-3.01** `ORG` Personas and what makes each buy / say no: on-call engineer, Head of SRE, CTO/VP Eng, CISO, Head of Operational Resilience, Procurement, architecture/change board. (p.4–5)
- **MPS-3.02** `BE` Bank pilot prerequisite: deployment inside its private cloud/DC with no inbound connection from Apporine. (p.5)
- **MPS-3.03** `BE` Bank pilot prerequisite: login through its own IdP with automatic provisioning and removal. (p.5)
- **MPS-3.04** `BE` Bank pilot prerequisite: two-person approval and segregation of duties for any change, plus a change record in its system. (p.5)
- **MPS-3.05** `BE` Bank pilot prerequisite: every AI conclusion traceable to evidence; model documentation its model-risk team can validate. (p.6)
- **MPS-3.06** `BE` Bank pilot prerequisite: audit logs streamed to its security monitoring; encryption with its own keys. (p.6)
- **MPS-3.07** `ORG` Bank pilot prerequisite: contract terms (audit rights, incident assistance, exit strategy, data return); source-code escrow, insurance, clear support model. (p.6)

## §4 Product principles (p.6–7)
- **MPS-4.01** `BE` Evidence before opinion: every AI claim links to the query, log line, metric or change that supports it; no evidence, no claim.
- **MPS-4.02** `BE` Say "I don't know" early: on low confidence show what was checked and ruled out instead of guessing.
- **MPS-4.03** `BE` Read-only by default: nothing changes production until a customer admin enables a specific action for a specific scope.
- **MPS-4.04** `BE` Autonomy earned: actions move up the ladder only on recorded evidence; drop automatically after any failure.
- **MPS-4.05** `BE` Every action reversible or blocked: if it cannot be rolled back or verified, it needs a human.
- **MPS-4.06** `BE` Customer data stays where the customer decides: deployment mode, model location and retention are settings.
- **MPS-4.07** `BE` `OPS` Relyxus must not depend on what it watches: keeps working when the customer's cluster, region or chat tool is down.
- **MPS-4.08** `UI` Clear in two minutes: a new responder understands what broke, impact and next step within 2 min of opening.
- **MPS-4.09** `UI` `BE` Fast during the worst hour: responsive under alert storms; no screen waits > 1 s without showing progress.
- **MPS-4.10** `BE` One source of truth: the incident record feeds chat, tickets, reports and audit; no manual copying.
- **MPS-4.11** `BE` Compliance by design: clocks, approvals and audit evidence produced as the incident happens.
- **MPS-4.12** `BE` Telemetry is untrusted input: logs/alerts never become instructions to the AI. (p.7)

## §5 Differentiators and table stakes (p.7–10)
- **MPS-5.01** `BE` `OPS` Four deployment modes incl. air-gapped with local AI model, full product incl. safe actions inside the customer network. ≡ MPS-6.03
- **MPS-5.02** `BE` Autonomy ladder per action, per service, per environment; promotion only on recorded success; automatic demotion. ≡ §10
- **MPS-5.03** `BE` Bank-grade approval gates: four-eyes, SoD, change-freeze calendar, blast-radius limits, break-glass; every action creates a change record.
- **MPS-5.04** `BE` Regulator Clock + drafted reports across EU, UK, US, Singapore, Australia, India, Gulf. ≡ §12
- **MPS-5.05** `BE` Impact-tolerance live tracker: "time to breach" per important business service + MAS 4-hour yearly downtime budget per critical system. ≡ §12
- **MPS-5.06** `BE` Incident Replay and public accuracy scorecard on the customer's own past incidents. ≡ §13
- **MPS-5.07** `BE` Third-party/concentration map: maps services to cloud regions and vendors; checks provider status in the first minute. ≡ MPS-8.10, MPS-12.11
- **MPS-5.08** `BE` Tamper-evident evidence ledger (hash-chained record of every input, model version, prompt template, output) and exportable model-governance documentation.
- **MPS-5.09** `BE` Business-impact first: revenue-per-minute and failed-transaction counters on every incident.
- **MPS-5.10** `BE` Prompt-injection firewall: telemetry quarantined as data; AI has no write tools; outputs schema-checked.
- **MPS-5.11** `BE` Runbook compiler: written runbooks → tested, gated, executable playbooks. ≡ MPS-13.09
- **MPS-5.12** `BE` Resilience Drill mode: replays past incidents as game days and records evidence. ≡ MPS-12.12
- **MPS-5.13** `BE` `ORG` Exit kit (one-click export in open formats) and source-code escrow for enterprise customers.
- **MPS-5.14** `UI` `BE` Arabic and English interface, full RTL, bilingual report templates.
- **MPS-5.15** `BE` Table stake: AI investigation across metrics, logs, traces, deploys and code changes.
- **MPS-5.16** `BE` Table stake: learns from past incidents (memory).
- **MPS-5.17** `BE` Table stake: checks that a fix actually worked.
- **MPS-5.18** `BE` Table stake: Slack and Microsoft Teams native.
- **MPS-5.19** `BE` Table stake: Jira and ServiceNow tickets and change records.
- **MPS-5.20** `BE` Table stake: post-mortems and timelines generated automatically.
- **MPS-5.21** `BE` Table stake: 60+ integrations plus an MCP server and client.
- **MPS-5.22** `BE` Table stake: status pages and stakeholder updates.
- **MPS-5.23** `BE` Table stake: on-call schedules and escalation.
- **MPS-5.24** `BE` Table stake: SSO, user provisioning, RBAC, audit log.
- **MPS-5.25** `BE` Table stake: public API and webhooks. (p.10)

## §6 System architecture and deployment modes (p.10–12)
- **MPS-6.01** `BE` One codebase runs in four modes. Edge Agent always runs in the customer environment and only connects outward; the AI Brain can only read; every change passes the policy engine. (p.10)
- **MPS-6.02** `BE` Target architecture — 3 zones / 16 components (diagram p.11): Customer env {monitoring & logs; K8s/VMs/clouds; Edge Agent (reads data, runs approved actions); optional local AI model; IdP}. Relyxus platform {web console & API; durable workflow engine; AI Brain (read-only tools); policy engine & gates; evidence ledger & database; model gateway}. People & tools {Slack/Teams; Jira/ServiceNow; paging/on-call; SIEM audit stream; regulator reports}. Every change passes the policy engine and runs through the customer-side agent. (p.11)
- **MPS-6.03** `BE` `OPS` Modes: SaaS multi-tenant (Ph1; our cloud, customer-chosen region; Claude via our account or customer's model account); Dedicated single-tenant (Ph3; our cloud isolated per customer; regional endpoints or customer account); Self-hosted (Ph3; customer K8s; customer cloud model account or local open-weight model); Air-gapped (Ph4; isolated network; local open-weight model only; offline updates). (p.11–12)
- **MPS-6.04** `BE` Claude reachable via Anthropic API, Amazon Bedrock, Google Cloud, Microsoft Foundry; regional endpoints keep routing inside a geography; air-gapped uses a local model with accuracy trade-off measured by Replay. (p.12)
- **MPS-6.05** `BE` Agent opens an encrypted, mutually authenticated outbound connection to the platform and receives work over it; no inbound firewall hole. (p.12)

## §6A Platform operations (p.12–15)
- **MPS-6A.01** `OPS` Bank platform team can install, upgrade, roll back, back up and recover with no Apporine shell access; every step has a preflight check, an audit record and a way back. (p.12)
- **MPS-6A.02** `OPS` `ORG` Responsibility matrix per mode for infrastructure, install/upgrades, DB & evidence backups, restore/DR drills (SaaS: Apporine quarterly; dedicated: Apporine quarterly with report shared; self-hosted: customer guided by drill procedure; air-gapped: customer), encryption keys, AI model hosting, security patches, support access (SaaS/dedicated off by default + customer-approved sessions; self-hosted none unless customer opens; air-gapped no remote access). (p.12–13)
- **MPS-6A.03** `OPS` Preflight (`relyxus preflight`) checks K8s version, CPU, memory, storage, egress rules, DNS, certificates, DB version & extensions, object storage, licence validity, image signatures, clock sync; any failure blocks install/upgrade with a plain-language fix. (p.13)
- **MPS-6A.04** `OPS` `UI` Install through Helm chart or operator; Platform Operations page shows every component, version and health. (p.13)
- **MPS-6A.05** `OPS` `relyxus upgrade plan <version>` shows version jump, compatibility checks, DB migrations and reversibility, required backups, breaking changes, release notes, risk level; upgrades skipping unsupported versions are refused. (p.13)
- **MPS-6A.06** `OPS` Backup gate: an upgrade with a destructive DB migration cannot start until a fresh verified backup exists and its restore check passed. (p.13)
- **MPS-6A.07** `OPS` Rolling upgrade: one replica first, smoke tests, then the rest; errors above threshold halt automatically. (p.13)
- **MPS-6A.08** `OPS` `BE` Rollback: one command returns to previous version; DB changes backward-compatible for one version so rollback never needs a restore. (p.13)
- **MPS-6A.09** `OPS` `relyxus support-bundle`: logs, versions, configuration with all secrets removed; customer reviews before sharing. (p.13)
- **MPS-6A.10** `OPS` Air-gapped updates: signed bundle of images, charts, model files, rule packages; signatures and checksums verified offline before loading into internal registry. (p.14)
- **MPS-6A.11** `BE` Licence states Active, Grace (30 days after expiry), Expired. Licence problems never stop alert intake or running investigations; after grace, configuration changes and upgrades are blocked until renewed. (p.14) — see Q-07
- **MPS-6A.12** `BE` `OPS` Every platform-operations step writes audit: who, when, version, result. (p.14)
- **MPS-6A.13** `OPS` Backup contract: main DB (records, config, policies, workflow state) — continuous WAL archiving + daily full, encrypted with customer key where configured, 35-day retention, restore check row counts + config checksums. (p.14)
- **MPS-6A.14** `OPS` `BE` Evidence ledger & audit log — inside main DB and object storage, continuous, per retention policy, full hash-chain re-verification after every restore. (p.14)
- **MPS-6A.15** `OPS` Object storage (evidence snapshots, reports, exports) — versioned bucket with replication, continuous, per retention policy, sample objects re-hashed. (p.14)
- **MPS-6A.16** `OPS` `BE` Secrets & keys held in customer vault; Relyxus stores references only; connector health checks after restore. (p.14)
- **MPS-6A.17** `OPS` Event bus not backed up by design: transient, replayed from sources. (p.14)
- **MPS-6A.18** `OPS` Recovery targets: SaaS RTO 1 h / RPO 5 min; self-hosted reference RTO 4 h / RPO 15 min (customers may tighten). (p.14)
- **MPS-6A.19** `OPS` Quarterly scripted DR drill: restore into isolated namespace → verify evidence hash chain, row counts, config checksum → smoke tests → record result. Platform Operations page shows last successful backup and last passed restore test. (p.15)
- **MPS-6A.20** `OPS` `BE` Public SaaS status page: health by region and component (web, API, alert intake, AI gateway, notifications), email/webhook/RSS subscriptions, archive of notices. (p.15)
- **MPS-6A.21** `BE` `UI` Self-hosted consoles show local component health separately from Apporine-controlled dependencies (licence service, update registry, optional hosted models). (p.15)
- **MPS-6A.22** `OPS` Acceptance: bank team upgrades and rolls back without Apporine shell access, every step audited; failed preflight blocks upgrade; destructive migration blocked until verified backup; drill recreates a self-hosted tenant from backup and proves evidence integrity; customers can subscribe to SaaS status by region/component. (p.15)

## §7 Module: Connect (p.15–19)
- **MPS-7.01** `BE` Connecting a tool takes < 5 min, never breaks silently, never grants more access than needed. (p.15)
- **MPS-7.02** `UI` `BE` Ph0 Integrations Hub: catalogue with search, categories, status badges (Connected, Degraded, Disabled, Not connected); filter by category and health. (p.15)
- **MPS-7.03** `BE` `UI` Ph0 Guided setup wizard per connector; every connector has the same six steps. (p.15) — see Q-23
- **MPS-7.04** `BE` Ph2 Read and action credentials are separate objects; write access off by default; enabling needs an admin plus a security admin. (p.16)
- **MPS-7.05** `BE` Ph0 Health check every 60 s; three failed checks → Degraded + alert integration owner; investigations warn when evidence came from a degraded source. (p.16)
- **MPS-7.06** `BE` Ph0 Credentials stored in the vault, never shown again after saving; rotation reminders; customer-managed keys in enterprise modes. (p.16)
- **MPS-7.07** `BE` Ph1 Auto-discovery of K8s services, cloud resources and OTel service graphs; proposes services/dependencies; a human confirms before they enter the catalogue. (p.16)
- **MPS-7.08** `BE` Ph1 Service mapping: maps labels (job, namespace, tags) to services and owners; imports owners from code-owner files and service catalogues. (p.16)
- **MPS-7.09** `BE` Ph1 Data policy per connector: which fields may reach the AI, retention and redaction; redaction for card numbers, emails, national IDs, tokens runs before any AI call. (p.16)
- **MPS-7.10** `BE` Ph5 Connector SDK and custom HTTP connector: import an OpenAPI file or define queries; sandboxed; read-only unless approved. (p.16)
- **MPS-7.11** `BE` Ph5 MCP client and server: uses customer's MCP tools and exposes Relyxus to their agents; allow-list per MCP tool; write tools follow the same gates. (p.16)
- **MPS-7.12** `BE` Connector state machine: Draft→{Testing, Removed}; Testing→{Connected, Draft on failure}; Connected→{Degraded, Disabled, Removed}; Degraded→{Connected auto on recovery, Disabled, Removed}; Disabled→{Connected, Removed}; Removed = soft-deleted 30 days then credentials destroyed → {Restored within 30 days}. (p.17)
- **MPS-7.13** `BE` Add flow step: catalogue card explains what will be read and confirms read-only. (p.17)
- **MPS-7.14** `BE` Add flow step: reach via direct URL, in-cluster Edge Agent (recommended for private networks) or long-term store (Thanos, Mimir). (p.17)
- **MPS-7.15** `BE` Add flow step: authentication none / basic / bearer / mutual TLS; secrets go straight to the vault. (p.17)
- **MPS-7.16** `BE` Add flow step: test connection — harmless query, version check, response time, confirm credentials cannot write; each check shows tick or plain-language fix. (p.17)
- **MPS-7.17** `BE` Add flow step: scope clusters/namespaces/jobs; default everything, with a count of series in scope. (p.17)
- **MPS-7.18** `BE` Add flow step: map to services (suggest from labels; accept/edit/skip). (p.17)
- **MPS-7.19** `BE` Add flow step: data policy — retention and redaction; preview a sample with sensitive values masked. (p.17)
- **MPS-7.20** `BE` Add flow step: save → Connected, health monitoring starts, change written to audit log. (p.17)
- **MPS-7.21** `BE` Remove flow: list dependents (services, alert rules, policies, open investigations); user reassigns or accepts breakage; user types connector name to confirm; orgs can require a second approver; soft-delete 30 days then credentials destroyed; every step audited. (p.17–18)
- **MPS-7.22** `BE` The add/test/scope/map/policy/remove pattern applies to every connector. (p.18)
- **MPS-7.23** `BE` Ph3 Service reconciliation: one real service appears once however many tools discover it. (p.18)
- **MPS-7.24** `BE` Ph3 Source priority: 1 human edit with reason (any field) > 2 ServiceNow CMDB when named authority (owner, business service, tier) > 3 catalogue import — Backstage, code-owner files (owner team, repository, on-call) > 4 auto-discovery (runtime location, dependencies). (p.18)
- **MPS-7.25** `BE` Ph3 Each service stores external IDs from each source; matching IDs merge automatically; likely matches go to a review queue, never merge silently. (p.18)
- **MPS-7.26** `BE` Ph3 Service lifecycle Active → Deprecated → Retired; retired services keep incident history; alerts still arriving for them are flagged. (p.18)
- **MPS-7.27** `BE` Ph3 Service with no telemetry and no source update for 30 days marked Stale for review. (p.18)
- **MPS-7.28** `BE` Ph3 Owners confirm services quarterly; owner removed through SCIM → "No owner" and routes to platform team. (p.18)
- **MPS-7.29** `BE` Ph3 ServiceNow CMDB sync is read-first; write-back optional and limited to Relyxus-owned fields (e.g. discovered dependencies). (p.18)
- **MPS-7.30** `BE` Ph3 Rotation: add new secret to vault → test without switching → overlap window (default 24 h) → cut over with health check → revoke old → one-click audited rollback on failure during overlap. (p.18–19)
- **MPS-7.31** `BE` Ph3 Expiry alarms to connector owner 30, 14, 7, 1 days before token/cert expiry; agent certificates renew automatically; neither secret ever in UI or logs. (p.19)
- **MPS-7.32** `BE` Ph3 Each connector declares version, required API endpoints and fields, permissions. (p.19)
- **MPS-7.33** `BE` Ph3 Daily connector contract tests; a breaking change marks connector Degraded with exact reason even when plain health check passes. (p.19)
- **MPS-7.34** `OPS` Ph3 Each release publishes a connector-vs-tool-version compatibility matrix with deprecation warnings. (p.19)
- **MPS-7.35** `BE` Acceptance: K8s + CMDB service never becomes two; changes reviewable; retirement keeps history; zero-downtime rotation without exposing either secret; Degraded on required API behaviour change even if HTTP check passes. (p.19)

## §8 Module: Detect and triage (p.19–22)
- **MPS-8.01** `BE` Goal: one incident per real problem with right severity and owner within seconds of the first alert. (p.19)
- **MPS-8.02** `BE` Ph0 Universal intake from Alertmanager, Grafana, Datadog, CloudWatch, Azure Monitor, PagerDuty, Opsgenie, generic webhooks; every alert normalised to source, service, severity, labels, start time, fingerprint. (p.19)
- **MPS-8.03** `BE` Ph0 Deduplication: same fingerprint within the open window updates the existing alert. (p.20)
- **MPS-8.04** `BE` Ph1 Grouping: same service or dependency-map neighbours within 10 min (configurable) join one incident; humans can split/merge; system learns from it. (p.20)
- **MPS-8.05** `BE` Ph1 Alert-storm protection: above a set rate (default 50 alerts/min) everything joins one storm incident with one investigation. (p.20)
- **MPS-8.06** `BE` Ph1 Severity engine suggests SEV1–SEV4 from business impact first, then technical signals; humans override with a reason. (p.20)
- **MPS-8.07** `BE` Ph1 Ownership routing from service catalogue; fallback platform team; never leaves an incident unowned. (p.20)
- **MPS-8.08** `BE` Ph2 Change watch: compare error rate and latency before/after each deploy; open "suspected bad deploy" incident if worse. (p.20)
- **MPS-8.09** `BE` Ph2 SLO multi-window burn-rate alert rules generated from SLOs in the catalogue. (p.20)
- **MPS-8.10** `BE` Ph3 Provider status check in the first minute for regions/vendors the service depends on; shown in incident header. (p.21)
- **MPS-8.11** `BE` Ph1 Maintenance windows silence expected alerts; linked to change records; alerts outside declared scope still fire. (p.21)
- **MPS-8.12** `BE` Ph4 Optional anomaly detection: baselines per hour of week; only for customer-selected business metrics. (p.21)
- **MPS-8.13** `BE` Default editable severity guide: SEV1 important business service down/outside tolerance → page on-call + lead, open war room, start regulator clocks; SEV2 major degradation → page on-call, investigation starts; SEV3 minor/partial → notify team channel; SEV4 no customer impact yet → ticket only. (p.21)
- **MPS-8.14** `BE` Ph1 Business impact model per business service: impact metrics (connector + query), formula, currency (ISO 4217 stored with every value), freshness limit, fallback assumption, confidence label (Measured / Estimated / Assumed), severity thresholds. (p.21–22)
- **MPS-8.15** `BE` Every money-at-risk value on screen, in reports and via API shows formula, source, timestamp and confidence label. (p.22)
- **MPS-8.16** `BE` Responder can override an impact value with a reason; overrides audited and visibly marked. (p.22)
- **MPS-8.17** `BE` Acceptance: every displayed money-at-risk value shows formula, source, timestamp, confidence; manual changes audited. (p.22)

## §8A Incident model (p.22–26)
- **MPS-8A.01** `BE` Ph1 Incident types configurable without code; a type defines: allowed severities + default severity; fields shown/required per lifecycle stage; default visibility; default roles; regulator mappings; automations; forms (declare/update/resolve); communication defaults. (p.22–23)
- **MPS-8A.02** `BE` Default editable types: Production outage, Degraded performance, Payment incident, Security event (Invite only by default), Third-party outage, Data incident (Restricted by default), Regulatory reportable incident, Exercise or drill, Internal operational event. (p.23)
- **MPS-8A.03** `BE` Ph1 Custom-field library types: text, number, currency, date-time, yes/no, single choice, multiple choice, user, team, service, vendor, URL/reference. (p.23)
- **MPS-8A.04** `BE` Fields can display conditionally (e.g. type = Payment incident AND severity ∈ {SEV1, SEV2}) and be required at a specific stage. (p.23)
- **MPS-8A.05** `BE` Deleting a field archives it; existing values stay. (p.23)
- **MPS-8A.06** `BE` Ph0 Every change to a type, field or form creates a new audited configuration version; each incident keeps the configuration version it was declared under. (p.23)
- **MPS-8A.07** `BE` Ph0 Lifecycle: 6 main states Triage, Investigating, Mitigating, Monitoring, Resolved, Closed; 2 exits Cancelled, Merged; 2 controlled loops (fix did not hold; reopen). (p.24) — see Q-11
- **MPS-8A.08** `BE` Triage → Investigating (declare): by responder, integration or workflow; requires type, title, severity, affected service; fires investigation, roles, notification rules, clock evaluation. (p.24)
- **MPS-8A.09** `BE` Investigating → Mitigating: by IC or responder; requires a working hypothesis or action recorded; fires stakeholder-update timer. (p.24)
- **MPS-8A.10** `BE` Mitigating → Monitoring: by IC; requires mitigation action recorded; fires verification watch on impact metrics. (p.24)
- **MPS-8A.11** `BE` Monitoring → Resolved: by IC; requires impact back to normal for the type's watch period + resolution fields; fires post-incident review creation and offers open live tasks as follow-ups. (p.24)
- **MPS-8A.12** `BE` Resolved → Closed: by review owner; requires post-incident review signed off; fires report lock and analytics update. (p.24)
- **MPS-8A.13** `BE` Monitoring → Mitigating (fix did not hold): by IC or automatic regression detector; fires timeline event and notifies commander. (p.24)
- **MPS-8A.14** `BE` Resolved → Investigating (reopen): by IC with reason; same incident ID; original timeline kept. (p.25)
- **MPS-8A.15** `BE` Any open state → Cancelled: by IC with reason (false alarm, duplicate); clocks stop; regulator drafts discarded with an audit record. (p.25) — see Q-11
- **MPS-8A.16** `BE` Any open state → Merged: by IC with target incident; ID redirects; timelines combined with source labels. (p.25)
- **MPS-8A.17** `BE` Reopen allowed for 7 days after resolution; after that a new incident is opened and linked as recurrence. (p.25)
- **MPS-8A.18** `BE` On reopen: submitted regulator stages stay submitted; new obligations evaluated under the incident's pinned rule package; impact-tolerance timers resume. (p.25)
- **MPS-8A.19** `BE` Raising severity to SEV1 opens the war room, prompts regulator classification, applies the type's SEV1 automations. (p.25)
- **MPS-8A.20** `BE` Metric timestamps: impact started, detected, declared, acknowledged, mitigated, resolved, closed; MTTR = impact started → resolved by default, defined once in the metric catalogue. (p.25)
- **MPS-8A.21** `BE` Types may rename states or add sub-states but cannot remove regulator-relevant transitions or their timestamps. (p.25)
- **MPS-8A.22** `BE` Ph0 Every transition validated on the server, audited, behaves identically in web app, API and chat. (p.24, p.26)
- **MPS-8A.23** `BE` Ph0 model / Ph3 full Visibility modes: Workspace (everyone with workspace access); Restricted group (named teams/roles); Invite only (named people); Confidential/legal hold (invite only + exports locked + retention held). (p.25)
- **MPS-8A.24** `BE` Restriction applies to search, lists, API, notifications, webhooks, chat channels, exports, analytics, AI retrieval; someone without access cannot learn the incident exists. (p.25)
- **MPS-8A.25** `BE` Notifications to non-members never carry title or details; chat channels for restricted incidents are created private. (p.26)
- **MPS-8A.26** `BE` Incident memory never retrieves facts from a restricted incident for someone without access. (p.26)
- **MPS-8A.27** `BE` Loosening visibility needs IC + security admin; every access grant, removal and break-glass access audited; break-glass alerts the security team. (p.26)
- **MPS-8A.28** `BE` Ph2 Merge: merged IDs redirect; timelines combine with source labels; regulator clocks keep the earliest start (merge never extends a deadline). (p.26)
- **MPS-8A.29** `BE` Ph2 Split: selected alerts, evidence and tasks move to a new incident linked back. (p.26)
- **MPS-8A.30** `BE` Ph2 Parent/child: major incident holds children per region or business line; parent impact sums children without double-counting. (p.26)
- **MPS-8A.31** `BE` Ph2 Links: duplicate of, caused by, related to, recurrence of; shown in timelines and reports. (p.26)
- **MPS-8A.32** `BE` Acceptance: admins create a type with conditional and stage-required fields without code; changes versioned and audited; old incidents keep their version. (p.26)
- **MPS-8A.33** `BE` Acceptance: every transition server-validated, audited, identical via UI/API/chat and covered by tests; reopening preserves timeline and shows which clocks resume. (p.26)
- **MPS-8A.34** `BE` Acceptance: unauthorised user cannot discover a restricted incident's title, metadata, evidence or existence via search, API or notifications; AI retrieval never crosses the boundary. (p.26)
- **MPS-8A.35** `BE` Acceptance: merging preserves original IDs and audit histories; reports separate parent and child impact. (p.26)

## §9 Module: Investigate — AI Brain (p.26–30)
- **MPS-9.01** `BE` Ph1 Brain plans, gathers evidence in parallel, ranks causes, tries to prove itself wrong before speaking; read-only tools only; works inside time and cost budgets; says "not sure yet" rather than guess. (p.26)
- **MPS-9.02** `BE` Loop (diagram p.27): incident opened → scope & plan → gather evidence in parallel → rank → try to disprove → confident? (no & time left → gather again; no & budget spent → report what it knows; yes → explain cause & suggest action) → learn from human verdict. Every claim links to supporting evidence.
- **MPS-9.03** `BE` Seven read-only evidence tools: metrics/logs/traces; K8s & cloud events; deploys & config changes; provider status pages; runbooks & documents; similar past incidents; business metrics. (p.27)
- **MPS-9.04** `BE` Scope & plan reads incident, affected services, dependency map, last 2 h of changes; writes a short plan shown to humans and editable mid-investigation. (p.27)
- **MPS-9.05** `BE` Every query and result is saved to the evidence ledger with timestamps. (p.27)
- **MPS-9.06** `BE` Ranking scores evidence fit, time proximity to a change, historical frequency for this service; shows top three with confidence, not one answer. (p.28)
- **MPS-9.07** `BE` Separate checker step seeks counter-evidence; causes failing the check drop with the reason shown. (p.28)
- **MPS-9.08** `BE` Confidence calibrated against Replay; below the customer's threshold the Brain gathers more or reports what it knows. (p.28)
- **MPS-9.09** `BE` Plain-language summary (what broke, impact, cause, evidence, suggested action and risk); every sentence links to evidence; suggested actions go to the policy engine, never straight to production. (p.28)
- **MPS-9.10** `BE` Learn: capture human verdict, real root cause and fix that worked; improves retrieval/ranking for this customer; customer data never used to train shared models. (p.28)
- **MPS-9.11** `BE` Budgets (customer-adjustable): first hypothesis < 3 min; deep investigation < 15 min; AI spend capped per severity with alerts at 80%; concurrency grouped by incident, not alert. (p.28)
- **MPS-9.12** `BE` Model routing: fast model for triage/summaries, stronger model for hard reasoning; customer chooses provider and region or local open-weight model; gateway allows swap without code change; Replay decides model per customer. (p.28–29)
- **MPS-9.13** `BE` Safety: no write tools, ever — actions are proposals to the policy engine. (p.29)
- **MPS-9.14** `BE` Safety: telemetry quarantined as data; instructions in logs/alerts neutralised and flagged suspicious (OWASP LLM01). (p.29)
- **MPS-9.15** `BE` Safety: personal data redacted before any model call per connector data policy. (p.29)
- **MPS-9.16** `BE` Safety: output must match a strict schema; malformed or unsupported claims rejected and retried. (p.29)
- **MPS-9.17** `BE` Safety: every model call records model, version, prompt template version, input hash, output hash in the evidence ledger. (p.29)
- **MPS-9.18** `BE` Ph1 Model allow-list per workspace (providers, models, regions); anything else refused at the gateway. (p.29)
- **MPS-9.19** `BE` Pinning of an exact model version or approved family; moving outside the pin needs customer approval. (p.29)
- **MPS-9.20** `BE` Ph1 Routes: each step type (triage, deep reasoning, summaries) has a primary and optional fallback route; both satisfy allow-list and residency. (p.29)
- **MPS-9.21** `BE` Ph1 No-external-fallback workspace setting: fallback only to a local model or evidence-only mode, never another external provider. (p.29)
- **MPS-9.22** `BE` Provider outage: after repeated failures/timeouts the route pauses; evidence gathering continues; incident shows "AI reasoning paused: provider unavailable" with raw evidence and runbooks; resumes automatically. (p.30)
- **MPS-9.23** `BE` Ph1 Release gate: any material change (model, prompt template, retrieval) must pass Replay with no drop beyond agreed tolerance in accuracy or calibration. (p.30)
- **MPS-9.24** `BE` `OPS` Staged rollout internal → opted-in → everyone; shadow scoring watches live results and rolls back on regression. (p.30)
- **MPS-9.25** `BE` Regulated workspaces: model or prompt change waits for customer approval shown with Replay results. (p.30)
- **MPS-9.26** `BE` Ph4 Deprecation: provider retirement notices tracked; customers get a migration plan ≥ 90 days ahead where provider allows. (p.30)
- **MPS-9.27** `BE` Change history: customers see which model and prompt versions were active in their workspace, and when. (p.30)
- **MPS-9.28** `BE` Acceptance: regulated customer can pin a model or family; every route change audited; fallback never breaks residency; Replay gates material changes. (p.30)

## §10 Module: Act — autonomy ladder and approval gates (p.30–36)
- **MPS-10.01** `BE` Ph2 Customers decide per action and per service how much Relyxus may do; nothing automatic until the customer says so. (p.30)
- **MPS-10.02** `BE` Autonomy levels: L0 Observe (diagnoses only); L1 Suggest (exact command + expected effect, human runs it); L2 One-click approval (one named approver); L3 Four-eyes (two approvers from different roles; proposer cannot approve); L4 Automatic within policy limits (notifies, rolls back if verification fails). (p.30–31)
- **MPS-10.03** `BE` Action lifecycle (diagram p.31): Action proposed → Policy check → {Blocked by policy | Waiting for approvers | Allowed automatically}; Waiting → {Rejected or expired | approved → Dry run & pre-checks}; Allowed automatically → Dry run & pre-checks; → Executing → Verifying the fix → {Succeeded and closed | Rolled back, escalated}. Kill switch can cancel any state; every transition audited. Caption: "11 states, 1 policy decision". — see Q-10
- **MPS-10.04** `BE` Gate policy parts: Scope (actions × targets), Who (approvers; never the proposer), When (hours, freezes), Conditions (e.g. confidence ≥ 85%, severity, no concurrent action on service), Limits (pods %, runs/hour, never all regions), Requirements (change record, justification, fresh MFA), On timeout (escalate; never auto-approve L3), Verification (metric/threshold/window else rollback & page). (p.32)
- **MPS-10.05** `BE` Policies are stored and editable in the UI or as code (YAML example `restart-payments-workers`). (p.32–33)
- **MPS-10.06** `BE` Ph4 Earned autonomy: propose one-level promotion only after ≥ 20 executions of the same action on the same service class, ≥ 95% verified success, no rollbacks in last 30 days; an admin must accept. (p.33)
- **MPS-10.07** `BE` Any failed verification or rollback drops the action one level immediately and notifies the policy owner. (p.33)
- **MPS-10.08** `BE` Every promotion and demotion recorded with its evidence. (p.33)
- **MPS-10.09** `BE` Built-in actions (all through same gates) and default maximum levels: Kubernetes — rollout restart, scale replicas (L4), roll back deployment via Argo CD/Helm (L3), pause rollout, cordon node; Servers — restart service, clear allow-listed temp paths, rotate logs (L4); Cloud — restart instance, change ASG, fail over LB target (L3); Application — feature flag, rate limit (L3); Data — DB failover, restore backup (L1 only, humans run); Network — DNS/traffic failover (L3 + mandatory freeze check). (p.33)
- **MPS-10.10** `BE` Safety on every action: short-lived narrowly-scoped per-action credentials; one-action-per-target lock; pre-checks; blast-radius calculator; global admin kill switch; automatic rollback on failed verification; before/after snapshots in evidence ledger. (p.33)
- **MPS-10.11** `BE` Ph2 Approver resolvers: named user; group/role; service owner (from catalogue); on-call schedule (who is on call now); manager chain (from directory); external change record (approval in ServiceNow). (p.34)
- **MPS-10.12** `BE` Quorum and order: parallel (any N of M) or sequential stages. (p.34)
- **MPS-10.13** `BE` Approval valid for a set time (default 15 min); void on expiry or if policy, target or proposed command changes before execution. (p.34)
- **MPS-10.14** `BE` Delegation with scope and end date; out-of-office (manual or connected calendar) hands requests to configured backup; delegates must be eligible; all audited. (p.34)
- **MPS-10.15** `BE` No eligible approver → escalate to policy's fallback resolver; if nobody eligible the action stays blocked; L3 never auto-approved. (p.34)
- **MPS-10.16** `BE` No self-approval: proposer and their delegates excluded; one person holding two required roles counts once. (p.34)
- **MPS-10.17** `BE` Each approver recorded with the reason they were eligible (e.g. "on call for database-primary at 03:12"). (p.34)
- **MPS-10.18** `BE` Ph2 Policy precedence (high→low): global kill switch & org security denials; org; workspace; environment; service; action; incident-type defaults. Evaluation deterministic, fails closed. (p.35)
- **MPS-10.19** `BE` Deny wins at any level; strictest value wins (lowest autonomy, smallest blast radius, lowest rate limit, shortest validity). (p.35)
- **MPS-10.20** `BE` Approvals add up (every required approver from every applicable policy, highest quorum); time windows intersect; freeze calendars combine. (p.35)
- **MPS-10.21** `BE` Unresolvable conflict blocks the action with an explanation naming the conflicting policies. (p.35)
- **MPS-10.22** `BE` Effective policy view before any execution and in the simulator: single effective policy with every constraint traced to source policy and version. (p.35)
- **MPS-10.23** `BE` Emergency policy may loosen limits during a SEV1 only if two authorised people activate it; auto-expires within 4 h; fully audited. (p.35)
- **MPS-10.24** `BE` Ph2 Playbook runtime records playbook version, inputs, and each step state: Pending, Running, Succeeded, Failed, Skipped (reason), Waiting for approval, Waiting for manual checkpoint, Rolled back. (p.35)
- **MPS-10.25** `BE` Each step keeps inputs/outputs (sensitive values redacted), retries, timeout and any rollback; resume from a failed step only if marked resumable and policy is re-checked at resume; all step data to evidence ledger and audit log. (p.35)
- **MPS-10.26** `BE` Ph5 Policy recommendation assistant: suggests removing unused, fixing conflicting/redundant rules, tightening rarely used permissions; never publishes changes itself; shows evidence; needs authorised approval. (p.35)
- **MPS-10.27** `BE` Acceptance: "DB failover needs VP Eng + DB on-call" configurable without code; simulator shows who would be asked for a sample incident; runtime records each approver and eligibility. (p.35)
- **MPS-10.28** `BE` Acceptance: one effective policy shown per proposed action with traced constraints; conflicts fail closed; no approval usable after expiry or policy/target change; operator can explain a playbook failure and resume only permitted steps. (p.36)

## §11 Module: Communicate, collaborate, on-call (p.36–39)
- **MPS-11.01** `BE` Ph1 Incident channel: Slack or Teams channel per SEV1/SEV2 incident; invites owners; name/members per customer templates; bot posts live summary card. (p.36)
- **MPS-11.02** `BE` Ph1 Live summary card (what broke, impact, likely cause, actions, clocks) updates in place. (p.36)
- **MPS-11.03** `BE` Ph2 Approve/reject actions from Slack/Teams buttons; MFA re-confirmation when policy demands. (p.36)
- **MPS-11.04** `BE` Ph1 Incident roles (IC, communications lead, scribe) assigned by policy or single command; shown in header. (p.36)
- **MPS-11.05** `BE` Ph2 Stakeholder update drafts for executives, support, customers on a timer (default every 30 min for SEV1); human approves before sending. (p.36)
- **MPS-11.06** `BE` Ph3 Status-page drafts in plain language, no internal detail; publish to Statuspage, Better Stack or own page. (p.36)
- **MPS-11.07** `BE` Ph1 Escalation chase responder → lead → executive; default 10, 20, 30 min; stops on acknowledgement. (p.36)
- **MPS-11.08** `BE` Ph1 Paging integration with PagerDuty/Opsgenie; escalation state synced both ways. (p.37)
- **MPS-11.09** `BE` Ph3 On-call lite (native): schedules, overrides, follow-the-sun, SMS, voice, mobile push; Opsgenie schedule import. (p.37)
- **MPS-11.10** `UI` `BE` Ph2 Mobile approvals: approve/reject/acknowledge from phone; installable web app first; biometric re-confirmation. (p.37)
- **MPS-11.11** `BE` Ph3 Bilingual English/Arabic drafts side by side; default language per audience. (p.37)
- **MPS-11.12** `UI` Ph3 Executive view: impact, money at risk, time to tolerance breach, next update time; read-only. (p.37)
- **MPS-11.13** `BE` Every Relyxus-written message states what is known, what is not, and when the next update comes; never guesses a cause in a customer-facing message; never sends to customers or regulators without human approval. (p.37)
- **MPS-11.14** `BE` Ph1 Live tasks are first-class and separate from follow-ups: title, single owner (unassigned highlighted), priority. (p.37)
- **MPS-11.15** `BE` Task status Open, In progress, Blocked, Done, Cancelled (with reason). (p.37)
- **MPS-11.16** `BE` Task due/ETA; overdue alerts owner and IC. (p.37)
- **MPS-11.17** `BE` Task dependencies on another task, an approval or an action. (p.37)
- **MPS-11.18** `BE` Task links to evidence, actions, approvals, runbook steps. (p.38)
- **MPS-11.19** `BE` Task source: manual, type template, playbook, workflow, or AI suggestion (human must accept). (p.38)
- **MPS-11.20** `BE` Tasks created/assigned/completed from web, chat and mobile; every change on the timeline. (p.38)
- **MPS-11.21** `BE` At resolution open tasks offered as follow-ups or cancelled with reason. (p.38)
- **MPS-11.22** `BE` Task visibility always follows incident visibility. (p.38)
- **MPS-11.23** `BE` Ph2 Commander handoff builds a package: summary, open tasks, pending approvals, active clocks/deadlines, risks & unknowns, next update time. (p.38)
- **MPS-11.24** `BE` Incoming commander must acknowledge; pending approvals and clocks due within 1 h must be acknowledged or explicitly deferred with reason; outgoing/incoming and time recorded on timeline; same for comms lead and other roles. (p.38)
- **MPS-11.25** `BE` Ph3 Coverage checks flag uncovered hours, overlaps, time-zone/DST shifts, leave conflicts (calendar/HR connected); schedule owners warned 72 h before a gap. (p.38)
- **MPS-11.26** `BE` Overrides carry owner, reason, expiry and auto-expire; swaps need both people to confirm; delegation follows §10 approval rules; effective-schedule preview incl. overrides. (p.38)
- **MPS-11.27** `BE` Ph3 Status page: components map to business services, grouped by product/region; pages public, sign-in only or partner-only. (p.38)
- **MPS-11.28** `BE` Status subscriptions email, SMS, webhook, RSS with subscriber management and consent records. (p.38)
- **MPS-11.29** `BE` Status post lifecycle Draft → In review → Approved → Published → Updated → Resolved; approval rules by severity and audience (e.g. public SEV1 needs comms lead + legal); rejected drafts kept with reason. (p.38)
- **MPS-11.30** `BE` Author previews exact public text and receiving audience before publishing. (p.38)
- **MPS-11.31** `BE` Scheduled maintenance posts, bilingual templates, full history; Relyxus is source of truth for posts it publishes when synced to Statuspage/Better Stack. (p.39)
- **MPS-11.32** `BE` Acceptance: IC sees all live tasks/owners; tasks work from web and chat; every change on timeline; unresolved tasks become follow-ups; handoff records both commanders + timeline event with acknowledgement/deferral; coverage-gap warnings; overrides show owner/reason/expiry; comms lead previews exact content and audience; approval rules from policy; rejected drafts auditable. (p.39)

## §11A Notifications (p.39–41)
- **MPS-11A.01** `BE` Ph1 basic (chat, email) / Ph3 full Notification rule: trigger (event), conditions, recipients (resolved like approvers), channels (push, SMS, voice, email, Slack/Teams, webhook), renotify (e.g. every 5 min up to 3), escalation (hand to escalation policy). (p.39–40)
- **MPS-11A.02** `BE` Rule example supports per-recipient class and `only_if` conditions (e.g. regulator_clock_started). (p.40)
- **MPS-11A.03** `BE` Classes: Critical page (SEV1/2 pages, approvals about to expire, clocks past 75%) overrides quiet hours when org policy says so within local legal limits; Action needed (approval requests, task assignments, report sign-offs) respects quiet hours unless escalated to critical; Informational (stakeholder updates, summaries, weekly reports) respects quiet hours, can be a digest. (p.40)
- **MPS-11A.04** `BE` Ph3 Personal preferences: channel order per class with delays, quiet hours, language, time zone; phone/email verified before use; "Send test" checks every channel and records result. (p.40)
- **MPS-11A.05** `BE` Ph3 Delivery tracking per attempt: rule, recipient, channel, provider message ID, status (queued, sent, delivered, failed, acknowledged), time taken; failed channel falls through to the next; admins see failures in one place. (p.40)
- **MPS-11A.06** `BE` Restricted incidents: notify only permitted people with no title/detail beyond "A restricted incident needs your attention". (p.40)
- **MPS-11A.07** `BE` Ph5 Notification analytics (ack times, missed pages, noisy rules, after-hours load, channel reliability) aggregated without exposing sensitive incident content. (p.41)
- **MPS-11A.08** `BE` Acceptance: "SEV1 payments → payments on-call + Head of SRE + compliance if a clock starts" defined without code; users test every channel; critical overrides quiet hours only as policy allows; every delivery attempt visible with status and timing. (p.41)

## §12 Module: Comply — Regulator & Resilience Pack (p.41–44)
- **MPS-12.01** `BE` Rule library at launch: EU DORA major ICT incident (initial 4 h from classification, max 24 h from awareness; intermediate 72 h; final 1 month). (p.41)
- **MPS-12.02** `BE` UK FCA/PRA operational incident reporting: new unified rules from 18 March 2027; templates shipped before then. (p.41)
- **MPS-12.03** `BE` Singapore MAS TRM: notify within 1 h of discovery; root-cause report within 14 days. (p.41)
- **MPS-12.04** `BE` Australia APRA CPS 230: material incident within 72 h; disruption outside tolerance within 24 h. (p.41)
- **MPS-12.05** `BE` USA NYDFS 500.17: cybersecurity incident within 72 h; extortion payment within 24 h. (p.41)
- **MPS-12.06** `BE` India CERT-In: specified cyber incidents within 6 h. (p.41)
- **MPS-12.07** `BE` Saudi Arabia, UAE, Pakistan (SAMA, central bank, SBP): customer-configured clocks and templates, validated with local counsel before launch. (p.42)
- **MPS-12.08** `BE` Ph3 Classification assistant checks incident against jurisdiction's major-incident criteria; suggests with reasons; a named compliance officer confirms; confirmation time starts the clock. (p.42)
- **MPS-12.09** `BE` Ph3 Live clocks on incident header and compliance centre; warnings at 50%, 75%, 90%; escalate to compliance owner. (p.42)
- **MPS-12.10** `BE` Ph3 Drafted reports fill regulator fields from incident record and evidence; every field shows its source; empty fields highlighted, never invented. (p.42)
- **MPS-12.11** `BE` Ph3 Approval & submission log: compliance signs off; export PDF and structured data; record when/how submitted; version history of every draft; v1 never auto-submits. (p.42)
- **MPS-12.12** `BE` Ph3 Impact-tolerance tracker: maps services to important business services/critical operations with tolerances; live time-to-breach; breach starts the relevant clock (e.g. APRA 24 h). (p.42)
- **MPS-12.13** `BE` Ph3 Downtime budget: unplanned downtime per critical system vs yearly limit (MAS 4 h in 12 months). (p.42)
- **MPS-12.14** `BE` Ph4 Third-party & concentration map: vendors and cloud regions per important service; feeds DORA registers and UK third-party reporting; highlights single points of failure. (p.43)
- **MPS-12.15** `BE` Ph4 Resilience Drill mode: replays past incidents as rehearsals; evidence pack for scenario testing and recovery-time validation. (p.43)
- **MPS-12.16** `BE` Ph3 Evidence pack export: timeline, evidence, approvals, model calls, report versions in one bundle, all hash-verified. (p.43)
- **MPS-12.17** `BE` Guardrail: classification and submission always need a named person. (p.43)
- **MPS-12.18** `BE` Ph3 (versions Ph0) Rule package records: jurisdiction/regulator/rule; version and effective dates; source citations; clocks & classification criteria; report templates & field mappings; review owner & validation status (Draft → Counsel-reviewed → Customer-validated, with dates); migration notes. (p.43)
- **MPS-12.19** `BE` Each workspace activates the packages it needs; customer stricter internal deadlines are a separate override layer that can never loosen a regulator deadline. (p.43)
- **MPS-12.20** `BE` Pinning: classification stores the package version in force; reports pinned too; new versions never rewrite past deadlines or submitted reports; moving an open incident to a newer version needs a compliance officer's explicit audited decision. (p.44)
- **MPS-12.21** `BE` `OPS` Distribution: Apporine publishes packages as signed updates with change notes (offline bundles for air-gap); customers review and activate. (p.44)
- **MPS-12.22** `BE` Every clock and report shows its package, version, sources and validation status. (p.44)
- **MPS-12.23** `BE` `OPS` Each package ships scenario tests (facts → expected classification and deadlines) run on every release. (p.44)
- **MPS-12.24** `BE` Acceptance: auditor sees which package version governed an incident with sources and effective date; new version never silently rewrites historical deadlines or reports. (p.44)

## §13 Module: Learn and prove (p.44–46)
- **MPS-13.01** `BE` Ph1 Incident Replay: re-runs the Brain on past incidents using only data that existed at the time; time-fenced queries; known root cause hidden until scoring. (p.44)
- **MPS-13.02** `BE` Ph1 Shadow mode: runs silently on live incidents, posts to a private channel, scored later against human root cause; zero production risk. (p.44)
- **MPS-13.03** `BE` Ph1 Accuracy scorecard: correct-first rate, top-three rate, time to first hypothesis, by incident type, with calibration chart. (p.44)
- **MPS-13.04** `BE` Ph1 Root-cause capture at closing: one-click from Brain's top three or free text; required for SEV1 and SEV2. (p.44)
- **MPS-13.05** `BE` Ph1 Incident memory: similar past incidents and fixes by symptoms, service, change; shown in the first 60 s. (p.44)
- **MPS-13.06** `BE` Ph2 Post-mortem generator: blameless draft from timeline and evidence; sections summary, impact, timeline, cause, went well/badly, actions; actions become tickets. (p.45)
- **MPS-13.07** `BE` Ph2 Action-item tracker: overdue items reminded weekly; recurring causes flagged. (p.45)
- **MPS-13.08** `BE` Ph2 Recurrence detector links same-root-cause incidents ("4 times in 60 days"). (p.45)
- **MPS-13.09** `BE` Ph5 Runbook compiler: imports from Confluence, Notion, SharePoint, Markdown; each step becomes a read check or gated action; human review before activation. (p.45)
- **MPS-13.10** `BE` Ph2 Reliability report weekly and quarterly: MTTR trend, top causes, toil hours saved, autonomy coverage, accuracy trend. (p.45)
- **MPS-13.11** `BE` Replay sales flow: connect read-only sources, pick 30–50 past incidents with known causes, run overnight, scorecard shows correct-first, top-three, minutes saved, every miss explained. (p.45)
- **MPS-13.12** `BE` Ph3 Post-incident review states Draft → In review → Approved → Published → Closed. (p.45)
- **MPS-13.13** `BE` Required reviewers by severity/type (default SEV1: IC, service owner, Head of SRE, + compliance officer if a clock started; security events add CISO). (p.45)
- **MPS-13.14** `BE` Due dates configurable (default SEV1: draft 5 business days, approval 10); overdue escalates to review owner's manager. (p.45)
- **MPS-13.15** `BE` Redaction: sections internal-only; wider audiences get redacted version; customer data and security details redacted by default. (p.45)
- **MPS-13.16** `BE` Lessons learned required for SEV1 and SEV2. (p.45)
- **MPS-13.17** `BE` Closure gate: SEV1/SEV2 cannot be Closed until required reviewers sign off and every mandatory follow-up has owner and due date, unless an authorised exception with reason is recorded; mandatory follow-ups tracked with reminders. (p.45–46)
- **MPS-13.18** `BE` Ph3 Metric catalogue: every metric (MTTR, time to acknowledge, incident count, time to first hypothesis, diagnosis accuracy, toil saved, autonomy coverage, AI spend, downtime vs tolerance) has one definition — formula, timestamps, filters, owner, version; dashboards/reports use catalogue metrics only. (p.46)
- **MPS-13.19** `BE` Custom dashboards per workspace or business service: saved filters, drill-through, scheduled email/PDF delivery, role-based export permissions; every export logged. (p.46)
- **MPS-13.20** `BE` Analytics exclude restricted incidents unless viewer has access; breakdowns that would reveal a single restricted incident are suppressed. (p.46)
- **MPS-13.21** `BE` Ph5 Cross-incident knowledge graph, permission-aware; every recommendation traces to concrete incidents/evidence; restricted facts never leak. (p.46)
- **MPS-13.22** `BE` Acceptance: SEV1 cannot be review-complete without required sign-offs or authorised exception; one metric definition everywhere; restricted incidents excluded unless authorised. (p.46)

## §14 Module: Govern (p.46–48)
- **MPS-14.01** `BE` Structure: Organisation → Workspaces (business units/regions, each with its own data residency) → Teams → Services; user can be in several teams; permissions follow team and workspace. (p.46) — see Q-18
- **MPS-14.02** `BE` Built-in roles (custom roles derivable): Owner — everything incl. billing & deleting org / cannot approve own proposals. Admin — users, teams, connectors, settings / cannot change security settings without a security admin. (p.46)
- **MPS-14.03** `BE` Security admin — SSO, keys, data policies, enable write access, kill switch / cannot approve production actions alone. (p.47)
- **MPS-14.04** `BE` Compliance officer — classify incidents, approve reports, manage clocks / cannot change connectors or policies. (p.47)
- **MPS-14.05** `BE` Policy owner — create/edit gate policies for their services / cannot approve changes to own policies (needs second policy owner). (p.47)
- **MPS-14.06** `BE` Incident commander — run incidents, assign roles, approve L2 in scope / cannot approve L3 alone. (p.47)
- **MPS-14.07** `BE` Responder — investigate, propose actions, approve within policy / cannot edit policies. (p.47)
- **MPS-14.08** `BE` Viewer — read incidents and reports in their workspaces / nothing that changes state. (p.47)
- **MPS-14.09** `BE` Auditor — read everything incl. audit log and evidence for a set period / nothing that changes state. (p.47)
- **MPS-14.10** `BE` Ph3 SSO SAML & OIDC (Entra ID, Okta, Google, Ping, others); can enforce SSO-only. (p.47)
- **MPS-14.11** `BE` Ph3 SCIM: joiners and leavers synced within minutes. (p.47)
- **MPS-14.12** `BE` Ph2 MFA re-confirmation for approvals, key changes, enabling write access. (p.47)
- **MPS-14.13** `BE` Ph2 SoD: proposer never approves; policy edits need a second policy owner. (p.47)
- **MPS-14.14** `BE` Ph3 JIT elevation with reason and expiry (default 4 h), fully logged. (p.47)
- **MPS-14.15** `BE` Ph3 Break-glass accounts alert the security team the moment used. (p.47)
- **MPS-14.16** `BE` Ph2 Tamper-evident audit log: every login, sensitive-evidence view, change, approval and model call; each entry hash-chained to the previous. (p.47)
- **MPS-14.17** `BE` Ph3 SIEM streaming to Splunk, Sentinel, QRadar or any syslog/HTTP endpoint. (p.48)
- **MPS-14.18** `BE` Ph3 Retention per workspace; defaults satisfy strictest common rule (e.g. 180-day log retention in India). (p.48)
- **MPS-14.19** `BE` Ph3 IP allow-lists for console; idle and absolute session timeouts. (p.48)
- **MPS-14.20** `BE` Ph1 Scoped API tokens: least privilege, expiry dates, last-used tracking. (p.48)
- **MPS-14.21** `BE` Ph2 Usage and AI-spend dashboard: tokens and cost per incident, team, month; budget alerts. (p.48)
- **MPS-14.22** `BE` Ph3 Incident visibility management (4 modes; loosening needs IC + security admin). (p.48) ≡ MPS-8A.27
- **MPS-14.23** `BE` Ph3 Personal preferences: language, date format, week start, number & currency format, time zone, theme (System/Light/Dark), notification preferences; per user with workspace defaults. (p.48)
- **MPS-14.24** `BE` Ph1 Machine-safe values: stored timestamps UTC ISO 8601; money integer amount + ISO 4217 currency regardless of display locale. (p.48)
- **MPS-14.25** `BE` Ph3 Customer-controlled support access (approval, time limits, full audit). (p.48) ≡ MPS-17.12
- **MPS-14.26** `BE` Ph2 Permission-aware global search filtered by role and visibility before ranking. (p.48) ≡ MPS-15.05

## §14A Configuration as code (p.49–50)
- **MPS-14A.01** `BE` Ph3 Managed as code (non-secret only): teams & membership mappings, services & dependencies, business services & impact models, connectors (secret references only), policies & approval resolvers, escalation chains & schedules, notification rules, incident types/fields/forms, status-page components, rule-package activations & overrides, workspace settings (retention, residency, model allow-list). (p.49)
- **MPS-14A.02** `BE` Ph0 Stable identity: every object has an immutable ID and a human-readable key; imports match on key with a documented key→ID mapping. (p.49)
- **MPS-14A.03** `BE` Ph3 Export/import a whole workspace as YAML or JSON. (p.49)
- **MPS-14A.04** `BE` `OPS` Ph3/4 Terraform provider and CLI `relyxus config plan|apply|diff`; plan lists every create/update/delete; deletions need an explicit flag and an approver. (p.49) — see Q-28
- **MPS-14A.05** `BE` Ph3 Environment promotion staging → production via plan/apply; production policy changes still need policy-owner approval. (p.49)
- **MPS-14A.06** `BE` Ph3 Nightly drift detection vs last applied version → drift report; objects lockable as "managed by code" (UI edits blocked) or open with drift warning. (p.49)
- **MPS-14A.07** `BE` Ph0 Every change from UI, API or Terraform creates a configuration version recording who, when, source, exact difference; non-destructive changes can be rolled back to any earlier version. (p.49)
- **MPS-14A.08** `BE` `OPS` Configuration exports included in backups so a workspace can be rebuilt from code. (p.49)
- **MPS-14A.09** `BE` Ph3 Change touching > 25 objects (configurable) shows a preview: difference, count, examples, dry run where possible. (p.49)
- **MPS-14A.10** `BE` Bulk selection works with filters; sensitive settings (security, residency, retention, policies) require a reason. (p.49)
- **MPS-14A.11** `BE` Reversible changes get a 10-minute undo window; irreversible actions (final deletion after soft-delete, key destruction) sit in a danger zone with typed confirmation and a second admin. (p.49)
- **MPS-14A.12** `BE` Ph5 Workspace templates: versioned bundles of roles, types, forms, policies, notification rules, report settings, with drift comparison. (p.50)
- **MPS-14A.13** `BE` Acceptance: recreate a workspace's non-secret config elsewhere, review a plan, block destructive drift, keep stable IDs or documented mapping; changes affecting hundreds of objects cannot run without showing scope; irreversible actions clearly separated. (p.50)

## §15 Screens and UX (p.50–55)
- **MPS-15.01** `UI` UI/UX Enterprise Specification governs layouts, component behaviour and states (empty, loading, error, degraded, permission-denied, read-only, mobile); on product logic MPS wins, on layout/interaction UI/UX spec wins. (p.50)
- **MPS-15.02** `UI` `BE` Page inventory (each must exist with its key elements and "must handle" behaviour): Sign-in (SSO button, email sign-in for small teams, workspace picker; expired session returns to same page); Onboarding wizard (create org → connect source → confirm services → invite team → first Replay; progress, skip/resume, partial completion saved, first value < 30 min); Command centre (open incidents by severity, pending approvals, clocks, services at risk, connector health; "All clear" with 24 h summary); Incident list (filters severity/service/status/team/date, saved views, bulk actions; thousands of rows, live updates); War room (header severity/status/impact/money/clocks; timeline; AI findings with evidence; actions & approvals; chat bridge; Acknowledge, Assign roles, Approve, Reject, Escalate, Declare resolved; updates within 1 s, never reorders what user reads); Evidence explorer (graph, raw query/result, "open in Grafana", ruled-out causes; large logs paginated; sensitive fields masked); Approvals inbox (risk, blast radius, effect, rollback plan; Approve/Reject/Ask question; MFA re-confirm; expiry countdown). (p.50–51)
- **MPS-15.03** `UI` `BE` Pages cont.: Service catalogue & dependency map (owners, SLOs, graph, regions, vendors; 1,000+ services readable); Business services & tolerances (changes need policy-owner approval); Integrations hub; Policies & autonomy (visual + code view, simulator "last 30 days", version history, promotion proposals; unsaved-change warning, diff before publish); Runbooks & playbooks (import, edit, dry-run test, link services; review before activation); Replay & accuracy (progress + ETA); Reports (drafts, approvals, versions, PDF/structured export; locked once submitted, amendments new versions); Compliance centre (clocks, deadlines, third-party map, drills; read-only for auditors); On-call & escalation (calendar, overrides, escalation editor, Opsgenie import; time zones explicit); Analytics (CSV export, scheduled email); Audit log (search/filter, hash-verification status, export, SIEM stream status; millions of entries, fast search); Settings (users, teams, roles, SSO, SCIM, keys, data policies, AI model/region, retention, API tokens, licence; dangerous settings need typed confirmation + second admin); Mobile approval view (summary, Approve/Reject/Acknowledge, call commander; slow networks; biometric). (p.52–53)
- **MPS-15.04** `UI` `BE` v2.0 pages: Declare incident (type first, title, services, suggested severity, impact, visibility, conditional fields, similar-incident warning, Declare / Save draft; required-field checks per type; trained user declares < 60 s); Incident tasks; Notification rules (list, editor, test-send, delivery log; handle rules reaching restricted incidents); Incident types & fields (changes never alter past incidents); Rule packages (unvalidated packages clearly marked); Configuration (export/import, plan, drift, history, rollback; "managed by code" locks); Platform operations self-hosted (health, versions, upgrade plan, backup/restore status, diagnostics; failed preflight, upgrade in progress, licence grace); Support access (request, approve, sessions, revoke, log; immediate revocation); Trust centre external (current docs, NDA-gated, subscriptions; expired marked). (p.53–54)
- **MPS-15.05** `UI` UX standards: first load < 1.5 s; click/keypress response < 100 ms; live updates < 1 s; progress text within 2 s, never a bare spinner; command palette Ctrl/Cmd+K + shortcuts; WCAG 2.2 AA; English + Arabic RTL; timestamps in viewer's time zone with one-click UTC; theme System/Light/Dark, org may default war room to Dark, severity never by colour alone; errors in plain language with next step and support reference ID; destructive actions typed confirmation, undo, second approver where policy requires; degraded-mode banner when Relyxus itself has a problem. (p.54–55)
- **MPS-15.06** `BE` Ph1 Global search covers incidents, evidence, services, people, policies, runbooks, reports, audit events; grouped by type; recent first. (p.55)
- **MPS-15.07** `BE` Permissions applied before ranking: a restricted incident never appears, not even as a count or title fragment. (p.55)
- **MPS-15.08** `UI` `BE` Command palette runs declare incident, open approvals, jump to service, switch workspace, start playbook (still policy-gated); everything works by keyboard alone. (p.55)
- **MPS-15.09** `UI` Ph5 Personalised command centre: role-based widget presets; admins lock mandatory widgets. (p.55)
- **MPS-15.10** `BE` `UI` Acceptance: responder finds an incident, service, policy or runbook from anywhere in two interactions; results respect roles and visibility; full keyboard use. (p.55)

## §16 Integrations catalogue (p.56–58)
- **MPS-16.01** `BE` ~70 connectors across 14 categories by end of Phase 5; every connector follows the §7 pattern. (p.56)
- **MPS-16.02** `BE` Ph0–1 connectors: Prometheus, VictoriaMetrics, Thanos, Grafana Mimir; Grafana Loki; OpenTelemetry (OTLP); Alertmanager, Grafana alerting, generic webhooks; vanilla K8s, EKS, AKS, GKE; Linux via Edge Agent; GitHub; Slack; Jira; PagerDuty & Opsgenie sync; Notion, Markdown in Git; Google sign-in; Webhooks, REST API. (p.56–57)
- **MPS-16.03** `BE` Ph2–3 connectors: Datadog, CloudWatch, Azure Monitor, GCP Monitoring; Elasticsearch, OpenSearch, Splunk, CloudWatch Logs, Azure Log Analytics, GCP Logging; Tempo, Jaeger; Datadog monitors, CloudWatch alarms, Azure alerts, PagerDuty, Opsgenie; OpenShift, Rancher, k3s; Windows via Edge Agent; AWS/Azure/GCP resources/health/events; GitLab, Bitbucket, Argo CD, Flux, Jenkins; LaunchDarkly, Unleash; Teams; ServiceNow (incidents & change), Freshservice; native on-call SMS/voice via telecom; Confluence, SharePoint, Google Drive; Okta, Entra ID, Ping, SCIM; MCP client and server. (p.56–57)
- **MPS-16.04** `BE` Ph4–5 connectors: New Relic, Dynatrace, Zabbix, Elastic metrics; Graylog, Sumo Logic; Datadog APM, Dynatrace traces; Zabbix, Nagios, SolarWinds alerts; multi-cluster federation; VMware vSphere; Oracle Cloud, Alibaba, regional Gulf clouds; Spinnaker, Harness, Terraform state; Flagsmith, ConfigCat; Google Chat, Mattermost; BMC Helix, Zendesk; WhatsApp Business for approvals where permitted; Backstage; Splunk/Sentinel/QRadar audit streams; connector SDK and marketplace. (p.56–57)
- **MPS-16.05** `ORG` Connector build order follows incident archaeology, not logo size. (p.57)
- **MPS-16.06** `BE` Ph2 ITSM ownership: incident severity/state/timeline/roles owned by Relyxus, Relyxus → ServiceNow, Relyxus wins and ServiceNow edit overwritten and logged. (p.57)
- **MPS-16.07** `BE` ServiceNow-only fields (assignment group, category): ServiceNow → Relyxus, read-only in Relyxus, ServiceNow wins. (p.57)
- **MPS-16.08** `BE` External change-record approval (when policy uses it): ServiceNow → Relyxus; a revocation in ServiceNow voids the Relyxus approval immediately. (p.57)
- **MPS-16.09** `BE` Action execution result: Relyxus → ServiceNow change record; Relyxus wins. (p.57)
- **MPS-16.10** `BE` Jira follow-up tickets (status, assignee): Jira → Relyxus read-only mirror; Jira wins; Relyxus tracks overdue. (p.58)
- **MPS-16.11** `BE` Comments/work notes: both directions, append-only, labelled by source, never edited across systems. (p.58)
- **MPS-16.12** `BE` Every outbound call carries an idempotency key; inbound webhooks deduplicated by event ID. (p.58)
- **MPS-16.13** `BE` External approval granted before policy/target/command changed is invalid. (p.58)
- **MPS-16.14** `BE` Failed syncs retry with backoff up to 24 h; failures > 15 min alert integration owner and show on the incident. (p.58)
- **MPS-16.15** `BE` Linking stores external ID; unlinking stops sync but keeps history; deleted external record shown as removed, incident carries on. (p.58)
- **MPS-16.16** `BE` Provenance: every synced value shows its origin (e.g. "set in ServiceNow by J. Smith at 10:42"). (p.58)
- **MPS-16.17** `BE` Acceptance: duplicate webhooks never create duplicate state changes; revoked external approval never stays valid; users always see whether state came from Relyxus or external system. (p.58)

## §17 Security architecture (p.58–61)
- **MPS-17.01** `BE` Ph2–3 Identity & access: SSO-only option, SCIM, MFA re-confirmation for approvals, role- and attribute-based access, SoD, JIT elevation, break-glass alerts, session limits, IP allow-lists. (p.58)
- **MPS-17.02** `BE` Ph1–3 Tenant isolation: separate encryption keys per tenant; database row-level security; per-tenant queues and storage paths; dedicated single-tenant option. (p.58)
- **MPS-17.03** `BE` Ph1–3 Data protection: TLS 1.3 in transit; mTLS agent↔platform; AES-256 at rest; customer-managed keys and HSM support; field-level redaction before AI calls; configurable retention and verified deletion. (p.59)
- **MPS-17.04** `BE` `OPS` Ph1–4 Network: agent outbound only, no inbound ports; private connectivity in dedicated mode; egress allow-list; air-gapped with offline update bundles. (p.59)
- **MPS-17.05** `BE` Ph1–2 AI safety: no write tools; telemetry quarantined; prompt-injection detection; strict output schemas; model and prompt versions logged; no training on customer data; zero-data-retention terms where available; per-incident token budgets. (p.59)
- **MPS-17.06** `BE` Ph2 Action safety: policy engine on every action; short-lived per-action credentials from vault; target locks; blast-radius limits; dry runs; automatic rollback; global kill switch. (p.59)
- **MPS-17.07** `OPS` Ph0 Supply chain: signed container images; SBOM per release; dependency and image scanning in CI; reproducible builds; protected branches with mandatory review; secrets scanning. (p.59)
- **MPS-17.08** `BE` `ORG` Ph2–5 Operations & assurance: tamper-evident audit log; SIEM streaming; annual pen test + one per major release; bug bounty after GA; own incident response plan with customer notification commitments; SOC 2 Type II, ISO 27001, ISO 42001 roadmap. (p.59)
- **MPS-17.09** `BE` Threat controls: prompt injection (telemetry is data; no write tools; policy checks every action); stolen approver account (MFA re-confirm, four-eyes, anomaly alerts on approval patterns); over-privileged agent (read/write creds separated, per-action short-lived creds, deny-lists for destructive verbs); data leakage to model providers (gateway enforces region/provider per workspace, redaction, local option); malicious insider (no standing access, customer-approved JIT, full audit); compromised release (signed images, install-time verification, staged rollout, rollback); runaway automation (rate limits per action & target, auto-demotion, kill switch). (p.59–60)
- **MPS-17.10** `BE` Worst outcome is Relyxus causing an outage; §9/10/17 design must make that impossible without a human choosing it. (p.60)
- **MPS-17.11** `BE` No Apporine employee ever has standing access to customer data; support only via sessions the customer approves and can watch. (p.60)
- **MPS-17.12** `BE` Ph3 Support request linked to a ticket naming workspace, data classes (configuration only / metadata / evidence), duration ≤ 4 h (renewable), reason. (p.60)
- **MPS-17.13** `BE` Customer admin approves (or two admins if workspace requires); access off by default for every regulated workspace. (p.60)
- **MPS-17.14** `BE` Session: short-lived credentials limited to approved scope; every action and query logged and visible live; customer can join as observer. (p.60)
- **MPS-17.15** `BE` Customer can end the session instantly; auto-ends at time limit; a session report follows. (p.60)
- **MPS-17.16** `BE` `OPS` Diagnostics bundles strip secrets and are customer-reviewed; self-hosted/air-gapped have no remote path unless the customer opens one. (p.61)
- **MPS-17.17** `BE` Ph3 Residency: primary DB and evidence objects; backups/DR copies; AI model calls (primary and fallback); analytics aggregation (org-wide views aggregate inside each region); notification content (or message carries no incident detail); exports and support sessions — all stay in the workspace's allowed regions. Global metadata (org/workspace names, login identity, licence, billing) may be global and is listed explicitly. (p.61)
- **MPS-17.18** `BE` Every data path declares its region; a configuration that would send restricted data out of bounds is rejected on save with reason, and a runtime check blocks it again before sending. (p.61)
- **MPS-17.19** `BE` "Run residency check" lists every configured data path with region and produces an auditor report; any violation fails. (p.61)
- **MPS-17.20** `BE` Acceptance: no standing production-data access for support; admins see active/recent sessions and revoke instantly; residency check lists every path and fails out-of-region configuration. (p.61)

## §18 Compliance and regulators by country (p.61–64)
- **MPS-18.01** `ORG` Matrix is a starting point for legal review; local counsel confirms before contracts. (p.61)
- **MPS-18.02** `ORG` `BE` EU DORA third-party risk (Art. 28–30): accept DORA contract clauses, support audits, provide exit plan; product supplies exit kit, audit evidence packs, DORA addendum. (p.62)
- **MPS-18.03** `BE` EU AI Act (as amended by Digital Omnibus): build to high-risk standards — logging, human oversight, technical documentation; model-governance pack; human approval by design. (p.62)
- **MPS-18.04** `BE` UK FCA/PRA operational resilience: important business services, impact tolerances, incident and third-party templates. (p.62)
- **MPS-18.05** `BE` UK PRA SS1/23 model risk: model cards, version lineage, Replay accuracy reports detailed enough for validation. (p.62)
- **MPS-18.06** `BE` `ORG` NYDFS 500.17: clocks and drafted notices; Apporine's own notification promise must be fast. (p.62)
- **MPS-18.07** `ORG` SOC 2 expected by enterprise buyers; trust centre with reports. (p.63)
- **MPS-18.08** `BE` Singapore MAS TRM: 1-hour clock, downtime budget tracker, 14-day report template; recovery within 4 h. (p.63)
- **MPS-18.09** `BE` `ORG` Australia APRA CPS 230: tolerance tracker, clocks; CPS 230 clauses in contracts. (p.63)
- **MPS-18.10** `BE` `OPS` India CERT-In: 6-hour clock; ICT logs kept 180 days within India (in-country deployment or log copies); retention settings. (p.63)
- **MPS-18.11** `BE` `OPS` Saudi Arabia SAMA/NCA and UAE Central Bank: data stays in-country; self-hosted or in-Kingdom/UAE deployment with local model. (p.63)
- **MPS-18.12** `OPS` Pakistan SBP cloud-outsourcing framework: self-hosted mode. (p.64)
- **MPS-18.13** `ORG` Certification roadmap: SOC 2 Type I Ph3, Type II after 6-month window; ISO 27001 Ph5; ISO 42001 Ph5 or soon after; CSA STAR Ph4; PCI DSS not planned (avoid storing card data via redaction). (p.64)

## §19 Tier-1 bank questions (p.64–66)
- **MPS-19.01** `ORG` `BE` Answers ready by phase: private cloud Ph3; no internet Ph4; no training on customer data Ph1; own login + SCIM Ph3; AI cannot change prod alone Ph2; respects change process (change record + freeze calendars) Ph2; model-risk validation Ph3; hash-chained audit to SIEM Ph3; customer-managed keys + HSM Ph3; escrow/exit plan Ph3; on-site audit rights Ph3; certifications Ph3–5; own-incident notification within 24 h Ph3; 24/7 support Ph3; published sub-processor list with advance notice (none in self-hosted beyond chosen) Ph3; legacy/mainframe via exported logs/metrics, never direct Ph4; scale tested at 10,000 alerts/min and 5,000 services per tenant before GA Ph4; insurance Ph3. (p.64–66)
- **MPS-19.02** `BE` `OPS` Ph3 Trust centre tiers: Public (security overview, architecture & data-flow diagrams per mode, sub-processor list, uptime history, advisories, policy summaries); Under NDA via approved request + e-signed NDA (SOC 2, pen-test summary, ISO certs, full policies, DORA/CPS 230 addenda, insurance, escrow summary, BCP). (p.66)
- **MPS-19.03** `BE` Every trust document carries version, effective date, expiry; superseded versions clearly marked. (p.66)
- **MPS-19.04** `BE` Every NDA-document download logged with identity. (p.66)
- **MPS-19.05** `BE` Subscribers notified of changes incl. new sub-processors ≥ 30 days before they start. (p.66)
- **MPS-19.06** `BE` Acceptance: buyers self-serve current approved documents; expired/superseded marked; sensitive-report access logged. (p.66)

## §20 Core data model (p.67–71)
- **MPS-20.01** `BE` 24 core + 29 v2.0 entities; Incident at centre; every table carries organisation and workspace identifiers plus created/updated timestamps; evidence ledger and audit log are append-only; every configuration object versioned. (p.67, p.69)
- **MPS-20.02** `BE` Organisation: name, plan, deployment mode, default region; owns workspaces. (p.67)
- **MPS-20.03** `BE` Workspace: name, data residency, retention policy, AI model setting; belongs to an org; owns teams, services, connectors. (p.67)
- **MPS-20.04** `BE` User: name, email, IdP subject, status, last sign-in; many teams, many roles. (p.67)
- **MPS-20.05** `BE` Team: name, on-call schedule, escalation policy; owns services. (p.67)
- **MPS-20.06** `BE` Role and Permission: role name, permission list, conditions (environment, region); assigned to users per workspace. (p.67)
- **MPS-20.07** `BE` Connector: type, endpoint, auth method, secret reference, state, health, scope, data policy; belongs to workspace; read and write credentials stored separately. (p.67)
- **MPS-20.08** `BE` Service: name, tier, owner team, environment, labels, SLOs; depends on services; linked to business services. (p.67)
- **MPS-20.09** `BE` Dependency: from service → to service / vendor / cloud region, type; builds dependency & concentration map. (p.67)
- **MPS-20.10** `BE` Business Service: name, tolerance (time, data loss, minimum service), downtime budget, regulator mappings; linked to many services. (p.67)
- **MPS-20.11** `BE` Alert: source, fingerprint, severity, labels, start & end time, status; grouped into one incident. (p.67)
- **MPS-20.12** `BE` Incident: number, title, type & configuration version, severity, state, visibility, impact, money at risk, roles, impact started/detected/declared/acknowledged/mitigated/resolved/closed; one investigation, many actions, reports, clocks. (p.67)
- **MPS-20.13** `BE` Investigation: plan, status, budgets, model route; belongs to incident; produces hypotheses. (p.68)
- **MPS-20.14** `BE` Hypothesis: cause, confidence, rank, status (confirmed, ruled out), reason; supported/refuted by evidence. (p.68)
- **MPS-20.15** `BE` Evidence: type, query, result reference, source connector, captured at, content hash; append-only; hash-chained. (p.68)
- **MPS-20.16** `BE` Model Call: provider, model, version, prompt template version, input hash, output hash, tokens, cost, latency; append-only; linked to investigation step. (p.68)
- **MPS-20.17** `BE` Policy: scope, autonomy level, approvers, rules, limits, verification, version; versioned; changes need a second policy owner. (p.68)
- **MPS-20.18** `BE` Action: type, target, parameters, proposed by, state, dry-run result, verification result, rollback reference; follows §10 state machine. (p.68)
- **MPS-20.19** `BE` Approval: action, approver, decision, reason, MFA confirmed, time; proposer never approver. (p.68)
- **MPS-20.20** `BE` Runbook and Playbook: title, steps, linked services, source document, review status; steps reference actions and checks. (p.68)
- **MPS-20.21** `BE` Regulatory Clock: rule package version, jurisdiction, started at, deadline, stage, owner, status; belongs to incident; drives reminders. (p.68)
- **MPS-20.22** `BE` Report: type (post-mortem, regulator stage), version, status, approver, submitted at; locked after submission; amendments are new versions. (p.68)
- **MPS-20.23** `BE` Replay Run: incidents tested, model route, correct-first rate, top-three rate, minutes saved; belongs to workspace; feeds scorecard. (p.68)
- **MPS-20.24** `BE` Escalation and On-call: schedule, rotation, overrides, escalation steps, acknowledgements; linked to teams and incidents. (p.68)
- **MPS-20.25** `BE` Audit Event: actor, action, target, before and after, IP, time, previous hash; append-only; streamed to SIEM. (p.68)
- **MPS-20.26** `BE` Incident Type: name, version, allowed severities, default visibility, forms, regulator mappings, automations; incident stores type version. (p.69)
- **MPS-20.27** `BE` Custom Field Definition: key, data type, options, validation, display conditions, required-at stages, archived; versioned; archiving keeps values. (p.69)
- **MPS-20.28** `BE` Custom Field Value: incident, field definition version, typed value, set by, set at; changes appear on timeline. (p.69)
- **MPS-20.29** `BE` Configuration Version: object type, object ID, version, difference, source (UI, API, Terraform), actor; one per change; used for rollback and drift. (p.69)
- **MPS-20.30** `BE` Incident Visibility Grant: incident, person/team/role, granted by, reason, expiry; enforced in search, API, notifications, exports, analytics, AI retrieval. (p.69)
- **MPS-20.31** `BE` Incident Relationship: from, to, type (merged into, parent of, duplicate of, caused by, related to, recurrence of); merges keep original IDs as redirects. (p.69)
- **MPS-20.32** `BE` Incident Task: incident, title, owner, status, priority, due, dependencies, links, source, completed at/by; inherits visibility; converts to follow-up. (p.69)
- **MPS-20.33** `BE` Role Handoff: incident, role, from user, to user, package snapshot, acknowledged at, deferred items; creates timeline event. (p.69)
- **MPS-20.34** `BE` Approval Route: policy, stage, resolver type & settings, quorum, order, validity, fallback; each runtime approval records resolver and eligibility reason. (p.69)
- **MPS-20.35** `BE` Delegation: delegator, delegate, scope, start, end, reason; delegate independently eligible. (p.69)
- **MPS-20.36** `BE` Effective Policy Snapshot: proposed action, policies & versions applied, resulting constraints, evaluated at; stored with every action. (p.70)
- **MPS-20.37** `BE` Playbook Run and Step Run: playbook version, inputs, step states, outputs (redacted), retries, checkpoints, rollbacks; part of evidence ledger. (p.70)
- **MPS-20.38** `BE` Notification Rule: trigger, conditions, recipients, channels, class, renotify, version; versioned. (p.70)
- **MPS-20.39** `BE` Notification Preference: user, class, channel order, quiet hours; critical overrides follow org policy. (p.70)
- **MPS-20.40** `BE` Notification Delivery: rule, recipient, channel, provider message ID, status, timestamps; append-only. (p.70)
- **MPS-20.41** `BE` Rule Package Version: jurisdiction, regulator, version, effective from/to, sources, validation status, test suite; signed; never edited after release. (p.70)
- **MPS-20.42** `BE` Rule Package Activation: workspace, package version, overrides, activated by; overrides only tighten. (p.70)
- **MPS-20.43** `BE` Model Route and Release: workspace, step type, primary route, fallback route, pinned version, allow-list, release version, approval; changes audited; residency-checked. (p.70)
- **MPS-20.44** `BE` Residency Policy: workspace, allowed regions per data path, last check result; checked on save and at runtime. (p.70)
- **MPS-20.45** `BE` Support Access Session: requester, approvers, scope, start, end, revoked at, action log; visible to customer admins in real time. (p.70)
- **MPS-20.46** `BE` Deployment and Upgrade Run: version, components, preflight result, plan, status, rollback reference; self-hosted & air-gapped. (p.70)
- **MPS-20.47** `BE` Backup Record and Restore Test: component, time, size, checksum, verification & restore-test results; feeds Platform Operations. (p.70)
- **MPS-20.48** `BE` Impact Model: business service, metrics, formula, currency, freshness limit, fallback, thresholds, version; every displayed value cites it. (p.71)
- **MPS-20.49** `BE` Status Page, Component, Post, Subscriber: audience, components, post state, approvals, subscriptions, consent; posts keep full history incl. rejected drafts. (p.71)
- **MPS-20.50** `BE` Post-Incident Review: incident, state, required reviewers, approvals, due dates, redactions, exceptions; gates incident closure. (p.71)
- **MPS-20.51** `BE` Metric Definition and Dashboard: metric key, formula, version, owner; dashboard filters, schedule, permissions; one definition per metric. (p.71)
- **MPS-20.52** `BE` Connector Schema Version: connector, version, required endpoints & fields, contract-test result; breaking change → Degraded. (p.71)
- **MPS-20.53** `BE` User Preferences: language, date format, week start, number & currency format, time zone, theme; display only, stored values stay ISO. (p.71)
- **MPS-20.54** `BE` Trust Document: title, tier, version, effective date, expiry, access log; NDA-tier downloads logged. (p.71)

## §21 Non-functional requirements (p.71–73)
- **MPS-21.01** `OPS` Pass/fail targets; a phase is not complete until met in a load test, not a demo. (p.71)
- **MPS-21.02** `OPS` SaaS availability 99.95% monthly. (p.71)
- **MPS-21.03** `OPS` Self-hosted HA install option: no single point of failure; survives loss of one node or zone. (p.71)
- **MPS-21.04** `BE` `OPS` Independence: runs on separate infrastructure; caches service map and recent context; falls back to email and SMS if chat is down. (p.71)
- **MPS-21.05** `BE` Alert intake 10,000 alerts/min per tenant sustained without loss. (p.72)
- **MPS-21.06** `BE` Scale: 5,000 services and 2,000 users per tenant. (p.72)
- **MPS-21.07** `BE` First hypothesis median < 3 min, p95 < 6 min. (p.72)
- **MPS-21.08** `UI` First load < 1.5 s; interaction < 100 ms. (p.72)
- **MPS-21.09** `OPS` Durability: no data loss on node/zone failure; daily backups; restores tested monthly. (p.72)
- **MPS-21.10** `OPS` Own recovery: RTO 1 h, RPO 5 min for SaaS. (p.72)
- **MPS-21.11** `OPS` `BE` Zero-downtime rolling upgrades; DB changes backward-compatible for one version. (p.72)
- **MPS-21.12** `OPS` No known critical vulnerabilities in releases; high severity fixed within 7 days. (p.72)
- **MPS-21.13** `UI` WCAG 2.2 AA; English and Arabic at Phase 3, French and German later; latest two Chrome, Edge, Safari, Firefox + mobile Safari/Chrome. (p.72)
- **MPS-21.14** `BE` `OPS` Self-observability: OTel traces, metrics, logs for every service; own SLOs and on-call. (p.72)
- **MPS-21.15** `BE` Cost control: per-incident budgets, alerts at 80%, monthly spend report per tenant. (p.72)
- **MPS-21.16** `BE` Critical notification first delivery attempt < 30 s p95; next channel per preferences. (p.73)
- **MPS-21.17** `BE` Global search < 500 ms p95 up to 10 million indexed records per tenant. (p.73)
- **MPS-21.18** `BE` Restricted incidents: zero leakage via search, API, notifications, exports, analytics, AI retrieval; automated permission tests every release. (p.73)
- **MPS-21.19** `OPS` Self-hosted recovery RTO 4 h / RPO 15 min; restore test every quarter. (p.73)
- **MPS-21.20** `BE` Residency check must pass before a regulated workspace goes live and after every data-path change. (p.73)
- **MPS-21.21** `BE` Configuration plan < 30 s for 1,000 objects. (p.73)
- **MPS-21.22** `OPS` Self-hosted upgrade and rollback zero downtime; rollback within 15 min. (p.73)
- **MPS-21.23** `BE` Approval validity default 15 min; never usable after expiry or policy/target change. (p.73) ≡ MPS-10.13

## §22 Technology stack decisions (p.73–75)
- **MPS-22.01** `XS` Core services Python + FastAPI (Node.js rejected). (p.73)
- **MPS-22.02** `BE` Edge Agent in Go. (p.74)
- **MPS-22.03** `BE` Temporal for durable workflows (hand-written queues and n8n rejected). (p.74)
- **MPS-22.04** `BE` OPA (Rego) policy engine. (p.74)
- **MPS-22.05** `BE` PostgreSQL with RLS and pgvector (no separate vector DB). (p.74)
- **MPS-22.06** `BE` ClickHouse optional for event analytics for big tenants, not required everywhere. (p.74)
- **MPS-22.07** `BE` NATS JetStream event bus (Kafka rejected). (p.74)
- **MPS-22.08** `BE` S3-compatible object storage ("MinIO when self-hosted"). (p.74) — superseded by TSD-7.02; see Q-26
- **MPS-22.09** `BE` Secrets: HashiCorp Vault or OpenBao; cloud key services in SaaS. (p.74)
- **MPS-22.10** `BE` Identity: Keycloak embedded for self-hosted; same SSO/SCIM flows in SaaS. (p.74)
- **MPS-22.11** `UI` Frontend Next.js, React, TypeScript, Tailwind, Radix. (p.74)
- **MPS-22.12** `BE` `UI` Live updates via WebSockets with SSE fallback (polling rejected). (p.75)
- **MPS-22.13** `UI` ECharts; React Flow for dependency maps. (p.75)
- **MPS-22.14** `BE` Provider-neutral AI gateway: Claude via Anthropic API, Bedrock, Google Cloud, Microsoft Foundry; local open-weight via vLLM. (p.75)
- **MPS-22.15** `OPS` Packaging: Helm charts + K8s operator; Docker Compose for trials. (p.75)
- **MPS-22.16** `OPS` Supply chain: GitHub Actions, signed images, SBOMs, image and dependency scanning. (p.75)
- **MPS-22.17** `OPS` Self-monitoring: OpenTelemetry, Prometheus, Grafana. (p.75)
- **MPS-22.18** `BE` n8n prototype stays as demo/internal automation; its logic (alert intake, context gathering, escalation timers, post-mortems) re-implemented as tested services in Ph0–1. (p.75)
- **MPS-22.19** `XS` Every change through a PR with ≥ 1 human reviewer; AI assistants never merge without review; tests required for policy, action and evidence code; nothing reaches production without passing the same gates we sell. (p.75)

## §22A Engineering build contract (p.75–78)
- **MPS-22A.01** `XS` Every line built against a section of the spec, a schema and its acceptance criteria; if the spec is silent nobody invents behaviour — raise a specification question. (p.75)
- **MPS-22A.02** `XS` Monorepo layout: apps/{web, trust-centre}; services/{api, brain, workflows, notifier, connectors, search}; policy/; agent/; packages/{schemas (OpenAPI 3.1, event JSON Schemas, shared types), ui}; rule-packages/ (with scenario tests); deploy/{helm, operator, compose, airgap}; docs/{spec (this doc, one md per section), adr}; tests/{e2e, load, security, replay-benchmark}. (p.76) — see Q-04, Q-24
- **MPS-22A.03** `XS` API first: every endpoint written in the OpenAPI file before code; server stubs and typed clients generated from it. (p.76) — see Q-03
- **MPS-22A.04** `XS` REST: versioned paths (/v1), JSON, cursor pagination, standard filter and sort parameters, errors as RFC 9457 problem details with a correlation ID. (p.76) — see Q-01, Q-02
- **MPS-22A.05** `XS` Safe writes: idempotency key on every request that creates or acts; ETag + If-Match on updates. (p.76)
- **MPS-22A.06** `XS` Rate limits: 429 with Retry-After. (p.76)
- **MPS-22A.07** `XS` Every state change emits a versioned event (e.g. incident.declared.v1, approval.granted.v1, clock.started.v1) in a CloudEvents envelope with a JSON Schema; webhooks deliver the same events, signed and retried. (p.77)
- **MPS-22A.08** `XS` One shared authorisation layer enforces tenant, role and incident visibility for every endpoint, event and search; never ad hoc inside handlers. (p.77)
- **MPS-22A.09** `XS` Data: migrations expand first, contract later; RLS for tenancy; money integer + currency; timestamps UTC. (p.77)
- **MPS-22A.10** `XS` Configuration: immutable IDs, human keys and versions for every configuration object. (p.77)
- **MPS-22A.11** `XS` Secrets never in code, logs, events or test data; vault references only; secret scanning in CI. (p.77)
- **MPS-22A.12** `XS` AI only through the model gateway; prompts are versioned files in the repo; outputs validated against JSON Schemas; every call written to the evidence ledger. (p.77)
- **MPS-22A.13** `XS` Unfinished work behind feature flags, switched on only when its phase gate passes. (p.77)
- **MPS-22A.14** `XS` Definition of done: linked to spec section + acceptance criteria; OpenAPI and event schemas updated with changelog entry; unit + integration tests; permission tests for every role and restricted incidents; acceptance criteria automated as E2E; audit events for every state change; tested in every claimed deployment mode (CI matrix); performance budgets checked; WCAG + EN/AR RTL for UI; security review for actions/policies/secrets/AI/permissions; user docs + API reference updated; human-approved incl. AI-generated code. (p.77)
- **MPS-22A.15** `XS` Keep the spec in docs/spec as markdown; every task names its section and pastes its acceptance criteria; generate from schemas first then write logic; record spec gaps as ADRs; security-sensitive paths (actions, policies, approvals, secrets, permissions, AI gateway) need two human reviewers. (p.78)

## §23 Build phases (p.78–82)
- **MPS-23.01** `ORG` Six phases, each ends with a demoable product and an exit gate; failed gate → fix before adding. (p.78)
- **MPS-23.02** `ORG` `BE` Phase plan (p.79): Ph0 Foundations wk1–4 (repos, CI, signed builds, test harness; tenancy, auth skeleton, design system; read-only Prometheus, Loki, K8s, Slack; 30-incident benchmark set) gate: benchmark runs nightly end to end. Ph1 See & explain wk5–12 (Brain v1 + evidence ledger; war room + Slack summaries; Replay, scorecard, shadow mode; onboarding; 2 design partners) gate: 60% first, 80% top-3, first answer < 3 min. Ph2 Act safely wk13–20 (Edge Agent actions, durable workflows; policy engine L0–L3, four-eyes; verification, rollback, kill switch; ServiceNow change records, mobile approvals) gate: zero unapproved changes, pen test passed. Ph3 Enterprise ready wk21–30 (SSO, SCIM, roles, SoD; hash-chained audit, SIEM, customer keys; self-hosted install; Regulator Pack; tolerance tracker, on-call lite, Arabic UI) gate: SOC 2 Type I, first enterprise contract. Ph4 Sovereign & scale wk31–40 (air-gapped + local model; HA, 10k alerts/min load test; deep cloud connectors; dependency map, earned autonomy, drills) gate: air-gapped install in a day, 99.95% for 30 days. Ph5 Platform wk41–52 (connector SDK, MCP; runbook compiler, code-fix suggestions; marketplaces, partners; SOC 2 Type II, ISO 27001 underway) gate: 10 paying customers, 70% correct-first.
- **MPS-23.03** `ORG` End-of-phase gap review: usability test (5 engineers), accuracy review, security review + threat model update, load & failure test vs §21, design-partner feedback, competitor check, docs/changelog/demo; plus update the §26 traceability table. (p.79, p.82)
- **MPS-23.04** `ORG` What each phase lets us sell (Ph1 Replay pilots/shadow; Ph2 Professional plan; Ph3 Enterprise & self-hosted; Ph4 Sovereign & air-gapped; Ph5 platform deals). (p.80)
- **MPS-23.05** `BE` Ph0 v2.0 items: incident lifecycle state machine and incident-type model (8A); shared authorisation layer incl. incident visibility; configuration versions with stable IDs (14A); machine-safe values; event schemas; build contract (22A). (p.80)
- **MPS-23.06** `BE` Ph1 v2.0 items: incident types & custom fields, declare form, live tasks, basic notification rules (chat & email), global search, business impact model, model allow-list, routes, no-external-fallback, Replay release gate. (p.80)
- **MPS-23.07** `BE` Ph2 v2.0 items: approval resolvers, quorum, delegation, expiry; policy precedence & effective-policy view; emergency policies; playbook runtime; ServiceNow/Jira sync rules; commander handoff; merge, split, relationships. (p.80)
- **MPS-23.08** `BE` Ph3 v2.0 items: full restricted-incident enforcement; notification preferences, SMS, voice, delivery tracking; on-call coverage; rule packages & versions; PIR governance; support access; residency guardrails & check; configuration as code (Terraform, plan, drift); change preview & bulk safety; self-hosted platform ops, backup & restore tests; trust centre; status page; locale & theme preferences; metric catalogue; service reconciliation & CMDB sync; credential rotation; connector contract tests. (p.81)
- **MPS-23.09** `BE` Ph4 v2.0 items: air-gapped bundles & offline verification; automated DR drills; model deprecation & migration tooling; status-page subscriptions at scale. Ph5: workspace templates, personalised command centre, knowledge graph, notification analytics, policy recommendation assistant. (p.81)
- **MPS-23.10** `ORG` Spec gates: A product-contract freeze (every P0 has decision, owner, data-model/API/security impact, UI reference — before coding that feature); B regulated-pilot readiness (restricted incidents, named & dynamic approvals, precedence, support access, residency, ITSM sync testable — before first regulated pilot, Ph3); C enterprise admin readiness (config as code, upgrade/rollback, backup/restore, notification rules, search, audit visibility, bulk-safe admin pass acceptance — end Ph3); D compliance-pack readiness (versioned rule packages, pinned templates, visible counsel status, reproducible evidence export — before selling Regulator Pack); E GA UX readiness; F proof (Replay accuracy, speed, zero unapproved changes, upgrade/recovery & enterprise security tests meet targets — GA). (p.81–82)

## §24–§26 Metrics, risks, traceability (p.82–89)
- **MPS-24.01** `ORG` `BE` Success metrics by end of Ph5: 70% correct-first; 85% top-three; median first hypothesis < 3 min; zero unapproved changes; actions rolled back after verification failure < 2%; median MTTR reduction ≥ 30%; ≥ 25% incidents with an L2+ action; signup → first Replay < 1 day; weekly active responders ≥ 60% of on-call; 10 paying customers; ACV ≥ $40k; gross margin ≥ 75%; NRR ≥ 110%; pilot-to-paid 50%. (p.82–83)
- **MPS-25.01** `ORG` Risks and mitigations incl. external red-team test of the action path before Phase 2 GA. (p.83–84)
- **MPS-25.02** `ORG` Open questions before Ph3 (SI partners, DORA/CPS 230/SAMA clause wording, own incident-notification commitment, air-gap local model choice, escrow provider, Sovereign pricing). (p.84)
- **MPS-25.03** `ORG` `BE` v2.0 open questions: confirm defaults with design partners (15-min approval validity, 7-day reopen, 30-day licence grace, 24-h secret overlap, 25-object bulk threshold, quarterly restore tests) — implement these as configurable defaults; Terraform provider timing; rule-package owner; Gate B evidence. (p.85)
- **MPS-26.01** `ORG` Gap-audit traceability: P0-01…P0-16, P1-01…P1-16, P2-01…P2-05 mapped to sections and phases. (p.85–87)
- **MPS-26.02** `XS` Single definitions (must be used verbatim): Relyxus = product (formerly SentinelAI), Apporine = company; deployment modes exactly four; autonomy levels L0–L4; approval validity 15 min default, void on expiry or any policy/target/command change; incident states Triage, Investigating, Mitigating, Monitoring, Resolved, Closed + Cancelled, Merged; task = live work vs follow-up = post-incident; post-mortem ≡ post-incident review; roles = Owner, Admin, Security admin, Compliance officer, Policy owner, Incident commander, Responder, Viewer, Auditor; phase gates vs spec gates; UK date 18 March 2027; UI/UX spec governs layout. (p.87–88)
- **MPS-27S.01** `ORG` Sources section: figures/dates must be re-checked before use in contracts, pitches or regulator conversations. (p.88–89)

## §27 Deployment authority and enterprise packaging (p.90–93)
- **MPS-27.01** `XS` Section is additive; companion authority: MPS (product behaviour), Tech Stack (technologies), Deployment Spec (install kits, packaging), UI/UX (layout). (p.90) — see Q-06
- **MPS-27.02** `OPS` One product, one source tree, one release version; two deployment packages (A existing platform kit, B cloud foundation + kit) that never fork code, APIs, schemas or behaviour. (p.90)
- **MPS-27.03** `OPS` Same signed OCI image digest and product version deployable through both packages; cloud-specific build forbidden without ADR. (p.90)
- **MPS-27.04** `OPS` Package A prerequisites: supported K8s/EKS/GKE/AKS/OpenShift per matrix; OCI registry for immutable signed images (internal for air-gap); PostgreSQL with required extensions and TLS, defined backup ownership, credentials via approved secrets path; approved S3-compatible endpoint or certified adapter; customer OIDC/SAML IdP + group/role mapping; customer OpenBao/Vault/cloud secret manager + KMS/HSM, secrets never in Helm values/images/source; ingress hostname, certificates, egress allow-list/private connectivity. (p.91)
- **MPS-27.05** `OPS` Customer platform team runs the kit by default; Apporine-executed deployment uses temporary, least-privilege, approved, logged access revoked after the window; never permanent vendor cluster-admin. (p.91)
- **MPS-27.06** `OPS` Package A outcome: install from signed artifacts, prove exact digests and config, verify health, generate installation report, audited upgrade/rollback without rebuilding code. (p.91)
- **MPS-27.07** `OPS` Package B: customer-owned foundation as code for AWS (EKS, VPC, IAM, managed PG option, object storage, registry, KMS/secrets, ingress/DNS), GCP (GKE, Workload Identity, Cloud SQL…), Azure (AKS, VNet, managed identity, Azure DB for PG, Key Vault/HSM…); never a second Relyxus implementation. (p.92)
- **MPS-27.08** `OPS` OpenTofu is the IaC engine; separate provider root modules under a common contract; app code, images and Helm chart do not fork per cloud. Reference shape: infrastructure/opentofu/{modules/shared-contract, aws|gcp|azure/{modules,environments,examples}}, deploy/helm/relyxus/, release/manifest/. (p.92) — see Q-24
- **MPS-27.09** `OPS` State remote, encrypted, access-controlled, isolated per customer/environment; production state locking, versioning, backup, least privilege, destruction safeguards; credentials never in HCL, state outputs, CI logs, Helm values. (p.92)
- **MPS-27.10** `OPS` Release/portability gates: artifact identity, install, health, scale, disruption, upgrade/rollback, backup/recovery, security, residency, observability — evidence recorded per claimed cloud. (p.93)
- **MPS-27.11** `XS` Treat deployment spec as executable architecture; missing/contradictory → ADR; no cloud may require a different business-logic codebase; no self-hosted install may depend on an Apporine-only cloud service unless explicitly permitted. (p.93)
- **MPS-27.12** `OPS` Acceptance: A installs same signed release on conformant K8s; B creates AWS/GCP/Azure foundation then hands to A; customer installs without permanent Apporine access; air-gapped via signed offline artifacts and internal registry; details governed by Deployment Spec. (p.93)

## §28 Bank-grade privacy, security and regulated controls (p.94–97)
- **MPS-28.01** `BE` One product; bank-grade assurance via configurable controls and deployment profiles; secure defaults for every customer; stricter controls by policy, contract, jurisdiction or risk classification. (p.94)
- **MPS-28.02** `BE` Secure core (all) vs regulated option: tenant isolation (org/workspace authz + RLS vs dedicated tenant/DB/cluster/account); encryption (in transit & at rest vs CMK/BYOK/HSM + stricter rotation evidence); audit (tamper-evident log vs signed/verifiable exports, WORM archive); identity (SSO/federation + RBAC vs SCIM, step-up, dual control, JIT, break-glass); data lifecycle (retention + verified deletion vs legal hold, preservation, crypto-erasure); deployment; AI (governed routing vs customer-approved routes only, local model, stricter residency/egress). (p.94)
- **MPS-28.03** `BE` Data classes at minimum: operational telemetry, identity/access, incident/evidence, secrets/credentials, audit/security, customer-configured sensitive fields. (p.94)
- **MPS-28.04** `BE` Connectors collect only data needed for the configured purpose; broad collection not justified because a connector can access it. (p.94)
- **MPS-28.05** `BE` Field-level redaction/tokenisation configurable before AI, notification, support and export paths; secret/token/credential patterns always prohibited for AI and ordinary logs. (p.94)
- **MPS-28.06** `BE` Every external data path declares purpose, destination, region, retention, and whether customer content leaves the trust boundary; security admins can review the map. (p.94)
- **MPS-28.07** `BE` Analytics and product telemetry avoid customer incident content by default; content-bearing diagnostics need explicit policy and redaction. (p.94)
- **MPS-28.08** `BE` All application reads/writes enforce org/workspace context; RLS mandatory defence in depth for workspace-scoped records. (p.94)
- **MPS-28.09** `BE` Search indexing, caches, notifications, event streams, exports and AI retrieval inherit the same boundary; no secondary subsystem weaker than the primary API. (p.95)
- **MPS-28.10** `BE` Cross-tenant identifiers are untrusted input; a valid object ID does not imply access. (p.95)
- **MPS-28.11** `BE` Restricted incidents and sensitive evidence excluded before search ranking, analytics aggregation and AI retrieval, not filtered afterwards. (p.95)
- **MPS-28.12** `OPS` Dedicated infrastructure isolation available (single-tenant DB, cluster, account/project/subscription). (p.95)
- **MPS-28.13** `BE` CMK where configured; HSM-backed keys when required. (p.95)
- **MPS-28.14** `BE` Key references and crypto metadata auditable; raw key material never stored by Relyxus. (p.95)
- **MPS-28.15** `BE` Key rotation has plan, verification, rollback/failure handling, audit; must not silently make existing evidence unreadable. (p.95)
- **MPS-28.16** `BE` Key revocation/destruction is high-risk with impact preview and required approval; crypto-erasure satisfies deletion only when the boundary is complete and customer policy accepts it. (p.95)
- **MPS-28.17** `BE` `OPS` Backups, copies and DR replicas stay within encryption/residency policy and are included in deletion/retention reasoning. (p.95)
- **MPS-28.18** `BE` Retention configurable per data class and workspace within min/max safeguards. (p.95)
- **MPS-28.19** `BE` Legal hold overrides deletion for scoped records, is audited, and only authorised legal/compliance roles create or release it. (p.95)
- **MPS-28.20** `BE` Verified deletion reports scope, method, unresolved replicas/holds and completion without exposing deleted content. (p.95)
- **MPS-28.21** `BE` Customer exit: export in documented open formats, then controlled deletion per contract/retention/hold. (p.95)
- **MPS-28.22** `BE` Deletion promises include backups and derived stores per backup lifecycle; never promise immediate deletion from protected backups the architecture can't support. (p.95)
- **MPS-28.23** `BE` Evidence ledger/audit chain authoritative; security-sensitive actions record actor, effective identity, target, before/after where safe, policy/model/config versions, timestamp, result. (p.95)
- **MPS-28.24** `BE` Verifiable exports include manifest, schema version, time range, scope, hashes and signature/attestation; auditor can independently detect modification. (p.95)
- **MPS-28.25** `BE` Customers may route audit to SIEM and archive exports to customer-controlled immutable/WORM storage. (p.95)
- **MPS-28.26** `BE` Export, verification failure, chain discontinuity and SIEM backlog are themselves visible security events. (p.95)
- **MPS-28.27** `BE` No standing vendor access to self-hosted production data; dedicated/SaaS support off by default and customer-approved. (p.95)
- **MPS-28.28** `BE` Privileged support uses JIT access with scope, reason/ticket, expiry, immediate customer revocation. (p.95)
- **MPS-28.29** `BE` High-risk administration can require second approver and step-up auth; requester cannot satisfy SoD by approving own request. (p.95)
- **MPS-28.30** `BE` Break-glass visible, time-bounded, heavily audited; org defines who may invoke and required post-use review. (p.95)
- **MPS-28.31** `BE` Support session evidence includes effective identity, start/end, scope, action log; retained per customer policy. (p.96)
- **MPS-28.32** `OPS` Backup access separated from application write paths where supported; protected/immutable retention and separate backup trust boundaries available. (p.96)
- **MPS-28.33** `OPS` `BE` Restore drills in isolated environment verify tenant isolation, authorisation, evidence chain, config checksums, object integrity, key access, app health before promotion; restored data never broadly exposed to dev/test users; platform records last backup and last passed restore as customer-visible evidence. (p.96)
- **MPS-28.34** `BE` `OPS` Every regulated data path has allowed region & destination policy; violations rejected; runtime blocks unexpected outbound transfer; deny-by-default egress with allow-lists supported; private connectivity preferred/mandatory by policy. (p.96)
- **MPS-28.35** `BE` Edge Agent outbound-only; backup, analytics, model, notification, support and export paths included in residency checks; air-gapped has no internet dependency for normal operation, updates via signed offline bundles. (p.96)
- **MPS-28.36** `BE` AI via provider-neutral gateway; customer controls approved providers/models, region, fallback, and whether external routes are allowed at all. (p.96)
- **MPS-28.37** `BE` Permission filtering and data-policy redaction before model retrieval/calls. (p.96)
- **MPS-28.38** `BE` No training of external foundation models on customer data; ZDR/no-training terms preferred and enforced where customer policy requires. (p.96)
- **MPS-28.39** `BE` Every governed model call records model/provider route, prompt-template version, data-policy decision, output/evidence linkage — without storing prohibited secrets. (p.96)
- **MPS-28.40** `BE` Replay/model-evaluation gates material changes for regulated customers; local approved models for air-gap. (p.96)
- **MPS-28.41** `OPS` Every release: signed OCI, SBOM/provenance, dependency/container/secret scanning, protected review gates; critical vulns need documented remediation or formal risk acceptance before regulated release; severity timelines in security policy/SLA. (p.96)
- **MPS-28.42** `OPS` AppSec testing: permission-boundary tests, SAST/SCA, appropriate DAST/integration testing; extra review for high-risk releases; pen testing/certifications are org activities — passing tests is not certification. (p.96)
- **MPS-28.43** `BE` `UI` Admin experience: data-flow map (class, source, destination, region, retention, model route, ownership); residency check (fails unsafe config, auditor evidence); key status (ownership/reference, rotation, expiry/health, no key material); retention & legal hold (policy editor, impact preview, protected roles, history); support access (pending/active/past, scope, reason, expiry, action log, immediate revoke); audit verification (verify chain/export signature, inspect failures, SIEM delivery state); security posture (enabled control profile, deviations, risk acceptances). (p.96–97)
- **MPS-28.44** `BE` Acceptance: automated cross-tenant tests show zero leakage across API, search, notifications, analytics, events, exports, AI retrieval. (p.97)
- **MPS-28.45** `BE` Acceptance: CMK configured, rotated, validated without silent data loss; key operations audited. (p.97)
- **MPS-28.46** `BE` Acceptance: signed audit export generated and independently verified; tampering fails verification. (p.97)
- **MPS-28.47** `OPS` Acceptance: isolated restore drill verifies evidence integrity and authorisation before promotion. (p.97)
- **MPS-28.48** `BE` Acceptance: residency check covers primary data, backups, model calls, analytics, notifications, exports, support and blocks out-of-policy routes. (p.97)
- **MPS-28.49** `BE` Acceptance: support session auto-expires, revocable immediately, produces audit/session report. (p.97)
- **MPS-28.50** `BE` Acceptance: legal hold prevents scoped deletion until authorised release; verified deletion reports remaining holds/backups. (p.97)
- **MPS-28.51** `OPS` `BE` Acceptance: air-gapped deployment performs normal investigation/governance with approved local dependencies, no public internet path. (p.97)
- **MPS-28.52** `XS` `ORG` No screen or sales artifact claims certification/compliance not actually obtained. (p.97)
- **MPS-28.53** `XS` One codebase; optional regulated controls enabled by policy, entitlement and deployment profile; universal security controls mandatory; no bank/fintech/SaaS forks. (p.97)

## §29 Commercial licensing and entitlement governance (p.98–100)
- **MPS-29.01** `BE` `OPS` Release built once; customer-specific licences never embedded in OCI images or Helm chart binaries. (p.98)
- **MPS-29.02** `BE` Licensing controls commercial rights, support level, deployment allowances; never weakens universal security controls (encryption, tenant isolation, authn, authz, audit integrity, secure update verification, data protection mandatory for all tiers). (p.98)
- **MPS-29.03** `BE` Licensing supports connected, self-hosted and fully air-gapped customers. (p.98)
- **MPS-29.04** `BE` Commercial expiry never deletes customer data or abruptly stops active incident-response safety functions. (p.98)
- **MPS-29.05** `BE` Versioned, digitally signed licence artifact (e.g. relyxus.license) identifying customer, product, licence/revision, deployment binding/allowance, validity, support tier, entitlements; never customer passwords, cloud credentials, API secrets or Apporine private key material. (p.98)
- **MPS-29.06** `BE` Field classes: Identity (license_id, revision, customer_id, product_id — stable IDs; display names separate metadata); Validity (issued_at, not_before, expires_at, grace_policy — explicit, auditable); Deployment (production / non-production / DR allowance, logical deployment IDs — never pod/container IDs); Entitlements (feature/tier/quantity — commercial only); Trust (schema_version, key_id, signature — verifier rejects unknown/invalid envelope versions or signatures). (p.98)
- **MPS-29.07** `BE` Licence states & behaviour: Active (normal, subject to entitlements); Grace (continue incident safety functions, warn admins, restrict only policy-defined non-essential commercial/config changes); Expired (preserve data and history, don't interrupt safety-critical workflows, block defined new commercial/config operations, renewal path); Suspended/Revoked (connected: enforce authenticated signed status after refresh; air-gapped: bounded validity & replacement/import); Superseded (keep previous revision in immutable history). (p.98) — see Q-07, Q-08
- **MPS-29.08** `BE` Always verify the local signed licence before relying on entitlements. (p.99)
- **MPS-29.09** `BE` Connected (if customer policy permits): outbound-only request to Apporine licensing endpoint for signed entitlement/revocation refresh, sending only minimum licensing identifiers — no evidence, telemetry content or secrets. (p.99)
- **MPS-29.10** `BE` Loss of licensing connectivity uses cached signed state and the grace policy, never immediately stopping incident response. (p.99)
- **MPS-29.11** `BE` Air-gapped: no mandatory network dependency on Apporine; import licence and verify locally with Apporine public keys; renewal by importing a new signed revision; no instant remote revocation — bounded validity, replacement artifacts, customer-controlled suspension. (p.99)
- **MPS-29.12** `ORG` `BE` Licences created via an internal governed control plane (not hand-edited files), derived from approved Product, Customer, Contract/Subscription, Entitlement, Deployment records. (p.99)
- **MPS-29.13** `BE` Renewal or material change creates a new signed revision; signed artifacts never edited in place. (p.99)
- **MPS-29.14** `BE` Suspension/revocation require explicit reason and audit evidence; high-impact changes can require second approver; every issue, renew, suspend, revoke, rebind, download, delivery audited. (p.99)
- **MPS-29.15** `BE` Production licences signed with an Apporine asymmetric key in AWS KMS or equivalent HSM/KMS; private key non-exportable, never distributed; Relyxus holds only the public key set identified by key ID. (p.99)
- **MPS-29.16** `BE` Key rotation overlap period keeps valid licences verifying. (p.99)
- **MPS-29.17** `BE` Verification rejects tampered payloads, malformed envelopes, unsupported algorithms/schema versions, wrong customer/deployment bindings. (p.99)
- **MPS-29.18** `BE` Licensing is an Apporine platform capability (Product → Customer → Contract/Subscription → Entitlement → License → Deployment); Relyxus consumes only the runtime verification/entitlement interface. (p.99)
- **MPS-29.19** `ORG` Apporine Internal Admin Control Plane tracks products, customers, contracts, entitlements, licences, deployments, release metadata, approvals, audit; separate from the customer console and customer production; governed by ACP Spec v1.0 and Licensing Spec v1.0. (p.99) — see Q-05
- **MPS-29.20** `BE` Acceptance: new customer licence without rebuilding any image; air-gapped install & renew with internet blocked; cannot change expiry/entitlements/allowance without invalidating signature; key rotation doesn't break valid deployments during overlap; expiry/revocation never deletes data and follows safe degradation; auditors reconstruct who issued/changed a licence, under which approval, for which customer/product/deployment and with which key/revision. (p.100)
- **MPS-29.21** `XS` Implementation follows TSD v1.3, DEP v1.2, Licensing Spec v1.0, ACP Spec v1.0; raise a spec question rather than invent a licensing mechanism. (p.100)

---

# B. Enterprise Technology Stack & Architecture Decision v1.3 (TSD)

## §1–3 Decision, constraints, principles
- **TSD-1.01** `XS` Locked: Next.js 16.x + React 19.x + TypeScript (console); Python + FastAPI (core API); PostgreSQL 18 reference baseline; Temporal; NATS JetStream; OPA + Rego; Keycloak (OIDC/SAML); Go Edge Agent; Kubernetes + Helm; OpenTelemetry + Prometheus + Grafana.
- **TSD-1.02** `XS` Stack is a controlled architecture decision; AI tools must not introduce substitute frameworks, databases, brokers or identity platforms without architecture review.
- **TSD-2.01** `BE` `OPS` Constraints: same product in SaaS, dedicated, customer K8s, air-gapped; data/evidence/AI routing kept in approved region or network; auditable policy checks, approvals, rollback, verification for actions; evidence integrity survives restore; OIDC and SAML mandatory + enterprise provisioning; approvals/clocks/investigations/notifications survive restarts; large tenants without heavyweight analytics in base install; no public internet for core, identity, policy, workflows, updates, local models in air-gap; signed images, SBOMs, scanning, provenance; small-team velocity.
- **TSD-2.02** `BE` Inherited SLOs: critical notifications < 30 s p95; search < 500 ms p95 at 10M records/tenant; zero restricted-incident leakage; self-hosted RTO 4 h/RPO 15 min with quarterly restores; zero-downtime upgrades, rollback ≤ 15 min; approval validity 15 min, never reusable after expiry/target/policy change.
- **TSD-3.01** `XS` Boring recognised infrastructure at trust boundaries; novelty only in product logic.
- **TSD-3.02** `XS` Control plane stateless where practical; API scales horizontally.
- **TSD-3.03** `XS` PostgreSQL is primary source of truth; no second database until a measured workload requires it.
- **TSD-3.04** `XS` Durable orchestration for processes that wait, retry or survive restarts.
- **TSD-3.05** `XS` Authorisation and production-autonomy policy explicit and testable outside application code.
- **TSD-3.06** `XS` NATS = event bus; Temporal = workflow engine; never conflated.
- **TSD-3.07** `BE` Read-only connectors by default; read credentials separate from action credentials.
- **TSD-3.08** `BE` WebSockets are a delivery channel, not a system of record.
- **TSD-3.09** `XS` Instrument every service with OpenTelemetry from the start.
- **TSD-3.10** `XS` Prefer open standards and self-hostable software.

## §4 Backend framework and layering
- **TSD-4.01** `XS` FastAPI locked for services/api, services/brain, connector-facing APIs; Django only a documented fallback; never mix Django ORM and SQLAlchemy on the same domain model.
- **TSD-4.02** `XS` Layers: API/Presentation (HTTP, OpenAPI, auth context, request/response validation — no core business logic); Domain/Service (incident rules, approvals, impact logic, orchestration decisions, permission-aware behaviour — unit tested); Repository/Data (SQL, persistence, transactions, mapping — no product policy); Workflow (Temporal definitions/activities — durable, deterministic); Policy (OPA/Rego — versioned, testable).

## §5 Frontend
- **TSD-5.01** `UI` Locked frontend: Next.js 16.x App Router, self-hosted Node (no Vercel-only services); React 19.x; TS strict; Tailwind + design tokens; Radix/shadcn ownership; TanStack Query/Table/Virtual; React Hook Form + Zod; ECharts; React Flow; next-intl + ICU (EN/AR RTL); WebSockets + SSE fallback (polling never primary); Storybook; MSW against OpenAPI contracts; pin approved minor/patch.

## §6 Backend and service stack
- **TSD-6.01** `XS` Python (supported CPython line pinned in images); FastAPI; Pydantic; SQLAlchemy 2 with explicit transactions and repository pattern; psycopg 3; Alembic with reviewed forward/backward-planned migrations; Python + Temporal SDK workers; OPA bundles; OpenAPI with generated TS clients and CI contract tests; pytest (unit, integration, permission, contract); Ruff + Pyright/mypy. — see Q-09
- **TSD-6.02** `XS` Service boundaries: services/api (REST, auth context, tenancy, request coordination); services/brain (evidence reasoning, hypothesis ranking, model gateway); services/workflows (Temporal workers: incidents, approvals, clocks, notifications, long-running actions); services/connectors; services/notifier (email, push, SMS/voice/chat, delivery tracking); services/search (permission-aware indexing); policy (OPA bundles, tests, promotion); agent (Go Edge Agent).

## §7 Database, data, storage
- **TSD-7.01** `BE` PostgreSQL 18 (18.6 reference) system of record; RLS for tenant/workspace defence in depth; pgvector; FTS + pg_trgm (OpenSearch only when measured need); PgBouncer; Valkey cache (not source of truth); ClickHouse optional; audit/evidence integrity = PG metadata + object storage + hash chain verifiable after restore.
- **TSD-7.02** `BE` Provider-neutral object-storage interface; S3/S3-compatible baseline adapter; certified native GCS and Azure Blob adapters; business logic never depends on provider SDKs; MinIO must not be a hard dependency (archived April 2026, AGPLv3).
- **TSD-7.03** `OPS` Publish a tested PostgreSQL compatibility matrix; maintained versions only; never onboard on a major nearing EOL.

## §8 Workflow, eventing, cache
- **TSD-8.01** `BE` Temporal for long-running durable processes (investigations, approvals, regulator clocks); NATS JetStream for distribution and replay; WebSockets + SSE for live UI with state in backend; Valkey for cache, rate limits, short-lived state. Never replace Temporal with queue consumers or use Valkey as a durable event/workflow store.

## §9 Identity, authorisation, secrets
- **TSD-9.01** `BE` Keycloak self-hosted OIDC/SAML broker federating to Entra ID, Okta, Ping or customer IdP.
- **TSD-9.02** `BE` Relyxus-owned SCIM 2.0 bridge/service translating lifecycle into Keycloak/admin and Relyxus domain; do not depend on Keycloak preview SCIM (26.7).
- **TSD-9.03** `BE` OPA + Rego as external policy decision point; every sensitive decision logs policy, version, result.
- **TSD-9.04** `BE` OpenBao default secrets with Vault compatibility; short-lived credentials; PostgreSQL stores references, not raw long-lived secrets.
- **TSD-9.05** `BE` Customer-managed KMS/HSM where configured.
- **TSD-9.06** `BE` MFA via customer IdP + Relyxus step-up policy; production approvals can trigger reauthentication.

## §10 AI and model gateway
- **TSD-10.01** `BE` No business logic depends directly on a model vendor SDK; hosted routes (Anthropic API, Bedrock, Google Cloud, Microsoft Foundry) chosen per customer, region, residency, model policy; vLLM + approved local open-weight model for air-gap validated by Replay; every route, prompt and fallback versioned and auditable; permission filtering before retrieval; evidence is source of truth, AI output is interpretation.

## §11 Observability
- **TSD-11.01** `XS` OpenTelemetry for APIs, workers, connectors, Edge Agent; Prometheus metrics; Grafana; Loki or customer logging (structured, no secrets, SIEM/export); Tempo or customer tracing; Alertmanager — Relyxus alerts on its own degraded state; `/health`, `/ready`, `/metrics` endpoints.

## §12 DevOps and supply chain
- **TSD-12.01** `OPS` GitHub org + private monorepo; GitHub Actions; paid branch protection before production; OCI images; Kubernetes; Helm; Go operator later; Argo CD; OpenTofu; Docker Compose for local/trial only; Cosign/Sigstore; Syft/GitHub SBOM; Trivy + dependency scanning + Gitleaks on every PR/release; GitHub artifact attestations.

## §13 Testing and quality gates
- **TSD-13.01** `XS` Frontend: Testing Library + Vitest-compatible runner; Playwright; axe + keyboard (WCAG 2.2 AA).
- **TSD-13.02** `XS` Backend: pytest for domain rules, repositories, APIs, failure behaviour.
- **TSD-13.03** `XS` Every Rego policy has positive and negative OPA tests.
- **TSD-13.04** `XS` Temporal workflow tests: replay/determinism, timeouts, retries, versioning.
- **TSD-13.05** `XS` Contract: OpenAPI client generation + contract tests.
- **TSD-13.06** `XS` Security: permission matrix tests; restricted incidents never leak through any path.
- **TSD-13.07** `OPS` Performance: k6 or Locust at release gates.
- **TSD-13.08** `OPS` Recovery: automated restore drill (row counts, config checksum, evidence hash chain).

## §14–16 GitHub workflow, versions, cost
- **TSD-14.01** `XS` GitHub (not GitLab); short-lived feature branches; no direct pushes to main; every change via PR; ≥ 1 human reviewer; CODEOWNERS for policy, security, workflow, evidence code.
- **TSD-14.02** `OPS` Required CI: type checks, lint, unit tests, policy tests, migration checks, dependency scan, secret scan, container scan, critical E2E.
- **TSD-14.03** `OPS` Release images built only by controlled CI, signed, with SBOM/provenance; production promotion separate from build via GitOps/Argo CD with environment approvals.
- **TSD-14.04** `XS` Start as one private monorepo; don't create a repo per service. — see Q-04
- **TSD-15.01** `XS` Version policy: Next 16.x LTS; React per Next; PG 18 reference + qualified maintained majors; K8s N/N-1/N-2; Keycloak 26.x stable features only; Valkey 9.x pinned; OpenTofu 1.13.x pinned; lockfiles, digest-pinned bases, automated security updates, documented patch SLA; never "latest".
- **TSD-16.01** `ORG` Cost posture: open-source-first; real costs in infra, inference, SMS/voice, storage, backups, review, support.

## §17–19 Reference architecture, contract, changes
- **TSD-17.01** `XS` Request path: browser/PWA → Next.js (generated OpenAPI client + WS/SSE) → FastAPI API → Service/Domain (→ OPA decision, Temporal start/signal, NATS publish, AI gateway/brain) → Repository → PostgreSQL + pgvector; S3-compatible evidence/report storage; Go Edge Agent → outbound mTLS → connector/control plane.
- **TSD-17.02** `XS` Repository structure: apps/{web, trust-centre}; services/{api, brain, workflows, connectors, notifier, search}; policy/opa; agent; packages/{schemas, ui}; infrastructure/{docker, helm/relyxus, operator, argocd, opentofu/{aws,gcp,azure}, tests/{integration, security, permission, e2e, performance}}. — see Q-24
- **TSD-18.01** `XS` Rules: routes contain no core business logic; repositories no product policy; business rules in service/domain; long-running approvals, clocks, investigations in Temporal; production authorisation/autonomy in OPA/Rego; WebSockets, NATS, Valkey never system of record.
- **TSD-18.02** `XS` Cloud portability: one source tree/release; same signed digest on EKS/GKE/AKS, never rebuilt; one Helm chart; cloud differences in values overlays, OpenTofu roots or provider adapters; AWS/EKS reference, GCP/GKE & Azure/AKS first-class from day one; core code never imports AWS/GCP/Azure SDKs; a cloud is not production-supported until install, upgrade, rollback, backup/restore, scaling, security and failure tests pass.
- **TSD-18.03** `XS` Do not introduce without architecture approval: Django, Node.js backend, MongoDB, Kafka, RabbitMQ, separate vector DB, second ORM, second workflow engine, second broker, second identity system, second chart library, proprietary observability SDK as primary instrumentation, cloud-only service required for self-hosted/air-gapped.
- **TSD-19.01** `XS` Changes vs MPS: add PgBouncer; reference PG 18.6 and compatibility matrix; replicated JetStream; own SCIM boundary; remove MinIO as hard dependency; paid branch protection; Loki/Tempo optional; add Argo CD and OpenTofu; add Valkey.

## §21 Cloud, Kubernetes, infrastructure (authoritative deployment contract)
- **TSD-21.01** `OPS` Portability contract: AWS/GCP/Azure are profiles not products; same signed digest promoted; one Helm chart (provider values may select storage class, ingress, workload identity); differences only in OpenTofu, values overlays, adapters; AWS/EKS reference, GCP/Azure must pass same conformance before advertised; customer/on-prem K8s uses same images + generic profile.
- **TSD-21.02** `OPS` Layering: source → versioned OCI images (signed once) → common Helm chart → K8s workloads → AWS/GCP/Azure/generic profiles; OpenTofu creates infra below K8s only.
- **TSD-21.03** `OPS` Canonical layout infrastructure/{docker/{web,api,brain,workflows,connectors,notifier,search}, helm/relyxus/{values.yaml, values-aws|gcp|azure|self-hosted.yaml}, argocd/{base,aws,gcp,azure}, operator, opentofu/{aws,gcp,azure}/{modules, environments/{dev,staging,production}}}.
- **TSD-21.04** `OPS` `BE` Profile mapping: PostgreSQL (RDS / Cloud SQL / Azure DB or customer PG — app uses PG protocol/SQLAlchemy only); object storage via one ObjectStorage interface; registry mirrored by digest; KMS via security adapters; workload identity (no static cloud keys in pods); ingress; DNS as config; OTel. Managed services are references, substitutable.
- **TSD-21.05** `OPS` Workload contract: web, api, brain, workflows, connectors, notifier, search each ≥ 2 replicas in HA production with scaling signals as listed; OPA ≥ 2 replicas, production actions fail closed if policy decision unavailable; Edge Agent signed binary/optional container, outbound mTLS; DB migrations as a versioned artifact run once per release as a K8s Job before promotion, destructive migrations need backup gate + explicit approval; durable business processes in Temporal, CronJob only for housekeeping.
- **TSD-21.06** `OPS` Mandatory CPU/memory requests/limits from benchmarks; promotion blocked without approved resource budget.
- **TSD-21.07** `OPS` K8s baseline: namespaces (namespace alone insufficient where stronger isolation promised); dedicated SA per workload, no cluster-admin; non-root, no privilege escalation, drop caps, seccomp RuntimeDefault, RO root FS; default-deny NetworkPolicy; startup/readiness/liveness with /ready ≠ /health; replicas + topology spread; PDBs; HPA on measured signals with bounds; rolling maxUnavailable=0; graceful shutdown; no mutable tags; stateless pods.
- **TSD-21.08** `OPS` OpenTofu standard: no proprietary Terraform-only features without ADR; separate provider roots; pinned versions + committed lockfiles; Helm/Argo for K8s apps not OpenTofu; CI-only production applies with plan review and audit; encrypted, locked, versioned remote state per cloud/customer/env; no secrets in .tf/Git/plans/outputs; prevent-destroy on critical resources; fmt/validate/security scan per PR; explicit imports; standard tags.
- **TSD-21.09** `OPS` Environments: local (Compose or local K8s), development, staging, demo (synthetic data), production/customer — each with state and lifecycle rules.
- **TSD-21.10** `OPS` Supply chain: built once per release from reviewed commit; immutable semver + digest, SBOM, scan, signature, provenance; mirror by digest; promotion never rebuilds; customers verify before import; deployment policy rejects unsigned images and mutable tags.
- **TSD-21.11** `OPS` `BE` Networking: private DBs/brokers/workflow backends; limited public ingress; no standing inbound Apporine path; default-deny egress with model, notification, update and licence endpoints as explicit data paths; TLS everywhere, mTLS where required, cert rotation audited; workload identity; OpenBao secrets with KMS/HSM root keys; DNS/certs are configuration.
- **TSD-21.12** `BE` ObjectStorage interface with S3, GCS, Azure Blob adapters only in adapter packages; evidence/report/export logic cannot import provider SDKs.
- **TSD-21.13** `OPS` CI/CD flow: branch → PR → type/lint/unit/contract/policy/workflow/security tests → OCI build → SBOM/scan/sign/provenance → immutable digest → dev → integration/security → staging → upgrade/rollback/load/recovery → conformance → release → Argo CD/customer Helm by digest; customers may skip Argo CD.
- **TSD-21.14** `OPS` Cloud conformance gate: provisioning, install, scale, upgrade, rollback, recovery, failure, security, residency, observability, load.
- **TSD-21.15** `OPS` Customer package: signed image list + digests/signatures/SBOM/provenance; Helm chart + values templates; OpenTofu modules; compatibility matrix; preflight, upgrade plan, rollback, backup/restore runbook, DR drill; network/data-flow guide; release & migration notes; offline bundle for air-gap.
- **TSD-21.16** `OPS` No always-on three-cloud dev clusters; destroy only disposable non-production; production never auto-destroyed.
- **TSD-21.17** `OPS` Acceptance: single release installs on EKS/GKE/AKS with no source change or rebuild; common chart; three OpenTofu roots with separate state and consistent contract; every workload has probes, SA/RBAC, NetworkPolicy, resources, replica rule, metrics; digest-pinned signed images; no core module imports cloud SDKs; no support claim before conformance; banks mirror and install without Apporine shell access.
- **TSD-21.18** `OPS` Implementation lock: build all three cloud profile directories now; AWS/EKS is reference validation; GCP/Azure completed and tested before sold. — see Q-13

## §22 Bank-grade privacy and security architecture
- **TSD-22.01** `BE` Control profiles (not product versions): Secure Core (all, cannot be disabled), Regulated Control Profile, Bank-Grade Control Profile — with listed examples.
- **TSD-22.02** `BE` Every request, query, event, cache key, search document and AI retrieval carries a verified org/workspace security context; client-supplied tenant IDs never trusted as authorisation.
- **TSD-22.03** `BE` Application authorisation AND RLS must both pass; either denying blocks.
- **TSD-22.04** `BE` Sensitive data classified at ingestion and before AI routing; minimisation/redaction before external model, notification, support, export paths.
- **TSD-22.05** `OPS` Dedicated single-tenant DB/cluster/account isolation is a deployment choice, not a separate codebase.
- **TSD-22.06** `BE` Cache, search, analytics never weaken isolation; permission filtering before ranking or retrieval.
- **TSD-22.07** `BE` TLS 1.3 reference; mTLS for Edge Agent trust and optionally internal boundaries.
- **TSD-22.08** `BE` Strong encryption at rest; CMK KMS/HSM for enterprise; envelope encryption or equivalent provider-neutral pattern so business logic never depends on a single cloud KMS SDK.
- **TSD-22.09** `BE` Key rotation non-destructive, auditable, testable; rotation record captures old/new key reference, initiator, approver, scope, timestamps, verification result.
- **TSD-22.10** `BE` Crypto-erasure only when policy permits and all replicas/backups/derived data are inside the key-destruction boundary.
- **TSD-22.11** `BE` Production secrets/encryption material never in Git, images or ordinary logs.
- **TSD-22.12** `BE` Hash-chained audit ledger is system of record for security-sensitive state changes.
- **TSD-22.13** `BE` Verifiable audit export: manifest, hashes, time range, tenant/workspace scope, schema version, signature/attestation.
- **TSD-22.14** `BE` WORM export to customer Object-Lock storage when required; never claim WORM the backing platform does not enforce.
- **TSD-22.15** `BE` Clock synchronisation is a security control: material drift surfaces as degraded health and can block signature-sensitive operations.
- **TSD-22.16** `BE` Audit export is itself audited (actor, reason, scope, destination).
- **TSD-22.17** `BE` No standing Apporine production-data access in self-hosted/air-gap; support JIT, time-bounded, least-privilege, ticket-scoped; dual customer approval for high-risk; immediate revoke; session start/expiry/revocation/effective identity/actions in audit ledger; tamper-evident session report where feasible; screen recording optional and never silent; break-glass customer-controlled, separately logged, auto-expiring.
- **TSD-22.18** `OPS` Backups inherit residency/encryption/retention; backup permissions isolated; immutable retention configurable; restore drills verify isolation, row counts, checksums, evidence chain, secret references, key access, post-restore authorisation; restore env isolated until validated.
- **TSD-22.19** `BE` Residency/egress: every regulated path declares region & data class with config-time and runtime enforcement; deny-by-default egress for bank-grade; private connectivity preferred; AI calls record provider, model, region, prompt version, data-policy decision, fallback path; no training; ZDR preferred/required by policy; air-gap local model.
- **TSD-22.20** `OPS` Regulated release gates: cross-tenant negative tests (API, search, events, notifications, analytics, exports, AI retrieval); key rotation/failure tests; hash-chain & signed-export verification automated; restore drill; supply-chain gates; SAST/DAST + pen testing; residency/egress tests; JIT/support expiry/revocation/audit tests.
- **TSD-22.21** `XS` Never claim SOC 2, ISO 27001/42001, PCI DSS, DORA, UK resilience or other compliance before it is actually achieved; trace controls to obligations without hard-coding legal interpretation.
- **TSD-22.22** `XS` No separate bank/fintech/SaaS codebases; never weaken isolation/encryption/audit/permissions for lower tiers; no cloud-specific KMS/storage/identity/network in core; don't label immutable/air-gapped/CMK-compatible/bank-ready without passing automated tests; customer-policy-dependent behaviour is explicit, validated, audited configuration.

## §23 Commercial licensing and licence-trust architecture
- **TSD-23.01** `BE` One codebase and artifact set; entitlement external to images; licensing never weakens security.
- **TSD-23.02** `ORG` `BE` Apporine License Issuer: internal-only, creates payloads from approved entitlements; customers can never invoke signing.
- **TSD-23.03** `ORG` AWS KMS asymmetric key signs canonical payload bytes; private key never leaves KMS; sign permission restricted and audited.
- **TSD-23.04** `BE` Relyxus License Verifier: verifies signature, schema, validity window, customer/deployment binding, entitlements; runs locally using pinned Apporine public keys.
- **TSD-23.05** `ORG` Entitlement Service: stores rights, limits, contract dates, allowances; source for connected refresh; not required for offline verification.
- **TSD-23.06** `ORG` Admin Control Plane: staff SSO + MFA; privileged changes audited, four-eyes where configured.
- **TSD-23.07** `BE` Licence artifact never in images; canonical, versioned payload machine-validated before signing; envelope includes algorithm + key ID; pinned public key set; rotation overlap.
- **TSD-23.08** `BE` Connected refresh outbound-only when customer permits; offline/air-gapped fully verifiable without internet.
- **TSD-23.09** `BE` State machine: Active, Grace, Expired, Suspended/Revoked with required behaviours (as MPS-29.07, no Superseded row). — see Q-07
- **TSD-23.10** `BE` Asymmetric algorithm supported by AWS KMS; algorithm and key size versioned in schema/ADR.
- **TSD-23.11** `BE` Deterministic signing over canonical bytes; verification rejects altered payloads, unknown schema versions, unsupported algorithms, unknown key IDs, malformed envelopes.
- **TSD-23.12** `BE` Signing server-side only; browser, CLI and CI never receive private key material.
- **TSD-23.13** `BE` Every issue, renewal, suspension, revocation, export and download audit-logged with actor, reason, customer, product, licence revision, correlation ID.
- **TSD-23.14** `BE` Verifier unit tests: positive, tampered, expired, not-yet-valid, wrong-customer, wrong-deployment, wrong-key, rotated-key.
- **TSD-23.15** `BE` Licensing is Apporine platform capability (Product → Customer → Contract/Subscription → Entitlement → License → Deployment); future products reuse issuer with own IDs/entitlement definitions; Relyxus consumes a small verification interface and never calls the ACP directly.
- **TSD-23.16** `XS` Detailed payloads, APIs, admin workflows, key rotation, renewal, procedures governed by the Licensing & Entitlement Spec v1.0 — **if unavailable, do not invent a different licensing design.** — see Q-05

---

# C. Enterprise Deployment, Installation & Infrastructure Specification v1.2 (DEP)

## §1–4 Authority, model, boundaries, artifacts
- **DEP-1.01** `XS` Precedence: on product behaviour MPS wins; on locked technology TSD wins; DEP owns deployment-package boundary, install workflow, artifact contract, hand-off.
- **DEP-1.02** `OPS` Non-goals: no separate AWS/GCP/Azure version; no manual console-built infra; no standing vendor admin access; no customer secrets in Git, Helm values, images, OpenTofu; no "supported" cloud before conformance.
- **DEP-2.01** `OPS` Two packages: A Existing Customer Platform Kit (Apporine: signed release, chart, installer CLI, schemas, verification tooling, docs, SBOM/signatures/provenance; customer: cluster, registry, PG, object storage, identity, secrets/KMS, DNS/TLS/network, credentials) and B Customer Cloud Foundation + Kit (OpenTofu reference foundation + same Package A release).
- **DEP-2.02** `OPS` Package B always ends by invoking the Package A flow; no second installer, no separate images.
- **DEP-3.01** `OPS` Ownership matrix: foundation customer-owned; artifacts published by Apporine, imported by customer; install by customer platform team; DB/backups customer; secrets/KMS customer (Relyxus stores references); support access off by default; upgrade approval customer; production promotion never implicit from image publication.
- **DEP-3.02** `OPS` Self-hosted banks install/operate without inbound firewall access to Apporine.
- **DEP-4.01** `OPS` Release artifacts: images relyxus-{web, api, brain, workflows, connectors, notifier, search}:<semver> with digests; policy bundle relyxus-policy-<v>.tar.gz signed; chart relyxus-<v>.tgz; release manifest release-<v>.yaml (source revision, digests, chart digest, signatures, SBOM/provenance refs, compatibility); never deploy `latest`.
- **DEP-4.02** `XS` Repository/image names are stable interfaces; no ad-hoc names (service1, backend-new, stage2, final-image, cloud copies).

## §5–8 Package A
- **DEP-5.01** `OPS` Kit `relyxus-enterprise-install-kit-<version>.tar.zst` with RELEASE, manifest/{release.yaml, images.lock, compatibility.yaml}, bin/relyxus, charts/relyxus, config/{install-profile.example.yaml, install-profile.schema.json, values.schema.json}, signatures, sbom, provenance, checksums, licenses, docs/{install, upgrade, rollback, backup-restore, airgap, troubleshooting}.md, images/ (offline only); no customer secret.
- **DEP-6.01** `OPS` `BE` Install profile `install.relyxus.io/v1 RelyxusInstallation` (environment, deploymentMode, region, kubernetes, registry, database refs, objectStorage, identity, networking, ai.routePolicyRef) contains identifiers and secret references only.
- **DEP-6.02** `OPS` Profile validation rejects unknown keys, missing fields, unsupported K8s/PG versions, unapproved regions, invalid DNS/TLS, missing object-storage capabilities, unsupported model routing, raw secrets.
- **DEP-7.01** `OPS` Install workflow: release verify → preflight → bundle mirror → config render → config validate → helm lint → server-side dry run → atomic install (`--atomic --wait --timeout 30m`) → relyxus verify → smoke-test → install-report.
- **DEP-7.02** `OPS` A failed step stops with non-zero exit, plain-language explanation, machine-readable error code, safe next action; never continue after failed preflight, signature check, migration gate or readiness.
- **DEP-7.03** `XS` CLI commands are requirements, not claims of existence.
- **DEP-8.01** `OPS` Air-gapped kit contains every image, chart, policy/rule package and approved local-model artifact + signatures/SBOM/checksums; built in CI from the same manifest; verified before load; images imported into internal registry; Helm references only it; no installer step contacts GitHub, Docker Hub, Apporine SaaS, public registries or external model APIs; updates via same signed process with rollback.

## §9–12 Package B / OpenTofu
- **DEP-9.01** `OPS` Package B only when customer lacks conformant platform or asks; account remains customer environment; OpenTofu runs with customer-authorised credentials; kit layout relyxus-cloud-foundation-kit/{manifest, opentofu/{modules/{contract, kubernetes-addons, observability-hooks}, aws|gcp|azure/{modules, environments/{dev,staging,production}, examples}}, policy, tests, docs, package-a/README.pointer}.
- **DEP-10.01** `OPS` OpenTofu layout rules (contract module provider-neutral; provider dirs contain only their provider; environments separate remote state, destroy-protected; examples validate/plan in CI; tests before "supported") and output contract (cluster access metadata, region, registry, DB ref, object storage, secrets/KMS refs, ingress/DNS/TLS, observability).
- **DEP-11.01** `OPS` Cloud reference mapping (EKS/GKE/AKS; VPC/VNet; workload identity; RDS/Aurora, Cloud SQL, Azure DB; ECR/AR/ACR; KMS + secret managers; LB/ingress; DNS; OTel) — substitutable.
- **DEP-12.01** `OPS` OpenTofu rules: pin versions + lockfiles; no opaque mega-module; encrypted remote state; locking; no secrets anywhere; reviewed plan + approval for prod; no laptop prod apply; deletion protection, break-glass destroy; fmt/validate/lint/security/policy before plan; scheduled auditable drift detection; ephemeral envs tagged with owner/purpose/expiry/cost-centre; command sequence fmt → init → validate → plan → approval → apply → output → `relyxus preflight --foundation`.

## §13–16 Kubernetes, Helm, security, CI/CD
- **DEP-13.01** `OPS` Workload table (web, api, brain — no direct production write tools, workflows — deterministic across rollout, connectors — isolation/failure containment, notifier — at-least-once handled in app layer, search — rebuildable index, OPA — pinned bundle, Edge Agent).
- **DEP-13.02** `OPS` Stateful dependencies (PG, object storage, Keycloak, Temporal persistence, NATS) are not automatically in-cluster StatefulSets; profile explicitly chooses customer-managed, managed-cloud or supported self-hosted.
- **DEP-14.01** `OPS` Chart `deploy/helm/relyxus/` with Chart.yaml, values.yaml, values.schema.json (mandatory, rejects unknown/invalid), templates/{web, api, brain, workflows, connectors, notifier, search, policy, ingress, rbac, networkpolicies, pdb, hpa, serviceaccounts, config, tests}; no forks; no secrets in values; deterministic names and labels; sparing hooks — migrations have explicit retry/failure/rollback semantics; deterministic rendering with snapshot/policy tests. — see Q-24
- **DEP-15.01** `OPS` K8s security/availability baseline (namespaces, SA/RBAC, pod security, NetworkPolicy, resources, probes — liveness must not restart on merely degraded dependency, PDB/topology, HPA, graceful termination, digest pinning, stateless storage).
- **DEP-16.01** `OPS` CI/CD: build once; SBOM + provenance; scans; sign digests and release manifest; publish; dev; integration + install-kit tests; staging; EKS/GKE/AKS/OpenShift conformance; human release approval; release manifest. CI is the only publisher; signed manifest ties everything; explicit critical/high vuln policy (block / time-bounded exception / compensating control); production manifest updates reviewed, approved, audited.

## §17–21 Lifecycle, support, conformance, contract, DoD
- **DEP-17.01** `OPS` `relyxus upgrade plan|apply`, `backup verify`, `verify`, `rollback`; plan lists image/chart changes, K8s/API compatibility, migrations, reversibility, backup freshness, policy/rule changes, breaking changes.
- **DEP-17.02** `BE` `OPS` Schema evolution expand/contract; supported rollback never depends on an unsafe reverse migration. — see Q-09
- **DEP-17.03** `OPS` Canary first; automated health/SLO gates; Relyxus verifies backup freshness and restore evidence before destructive migration; DR drills restore into isolated namespace, verify row counts/checksum/hash chain, smoke test, record audit result.
- **DEP-18.01** `OPS` Install ownership: standard self-hosted customer-run (no Apporine access); assisted (temporary approved scoped logged session revoked at completion); air-gapped (no remote access); dedicated Apporine-hosted (Apporine within contracted controls). Hand-off complete only with install report, manifest/digests, runbooks, backup/restore ownership record, known config, admin/SSO access, monitoring integration, documented rollback point.
- **DEP-19.01** `OPS` Conformance matrix (provisioning, install, scale, node disruption, zone/failure, upgrade/rollback N-1→N, backup/restore, security, residency, observability, load); a folder that compiles is not a supported cloud.
- **DEP-20.01** `XS` Implement, don't reinterpret; missing/contradictory → ADR; locked contract (one product/tree/release/images/chart; two packages; Package B rule; profiles AWS/EKS, GCP/GKE, Azure/AKS, OpenShift via A; forbidden list).
- **DEP-21.01** `OPS` Release acceptance: images built/signed/scanned in CI; Package A from manifest installs on a clean conformant cluster; CLI implements verify, preflight, mirror/import, render/validate, verify, smoke-test, install-report with automated tests; air-gapped install with zero internet; Package B roots pass checks and expose output contract; state/approval/least-privilege/destroy protection tested; chart contains workloads, RBAC, NetworkPolicies, PDB/HPA/probes/resources/security contexts and schema validation; profiles supported only after conformance; upgrade/rollback and backup/restore tests pass; hand-off evidence reproducible.
- **DEP-A.01** `OPS` Canonical names: namespace relyxus-system; Helm release and chart `relyxus`; app.kubernetes.io labels; OCI prefix `<registry>/<prefix>/relyxus-*`; OpenTofu roots infrastructure/opentofu/{aws,gcp,azure}; manifest/release.yaml; config/install-profile.yaml; install-report.json.
- **DEP-B.01** `OPS` CLI contract: release verify; preflight (incl. licensing); bundle mirror/import (offline never reaches internet); config render/validate (deterministic, non-secret); verify; smoke-test; install-report (no secrets); upgrade plan/apply; rollback; support-bundle (redacted, reviewed before sharing).
- **DEP-C.01** `OPS` Hand-off checklist (10 items).

## §22 Bank-grade deployment controls
- **DEP-22.01** `OPS` `BE` Machine-readable control-profile manifest per regulated kit (securityProfile, residency.allowedRegions, egress.mode, keys.ownership/hsmRequired, audit.immutableArchiveRequired, supportAccess.mode, backup.isolatedVaultRequired, ai.externalRoutesAllowed).
- **DEP-22.02** `OPS` Additional preflight gates: K8s security, network, identity (no standing local accounts beyond emergency policy), DB isolation (TLS, RLS prerequisites, backup ownership), object storage (encryption, versioning, Object-Lock when required), keys/secrets, residency, time sync.
- **DEP-22.03** `OPS` Package B bank-grade modules (network isolation, private cluster, CMK, isolated backups, approved registry, SIEM hooks, deny-by-default egress); state under customer trust boundary unless contracted; mandatory destroy protection; install command cannot destroy foundations; foundation outputs limited to stable interfaces; core code never consumes cloud details.
- **DEP-22.04** `OPS` Mirroring preserves digest; signature/provenance verified after mirroring; immutable references only; hand-off includes SBOM, attestations, checksums, manifest, matrix, scan status; air-gap bundles exact and verified.
- **DEP-22.05** `OPS` K8s bank-grade baseline (identity, privileges, network, secrets, availability, probes, resources, audit — cluster changes and Relyxus app changes separately auditable).
- **DEP-22.06** `OPS` Backup isolation & recovery gate (separate credentials, residency, customer keys, immutable retention, restore success criteria, quarantine of restored data).
- **DEP-22.07** `OPS` Privileged install/support workflow (customer staff default; Apporine access temporary, approved, ticket-bound, revoked; JIT for troubleshooting with owner/scope/expiry/log; no vendor path for air-gap).
- **DEP-22.08** `OPS` Regulated installation acceptance report: release identity, security profile + deviations, residency map, key ownership, network verification, isolation tests (tenant/workspace negative test + RLS status), backup/restore, audit verification, support access standing status.
- **DEP-22.09** `XS` No compliance by configuration: tooling reports enabled/tested controls, never claims compliance.

## §23 Commercial licence packaging
- **DEP-23.01** `OPS` Kit has `commercial-license/{relyxus.license, license.schema.json, public-keys/apporine-license-signing-<key-id>.pem}` separate from `third-party-licenses/`; never mixed.
- **DEP-23.02** `BE` `OPS` CLI: `relyxus license inspect|verify|install|status|replace`; not documented as available until implemented and tested.
- **DEP-23.03** `OPS` `BE` Package A: preflight verifies release first, then licence envelope, schema, signing key, binding, validity; licence installed as config/secret referenced by deployment; Helm renders only a reference; logs never print full payload with contract metadata; hand-off report records licence ID/revision, key ID, state, expiry.
- **DEP-23.04** `OPS` Package B: OpenTofu never generates/signs licences; state never holds the private key.
- **DEP-23.05** `BE` Connected renewal/revocation: periodic outbound-only, TLS, authenticated, egress-aware retrieval of signed status; revocation signed and cannot execute operations in the cluster; connectivity loss uses cached signed state + grace.
- **DEP-23.06** `BE` Air-gapped renewal by importing a new signed artifact; bounded validity, replacement artifacts, customer-controlled suspension; offline verification validates release signatures and licence signature independently.
- **DEP-23.07** `BE` Licence state in backup/restore planning; restore cannot clone entitlement into unauthorised deployments; restored deployment revalidates binding before becoming writable; DR identifiers explicit in entitlement; migrations use replacement/rebind workflow, no hand edits.
- **DEP-23.08** `BE` `OPS` CI tests verifier with valid, tampered, expired, grace, wrong-customer, wrong-deployment, rotated-key fixtures; conformance tests online and offline verification; air-gap conformance proves install/operate/renew with endpoint blocked; installer fails closed on invalid signature, fails safe on commercial expiry.

---

# D. Master engineering prompt (MP)

- **MP-1.01** `XS` Document authority split: MPS = what; TSD = how engineered; DEP = how packaged/installed; Licensing Spec = commercial entitlements; ACP Spec = Apporine internal admin; UI/UX Spec = supporting frontend authority, cannot override product logic or backend security. Five authoritative + one supporting document expected. — see Q-05
- **MP-1.02** `XS` Read every attached document before code; never infer from filenames; never substitute architecture; never invent behaviour; raise a specification question when unclear.
- **MP-2.01** `XS` On any cross-document conflict STOP and return exact A, exact B, documents/sections, consequence, safest options, recommendation; wait for approval.
- **MP-3.01** `XS` Current phase is RELYXUS BACKEND FOUNDATION; do not begin full AWS production infra, EKS/GKE/AKS, production Helm, Argo CD envs, production OpenTofu, air-gap bundles, or full ACP UI without later approval — but the backend must support all future deployment modes from day one.
- **MP-4.01** `XS` Two systems: A Relyxus (customer product, runs in Apporine-managed, dedicated, customer K8s/cloud, OpenShift, on-prem, air-gapped) and B Apporine Internal Admin Control Plane (products, customers, contracts, entitlements, issuance/renewal/suspension/revocation, deployments, releases, approvals, audit). Never merge; never place ACP in customer K8s; customer production must not depend on ACP reachability; air-gapped Relyxus keeps working on its locally verifiable licence.
- **MP-5.01** `XS` One product, one codebase, one release line, one set of OCI artifacts; no AWS/Azure/GCP/Bank/Fintech/SaaS editions; configurable profiles, policies, integrations, regulatory controls, entitlements; cloud differences underneath, entitlements around, neither in core logic.
- **MP-6.01** `XS` Locked stack (as TSD), changes only via human-approved ADR.
- **MP-7.01** `XS` Prohibited drift list (as TSD-18.03); exception → ADR proposal, never silent.
- **MP-8.01** `XS` Layering API → application/domain services → repository, plus separate Temporal, OPA, eventing, connector adapters, AI gateway, storage abstraction, licence-verification boundary.
- **MP-8.02** `XS` API routes MUST validate transport input, establish authenticated identity, establish tenant/workspace context, call application services, return documented responses/errors; MUST NOT own business rules.
- **MP-8.03** `XS` Domain services own incident transitions, evidence rules, investigation, approvals, action governance, impact logic, product behaviour, authorisation-aware operations.
- **MP-8.04** `XS` Repositories own persistence, transactions, mapping, queries; never product policy.
- **MP-9.01** `XS` API-first flow: requirement → domain model → OpenAPI contract → implementation → generated client/types → frontend integration → tests; no arbitrary endpoints first; authoritative OpenAPI in the shared schema area.
- **MP-9.02** `XS` Inspect existing frontend mocks/provisional contracts; don't copy blindly; compare to MPS; backend contract eventually replaces them. — see Q-04
- **MP-9.03** `XS` Use where applicable: /api/v1 versioning, predictable JSON, RFC 9457 Problem Details, correlation/request IDs, cursor pagination, idempotency keys, ETag/If-Match, explicit concurrency behaviour.
- **MP-10.01** `BE` Tenancy is a security boundary: Organization → Workspace → workspace-scoped data; defence in depth (identity, authz, OPA, RLS, explicit workspace context, permission-aware retrieval); never trust client-supplied tenant/workspace IDs; no cross-tenant access to incidents, evidence, approvals, exports, AI retrieval, analytics, search, notifications, event data, audit records, configuration.
- **MP-11.01** `BE` Design for: tenant isolation, SoD, least privilege, SSO, MFA/step-up, SCIM, JIT, break-glass, customer-controlled support access, CMK, key rotation, crypto-erasure, immutable/verifiable audit, legal hold, residency, retention, deletion workflows, secure backups, restore validation, data minimisation, privacy-aware telemetry, AI privacy, controlled egress, private connectivity, air-gap, supply-chain assurance; compliance needs evidence, not just controls.
- **MP-12.01** `BE` Never licence-gate: encryption, tenant isolation, authn/authz security, audit integrity, secret protection, data protection, secure updates, fundamental vulnerability protections. Licensing may gate only documented commercial capabilities (premium connectors, regulatory content packs, advanced analytics, additional production deployments, premium AI, advanced replay, support tiers). — see Q-08
- **MP-13.01** `BE` Licences not in images; flow entitlement record → License Issuer → signed artifact → customer installation → local License Verifier → entitlements; artifact delivered separately.
- **MP-14.01** `XS` Private signing key never in Relyxus, images, repo, frontend, customer hands, logs or CI artifacts; verifier receives only public verification material.
- **MP-15.01** `BE` Connected licence mode: outbound-only, respects egress, no production data, ACP never in the runtime data path; no permanent remote-control connection.
- **MP-16.01** `BE` Air-gapped licence: local offline verification; offline renewal and entitlement import; never silently call public licensing endpoints; no "phone home or stop working".
- **MP-17.01** `BE` Licence lifecycle exactly as documented: issuance, activation where applicable, active, grace, expired, renewed, suspended, revoked, superseded; never shut down an active incident-response workflow on subscription change unless the spec explicitly requires it. — see Q-07
- **MP-18.01** `ORG` ACP conceptual hierarchy Apporine → Products → Customers → Contracts/Subscriptions → Entitlements → Licenses → Deployments + contacts, releases, approvals, staff, RBAC, audit, operational metadata; not built in this phase; licensing contracts designed so the future ACP can call them safely.
- **MP-19.01** `BE` Multi-product: never hard-code licensing to Relyxus; product-specific entitlements namespaced and versioned.
- **MP-20.01** `BE` Licensing audit for issue, renew, suspend, revoke, entitlement change, deployment-limit change, replace, key rotation, admin override — capturing actor, effective identity, timestamp, reason, previous/new value, customer, product, licence, approval, correlation ID; no destructive silent admin changes.
- **MP-21.01** `BE` AI chain Evidence → Investigation → Hypotheses → Confidence → Recommendation → Policy → Approval → Execution → Verification → Rollback; evidence authoritative, AI is interpretation; provider calls only via gateway; no vendor SDK logic in domain services; telemetry never privileged instructions.
- **MP-22.01** `BE` Storage portability: business operations expressed as store/retrieve/verify evidence, store/retrieve report, apply retention, delete per policy — no provider knowledge.
- **MP-23.01** `XS` Domain modelling: never copy frontend forms into tables; for each entity determine purpose, aggregate/ownership, org scope, workspace scope, lifecycle, authorisation boundary, audit, retention, immutability/versioning, external references, acceptance criteria, data classification.
- **MP-24.01** `XS` Candidate entities to validate against MPS (Organization … Model Route); licensing/Apporine concepts stay in their own bounded context.
- **MP-25.01** `XS` PG rules: SQLAlchemy 2, psycopg 3, Alembic, RLS, explicit transactions; migrations mandatory from day one; never manually mutate schemas; risky evolution explains risk, path, rollback, compatibility, expand/contract.
- **MP-26.01** `BE` Temporal for investigations, approval waits, timers, regulator clocks, retries, long-running actions, durable transitions; NATS for distribution/replay, never durable workflow state; OPA for documented policy/authorisation (no autonomy policy in ad-hoc Python conditionals); Valkey for cache, rate limits, ephemeral state, never system of record.
- **MP-27.01** `BE` Versioned domain events (e.g. incident.declared.v1, approval.requested.v1, approval.granted.v1, action.executed.v1) with schema version, tenant/workspace, entity ID, actor/effective identity, timestamp, correlation ID; never publish secrets.
- **MP-28.01** `XS` Observability day one: structured logging, correlation IDs, OTel, Prometheus, /health, /ready, service metrics; never log passwords, tokens, private keys, secrets, raw credentials, unnecessary sensitive incident data.
- **MP-29.01** `XS` Container-ready: no local persistent disk, single-host, sticky-session, static-IP assumptions; no embedded secrets/licences; no cloud metadata dependency; no provider assumptions in domain; stateless where practical.
- **MP-30.01** `OPS` Package A/B produce identical application behaviour; backend must not care which created the environment.
- **MP-31.01** `OPS` Commercial licence packaging separate from third-party notices; licences external to images; follow DEP layout.
- **MP-32.01** `OPS` Release flow source → tests → build → digest → SBOM → scans → signature → provenance → registry → promotion → deployment → verification; no mutable `latest`.
- **MP-33.01** `XS` Testing contract: unit (domain), integration (repos/services/DB), contract (OpenAPI), permission (tenant/workspace/role), RLS, OPA, Temporal (determinism, retries, timers, versioning), security (restricted data), licensing (valid/invalid signature, tampered, expired, grace, entitlement enforcement, offline, schema version, renewal, revocation), E2E; regression test for security-sensitive fixes.
- **MP-34.01** `XS` Errors: no broad exception hiding; keep internal context; safe client info; correlation IDs; no secrets; distinguish validation, authentication, authorisation, conflict, dependency failure, policy denial, licence problem, internal failure; never report success when a required downstream operation failed.
- **MP-35.01** `XS` No microservice without justification (independent scaling, trust boundary, runtime, durable worker, failure domain, ownership); follow documented service map.
- **MP-36.01** `XS` Repository direction: preserve existing repo; target relyxus/{apps/{web, trust-centre}, services/{api, brain, workflows, connectors, notifier, search}, policy/opa, agent, packages/{schemas, ui}, infrastructure/{helm, operator, argocd, opentofu, docker}, tests/{unit, integration, contract, permission, security, e2e, performance}, docs/{spec, adr}}; propose before moving files. — see Q-04, Q-24
- **MP-37.01** `XS` ACP repository placement (Apporine monorepo app vs separate repo) must be proposed when that phase starts; do not guess.
- **MP-38.01** `XS` Git: no direct pushes to main; short-lived meaningful branches (feat/…, fix/…, test/…, refactor/…); conventional scoped commits (e.g. `feat(incidents): …`); no meaningless names/messages.
- **MP-39.01** `XS` Careful human review for authn, authz, RLS, OPA, production actions, evidence integrity, audit, cryptography, licence signatures, entitlement enforcement, secrets, migrations, support access, customer-data boundaries.
- **MP-40.01** `XS` Phase 1 activities A–T (inspect repo, read docs, frontend, mocks, mapping, bounded contexts, service boundaries, tenancy, OpenAPI strategy, PG/RLS, migrations, Temporal/NATS/OPA responsibilities, evidence & audit foundations, AI gateway, storage, licensing boundary, Relyxus vs ACP, local dev, testing, spec gaps); no implementation code until plan approved.
- **MP-43.01** `XS` First response format: 18 sections (repo state … phases not started). — see Q-12
- **MP-41.01** `XS` Licensing order: domain model → schema → entitlement model → trust model → Issuer boundary → Verifier boundary → DB → API → audit → tests → offline workflow → connected workflow → Relyxus integration → ACP UI; no "Generate License" button before signing/entitlement architecture is correct.
- **MP-42.01** `ORG` ACP order when approved: A foundation & auth, B products & customers, C contracts, D entitlements, E licence issuance/renewal/revocation, F deployments, G releases, H approvals, I audit, J dashboards; follow ACP spec for UI/UX/security/AWS; no new design system.
- **MP-44.01** `XS` Per approved step: state spec requirement, architecture decision, files changed; implement; tests; run tests; lint/type checks; report exact results and unresolved issues; stop before next major phase.
- **MP-44.02** `XS` Never say "passed" unless it passed; never claim enterprise-ready, cloud support, air-gap support, or licensing security without the corresponding tests passing.
- **MP-45.01** `XS` Definition of done: behaviour, API contract, persistence, authorisation, tenant isolation, audit, error behaviour, observability, passing tests, migrations, security review, acceptance criteria; licensing additionally crypto verification, tamper rejection, expiry, entitlements, offline, audit, key-rotation compatibility.
- **MP-46.01** `XS` No false completion (folder ≠ feature; Helm chart ≠ support; verifier class ≠ secure licensing; audit table ≠ verifiable audit; RLS file ≠ proven isolation; Dockerfile ≠ production-ready; documented control ≠ implemented).
- **MP-47.01** `XS` Core principle: build once, package once, deploy the same product everywhere; licences separate from images; security never premium; customer governance customer-controlled; Apporine administration separate from customer production.

---

# D2. Apporine Licensing & Entitlement Architecture Specification v1.0 (LIC)

Scope note: `ACP` marks items that live in the Apporine Admin Control Plane / issuer side (system B, MP-4.01), not in the Relyxus runtime.

## §1–3 Authority, philosophy, system context
- **LIC-1.01** `XS` Implementation authority for Apporine commercial licensing across Relyxus and future products: creation, signing, delivery, verification, renewal, suspension, revocation, audit; separate from customer runtime business logic and from third-party licence notices.
- **LIC-1.02** `OPS` Customer-specific licences never embedded in OCI images; release built once; entitlement supplied as a separate signed artifact.
- **LIC-2.01** `XS` One Apporine licensing platform serves multiple products.
- **LIC-2.02** `OPS` One release serves multiple customers without rebuilding images.
- **LIC-2.03** `BE` Universal security is never a paid feature gate.
- **LIC-2.04** `BE` Offline verification is a first-class requirement.
- **LIC-2.05** `BE` Commercial enforcement never destroys customer data or makes an active incident unsafe.
- **LIC-2.06** `BE` `ACP` Every privileged licensing action is attributable, reviewable, auditable.
- **LIC-3.01** `ACP` Flow: administrators use the Admin Control Plane → Control API validates permissions and contract state → Entitlement Service determines rights → License Issuer canonicalises payload and asks AWS KMS to sign → artifact stored and delivered → Relyxus verifies locally with the public key set → connected deployments may refresh signed status; air-gapped need no Apporine connectivity.
- **LIC-3.02** `XS` Boundaries: control plane holds customer/product/contract metadata, entitlements, licence records, audit — never customer production secrets or broad cloud credentials; signing boundary holds payload hash, KMS key ID, signing request — never exportable private key; customer deployment holds signed artifact, public keys, local verification state — never the private key; OCI image holds generic code only — never customer licence, identifiers or secrets.

## §4 Canonical data model (control plane)
- **LIC-4.01** `ACP` Product: commercial product; has entitlement definitions and releases.
- **LIC-4.02** `ACP` Customer: legal/commercial organisation; has contracts, deployments, licences, contacts.
- **LIC-4.03** `ACP` Contract/Subscription: term, start/end, renewal, support tier; controls entitlement eligibility.
- **LIC-4.04** `ACP` `BE` Entitlement Definition: named capability or quantitative allowance; versioned per product.
- **LIC-4.05** `ACP` Customer Entitlement: customer-specific capability/limit derived from approved contract/order.
- **LIC-4.06** `ACP` `BE` Deployment: named authorised runtime instance/environment bound to customer, product, licence.
- **LIC-4.07** `ACP` License: logical commercial authorisation record with immutable revisions.
- **LIC-4.08** `ACP` `BE` License Revision: signed point-in-time artifact metadata — payload hash, key ID, validity, state, artifact URI.
- **LIC-4.09** `ACP` Approval Request: four-eyes workflow linking actor, reviewer, reason, target.
- **LIC-4.10** `ACP` Audit Event: append-only evidence correlating user, request, object, outcome.

## §5 Licence artifact format
- **LIC-5.01** `BE` Versioned signed envelope.
- **LIC-5.02** `BE` Logical fields: schema_version, license_id, revision, customer_id, product_id, deployment_bindings, issued_at, not_before, expires_at, grace_policy_id, entitlements, limits, support_tier, key_id, signature.
- **LIC-5.03** `BE` Payload canonicalised before signing; exact JSON/CBOR representation locked by schema and tests, not ad-hoc serialisation.
- **LIC-5.04** `BE` Never include passwords, customer API keys, cloud access keys, DB credentials, private signing keys or operational secrets.

## §6 Signing-key architecture
- **LIC-6.01** `ACP` Production signing with an AWS KMS asymmetric key in the Apporine production account.
- **LIC-6.02** `ACP` Private key non-exportable; applications may request signatures, never read the key.
- **LIC-6.03** `BE` `ACP` Separate dev/staging/prod signing keys; non-production licences must not verify as production licences.
- **LIC-6.04** `BE` Public keys distributed as a versioned key set with key IDs; verifier supports overlapping keys during rotation.
- **LIC-6.05** `ACP` Signing IAM limited to the issuer runtime role; humans cannot call KMS Sign from browsers.
- **LIC-6.06** `ACP` CloudTrail + application audit evidence for every KMS signing operation.

## §7 Licence state machine
- **LIC-7.01** `ACP` Draft: entitlements prepared, not approved; cannot be delivered or verified as active.
- **LIC-7.02** `BE` Issued/Active: approved, signed, current time valid → normal entitlement enforcement.
- **LIC-7.03** `BE` Grace: past term, within allowed grace → safety functions continue; warnings; restricted commercial changes.
- **LIC-7.04** `BE` Expired: grace ended → no data deletion; block defined new commercial/configuration operations; renewal available.
- **LIC-7.05** `BE` Suspended: temporary hold → connected enforcement after signed refresh; customer-facing reason code.
- **LIC-7.06** `BE` Revoked: authorisation withdrawn → connected deployments enforce signed revocation; offline uses bounded validity/replacement.
- **LIC-7.07** `BE` Superseded: replaced by a new revision; old revision remains in audit history.

## §8 Issuance workflow
- **LIC-8.01** `ACP` Steps: create/verify Customer & Product; record signed contract/order and term; configure entitlements and deployment allowance; policy validation (dates, incompatible options, duplicate deployment, support tier, product version); second approver per policy; issuer builds canonical payload and requests KMS signature; store artifact, payload hash, key ID, actor, approval, correlation ID; deliver via connected or offline channel; customer/verifier validates before installation; record delivery/activation acknowledgement where supported.

## §9 Renewal, suspension, revocation
- **LIC-9.01** `ACP` `BE` Renewal creates a new immutable revision; signed artifacts never edited.
- **LIC-9.02** `ACP` Revocation requires reason, authorisation, audit evidence; high-impact revocation requires four-eyes.
- **LIC-9.03** `BE` Connected revocation published as signed status/entitlement data; customer environments never accept an unsigned kill command.
- **LIC-9.04** `BE` Air-gapped revocation is not instantaneous: bounded validity, contract procedure, replacement artifact; limitation documented honestly.
- **LIC-9.05** `ACP` Reinstatement generates a new revision; history immutable.

## §10–12 Connected, air-gapped, deployment binding & DR
- **LIC-10.01** `BE` Relyxus verifies the local licence at startup and periodically according to policy.
- **LIC-10.02** `BE` If outbound licensing allowed, a dedicated client retrieves signed entitlement/revocation metadata from licensing.apporine.com or approved regional endpoint, sending only minimal identifiers, never incident/evidence data.
- **LIC-10.03** `BE` Connectivity loss uses cached signed state and grace policy; never a remote-control tunnel.
- **LIC-11.01** `ACP` `OPS` Air-gap: licence signed in production control plane; delivered via customer-approved offline channel with checksums/signing metadata.
- **LIC-11.02** `BE` Customer imports the file; Relyxus verifies entirely locally with distributed public keys; renewal repeats import; no internet dependency.
- **LIC-12.01** `BE` Licences bind to logical deployment IDs, never pod/container IDs.
- **LIC-12.02** `BE` Production, non-production and DR allowances are explicit entitlements.
- **LIC-12.03** `BE` Cluster rebuild under the same approved deployment identity restores the licence according to policy.
- **LIC-12.04** `ACP` `BE` Migration to a materially new deployment/customer environment requires rebind/reissue; no hand-edits.
- **LIC-12.05** `BE` DR activation can be pre-authorised in the entitlement.

## §13 Entitlement model
- **LIC-13.01** `BE` Universal security (encryption, tenant isolation, authN/Z, audit integrity, secure updates): always on, never sold as optional.
- **LIC-13.02** `BE` Commercial feature (advanced compliance packs, premium connectors, replay/analytics): enabled by entitlement.
- **LIC-13.03** `BE` Capacity/quantity (production deployments, non-prod deployments, seats): explicit numeric limit enforced without breaking safety.
- **LIC-13.04** `BE` Support tier (Standard/Premium/Enterprise): controls support SLA, not product security.
- **LIC-13.05** `BE` Regulatory content (jurisdiction rule packages): entitled and versioned; legal validation separate.

## §14 Admin roles
- **LIC-14.01** `ACP` Roles: Viewer/Support Read (view only); Commercial Ops (contracts, proposed entitlements; cannot sign alone); License Operator (create issuance/renewal requests; cannot bypass approval); Approver (cannot approve own request under SoD); Security Admin (key metadata/policies; cannot export private key); Super Admin (emergency only; logged; break-glass).

## §15 APIs and commands
- **LIC-15.01** `ACP` Control API (illustrative): POST /v1/licenses, POST /v1/licenses/{id}/renew, /suspend, /revoke, GET /v1/licenses/{id}, GET /v1/customers/{id}/entitlements; mutating admin APIs idempotent and audited.
- **LIC-15.02** `BE` Public/runtime API exposes only minimum signed status/refresh endpoints for connected deployments.
- **LIC-15.03** `BE` CLI: `relyxus license inspect|verify|install|status|replace`. ≡ DEP-23.02

## §16–17 Audit, security, privacy
- **LIC-16.01** `ACP` Append-only audit events for every material change; exportable licence history (revisions, actors, approvals, delivery, status changes); WORM-capable exports; correlate with CloudTrail/KMS evidence; material changes create new revisions.
- **LIC-17.01** `ACP` Staff SSO + MFA; least privilege; no shared admin accounts; separate prod/non-prod data and keys; customer metadata minimisation; no customer incident data in licensing platform; encryption at rest/in transit; Secrets Manager; KMS; rate limiting and WAF for external endpoints.
- **LIC-17.02** `BE` `ACP` Threat model covers licence forgery, replay, downgrade, stolen artifact, wrong-customer use, compromised admin account.

## §18 AWS reference implementation
- **LIC-18.01** `ACP` `OPS` Admin web Next.js on ECS Fargate behind ALB/WAF; Control API/issuer FastAPI on ECS Fargate; RDS PostgreSQL Multi-AZ; KMS asymmetric key; Secrets Manager; S3 with versioning/Object Lock; CloudTrail, CloudWatch, OTel/Prometheus export; Route 53 + ACM for admin.apporine.com / licensing.apporine.com.

## §19–21 Testing, sequence, done
- **LIC-19.01** `BE` Golden-vector tests for canonicalisation and signatures.
- **LIC-19.02** `BE` Tamper, expiry, clock skew, wrong customer/deployment and key-rotation tests.
- **LIC-19.03** `BE` Connected endpoint outage and stale-cache tests.
- **LIC-19.04** `OPS` Air-gap installation and renewal with all internet blocked.
- **LIC-19.05** `ACP` RBAC/SoD tests for admin APIs.
- **LIC-19.06** `ACP` Audit completeness tests: every mutation produces required evidence.
- **LIC-19.07** `BE` Load test issuance/verification; verifier stays cheap and local.
- **LIC-20.01** `XS` Sequence: 1 schemas/data model + ADR for envelope/canonicalisation; 2 local verifier library + exhaustive tests; 3 entitlement service + issuer API with non-production KMS key; 4 admin screens; 5 connected refresh endpoint/client; 6 air-gap packaging/renewal tooling; 7 production KMS, approvals, audit/WORM, DR, runbooks.
- **LIC-21.01** `XS` Done: no customer-specific image builds; private key unreachable from client code; valid/invalid artifacts behave exactly as documented; connected and air-gapped conformance tests pass; renewal/revocation history immutable and auditable; production licences issued only by authorised staff through the governed control plane; Relyxus keeps safe incident handling under expiry/failure per MPS.

---

# E. Open questions, conflicts and gaps

`BLOCKING` = I cannot derive the feature plan (step 3) or write the affected code correctly without an answer. Everything else has a recommended default that I will **not** apply until you confirm it.


## E0. Decisions taken (2026-10-14)

The product owner accepted the recommendations for these questions. They are recorded in ADR-0001 (Q-04, Q-14, Q-29, Q-31) and ADR-0003 (Q-01, Q-02, Q-03, Q-09, Q-15, Q-16, Q-18, Q-19, Q-20, Q-21, Q-22).

Still open: Q-07a, Q-08, Q-10, Q-11, Q-17, Q-23, Q-24, Q-26, Q-27, Q-28, Q-32, Q-33, Q-34.

## E1. Conflicts between context.md (HOW) and the specifications

**Q-01 `BLOCKING` Response and error envelope.**
- A: context.md §5 — every response is `{ "success": true, "data": {…}, "meta": {…} }` / `{ "success": false, "error": { "code", "message" } }`.
- B: MPS-22A.04 (p.76) "errors as RFC 9457 problem details with a correlation ID"; MP-9.03 "RFC 9457 Problem Details".
- Consequence: RFC 9457 defines the error body itself (`type`, `title`, `status`, `detail`, `instance` + extensions, `application/problem+json`). The two shapes can't both be the error format.
- Options: (a) RFC 9457 for errors (with a stable `code` and `correlation_id` extension, satisfying context.md §8's "stable machine-readable code") + context.md success envelope `{success, data, meta}`; (b) RFC 9457 errors and bare resource bodies on success; (c) context.md envelope everywhere and drop RFC 9457.
- Recommendation: **(a)**. It meets the spec's error contract and keeps context.md's success shape and machine codes.

**Q-02 `BLOCKING` Pagination.**
- A: context.md §5 — `?page=1&limit=20`, `meta: { page, limit, total, totalPages }`.
- B: MPS-22A.04 "cursor pagination"; MP-9.03 "cursor pagination". Also MPS-15.07: a restricted incident must never appear "not even as a count".
- Consequence: offset pages with `total` are a different contract, and a `total` computed before permission filtering would leak the existence of restricted incidents.
- Recommendation: cursor pagination `?cursor=…&limit=…` (limit capped at 100, per context.md), `meta: { next_cursor, limit }`, and no `total`.

**Q-03 `BLOCKING` OpenAPI authoring direction and location.**
- A: MPS-22A.03 "every endpoint is written in the OpenAPI file before code; server stubs and typed clients are generated from it"; MP-9.01 "authoritative OpenAPI contract belongs in the shared schema area" (`packages/schemas`, OpenAPI 3.1).
- B: context.md §6 allows spec-from-code *or* validation-from-spec, but never both by hand. FastAPI's native mode is code-first, and context.md's example uses OpenAPI 3.0.3.
- Options: (a) spec-first — hand-author `packages/schemas/openapi/api.yaml` (3.1), generate Pydantic models with datamodel-code-generator, and have CI verify the FastAPI app's emitted spec matches; (b) code-first — Pydantic/FastAPI is the source, CI exports the spec to `packages/schemas` and fails on uncommitted drift.
- Recommendation: (a) follows MPS literally but adds codegen friction; (b) is idiomatic FastAPI but departs from "written before code". **This is your call.** I lean (b) plus a contract-review step (the exported spec diff is reviewed in every PR) only if you accept that departure.
- Also confirm: Swagger UI at `/docs` and the raw spec at `/docs.json` (context.md), disabled in production.

**Q-14 `BLOCKING` Naming conventions vs Python.**
- A: context.md §4 — variables/functions `camelCase`, files `kebab-case`, layout `user.controller`, `user.service`.
- B: Locked stack is Python + Ruff (TSD-6.01, MP-6.01). Python cannot import modules with hyphens (`user-service.py` is not importable), and Ruff's pep8-naming rules (N802/N806/N815) reject camelCase functions and variables.
- Recommendation: PEP 8 inside Python: `snake_case` modules, functions and variables; `PascalCase` classes; `UPPER_SNAKE_CASE` constants. Keep context.md's feature-module grouping, e.g. `modules/incident/{controller,service,repository,model,schema}.py`. Keep the `is_/has_/can_/should_` boolean prefixes and verb-first function names.

**Q-09 Migration reversibility.**
- A: context.md §9 "Migrations are forward-only".
- B: TSD-6.01 "Alembic: reviewed, forward/backward planned"; MP-25.01 "explain rollback"; DEP-17.02 / MPS-6A.08 "rollback never depends on an unsafe reverse migration; schema backward-compatible for one version".
- Recommendation: forward-only in every shared environment, using expand/contract so version N-1 runs on schema N. Each migration documents its rollback plan in its docstring. `downgrade()` is implemented only for non-destructive dev convenience and never run in production.

**Q-15 JSON field casing** (context.md says pick one).
- The specs use snake_case for licence fields (`license_id`, `schema_version`, MPS-29.06) and camelCase for the install profile (`deploymentMode`, DEP-6.01).
- Recommendation: `snake_case` across the REST API and events.

## E2. Missing or version-mismatched source documents

**Q-05 Missing source documents — partly resolved 2026-10-14.**
- Licensing & Entitlement Architecture Spec v1.0 **received** (section D2, `LIC-` IDs). Licensing work is unblocked.
- Still missing: Apporine Internal Admin Control Plane Spec v1.0 (needed before any issuer/ACP work) and Relyxus UI/UX Master Design Spec v2.0 (supporting).

**Q-06 Document version references.**
- MPS p.1 says "Version 2.2 is the single source of truth" (inside the v2.3 document), and p.1, p.90 and p.97 name Tech Stack **v1.2** and Deployment **v1.1**. MPS §29.11 (p.100) names TSD **v1.3** and DEP **v1.2**, which are the versions supplied.
- Recommendation: treat MPS v2.3, TSD v1.3 and DEP v1.2 as the authoritative set.

## E3. Ambiguities and contradictions inside the specifications

**Q-07 Licence states and grace — partly resolved by LIC §7.**
- LIC-7.01–7.07 defines seven states: Draft, Issued/Active, Grace, Expired, Suspended, Revoked, Superseded. Treated as authoritative for licensing.
- Still open (a): which operations are "restricted commercial changes" (Grace) and "defined new commercial/configuration operations" (Expired)? MPS-6A.11 names "configuration changes and upgrades" after grace. No document gives the list. The verifier only *reports* the state; enforcement waits for this answer.
- Still open (b): the payload carries `grace_policy_id` (LIC-5.02), but no document defines the policies. Provisional: one policy `standard-30d` = 30 days (from MPS-6A.11), and unknown IDs are rejected. See ADR-0002.

**Q-32 Signature algorithm (LIC-5.03, TSD-23.10 say "versioned in schema/ADR").** Provisional ECDSA P-256 / SHA-256, which AWS KMS supports (`ECC_NIST_P256`, `ECDSA_SHA_256`). The envelope carries an `algorithm` field so it can change later. Confirm with Apporine security. See ADR-0002.

**Q-33 Public-key trust anchor.** The spec says keys are "pinned" (TSD-23.04), but the install kit ships `public-keys/*.pem` (DEP-23.01), which a customer could swap. Provisional: the verifier trusts only a key set passed in by the runtime. The runtime builds that set from keys embedded in the signed release; kit files are informational. Each key carries an `environment` so non-production keys cannot verify production licences (LIC-6.03). Needs confirmation before service integration.

**Q-34 Issuer / Control Plane placement (MP-37.01).** The issuer, entitlement service and KMS signing are Apporine system B. They are not built in this repo until you decide monorepo-app vs separate repo, and the ACP spec arrives. Tests use an in-memory test signer only.

**Q-08 Which capabilities are entitlement-gated?** LIC-13.01–13.05 now gives the categories (commercial feature, capacity, support, regulatory content) but no concrete entitlement keys for Relyxus. The verifier exposes generic namespaced keys; the Relyxus entitlement catalogue is still needed.

**Q-10 Action lifecycle state count.**
- The caption says "11 states, 1 policy decision" (p.31). The diagram shows 10 state boxes: Proposed, Blocked by policy, Allowed automatically, Waiting for approvers, Rejected or expired, Dry run & pre-checks, Executing, Verifying, Rolled back/escalated, Succeeded & closed. The kill switch "can cancel any state".
- Is "Rejected or expired" two states? Is "Cancelled (kill switch)" a state? Phase 2, so not blocking now.

**Q-11 `BLOCKING` (incident lifecycle is Phase 0) Incident lifecycle gaps.**
- (a) Cancelled: the diagram (p.24) draws Cancelled only from Triage and Investigating, but the table (p.25) says "Any open state → Cancelled". Which is right?
- (b) Is **Triage** the state of an incident that exists but isn't declared yet? That covers auto-grouped alerts and the "Save draft" button on the Declare page (MPS-15.04). Who may create an incident in Triage, and with which minimum fields?
- (c) What exactly is "acknowledged" (timestamp MPS-8A.20): a separate action, or the first IC assignment?

**Q-18 `BLOCKING` Role assignment model.**
- MPS-14.01: "permissions follow the team and the workspace".
- MPS-20.06: "Role and Permission … assigned to users per workspace", with "conditions (environment, region)".
- MPS-20.04: User has "many roles".
- Are roles granted to users per workspace, to teams (members inherit), or both? Are role conditions (environment, region) attribute-based constraints evaluated in OPA?
- Recommendation: both. Direct user–workspace grants and team grants are unioned, and conditions are evaluated in OPA.

**Q-19 `BLOCKING` Audit/evidence hash-chain design.**
- The specs require hash chaining (MPS-14.16, MPS-20.15, MPS-20.25) but don't specify:
  - chain scope (global, per organisation, or per workspace)
  - whether the evidence ledger and the audit log are one chain or two
  - the hash algorithm and canonical serialisation
- Phase is also inconsistent: MPS §14 table says Ph2; the phase plan p.79 says Ph3. Audit events themselves are required from Ph0 (MPS-22A.14).
- Recommendation: two chains (audit log, evidence ledger), each scoped per workspace, plus an organisation-level audit chain for org-scoped records. SHA-256 over RFC 8785 canonical JSON, with chain appends serialised by a per-chain row lock. Build it in the foundation phase.

**Q-20 Organisation-scoped vs workspace-scoped records.**
- MPS-20.01 says every table carries org *and* workspace IDs. But Organisation, User (spans workspaces), org-level policies (MPS-10.18 level 2) and the org-wide kill switch are not workspace-scoped.
- Recommendation: `organization_id` is always required; `workspace_id` is required on workspace-scoped tables and absent on org-scoped tables. RLS policies are written for both scopes.

**Q-21 How the workspace context travels in requests.**
- The spec is silent. context.md allows at most 2 levels of nesting, so `/workspaces/{id}/incidents/{id}/tasks` is not allowed.
- Recommendation: header `X-Relyxus-Workspace-Id`, always verified against the caller's memberships (never trusted, per MP-10.01). Resources stay top-level, e.g. `/api/v1/incidents/{id}/tasks`.

**Q-22 Incident "number" (MPS-20.12) vs context.md "never sequential integers as public IDs".**
- Recommendation: a UUIDv7 `id` is the only identifier. A per-workspace display number (e.g. `INC-1042`) is a non-identifying field and is never accepted as a lookup key on restricted paths.

**Q-16 `BLOCKING` (affects the auth skeleton, Phase 0) Identity before SSO.**
- SSO and SCIM are Phase 3 (MPS-14.10/11). Phase 0 has an "auth skeleton" (p.79). The Sign-in page needs "email sign-in for small teams" (MPS-15.02). Google sign-in is Ph0–1 (MPS-16.02). Keycloak is locked (TSD-9.01).
- Recommendation: from day one the API only accepts OIDC access tokens issued by Keycloak (Keycloak runs in Docker Compose locally). "Email sign-in" means Keycloak local accounts. Google is a Keycloak identity provider. Relyxus never stores passwords.

**Q-17 SaaS multi-region residency topology.**
- One organisation's workspaces may each have their own residency region (MPS-14.01). Data must stay in-region, but "global metadata may be global" (MPS-17.17).
- Nothing says how a SaaS deployment places data: one regional cell per region plus a global metadata plane, or something else.
- Not blocking for the foundation if `workspace.region` is modelled now. Needed before SaaS multi-region work.

**Q-23 "Same six steps" for every connector (MPS-7.03, p.15) vs the 8-step Prometheus flow (p.17).**
- Recommendation: treat "six" as the six-verb pattern from MPS-7.22 / §16 (add, test, scope, map, policy, remove). Not blocking.

**Q-24 Repository paths disagree between documents** (needed before infrastructure work, not now).
- Helm chart: `deploy/helm/relyxus/` (MPS-27.08, DEP-14.01, MPS-22A.02) vs `infrastructure/helm/relyxus/` (TSD-17.02, TSD-21.03, MP-36.01).
- Tests: root `tests/` (MPS-22A.02, MP-36.01) vs `infrastructure/tests/` (TSD-17.02).
- `rule-packages/` appears only in MPS-22A.02.

**Q-26 Local S3-compatible storage.**
- MPS-22.08 says "MinIO when self-hosted"; TSD-7.02 says MinIO must not be a hard dependency (archived, AGPLv3).
- Recommendation: TSD wins. Tests use an in-process S3 mock (moto); local dev uses an S3-compatible emulator chosen in an ADR. MinIO is not baked in anywhere.

**Q-28 Terraform provider for customer config-as-code (MPS-14A.04) vs OpenTofu as the infra IaC engine.**
- A provider works with both tools. Timing is already an open question in MPS-25.03. Phase 3, not blocking.

## E4. Scope and process

**Q-04 `BLOCKING` Repository shape.**
- This repo is `relyxus-backend` and contains only `README.md`, `context.md` and `important/`.
- The specs mandate one private monorepo `relyxus/` with `apps/web`, `services/*`, `policy/`, `agent/`, `packages/schemas` and more (MPS-22A.02, TSD-14.04, TSD-17.02, MP-36.01). MP-9.02 asks me to inspect the existing frontend, and there is none here.
- Questions:
  - (a) Where is the frontend?
  - (b) Should this repo be laid out as the monorepo's backend half (`services/api`, `services/workflows`, `packages/schemas`, `policy/opa`, …)? Or is the plan to merge into one `relyxus` monorepo later?
  - (c) Should context.md's `src/modules/…` structure apply inside each service, e.g. `services/api/src/relyxus_api/modules/incident/…`?
- Recommendation: (b) monorepo-shaped layout, with context.md's module structure inside each service.

**Q-13 `BLOCKING` What "the plan" and implementation cover.**
- The register spans six phases / 52 weeks, plus frontend, infrastructure and organisational items.
- MP-3.01 restricts current work to the backend foundation and forbids starting production Helm, OpenTofu, Argo CD and air-gap work. TSD-21.18 says "build all three cloud profile directories now"; that conflicts with MP-3.01 unless it means empty scaffolds.
- Proposal:
  - Step 3 maps **every** requirement to exactly one feature, including non-backend "features" such as *Frontend console*, *Deployment packaging*, *Organisational/commercial*, so nothing is dropped.
  - Step 4 breaks only the approved phase into PRs: **Backend Foundation = MPS Phase 0 backend scope (MPS-23.02 Ph0, MPS-23.05) + MP-40 items**.
  - Later phases get PR breakdowns when you approve them.

**Q-12 Process vs master prompt §43.**
- MP-43.01 requires the first response to be an 18-section architecture review. Your workflow (requirements → questions → features → PRs → plan) supersedes that.
- Recommendation: fold all 18 sections into the step 5 plan document so both are satisfied. Confirm.

**Q-27 Local development stack.**
- Recommendation: Docker Compose grows per PR (PostgreSQL 18 + pgvector first; then Keycloak, OPA, Temporal, NATS, Valkey, OpenBao as features need them), rather than all at once.

**Q-29 Python version.**
- TSD-6.01 says "current supported CPython line approved by the release train" but pins nothing. This machine has Python 3.10.
- Recommendation: Python 3.13, pinned via `.python-version` and in container base images.

**Q-30 GitHub actions on your behalf.**
- context.md §14 cycle: push, open PR into `develop`, link ticket, CI, review, squash merge.
- Should I push branches and open PRs with `gh`, or keep local branches for you to push? Is there a ticket tracker to link in PR descriptions?
- I will never merge my own PRs (context.md §14).

**Q-31 The `important/` folder.**
- It is untracked. MPS-22A.15 says to keep the spec in `docs/spec` as markdown.
- Should the source PDFs/DOCX (marked "Confidential") be committed, or only this register and markdown extracts? Or neither?

**Q-35 Task priority values (MPS-11.14).** The spec lists "priority" for live tasks but defines no scale. Provisional: `high` / `medium` / `low`, default `medium` (I8). Confirm or replace.

**Q-36 Can done or cancelled tasks reopen?** MPS-11.15 lists the statuses but no transitions between them. Provisional: done and cancelled are final; a new task is created instead (I8).


**Q-37 Which follow-ups are mandatory by default? (MPS-13.17)** The closure gate counts "mandatory follow-ups" for SEV1/SEV2 but the spec does not say what makes one mandatory. Provisional: `is_mandatory` defaults to true on SEV1/SEV2 incidents and false otherwise; anyone who can write incidents can change it (I14). Confirm, or name who may mark a follow-up optional.

**Q-38 Default required reviewers (MPS-13.13).** The spec defaults SEV1 reviewers to the incident commander, service owner and Head of SRE, plus the compliance officer if a regulator clock started and the CISO for security events. Services, a Head of SRE role, clocks and security events do not exist yet. Provisional (I17): the incident commander role holder is added automatically to SEV1/SEV2 reviews; SEV1/SEV2 reviews need at least one required reviewer before approval; the review owner adds others by hand. Confirm, and say whether SEV2 should share the SEV1 defaults.

**Q-39 Closure gate details (MPS-8A.12, MPS-13.17).** Provisional (I18): (a) unfinished live tasks (open, in progress, blocked) block closing, since MPS-11.21 expects each to become a follow-up or be cancelled at resolution; (b) only a workspace owner may record the "authorised exception" that skips the review, task and follow-up gates, and the root cause stays required for SEV1/SEV2 even then; (c) the review gate applies to every severity (MPS-8A.12), the follow-up and root-cause gates to SEV1/SEV2 only (MPS-13.04, 13.17). Confirm, or name the roles that may authorise exceptions.

**Q-40 Who may grant roles to teams? (Q-18)** A team role grant can give any workspace role, including owner, to every team member. Provisional (C2): only workspace owners grant or revoke team roles; team roles reach only people who are direct members of the workspace; `GET /api/v1/me/workspaces` still lists direct roles only, while `GET /api/v1/workspaces/current` shows effective roles. Confirm, or say whether admins may grant non-privileged roles.

**Q-41 Service tiers and environments (MPS-20.08).** The service record has a "tier" and an "environment" but the spec defines neither scale. Provisional (C3): tiers `tier_1` (most critical) to `tier_4`; environment is a short lowercase key (e.g. `production`, `eu-staging`) so policy precedence by environment (MPS-10.18) can key on it. Confirm the tier scale and whether environments should come from a fixed list.
