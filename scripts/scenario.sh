#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

API="${API:-http://127.0.0.1:8000}"
DATA=data
COMPOSE=(docker compose --env-file .env)

psql_q() {
    "${COMPOSE[@]}" exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -v ON_ERROR_STOP=1' <<<"$1"
}

step() { printf '\n==> %s\n' "$*"; }

upload_batch() {
    curl -sS --fail-with-body -X POST "$API/v1/depot/batches" \
        -F "file=@$1;type=text/plain" \
        | python3 -c 'import json,sys; print(json.load(sys.stdin)["batch_id"])'
}

wait_pending_zero() {
    local pending
    while true; do
        pending=$(curl -sS --fail "$API/v1/stats" | python3 -c 'import json,sys; print(json.load(sys.stdin)["pending"])')
        [ "$pending" -eq 0 ] && break
        echo "pending=$pending, waiting..."
        sleep 2
    done
    echo "pending=0"
}

live_posts_json() {
    psql_q "
        SELECT json_build_object(
            'lines',       (SELECT count(*) FROM reports_raw WHERE batch_id IS NULL),
            'applied',     count(*) FILTER (WHERE o.status = 'applied'),
            'duplicate',   count(*) FILTER (WHERE o.status = 'duplicate'),
            'quarantined', COALESCE((
                SELECT json_object_agg(reason, n) FROM (
                    SELECT quarantine_reason AS reason, count(*) AS n
                    FROM report_outcomes
                    WHERE batch_id IS NULL AND status = 'quarantined'
                    GROUP BY quarantine_reason
                ) q), '{}'::json)
        )
        FROM report_outcomes o
        WHERE o.batch_id IS NULL;"
}

assignment_id() {
    psql_q "
        SELECT a.id FROM assignments a
        JOIN duties d ON d.id = a.duty_id
        JOIN trainsets t ON t.id = a.trainset_id
        WHERE d.code = '$1' AND t.serial = '$2';"
}

request() {
    local code
    code=$(curl -sS -o /dev/stderr -w '%{http_code}' -X "$1" "$API$2" \
        -H 'Content-Type: application/json' -d "$3")
    echo " -> HTTP $code"
    [[ "$code" == 2* ]] || { echo "request failed: $1 $2" >&2; exit 1; }
}

