#!/usr/bin/env bash
# scripts/strip_trailers.sh — scrub forbidden trailers and multi-line bodies from a commit range.
#
# Project rule (CONTRIBUTING.md, docs/ROADMAP.md §7.7): every commit on `main` must be a single
# subject line with no body and no trailers. GitHub's squash-merge engine will sometimes inject
# Co-authored-by:/Signed-off-by: anyway when (a) Dependabot's source commits already contain
# trailers, or (b) someone clicks "Update branch" via the UI. This script rewrites a range of
# commits with `git filter-branch` keeping only each subject line, then prints the diff.
#
# It does NOT push. The maintainer (or the workflow in `.github/workflows/strip-trailers.yml`)
# is responsible for force-pushing after verifying the rewritten range.
#
# Usage:
#   scripts/strip_trailers.sh                      # rewrite from <last-clean-ancestor>..HEAD
#   scripts/strip_trailers.sh <since-rev>          # rewrite <since-rev>..HEAD
#   scripts/strip_trailers.sh <since-rev> <ref>    # rewrite <since-rev>..<ref>
#
# Defaults: <since-rev> = the latest tag matching `pre-rewrite-*` if present, else `HEAD~1`.
#           <ref> = HEAD.
set -euo pipefail

since="${1:-}"
ref="${2:-HEAD}"

if [ -z "$since" ]; then
  since=$(git tag --list 'pre-rewrite-*' --sort=-creatordate | head -n1 || true)
  if [ -z "$since" ]; then
    since="${ref}~1"
  fi
fi

echo "Range: ${since}..${ref}"
count=$(git rev-list --count "${since}..${ref}")
if [ "$count" -eq 0 ]; then
  echo "Nothing to rewrite."
  exit 0
fi

echo "Will rewrite $count commit(s) to keep only the subject line."
echo "Forbidden trailers stripped: signed-off-by, co-authored-by, made-with, generated-by, reported-by, reviewed-by, tested-by."
echo

if [ "${ASSUME_YES:-0}" != "1" ]; then
  read -r -p "Proceed (rewrites local history; does NOT push) [y/N]? " ans
  case "${ans:-}" in
    y|Y|yes|YES) ;;
    *) echo "Aborted."; exit 1 ;;
  esac
fi

# Backup tag so the maintainer can restore.
backup="pre-rewrite-$(date -u +%Y-%m-%d-%H%M%S)"
git tag "$backup" "$ref"
echo "Backup tag: $backup -> $(git rev-parse --short "$ref")"

# awk script keeps only line 1 of each commit message. Trailing whitespace is stripped.
FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f \
  --msg-filter 'awk "NR==1 { sub(/[[:space:]]+$/, \"\"); print; exit }"' \
  "${since}..${ref}"

remaining=$(git log --format='%b' "${since}..${ref}" \
  | grep -ciE '^(signed-off-by|co-authored-by|made-with|generated-by|reported-by|reviewed-by|tested-by):' \
  || true)

echo
if [ "$remaining" -ne 0 ]; then
  echo "ERROR: $remaining trailer line(s) still present after rewrite. Investigate before pushing."
  exit 2
fi

echo "Rewrite OK. Range now contains zero forbidden trailers and zero body content."
echo "To push (only on a branch you OWN; for main this requires temporarily allowing force pushes):"
echo "  git push --force-with-lease=${ref##*/}:$(git rev-parse "$backup") origin ${ref##*/}"
