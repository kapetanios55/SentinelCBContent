# SentinelCBContent — Authoring Standards

Rules for creating detection rules, hunting queries, and workbooks in this repo.
Follow these to ensure clean CI validation and successful Sentinel API deployment.

---

## Detection YAML

### Severity
Only these four values are accepted by the Sentinel API:
```
High | Medium | Low | Informational
```
> ⚠️ `Critical` is **not** a valid value. Use `High` and note the CVSS score in the description.

### MITRE Techniques — top-level only
The Sentinel API only accepts the format `T####` (4 digits). Sub-techniques are **not** supported.
```yaml
# ❌ Wrong
relevantTechniques:
  - T1059.004
  - T1505.003

# ✅ Correct
relevantTechniques:
  - T1059
  - T1505
```

### Tactic / Technique alignment
Every technique in `relevantTechniques` must have a corresponding tactic in `tactics`.
The API validates this and will reject mismatches.

| Technique | Required Tactic |
|-----------|----------------|
| T1083 (File & Dir Discovery) | Discovery |
| T1059 (Command & Scripting) | Execution |
| T1190 (Exploit Public-Facing App) | InitialAccess |
| T1572 (Protocol Tunneling) | CommandAndControl |

Always verify at https://attack.mitre.org/

### KQL — column names by table
MDE table column names are inconsistent. Key differences:

| Table | Account column |
|-------|---------------|
| `DeviceProcessEvents` | `AccountName` |
| `DeviceNetworkEvents` | `InitiatingProcessAccountName` |
| `DeviceFileEvents` | `InitiatingProcessAccountName` |
| `DeviceEvents` | `InitiatingProcessAccountName` |

When unioning across MDE tables, normalise with:
```kql
| extend AccountName = InitiatingProcessAccountName
```
before `| project`.

### KQL — connector-dependent tables
Tables like `CommonSecurityLog`, `SecurityEvent`, and `Syslog` only exist when the
corresponding data connector is deployed. The Sentinel API validates queries at deploy
time and rejects rules if a referenced table doesn't exist in the workspace.

**Fix:** use `union isfuzzy=true` so the rule deploys regardless:
```kql
// Single table → wrap in isfuzzy union
union isfuzzy=true (
    CommonSecurityLog
    | where TimeGenerated > ago(1h)
    | where ...
)

// Existing union → add isfuzzy=true
union isfuzzy=true (query1), (query2)
```

---

## Workbook ARM Templates

### `workbookSourceId` — must be a real workspace resource ID
This is what makes the workbook appear in the Sentinel → Workbooks menu.

```json
// ❌ Wrong — workbook deploys but is invisible in Sentinel
"workbookSourceId": {
  "defaultValue": "Azure Security Insights"
}

// ✅ Correct — use resourceId() ARM expression
"workbookSourceId": {
  "defaultValue": "[resourceId('microsoft.operationalinsights/workspaces', parameters('workbookWorkspaceName'))]"
}
```
Always add a `workbookWorkspaceName` parameter and pass it via the deploy workflow.

### Workspace picker query — don't filter by subscription GUID
The Subscription picker (type 6) returns a **full resource ID** (`/subscriptions/abc...`),
not a bare GUID. Filtering `| where subscriptionId in~ ({Subscription})` will always fail.

```kql
// ❌ Wrong
Resources
| where type =~ 'microsoft.operationalinsights/workspaces'
| where subscriptionId in~ ({Subscription})   // always fails

// ✅ Correct — crossComponentResources scopes it automatically
Resources
| where type =~ 'microsoft.operationalinsights/workspaces'
| project value = id, label = name, group = resourceGroup
| sort by label asc
```

---

## Hunting Queries

### Use savedSearches API — NOT huntingQueries
`Microsoft.SecurityInsights/huntingQueries` is **not** a valid REST endpoint. Deploying to it returns `NoRegisteredProviderFound`.

✅ Correct endpoint:
```
PUT .../providers/Microsoft.OperationalInsights/workspaces/{ws}/savedSearches/{id}?api-version=2020-08-01
```

Required body structure:
```json
{
  "properties": {
    "category":    "Hunting Queries",
    "displayName": "Query Name",
    "query":       "KQL here",
    "tags": [
      { "name": "description", "value": "..." },
      { "name": "tactics",     "value": "Impact,Execution" },
      { "name": "techniques",  "value": "T1485" }
    ],
    "version": 2
  }
}
```
The `category: "Hunting Queries"` and `version: 2` are what make the query appear in the Sentinel → Hunting menu.

### Each hunting query JSON must have an `id` field
The `savedSearches` PUT endpoint requires a stable ID in the URL. Add a UUID to every hunting query file:
```json
{ "id": "e1a2b3c4-d5e6-7890-abcd-ef1234567801", "name": "...", ... }
```

---

## GitHub Actions / Deploy

### Required secrets
All four must be configured (repo or `production` environment):
- `AZURE_CREDENTIALS`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_RESOURCE_GROUP`
- `SENTINEL_WORKSPACE`

### Redeploying all rules after a failed run
The deploy script uses `git diff HEAD~1 HEAD` to identify changed files.
To force a full redeploy, bump the `version` field across all detection files so
they all appear in the diff:
```bash
# Quick version bump across all detections
sed -i 's/^version: \(.*\)/version: \1/' Detections/*.yaml
```
Or update them with the version bump script used in this repo's CI history.