check() {
    CHECKPOINT="$1" API="$API" BATCH_01="$BATCH_01" BATCH_02="$BATCH_02" \
    LIVE_POSTS="$(live_posts_json)" EXPECTED="$DATA/expected.json" \
    python3 - <<'PY'
import json, os, urllib.parse, urllib.request

TOL = 0.01
api = os.environ["API"]
expected = json.load(open(os.environ["EXPECTED"]))[os.environ["CHECKPOINT"]]
batch_ids = {"depot-batch-01": os.environ["BATCH_01"], "depot-batch-02": os.environ["BATCH_02"]}
passed = failed = 0


def get(path, **params):
    url = f"{api}/v1{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as resp:
        return json.load(resp)


def report(ok, label, exp, act):
    global passed, failed
    if ok:
        passed += 1
        print(f"PASS {label} = {exp!r}")
    else:
        failed += 1
        print(f"FAIL {label}: expected {exp!r}, got {act!r}")


def same(exp, act):
    if isinstance(exp, (int, float)) and not isinstance(exp, bool):
        return isinstance(act, (int, float)) and abs(exp - act) <= TOL
    return exp == act


def compare(label, exp, act):
    if isinstance(exp, dict):
        if not isinstance(act, dict):
            act = {}
        if not exp:
            report(not any(act.values()), label, exp, act)
            return
        for key, value in exp.items():
            compare(f"{label}.{key}", value, act.get(key))
        if label.endswith("quarantined"):
            for key, value in act.items():
                if key not in exp and value:
                    report(False, f"{label}.{key}", 0, value)
    elif isinstance(exp, list):
        if not isinstance(act, list):
            act = []
        if not all(isinstance(e, dict) for e in exp):
            report(len(exp) == len(act) and all(map(same, exp, act)), label, exp, act)
            return
        if len(act) != len(exp):
            report(False, f"{label}.length", len(exp), len(act))
        for i, item in enumerate(exp):
            compare(f"{label}[{i}]", item, act[i] if i < len(act) else None)
    else:
        report(same(exp, act), label, exp, act)


def safe(fetch):
    try:
        return fetch()
    except Exception as e:
        return {"error": str(e)}


print(f"\n--- {os.environ['CHECKPOINT']} ---")
compare("stats", expected["stats"], safe(lambda: get("/stats")))
for name, exp in expected["batches"].items():
    compare(f"batches.{name}", exp, safe(lambda: get(f"/depot/batches/{batch_ids[name]}")))
compare("live_posts", expected["live_posts"], json.loads(os.environ["LIVE_POSTS"]))
for r in expected.get("readings", []):
    act = safe(lambda: get(f"/duties/{r['duty']}/readings", metric=r["metric"]))
    compare(f"readings[{r['duty']},{r['metric']}]", r, act)
for s in expected.get("summaries", []):
    compare(f"summaries[{s['duty']}]", s, safe(lambda: get(f"/duties/{s['duty']}/summary")))
for s in expected.get("stations", []):
    compare(f"stations[{s['duty']}]", s, safe(lambda: get(f"/duties/{s['duty']}/stations")))
for h in expected.get("hourly", []):
    act = safe(lambda: get(f"/duties/{h['duty']}/hourly", metric=h["metric"]))
    compare(f"hourly[{h['duty']},{h['metric']}]", h, act)

print(f"--- {os.environ['CHECKPOINT']}: {passed} PASS, {failed} FAIL ---")
open(os.environ.get("RESULT_FILE", "/dev/null"), "a").write(f"{failed}\n")
PY
}

RESULT_FILE=$(mktemp)
export RESULT_FILE
trap 'rm -f "$RESULT_FILE"' EXIT

step "seed"
"${COMPOSE[@]}" run --rm cli seed --file "$DATA/seed.json"

step "2. upload depot-batch-01.txt"
BATCH_01=$(upload_batch "$DATA/depot-batch-01.txt")
echo "batch_id=$BATCH_01"

step "3. live-stream.txt"
python3 "$DATA/send_live.py" --base "$API" --file "$DATA/live-stream.txt"

step "4. upload depot-batch-02.txt"
BATCH_02=$(upload_batch "$DATA/depot-batch-02.txt")
echo "batch_id=$BATCH_02"
wait_pending_zero
check checkpoint_a_after_step_4

step "5. VD-D03-20261103: TS-0003 removed at 08:40Z (first the end of TS-0003, then the start of TS-0005)"
request PATCH "/v1/assignments/$(assignment_id VD-D03-20261103 TS-0003)" '{"ended_at": "2026-11-03T08:40:00Z"}'
request PATCH "/v1/assignments/$(assignment_id VD-D03-20261103 TS-0005)" '{"started_at": "2026-11-03T08:40:00Z"}'

step "6. TS-0099 on line VD, assignment at VD-T01-20261104, replay-quarantine"
request POST /v1/trainsets '{"serial": "TS-0099", "line": "VD"}'
request POST /v1/duties/VD-T01-20261104/assignments \
    '{"trainset": "TS-0099", "started_at": "2026-11-04T09:00:00Z", "ended_at": "2026-11-04T15:00:00Z"}'
"${COMPOSE[@]}" run --rm cli replay-quarantine --reason unknown_trainset

step "7. wait for pending = 0"
wait_pending_zero
check final_after_step_7

FAILS=$(awk '{s += $1} END {print s + 0}' "$RESULT_FILE")
echo
if [ "$FAILS" -eq 0 ]; then echo "SCENARIO: PASS"; else echo "SCENARIO: FAIL ($FAILS wrong values)"; exit 1; fi
