"""``GitRunner`` — the **only** module that spawns git (core-pipeline.md §2).

Hard rules enforced here, by construction:

- **argv-only, never a shell** (C1 / crit-M3 dt2sg injection class). Every
  git invocation is a ``list[str]`` plus an explicit env dict. CSV-derived values
  (commit/tag messages, author identities, dates) reach git **only** via stdin or
  the environment, never argv; the single CSV-derived value that appears on an
  argv (a release tag) does so embedded inside a ``refs/tags/candidate/…`` path,
  which cannot be option-parsed.
- **ref-policy guard**: ``update_ref`` permits exactly the frozen build
  namespaces — ``refs/heads/candidate/**``, ``refs/tags/candidate/**`` and
  ``refs/scratch/**`` (§3.1.6). Anything else (final tags, ``SourceCode``, the
  default branch, ``refs/heads/ai/proposal/**``) raises ``HB-REF-POLICY`` (exit
  14) — those are written only by the M2/M4 capability holders, not the builder.
- **deterministic environment**: config is neutralized (``GIT_CONFIG_GLOBAL`` /
  ``GIT_CONFIG_SYSTEM`` → /dev/null, ``GIT_CONFIG_NOSYSTEM``), locale pinned to
  ``C``, ``TZ=UTC``. Object hashes never depend on the host's git config, locale
  or umask (no worktree, no index — plumbing only — so crit-M5 nondeterminism
  cannot enter).
"""

from __future__ import annotations

import os
import subprocess

from .errors import HistoryError

_ALLOWED_REF_PREFIXES = (
    "refs/heads/candidate/",
    "refs/tags/candidate/",
    "refs/scratch/",
)


def _base_env() -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
        "LANG": "C",
        "TZ": "UTC",
    }
    # honor an alternate git binary location if set, but never user config.
    for k in ("SYSTEMROOT", "HOME"):
        if k in os.environ:
            env[k] = os.environ[k]
    return env


