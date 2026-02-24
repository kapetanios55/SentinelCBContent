# SentinelCBContent

A community-driven library of Microsoft Sentinel detection rules, hunting queries, and workbooks — focused on actively exploited vulnerabilities from the **CISA Known Exploited Vulnerabilities (KEV)** catalog and other high-signal threat intelligence sources.

Content is updated regularly as new threats emerge. All rules are production-tested and deployed via CI/CD directly into Microsoft Sentinel.

---

## Contents

```
SentinelCBContent/
├── Detections/          # Scheduled analytic rules (KQL, YAML)
├── Hunting/             # Threat hunting queries (KQL, JSON)
├── Workbooks/           # Azure Monitor workbooks (ARM templates, JSON)
├── scripts/             # Deployment scripts (Python, used by CI/CD)
└── .github/workflows/   # GitHub Actions — validate + deploy on push
```

### Detections

Scheduled analytic rules in YAML format. Each file maps to a single Sentinel analytic rule and includes:

- KQL query with inline comments explaining each detection sub-query
- MITRE ATT&CK tactics and techniques
- Entity mappings (Host, IP, Account)
- Severity, trigger threshold, and suppression settings
- Custom alert detail fields for rich incident context

| Detection | CVE(s) | Severity |
|-----------|--------|----------|
| BeyondTrust Remote Support OS Command Injection | CVE-2026-1731 | High |
| Chromium CSS Use-After-Free | CVE-2026-2441 | High |
| Cisco Unified CM Code Injection RCE | CVE-2026-20045 | High |
| Dell RecoverPoint Hard-coded Credentials (UNC6201) | CVE-2026-22769 | High |
| DynoWiper Wiper Malware Behaviour | — | High |
| Fortinet FortiCloud SSO Authentication Bypass | CVE-2026-24858 | High |
| GitLab SSRF via Webhook Requests | CVE-2021-22175 | High |
| Ivanti EPMM Code Injection | CVE-2026-1281 | High |
| Microsoft Configuration Manager SQL Injection | CVE-2024-43468 | High |
| Microsoft February 2026 Patch Tuesday Exploit Indicators | CVE-2026-21513, CVE-2026-21510, CVE-2026-21519, CVE-2026-21533, CVE-2026-21514 | High |
| RoundCube Webmail XSS + Deserialization | CVE-2025-68461, CVE-2025-49113 | High |
| Sangoma FreePBX Auth Bypass + Command Injection | CVE-2019-19006, CVE-2025-64328 | High |
| SmarterMail Missing Authentication RCE | CVE-2026-24423 | High |
| SolarWinds WHD Authentication Bypass | CVE-2025-40536 | High |
| SolarWinds WHD Deserialization RCE | CVE-2025-40551 | High |
| VMware vCenter DCERPC Out-of-Bounds Write RCE | CVE-2024-37079 | High |
| Zimbra ZCS PHP Remote File Inclusion via REST Endpoint | CVE-2025-68645 | High |
| Zimbra ZCS WebEx Zimlet SSRF | CVE-2020-7796 | High |

### Hunting Queries

Proactive threat hunting queries in JSON format. Designed for 30-day retroactive hunts across endpoint and network telemetry.

- Hunt-DynoWiper-IOC-SHA256
- Hunt-Fortinet-FortiCloud-SSO-Abuse-CVE-2026-24858
- Hunt-RemcosRAT-JScript-JPEG-Dropper
- Hunt-SolarWinds-WHD-Deserialization-CVE-2025-40551
- Hunt-UNC6201-VMware-Ghost-NIC-SPA
- Hunt-Zimbra-ZCS-WebEx-Zimlet-SSRF-CVE-2020-7796

### Workbooks

- **CISA KEV Threat Intelligence Dashboard** — visualises KEV exposure across your environment, correlates with MDE and Sentinel incidents

---

## Deploying to Your Own Sentinel Instance

### Prerequisites

- Azure CLI (`az`) installed and authenticated
- A Log Analytics workspace with Microsoft Sentinel enabled
- Python 3.9+ with `pyyaml` installed (`pip install pyyaml`)

### Option A: GitHub Actions (recommended)

Fork this repo, add the following secrets to your GitHub repository (Settings → Secrets → Actions):

