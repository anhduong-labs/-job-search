#!/bin/bash
# Push jobs to Google Sheet - auto-refresh token
# IMPORTANT: Store CLIENT_ID and CLIENT_SECRET in ~/.openclaw/skills/job-scanner/.env
# Not in this script!

WORKSPACE="$HOME/.openclaw/workspace"
INPUT_FILE="$WORKSPACE/jobs_evaluated.json"
TOKEN_FILE="$WORKSPACE/google_token.json"
ENV_FILE="$HOME/.openclaw/skills/job-scanner/.env"

SHEET_ID=$(grep "JOB_SHEET_ID=" "$ENV_FILE" | cut -d= -f2)
CLIENT_ID=$(grep "GOOGLE_CLIENT_ID=" "$ENV_FILE" | cut -d= -f2)
CLIENT_SECRET=$(grep "GOOGLE_CLIENT_SECRET=" "$ENV_FILE" | cut -d= -f2)

[ -z "$SHEET_ID" ] && { echo "❌ JOB_SHEET_ID not found"; exit 1; }
[ -z "$CLIENT_ID" ] && { echo "❌ GOOGLE_CLIENT_ID not found in .env"; exit 1; }
[ -z "$CLIENT_SECRET" ] && { echo "❌ GOOGLE_CLIENT_SECRET not found in .env"; exit 1; }

echo "📊 Loading jobs..."
TOTAL=$(jq 'length' "$INPUT_FILE")
echo "   $TOTAL jobs"

# Refresh token
echo "🔐 Refreshing auth..."
REFRESH=$(jq -r '.refresh_token' "$TOKEN_FILE")

# Use CLIENT_ID and CLIENT_SECRET from .env (loaded above)
NEW_TOKEN=$(curl -s -X POST "https://oauth2.googleapis.com/token" \
  -d "client_id=$CLIENT_ID&client_secret=$CLIENT_SECRET&refresh_token=$REFRESH&grant_type=refresh_token" \
  | jq -r '.access_token // empty')

[ -z "$NEW_TOKEN" ] && { echo "❌ Token refresh failed"; exit 1; }
echo "   ✅ Auth OK"

# Tab name
TAB_NAME="jobs_eval_$(date +%Y%m%d)"

# Build rows
echo "📋 Building rows..."
ROWS=$(jq -r '
  ["Title","Company","Location","Grade","Score","Archetype","Match Reasons","Gaps","Priority","URL"] as $h |
  [$h] + [.[] | [
    .title // "",
    .company // "",
    .location // "",
    (.evaluation.grade // ""),
    (.evaluation.score // ""),
    (.evaluation.archetype // ""),
    ((.evaluation.match_reasons // [])[:2] | join(" | ")),
    ((.evaluation.gaps // [])[:1] | join(" | ")),
    (.evaluation.priority // ""),
    .url // ""
  ]]
' "$INPUT_FILE")

# Push - use single quotes and escape properly
echo "📤 Pushing to sheet..."
RANGE="'${TAB_NAME}'!A1"

RESPONSE=$(curl -s -X POST \
  "https://sheets.googleapis.com/v4/spreadsheets/$SHEET_ID/values/$RANGE:append?valueInputOption=USER_ENTERED" \
  -H "Authorization: Bearer $NEW_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"values\": $(echo "$ROWS" | jq -c .)}")

ERROR=$(echo "$RESPONSE" | jq -r '.error.message // empty')
if [ -n "$ERROR" ]; then
    echo "❌ Error: $ERROR"
    exit 1
fi

UPDATED=$(echo "$RESPONSE" | jq '.updates.updatedRows // 0')
echo "✅ Done! $UPDATED rows added to tab '$TAB_NAME'"
echo "📊 https://docs.google.com/spreadsheets/d/$SHEET_ID"
