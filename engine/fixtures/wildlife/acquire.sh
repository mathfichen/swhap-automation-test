#!/usr/bin/env bash
# acquire.sh — exemplar-pilot T1 (M1a): pin the Wild_LIFE fixture ground truth.
#
# Acquires, exactly once, the published Wild_Life-swhap exemplar and the
# author-supplied 1.02 release from PR #1, as:
#   - wildlife.bundle      git bundle carrying both pinned commits
#   - tarballs/            the four release tarballs, byte-exact
#   - tarballs.sha256      the frozen manifest (minted on first run)
#
# Idempotent: re-runs verify everything and write nothing when intact.
# The three published hashes are EMBEDDED below (from
# Wild_Life-swhap@MAIN_PIN metadata/checksums.sha256) so that upstream
# tampering is detected rather than inherited. The 1.02 hash has no
# published reference; it is minted on first acquisition and frozen by
# committing tarballs.sha256 (see analysis/impl/exemplar-pilot.md T1).
#
# NOTE: the published exemplar is fixture material for what the validator
# must CATCH (its v0.91/v1.0 tag trees are corrupted; see
# swhap-automation/analysis/brief-critique.md C4). Do not treat it as a
# correct reference. Never extract tarball contents here (quarantine
# discipline: inspection happens via `swhap inspect`, T3).

set -euo pipefail

REPO_URL="https://github.com/SoftwareHeritage/Wild_Life-swhap.git"
MAIN_PIN="1571ce554b575ddacb750fa8135d6df4841d0090"  # published main tip, 2026-06-05
PR1_PIN="5e05003011fc42ec21f0a386a876b85e4783d13a"   # PR #1 head: raw_materials/Life1.02Ultrix.tar
# SourceCode tip: the 3-commit (one-per-release, NO tags) reconstructed history.
# Its release trees are the TF gate ORACLE (real-tree vs real-manifest); the
# published v0.91/v1.0 trees carry the previous-version leak the validator must
# catch (C4 / followup-2). Release->commit mapping is BY COMMIT MESSAGE
# ("Wild_LIFE <ver>") because the published exemplar ships no annotated tags.
SC_PIN="24051137387e57d0bcd419e37fa1dba90d88c0eb"     # SourceCode tip (Wild_LIFE 1.0 commit)

# Published checksums (metadata/checksums.sha256 at MAIN_PIN):
LIFE_090_SHA="928453daa1ae1477113f323b2d98d3920d15999d8ed7d496f0b606598592df19"
LIFE_091_SHA="dbf206afbd22b57070a484687e24548efd66754397b81661121bc2de70ae5ce6"
LIFE_10_SHA="c8d3d7c72e9eeab2b6124348bc5e4b8f15d69c1fd29b35768251751a505a670e"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE="$HERE/wildlife.bundle"
TARBALLS="$HERE/tarballs"
MANIFEST="$HERE/tarballs.sha256"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

say() { printf '[acquire] %s\n' "$*"; }
die() { printf '[acquire] FATAL: %s\n' "$*" >&2; exit 1; }

# --- 1. Fetch the pinned commits -------------------------------------------
say "cloning $REPO_URL (bare)"
git clone --quiet --bare "$REPO_URL" "$WORK/repo.git"
git -C "$WORK/repo.git" fetch --quiet origin "+refs/pull/1/head:refs/heads/pin-pr1"

git -C "$WORK/repo.git" cat-file -e "${MAIN_PIN}^{commit}" \
  || die "pinned main commit $MAIN_PIN not found upstream"
git -C "$WORK/repo.git" cat-file -e "${PR1_PIN}^{commit}" \
  || die "pinned PR #1 commit $PR1_PIN not found upstream"
git -C "$WORK/repo.git" cat-file -e "${SC_PIN}^{commit}" \
  || die "pinned SourceCode commit $SC_PIN not found upstream"

upstream_main="$(git -C "$WORK/repo.git" rev-parse refs/heads/main)"
if [ "$upstream_main" != "$MAIN_PIN" ]; then
  say "NOTE: upstream main moved to ${upstream_main:0:12} (pin unchanged: ${MAIN_PIN:0:12})"
