#!/usr/bin/env python3
"""
deploy-hunting.py — Deploy Sentinel Hunting Queries via savedSearches API
Usage: python3 scripts/deploy-hunting.py [changed_files.txt]
Env:   AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP, SENTINEL_WORKSPACE

Hunting queries in Sentinel are stored as Log Analytics savedSearches with
category "Hunting Queries". This is the correct, supported deployment method.
API: Microsoft.OperationalInsights/workspaces/savedSearches (api-version=2020-08-01)
"""
import os, sys, json, subprocess

API_VERSION = "2020-08-01"

def map_techniques(techniques):
    """Strip sub-techniques — Sentinel only accepts T#### format."""
    seen, result = set(), []
    for t in techniques:
        top = t.split('.')[0]
        if top not in seen:
            seen.add(top)
            result.append(top)
    return result

def main():
    sub = os.environ.get('AZURE_SUBSCRIPTION_ID', '')
    rg  = os.environ.get('AZURE_RESOURCE_GROUP', '')
    ws  = os.environ.get('SENTINEL_WORKSPACE', '')

    if not all([sub, rg, ws]):
        print("❌ Missing env vars: AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP, SENTINEL_WORKSPACE")
        sys.exit(1)

    print(f"Subscription: {sub[:8]}...")
    print(f"Resource Group: {rg}")
    print(f"Workspace: {ws}")

    changed_file = sys.argv[1] if len(sys.argv) > 1 else 'changed_hunting.txt'
    try:
        with open(changed_file) as f:
            changed = [l.strip() for l in f if l.strip().endswith('.json')]
    except FileNotFoundError:
        print(f"❌ {changed_file} not found")
        sys.exit(1)

    if not changed:
        print("✅ No hunting query JSON files changed — nothing to deploy.")
        sys.exit(0)

    print(f"\nFiles to deploy: {changed}")

    deployed, errors = 0, []

    for filepath in changed:
        if not os.path.exists(filepath):
            print(f"  ⏭️  Skipping (deleted): {filepath}")
            continue

        print(f"\n→ Processing: {filepath}")
        try:
            with open(filepath) as f:
                q = json.load(f)
        except Exception as e:
            print(f"  ❌ JSON parse error: {e}")
            errors.append(filepath)
            continue

        query_id   = str(q.get('id', '')).strip()
        query_name = q.get('name', 'Unknown')
        tactics    = q.get('tactics', [])
        techniques = map_techniques(q.get('techniques', []))
        description = q.get('description', '')

        if not query_id:
            print(f"  ❌ Missing 'id' field in {filepath}")
            errors.append(filepath)
            continue

        print(f"  Name: {query_name}")
        print(f"  ID:   {query_id}")

        # savedSearches body — Sentinel reads category + tags to surface in Hunting
        tags = [{"name": "description", "value": description[:256]}]
        if tactics:
            tags.append({"name": "tactics", "value": ",".join(tactics)})
        if techniques:
            tags.append({"name": "techniques", "value": ",".join(techniques)})

        body = {
            "properties": {
                "category":    "Hunting Queries",
                "displayName": query_name,
                "query":       q.get('query', ''),
                "tags":        tags,
                "version":     2
            }
        }

        url = (
            f"https://management.azure.com/subscriptions/{sub}"
            f"/resourcegroups/{rg}"
            f"/providers/Microsoft.OperationalInsights/workspaces/{ws}"
            f"/savedSearches/{query_id}"
            f"?api-version={API_VERSION}"
        )

        print(f"  URL: {url}")

        cmd = ['az', 'rest', '--method', 'PUT', '--url', url,
               '--body', json.dumps(body), '--output', 'none']

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"  ✅ Deployed: {query_name}")
            deployed += 1
        else:
            print(f"  ❌ Failed: {query_name}")
            print(f"  STDOUT: {result.stdout[:500]}")
            print(f"  STDERR: {result.stderr[:500]}")
            errors.append(query_name)

    print(f"\n{'='*50}")
    print(f"Summary: {deployed} deployed, {len(errors)} failed")
    if errors:
        print(f"Failed: {errors}")
        sys.exit(1)

if __name__ == '__main__':
    main()
