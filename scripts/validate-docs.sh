#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

fail() {
  echo "docs validation failed: $*" >&2
  exit 1
}

tracked_local_notes="$(git ls-files 'docs/PLAN.md' 'docs/STAGE*.md' 'docs/STAGE_*.md')"
if [[ -n "$tracked_local_notes" ]]; then
  echo "$tracked_local_notes" >&2
  fail "PLAN/STAGE local planning notes must not be tracked by git."
fi

required_pairs=(
  "ADMIN_GUIDE.md"
  "DEPLOYMENT_GUIDE.md"
)

for name in "${required_pairs[@]}"; do
  [[ -f "docs/ru/$name" ]] || fail "missing Russian document: docs/ru/$name"
  [[ -f "docs/en/$name" ]] || fail "missing English document: docs/en/$name"
done

grep -q 'ru/ADMIN_GUIDE.md' docs/README.md || fail "docs/README.md does not link Russian admin guide."
grep -q 'en/ADMIN_GUIDE.md' docs/README.md || fail "docs/README.md does not link English admin guide."
grep -q 'ru/DEPLOYMENT_GUIDE.md' docs/README.md || fail "docs/README.md does not link Russian deployment guide."
grep -q 'en/DEPLOYMENT_GUIDE.md' docs/README.md || fail "docs/README.md does not link English deployment guide."

ignored_check="$(git check-ignore docs/PLAN.md docs/STAGE_13_40.md 2>/dev/null || true)"
grep -q 'docs/PLAN.md' <<<"$ignored_check" || fail "docs/PLAN.md is not ignored."
grep -q 'docs/STAGE_13_40.md' <<<"$ignored_check" || fail "docs/STAGE*.md is not ignored."

echo "Documentation validation completed."