class GitRunner:
    """Argv-only git plumbing bound to one repository (``cwd``)."""

    def __init__(self, repo: str, *, allow_scratch_only: bool = False):
        self.repo = os.path.abspath(repo)
        self.allow_scratch_only = allow_scratch_only

    # --- low-level -----------------------------------------------------------
    def run(
        self,
        args: list[str],
        *,
        input_bytes: bytes | None = None,
        env_extra: dict[str, str] | None = None,
    ) -> bytes:
        env = _base_env()
        if env_extra:
            env.update(env_extra)
        proc = subprocess.run(  # noqa: S603 - argv list, never shell
            ["git", *args],
            cwd=self.repo,
            env=env,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
        if proc.returncode != 0:
            raise HistoryError(
                f"git {' '.join(args[:2])} failed: "
                f"{proc.stderr.decode('utf-8', 'replace').strip()}",
                code="HB-GIT-VERSION" if args[:1] == ["version"] else "HB-PLAN-DRIFT",
                argv=args,
            )
        return proc.stdout

    def version(self) -> str:
        return self.run(["version"]).decode().strip()

    # --- object construction (deterministic) --------------------------------
    def hash_blob(self, content: bytes) -> str:
        return self.run(["hash-object", "-w", "-t", "blob", "--stdin"], input_bytes=content).decode().strip()

    def mktree(self, entries: list[tuple[str, str, str, bytes]]) -> str:
        """Build one tree object from ``(mode, type, oid, name_bytes)`` entries.

        ``git mktree`` sorts entries into canonical git tree order itself, so the
        resulting tree oid is independent of input order — but we also feed names
        bytewise-sorted for stability of the on-the-wire bytes.
        """
        lines = []
        for mode, typ, oid, name_b in sorted(entries, key=lambda e: e[3]):
            lines.append(b"%s %s %s\t%s" % (mode.encode(), typ.encode(), oid.encode(), name_b))
        stdin = b"\n".join(lines) + b"\n"
        return self.run(["mktree"], input_bytes=stdin).decode().strip()

    @staticmethod
    def _ident(role: str, ident: tuple[str, str, int, str]) -> bytes:
        # "<role> <name> <email> <epoch> <±HHMM>". The raw epoch is written
        # straight into the object body, so a negative (pre-1970, crit-M3) epoch
        # is recorded faithfully — git's date *front-end* (which rejects @<neg>)
        # is never consulted. Identity bytes carry CSV-derived values but only
        # ever via this stdin object body, never argv (C1).
        name, email, epoch, tz = ident
        return ("%s %s <%s> %d %s" % (role, name, email, epoch, tz)).encode("utf-8", "surrogateescape")

    @staticmethod
    def _normalize_message(message: bytes) -> bytes:
        # exactly one trailing LF (git commit/tag convention); interior LFs kept.
        return message.rstrip(b"\n") + b"\n"

    def write_commit(
        self,
        tree: str,
        *,
        parents: list[str],
        message: bytes,
        author: tuple[str, str, int, str],  # name, email, epoch, ±HHMM
        committer: tuple[str, str, int, str],
    ) -> str:
        """Compose a commit object and write it via ``git hash-object -t commit``.

        Direct object construction (rather than ``commit-tree``) makes the build
        independent of git's date-parsing front-end — the documented crit-M3
        failure class for pre-1970 dates — and pins every byte of the object, so
        the SHA-1 is identical across runs, machines and git versions (D4).
        """
        lines = [b"tree " + tree.encode()]
        for p in parents:
            lines.append(b"parent " + p.encode())
        lines.append(self._ident("author", author))
        lines.append(self._ident("committer", committer))
        lines.append(b"")  # blank line before message
        body = b"\n".join(lines) + b"\n" + self._normalize_message(message)
        return self.run(["hash-object", "--literally", "-t", "commit", "-w", "--stdin"], input_bytes=body).decode().strip()

    def write_tag(
        self,
        obj: str,
        *,
        tag: str,
        tagger: tuple[str, str, int, str],  # name, email, epoch, ±HHMM
        message: bytes,
    ) -> str:
        """Compose an annotated tag object and write it via ``git hash-object -t tag``.

        Same rationale as ``write_commit``: byte-pinned, negative-epoch-safe,
        version-independent annotated tags (the tagger date is the fixed curation
        timestamp, D4)."""
        header = (
            b"object " + obj.encode() + b"\n"
            b"type commit\n"
            b"tag " + tag.encode("utf-8", "surrogateescape") + b"\n"
            + self._ident("tagger", tagger) + b"\n"
            b"\n"
        )
        return self.run(
            ["hash-object", "--literally", "-t", "tag", "-w", "--stdin"],
            input_bytes=header + self._normalize_message(message),
        ).decode().strip()

    # --- refs (guarded) ------------------------------------------------------
    def _check_ref(self, ref: str) -> None:
        ok = ref.startswith(_ALLOWED_REF_PREFIXES)
        if self.allow_scratch_only:
            ok = ref.startswith("refs/scratch/")
        if not ok:
            raise HistoryError(
                f"ref-policy: builder may not write {ref!r} "
                "(allowed: refs/heads/candidate/**, refs/tags/candidate/**, refs/scratch/**)",
                code="HB-REF-POLICY",
                ref=ref,
            )

    def update_ref(self, ref: str, oid: str) -> None:
        self._check_ref(ref)
        # ref is namespace-prefixed (never starts with '-'); oid is hex.
        self.run(["update-ref", "--", ref, oid])

    def rev_parse(self, ref: str) -> str | None:
        try:
            return self.run(["rev-parse", "--verify", "--quiet", ref]).decode().strip() or None
        except HistoryError:
            return None

    def cat_file_type(self, oid: str) -> str:
        return self.run(["cat-file", "-t", oid]).decode().strip()

    def ls_tree_names(self, treeish: str) -> list[str]:
        out = self.run(["ls-tree", "--name-only", treeish]).decode("utf-8", "surrogateescape")
        return [line for line in out.splitlines() if line]