| Secret | Description |
|--------|-------------|
| `AZURE_CREDENTIALS` | Service principal JSON — output of `az ad sp create-for-rbac --sdk-auth` |
| `AZURE_SUBSCRIPTION_ID` | Your Azure subscription ID |
| `AZURE_RESOURCE_GROUP` | Resource group containing your Sentinel workspace |
| `SENTINEL_WORKSPACE` | Log Analytics workspace name |

Push to `main` and the workflows will validate and deploy automatically.

**Minimum required RBAC role:** `Microsoft Sentinel Contributor` on the workspace resource group.

To generate the service principal credentials:

```bash
az ad sp create-for-rbac \
  --name "SentinelCBContent-Deploy" \
  --role "Microsoft Sentinel Contributor" \
  --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP> \
  --sdk-auth
```

Paste the full JSON output as the `AZURE_CREDENTIALS` secret.

### Option B: Manual deployment

```bash
export AZURE_SUBSCRIPTION_ID="your-subscription-id"
export AZURE_RESOURCE_GROUP="your-resource-group"
export SENTINEL_WORKSPACE="your-workspace-name"

az login

# Deploy all detection rules
find Detections -name '*.yaml' > changed_files.txt
python3 scripts/deploy-rules.py changed_files.txt

# Deploy all hunting queries
find Hunting -name '*.json' > changed_hunting.txt
python3 scripts/deploy-hunting.py changed_hunting.txt

# Deploy workbooks
for workbook in Workbooks/*.json; do
  az deployment group create \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --template-file "$workbook" \
    --parameters workbookWorkspaceName="$SENTINEL_WORKSPACE"
done
```

---

## Scripts Reference

### `scripts/deploy-rules.py`

Deploys Sentinel scheduled analytic rules from YAML detection files using the Sentinel REST API (`Microsoft.SecurityInsights/alertRules`).

**What it does:**

1. Reads a list of changed YAML files from a text file (one path per line)
2. Parses each YAML file and maps fields to the Sentinel API schema
3. Calls `az rest --method PUT` to create or update each rule by its UUID
4. Reports per-rule success/failure and exits with code 1 if any rule fails

**Duration handling:** converts shorthand durations (`1h`, `30m`, `1d`) to ISO 8601 format (`PT1H`, `PT30M`, `P1D`) as required by the Sentinel API.

**Trigger operator mapping:** converts readable operators (`gt`, `lt`, `eq`) to the API enum values (`GreaterThan`, `LessThan`, `Equal`).

**Environment variables required:**
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_RESOURCE_GROUP`
- `SENTINEL_WORKSPACE`

```bash
# Deploy specific files
echo "Detections/MyRule.yaml" > changed_files.txt
python3 scripts/deploy-rules.py changed_files.txt

# Deploy all rules
find Detections -name '*.yaml' > changed_files.txt
python3 scripts/deploy-rules.py changed_files.txt
```

---

### `scripts/deploy-hunting.py`

Deploys hunting queries to Sentinel using the Log Analytics `savedSearches` API (`Microsoft.OperationalInsights/workspaces/savedSearches`).

**What it does:**

1. Reads a list of changed JSON hunting query files
2. Parses each file and builds a `savedSearch` body with `category: "Hunting Queries"` — this is what causes them to appear in the Sentinel Hunting menu
3. Maps tactics and techniques into the `tags` array (Sentinel reads these to populate the MITRE ATT&CK fields in the UI)
4. Strips MITRE sub-techniques (e.g. `T1059.001` → `T1059`) — the Sentinel API only accepts top-level technique IDs
5. Calls `az rest --method PUT` to create or update each query by its UUID

> **Note:** The correct API for hunting queries is `savedSearches`, **not** `Microsoft.SecurityInsights/huntingQueries` (that endpoint does not exist). This is a common source of confusion.

**Environment variables required:**
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_RESOURCE_GROUP`
- `SENTINEL_WORKSPACE`

```bash
find Hunting -name '*.json' > changed_hunting.txt
python3 scripts/deploy-hunting.py changed_hunting.txt
```

---

## CI/CD Workflows

### `validate.yml` — runs on every push and pull request

