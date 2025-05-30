#!/bin/bash
echo "🚀 Running ESLint in Docker..."

REPORT_PATH=./analysis/static/report/eslint_report.json

docker run --name eslint \
  -v ./frontend:/app \
  -v /app/node_modules \
  -w /app \
  node:20 \
  bash -c "
    mkdir -p /home/report &&
    npm install &&
    npx eslint /app\
      --format json \
      --output-file /home/report/eslint_report.json
  "

docker cp eslint:/home/report/eslint_report.json $REPORT_PATH
docker rm -f eslint

ERRORS=$(jq '[.[] | .messages[] | select(.severity == 2)] | length' $REPORT_PATH)

echo "🚨 ESLint errors found: $ERRORS"

if [ "$ERRORS" -gt 5 ]; then
  echo "❌ ESLint error found: $ERRORS"
  exit 1
fi