#!/bin/bash
# check-ci.sh — Poll GitHub Actions and report validate + deploy status
# Usage: ./scripts/check-ci.sh [max_wait_seconds]
# Requires: curl (no auth needed for public repo)

REPO="kapetanios55/SentinelCBContent"
MAX_WAIT=${1:-120}
POLL_INTERVAL=10
VALIDATE_WF_ID="236815922"
DEPLOY_WF_ID="236815921"

echo "🔍 Checking CI status for: $REPO"

get_latest_run() {
    local wf_id=$1
    curl -s "https://api.github.com/repos/$REPO/actions/workflows/$wf_id/runs?per_page=1" \
    | python3 -c "
import sys, json
data = json.load(sys.stdin)
runs = data.get('workflow_runs', [])
if runs:
    r = runs[0]
    print(r['status'], r['conclusion'] or 'pending', r['head_sha'][:7], r['html_url'])
else:
    print('unknown none - -')
"
}

waited=0
while [ $waited -lt $MAX_WAIT ]; do
    VAL=$(get_latest_run $VALIDATE_WF_ID)
    DEP=$(get_latest_run $DEPLOY_WF_ID)

    VAL_STATUS=$(echo $VAL | awk '{print $1}')
    VAL_CONCLUSION=$(echo $VAL | awk '{print $2}')
    DEP_STATUS=$(echo $DEP | awk '{print $1}')
    DEP_CONCLUSION=$(echo $DEP | awk '{print $2}')

    if [ "$VAL_STATUS" == "completed" ] && [ "$DEP_STATUS" == "completed" ]; then
        echo ""
        echo "═══════════════════════════════════"
        echo "  CI Results"
        echo "═══════════════════════════════════"

        if [ "$VAL_CONCLUSION" == "success" ]; then
            echo "  ✅ Validate: PASSED"
        else
            echo "  ❌ Validate: FAILED ($VAL_CONCLUSION)"
            echo "     $(echo $VAL | awk '{print $4}')"
        fi

        if [ "$DEP_CONCLUSION" == "success" ]; then
            echo "  ✅ Deploy: SUCCEEDED"
        elif [ "$DEP_CONCLUSION" == "skipped" ]; then
            echo "  ⏭️  Deploy: SKIPPED (secrets not configured)"
        else
            echo "  ❌ Deploy: FAILED ($DEP_CONCLUSION)"
            echo "     $(echo $DEP | awk '{print $4}')"
        fi

        echo "═══════════════════════════════════"

        # Exit code: 0 if validate passed, 1 if failed
        if [ "$VAL_CONCLUSION" != "success" ]; then
            exit 1
        fi
        exit 0
    fi

    echo "  ⏳ Waiting for CI... (validate: $VAL_STATUS/$VAL_CONCLUSION, deploy: $DEP_STATUS/$DEP_CONCLUSION)"
    sleep $POLL_INTERVAL
    waited=$((waited + POLL_INTERVAL))
done

echo "⚠️ Timed out waiting for CI results after ${MAX_WAIT}s"
exit 2
