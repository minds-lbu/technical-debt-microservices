#!/bin/bash
# Quick health snapshot for running pipelines - safe to run anytime, read-only
cd ~/dissertation
TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
echo "=== Health check: $TIMESTAMP ==="

echo "--- Processes ---"
ps aux | grep pipeline.py | grep -v grep

echo "--- Memory ---"
free -h | grep -E "Mem|Swap"

echo "--- SonarQube status ---"
curl -s http://localhost:9000/api/system/status | python3 -c "import json,sys; print(json.load(sys.stdin).get('status','UNREACHABLE'))" 2>/dev/null || echo "UNREACHABLE"

echo "--- Row counts ---"
for f in results/light-4j_results.csv results/taotao-cloud-project_results.csv; do
  if [ -f "$f" ]; then
    echo "$f: $(tail -n +2 "$f" | wc -l) rows"
  fi
done

echo "--- Recent failure rate (last 50 log lines) ---"
for log in light4j_retry_log.txt taotao_log.txt; do
  if [ -f "$log" ]; then
    fails=$(tail -50 "$log" | grep -cE "SCAN_FAILED|ANALYSIS_FAILED|OutOfMemory")
    echo "$log: $fails failure-related lines in last 50"
  fi
done

echo "--- Docker container check ---"
docker ps --format '{{.Names}}: {{.Status}}'

echo "=== End health check ==="