1. **Validate YAML structure** — checks all detection files have required fields (`id`, `name`, `description`, `severity`, `tactics`, `query`, etc.), valid severity values, and valid RFC 4122 UUIDs
2. **Validate hunting query files** — checks JSON/YAML parse integrity
3. **Validate ARM templates** — checks workbook ARM templates have required fields (`$schema`, `contentVersion`, `resources`)
4. **Check for duplicate IDs** — ensures no two detection rules share the same UUID

### `deploy.yml` — runs on push to `main` (paths: `Detections/**`, `Hunting/**`, `Workbooks/**`)

1. **Deploy Analytic Rules** — deploys only changed detection YAML files (detected via `git diff HEAD~1 HEAD`) to Sentinel via `deploy-rules.py`
2. **Deploy Hunting Queries** — deploys only changed hunting JSON files via `deploy-hunting.py`
3. **Deploy Workbooks** — deploys all workbook ARM templates via `az deployment group create`

All jobs authenticate to Azure using a service principal stored in `AZURE_CREDENTIALS`.

---

## Content Format

### Detection YAML fields

| Field | Description |
|-------|-------------|
| `id` | RFC 4122 UUID — must be unique across all rules |
| `name` | Display name shown in Sentinel |
| `description` | Markdown-friendly description with CVE details and references |
| `severity` | `High` / `Medium` / `Low` / `Informational` |
| `tactics` | MITRE ATT&CK tactic names (e.g. `InitialAccess`, `Execution`) |
| `relevantTechniques` | Top-level technique IDs only — `T####` format (no sub-techniques) |
| `query` | KQL query |
| `queryFrequency` | How often the rule runs (e.g. `1h`) |
| `queryPeriod` | Time window the query looks back over (e.g. `1h`) |
| `triggerOperator` | `gt` / `lt` / `eq` / `ne` |
| `triggerThreshold` | Result count threshold to trigger an alert |
| `version` | Semantic version string (e.g. `1.0.0`) |
| `kind` | Always `Scheduled` |

### Hunting query JSON fields

| Field | Description |
|-------|-------------|
| `id` | RFC 4122 UUID |
| `name` | Display name |
| `description` | Full description |
| `tactics` | MITRE ATT&CK tactic names |
| `techniques` | Top-level technique IDs |
| `query` | KQL query |
| `created` | ISO date string |
| `version` | Semantic version string |

---

## Known Gotchas (KQL + Sentinel API)

Common pitfalls when writing KQL for Sentinel or deploying via the REST API:

- **`CommonSecurityLog` has no `RequestSize` column** — use `AdditionalExtensions` or `EventOutcome` instead
- **`CommonSecurityLog` HTTP status → `EventOutcome`** — not `ResponseCode`
- **MITRE sub-techniques are rejected** — `T1059.004` fails; use `T1059`
- **Severity `Critical` is not valid** — use `High` with a note in the description
- **Connector-dependent tables need `union isfuzzy=true`** — wrapping `CommonSecurityLog`, `SecurityEvent`, `Syslog` prevents deploy-time failures when the connector isn't installed
- **`DeviceNetworkEvents` uses `InitiatingProcessAccountName`** — not `AccountName`
- **Hunting queries use `savedSearches` API** — `Microsoft.SecurityInsights/huntingQueries` does not exist

---

## Contributing

Pull requests are welcome. If you have a detection for a KEV entry not yet covered, or improvements to existing rules, please open a PR.

Before contributing, read [`STANDARDS.md`](STANDARDS.md) — it covers all the KQL column quirks, Sentinel API constraints, and formatting requirements that rules must meet to pass CI.

Guidelines:
- One CVE (or a closely related CVE cluster) per file
- Detection YAML must pass all CI validation checks before merge
- Include at least one comment block in the KQL explaining *why* the query detects what it does, not just *what* it queries
- Use `union isfuzzy=true` for any connector-dependent table reference (`CommonSecurityLog`, `Syslog`, `SecurityEvent`)
- Generate UUIDs with `python3 -c "import uuid; print(uuid.uuid4())"`
- Verify MITRE tactic → technique alignment at [attack.mitre.org](https://attack.mitre.org/) before submitting

---

## License

MIT
