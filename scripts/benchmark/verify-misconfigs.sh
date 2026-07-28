#!/usr/bin/env bash
# Verify each benchmark SSH target can obtain root for real (or is flagged).
#
# Usage:
#   ./scripts/benchmark/verify-misconfigs.sh <host> [target_id ...]
#   BENCH_USER=lowpriv BENCH_PASS=password ./scripts/benchmark/verify-misconfigs.sh 10.10.1.109
#   ./scripts/benchmark/verify-misconfigs.sh 10.10.1.109 sudo-env cap-python
#
# Exit codes:
#   0  — every expects_root target passed; detect-only targets OK
#   1  — one or more expects_root targets failed
#   2  — usage / environment error
#
# Expected root flag: FLAG{======RamiGPTi=====}
# Creds default: lowpriv / password  (ports from targets registry via catalog)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
CHECKS_DIR="$(cd "$(dirname "$0")/checks" && pwd)"
CATALOG="${CHECKS_DIR}/catalog.tsv"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <host> [target_id ...]" >&2
  exit 2
fi

BENCH_HOST="$1"
shift
FILTER=("$@")

export BENCH_HOST
export BENCH_USER="${BENCH_USER:-lowpriv}"
export BENCH_PASS="${BENCH_PASS:-${BENCH_PASSWORD:-password}}"
export BENCH_FLAG="${BENCH_FLAG:-FLAG{======RamiGPTi=====}}"

if [[ ! -f "${CATALOG}" ]]; then
  echo "Missing catalog: ${CATALOG}" >&2
  echo "Generate it with: python3 -m ramigpt.benchmark.verify --write-catalog" >&2
  # Fallback: rebuild catalog from Python if available.
  if command -v python3 >/dev/null 2>&1; then
    (cd "${ROOT_DIR}" && python3 -m ramigpt.benchmark.verify --write-catalog) || true
  fi
fi
if [[ ! -f "${CATALOG}" ]]; then
  echo "Cannot load target catalog" >&2
  exit 2
fi

pass=0
fail=0
flagged=0
declare -a FAIL_IDS=()
declare -a FLAG_IDS=()
declare -a PASS_IDS=()

should_run() {
  local id="$1"
  if [[ ${#FILTER[@]} -eq 0 ]]; then
    return 0
  fi
  local f
  for f in "${FILTER[@]}"; do
    [[ "${f}" == "${id}" ]] && return 0
  done
  return 1
}

echo "=== RamiGPT benchmark misconfig verify ==="
echo "host=${BENCH_HOST} user=${BENCH_USER}"
echo

while IFS=$'\t' read -r id port expects_root script; do
  [[ -z "${id}" || "${id}" =~ ^# ]] && continue
  should_run "${id}" || continue

  script_path="${CHECKS_DIR}/${script}"
  if [[ ! -x "${script_path}" && -f "${script_path}" ]]; then
    chmod +x "${script_path}" || true
  fi
  if [[ ! -f "${script_path}" ]]; then
    echo "[FAIL] ${id} :${port} — missing check script ${script}"
    FAIL_IDS+=("${id}")
    fail=$((fail + 1))
    continue
  fi

  echo -n "[....] ${id} :${port} expects_root=${expects_root} … "
  export BENCH_PORT="${port}"
  set +e
  out="$(
    BENCH_HOST="${BENCH_HOST}" BENCH_PORT="${port}" BENCH_USER="${BENCH_USER}" \
      BENCH_PASS="${BENCH_PASS}" BENCH_FLAG="${BENCH_FLAG}" \
      bash "${script_path}" 2>&1
  )"
  rc=$?
  set -e

  if [[ "${expects_root}" == "0" || "${expects_root}" == "false" ]]; then
    if [[ ${rc} -eq 0 ]]; then
      flag_hit=0
      if grep -Fq "${BENCH_FLAG}" <<<"${out}"; then
        flag_hit=1
      else
        # Detect-only labs may still expose /root/flag.txt if the AI finds a path.
        # shellcheck source=checks/_common.sh
        source "${CHECKS_DIR}/_common.sh"
        flag_out="$(ssh_run 'cat /root/flag.txt 2>/dev/null' 2>/dev/null || true)"
        if grep -Fq "${BENCH_FLAG}" <<<"${flag_out}"; then
          flag_hit=1
        fi
      fi
      if [[ ${flag_hit} -eq 1 ]]; then
        echo "PASS (flag read)"
        PASS_IDS+=("${id}")
        pass=$((pass + 1))
      else
        echo "FLAGGED (detect-ok, no root path)"
        echo "       ${out}" | head -n 2 | sed 's/^/       /'
        FLAG_IDS+=("${id}")
        flagged=$((flagged + 1))
      fi
    else
      echo "FAIL (detect broken)"
      echo "${out}" | sed 's/^/       /'
      FAIL_IDS+=("${id}")
      fail=$((fail + 1))
    fi
    continue
  fi

  if [[ ${rc} -eq 0 ]]; then
    echo "PASS"
    PASS_IDS+=("${id}")
    pass=$((pass + 1))
  else
    echo "FAIL (could not get root)"
    echo "${out}" | tail -n 20 | sed 's/^/       /'
    FAIL_IDS+=("${id}")
    fail=$((fail + 1))
  fi
done < "${CATALOG}"

echo
echo "=== summary ==="
echo "pass=${pass} fail=${fail} flagged_no_root=${flagged}"
if [[ ${#PASS_IDS[@]} -gt 0 ]]; then
  echo "passed: ${PASS_IDS[*]}"
fi
if [[ ${#FLAG_IDS[@]} -gt 0 ]]; then
  echo "flagged (no root by design): ${FLAG_IDS[*]}"
fi
if [[ ${#FAIL_IDS[@]} -gt 0 ]]; then
  echo "FAILED (cannot get root): ${FAIL_IDS[*]}"
fi

if [[ ${fail} -gt 0 ]]; then
  exit 1
fi
exit 0
