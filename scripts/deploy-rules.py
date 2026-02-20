#!/usr/bin/env python3
"""
deploy-rules.py — Deploy Sentinel analytic rules via az rest
Usage: python3 scripts/deploy-rules.py <changed_files.txt>
Env:   AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP, SENTINEL_WORKSPACE
"""
import os, sys, yaml, json, subprocess, re

def to_iso8601(val):
    s = str(val).strip()
    if s.startswith('PT') or s.startswith('P'):
        return s
    m = re.match(r'^(\d+)([mhd])$', s)
    if not m:
        print(f"  ⚠️  Cannot parse duration '{val}', using as-is")
        return s
    n, unit = m.groups()
    return {'m': f'PT{n}M', 'h': f'PT{n}H', 'd': f'P{n}D'}[unit]

def map_operator(op):
    mapping = {
        'gt': 'GreaterThan', 'lt': 'LessThan', 'eq': 'Equal',
        'ne': 'NotEqual', 'gte': 'GreaterThanOrEqual', 'lte': 'LessThanOrEqual'
    }
    return mapping.get(str(op).lower(), str(op))

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

    # Read file list
    changed_file = sys.argv[1] if len(sys.argv) > 1 else 'changed_files.txt'
    try:
        with open(changed_file) as f:
            changed = [l.strip() for l in f if l.strip().endswith('.yaml')]
    except FileNotFoundError:
        print(f"❌ {changed_file} not found")
        sys.exit(1)

    if not changed:
        print("✅ No detection YAML files changed — nothing to deploy.")
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
                rule = yaml.safe_load(f)
        except Exception as e:
            print(f"  ❌ YAML parse error: {e}")
            errors.append(filepath)
            continue

        rule_id   = str(rule.get('id', '')).strip()
        rule_name = rule.get('name', 'Unknown')

        if not rule_id:
            print(f"  ❌ Missing 'id' field in {filepath}")
            errors.append(filepath)
            continue

        print(f"  Name: {rule_name}")
        print(f"  ID:   {rule_id}")

        body = {
            'kind': 'Scheduled',
            'properties': {
                'displayName':        rule_name,
                'description':        str(rule.get('description', '')).strip(),
                'severity':           rule.get('severity', 'Medium'),
                'enabled':            True,
                'query':              str(rule.get('query', '')).strip(),
                'queryFrequency':     to_iso8601(rule.get('queryFrequency', 'PT1H')),
                'queryPeriod':        to_iso8601(rule.get('queryPeriod', 'PT1H')),
                'triggerOperator':    map_operator(rule.get('triggerOperator', 'GreaterThan')),
                'triggerThreshold':   int(rule.get('triggerThreshold', 0)),
                'tactics':            rule.get('tactics', []),
                'techniques':         rule.get('relevantTechniques', []),
                'suppressionEnabled': False,
                'suppressionDuration': 'PT1H',
            }
        }

        if 'entityMappings' in rule:
            body['properties']['entityMappings'] = rule['entityMappings']

        url = (f"https://management.azure.com/subscriptions/{sub}"
               f"/resourceGroups/{rg}"
               f"/providers/Microsoft.OperationalInsights/workspaces/{ws}"
               f"/providers/Microsoft.SecurityInsights/alertRules/{rule_id}"
               f"?api-version=2023-02-01")

        body_json = json.dumps(body)
        print(f"  URL: {url}")

        cmd = ['az', 'rest', '--method', 'PUT', '--url', url,
               '--body', body_json, '--output', 'none']

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"  ✅ Deployed: {rule_name}")
            deployed += 1
        else:
            print(f"  ❌ Failed: {rule_name}")
            print(f"  STDOUT: {result.stdout[:500]}")
            print(f"  STDERR: {result.stderr[:500]}")
            errors.append(rule_name)

    print(f"\n{'='*50}")
    print(f"Summary: {deployed} deployed, {len(errors)} failed")
    if errors:
        print(f"Failed: {errors}")
        sys.exit(1)

if __name__ == '__main__':
    main()
