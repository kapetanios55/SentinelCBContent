#!/bin/bash
# check-ci.sh — Poll GitHub Actions and report validate + deploy status for current HEAD
# Usage: ./scripts/check-ci.sh [max_wait_seconds]

REPO="kapetanios55/SentinelCBContent"
MAX_WAIT=${1:-120}
POLL_INTERVAL=10
VALIDATE_WF_ID="236815922"
DEPLOY_WF_ID="236815921"
HEAD_SHA=$(git rev-parse HEAD)
SHORT_SHA=${HEAD_SHA:0:7}

echo "🔍 Checking CI for commit: $SHORT_SHA"

get_run_for_sha() {
    local wf_id=$1
    local sha=$2
    curl -s "https://api.github.com/repos/$REPO/actions/workflows/$wf_id/runs?per_page=10" \
    | python3 -c "
import sys, json
data = json.load(sys.stdin)
for r in data.get('workflow_runs', []):
    if r['head_sha'] == '$sha':
        print(r['status'], r['conclusion'] or 'pending', r['id'], r['html_url'])
        sys.exit(0)
print('not_triggered - - -')
"
}

waited=0
while [ $waited -lt $MAX_WAIT ]; do
    VAL=$(get_run_for_sha $VALIDATE_WF_ID $HEAD_SHA)
    DEP=$(get_run_for_sha $DEPLOY_WF_ID $HEAD_SHA)

    VAL_STATUS=$(echo $VAL | awk '{print $1}')
    VAL_CONCLUSION=$(echo $VAL | awk '{print $2}')
    DEP_STATUS=$(echo $DEP | awk '{print $1}')
    DEP_CONCLUSION=$(echo $DEP | awk '{print $2}')

    # Wait if validate is still in progress
    if [ "$VAL_STATUS" == "not_triggered" ] || [ "$VAL_STATUS" == "in_progress" ] || [ "$VAL_STATUS" == "queued" ]; then
        echo "  ⏳ Waiting... validate=$VAL_STATUS, deploy=$DEP_STATUS"
        sleep $POLL_INTERVAL
        waited=$((waited + POLL_INTERVAL))
        continue
    fi

    # Validate completed (deploy may or may not have triggered)
    echo ""
    echo "═══════════════════════════════════"
    echo "  CI Results for $SHORT_SHA"
    echo "═══════════════════════════════════"

    if [ "$VAL_CONCLUSION" == "success" ]; then
        echo "  ✅ Validate: PASSED"
    else
        echo "  ❌ Validate: FAILED ($VAL_CONCLUSION)"
        echo "     $(echo $VAL | awk '{print $4}')"
    fi

    if [ "$DEP_STATUS" == "not_triggered" ]; then
        echo "  ℹ️  Deploy: NOT TRIGGERED (no content changes in this commit)"
    elif [ "$DEP_CONCLUSION" == "success" ]; then
        echo "  ✅ Deploy: SUCCEEDED"
    elif [ "$DEP_CONCLUSION" == "skipped" ] || \
         ([ "$DEP_STATUS" == "completed" ] && echo "$DEP" | grep -q "skipped"); then
        echo "  ⏭️  Deploy: SKIPPED (secrets not configured — add AZURE_CREDENTIALS to repo secrets)"
    elif [ "$DEP_STATUS" == "in_progress" ] || [ "$DEP_STATUS" == "queued" ]; then
        echo "  ⏳ Deploy: IN PROGRESS..."
    elif [ "$DEP_CONCLUSION" == "failure" ]; then
        echo "  ❌ Deploy: FAILED"
        echo "     $(echo $DEP | awk '{print $4}')"
    else
        echo "  ❓ Deploy: $DEP_STATUS/$DEP_CONCLUSION"
    fi

    echo "═══════════════════════════════════"

    [ "$VAL_CONCLUSION" == "success" ] && exit 0 || exit 1
done

echo "⚠️ Timed out after ${MAX_WAIT}s"
exit 2