fi
upstream_sc="$(git -C "$WORK/repo.git" rev-parse refs/heads/SourceCode)"
if [ "$upstream_sc" != "$SC_PIN" ]; then
  say "NOTE: upstream SourceCode moved to ${upstream_sc:0:12} (pin unchanged: ${SC_PIN:0:12})"
fi

git -C "$WORK/repo.git" update-ref refs/heads/pin-main "$MAIN_PIN"
git -C "$WORK/repo.git" update-ref refs/heads/pin-pr1 "$PR1_PIN"
git -C "$WORK/repo.git" update-ref refs/heads/pin-sourcecode "$SC_PIN"

# --- 2. Bundle (write once, verify thereafter) ------------------------------
# Tamper-detecting: every pin's EXACT sha must be a head in the bundle, else we
# rebuild (a bundle missing pin-sourcecode predates the TF-oracle fix).
need_create=1
if [ -f "$BUNDLE" ]; then
  heads="$(git bundle list-heads "$BUNDLE")"
  if grep -q "^$MAIN_PIN refs/heads/pin-main$" <<<"$heads" \
     && grep -q "^$PR1_PIN refs/heads/pin-pr1$" <<<"$heads" \
     && grep -q "^$SC_PIN refs/heads/pin-sourcecode$" <<<"$heads"; then
    say "bundle exists with all three pins; verifying"
    need_create=0
  else
    say "bundle exists but is missing a pin (or carries a different sha); recreating"
    rm -f "$BUNDLE"
  fi
fi
if [ "$need_create" = 1 ]; then
  say "creating wildlife.bundle (pin-main + pin-pr1 + pin-sourcecode)"
  git -C "$WORK/repo.git" bundle create "$BUNDLE" pin-main pin-pr1 pin-sourcecode
fi
git bundle verify "$BUNDLE" >/dev/null 2>&1 || die "bundle fails 'git bundle verify'"

# --- 3. Tarballs (byte-exact from the pinned trees) -------------------------
mkdir -p "$TARBALLS"
extract() { # <commit> <repo-path> <dest-name>
  local dest="$TARBALLS/$3"
  if [ ! -f "$dest" ]; then
    say "extracting $3 from ${1:0:12}:$2"
    git -C "$WORK/repo.git" show "$1:$2" > "$dest.tmp" && mv "$dest.tmp" "$dest"
  fi
}
extract "$MAIN_PIN" "raw_materials/life_090.tgz"        "life_090.tgz"
extract "$MAIN_PIN" "raw_materials/life_091.tgz"        "life_091.tgz"
extract "$MAIN_PIN" "raw_materials/life_10.tgz"         "life_10.tgz"
extract "$PR1_PIN"  "raw_materials/Life1.02Ultrix.tar"  "Life1.02Ultrix.tar"

# --- 4. Verify the three published hashes (embedded reference) --------------
check_published() { # <file> <expected-sha256>
  local got
  got="$(sha256sum "$TARBALLS/$1" | cut -d' ' -f1)"
  [ "$got" = "$2" ] || die "$1: sha256 $got != published $2"
  say "verified $1 against published checksum"
}
check_published life_090.tgz "$LIFE_090_SHA"
check_published life_091.tgz "$LIFE_091_SHA"
check_published life_10.tgz  "$LIFE_10_SHA"

# Cross-check: the in-repo checksum file must agree with our embedded copy.
git -C "$WORK/repo.git" show "$MAIN_PIN:metadata/checksums.sha256" > "$WORK/published.sha256"
( cd "$TARBALLS" && sha256sum -c --quiet "$WORK/published.sha256" ) \
  || die "in-repo metadata/checksums.sha256 disagrees with tarballs"

# --- 5. Manifest: mint once (incl. 1.02), then always verify ----------------
if [ ! -f "$MANIFEST" ]; then
  say "minting tarballs.sha256 (freezes the 1.02 hash)"
  ( cd "$TARBALLS" && sha256sum life_090.tgz life_091.tgz life_10.tgz Life1.02Ultrix.tar ) > "$MANIFEST"
fi
( cd "$TARBALLS" && sha256sum -c --quiet "$MANIFEST" ) \
  || die "tarballs do not match frozen manifest $MANIFEST"
say "manifest verified:"
sed 's/^/[acquire]   /' "$MANIFEST"

say "OK — fixtures intact (bundle + 4 tarballs + manifest)"
