"""RepoContext — read-only git access, argv-only (never shell string
interpolation; the C1/crit-M3 injection lesson is a design rule). Pinned system
git via plumbing.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass


class GitError(RuntimeError):
    pass


def git(repo: str, *args: str, check: bool = True) -> bytes:
    """Run a git command argv-only and return stdout bytes."""
    cmd = ["git", "-C", repo, "-c", "core.quotePath=false", *args]
    p = subprocess.run(cmd, capture_output=True)
    if check and p.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed ({p.returncode}): "
            f"{p.stderr.decode('utf-8', 'replace')}"
        )
    return p.stdout


def git_text(repo: str, *args: str, check: bool = True) -> str:
    return git(repo, *args, check=check).decode("utf-8", "surrogateescape")


@dataclass
class TreeEntry:
    mode: str       # e.g. "100644", "100755", "120000", "160000"
    type: str       # "blob" | "tree" | "commit"
    blob: str       # object sha
    path: str       # repo-relative POSIX path (bytes-safe; may carry surrogates)


class RepoContext:
    def __init__(self, repo: str):
        self.repo = repo

    # ---- ref enumeration -------------------------------------------------
    def rev_parse(self, ref: str) -> str | None:
        try:
            return git_text(self.repo, "rev-parse", "--verify", ref).strip()
        except GitError:
            return None

    def ref_exists(self, ref: str) -> bool:
        return self.rev_parse(ref) is not None

    def default_branch(self) -> str | None:
        for b in ("main", "master"):
            if self.ref_exists(f"refs/heads/{b}"):
                return b
        return None

    def head(self) -> str | None:
        db = self.default_branch()
        if db:
            return self.rev_parse(f"refs/heads/{db}")
        return self.rev_parse("HEAD")

    def tags(self) -> list[str]:
        out = git_text(self.repo, "for-each-ref", "--format=%(refname)",
                       "refs/tags/")
        return sorted(line[len("refs/tags/"):] for line in out.splitlines()
                      if line.strip())

    def is_annotated_tag(self, tag: str) -> bool:
        t = git_text(self.repo, "cat-file", "-t", f"refs/tags/{tag}",
                     check=False).strip()
        return t == "tag"

    # ---- tree listing ----------------------------------------------------
    def ls_tree(self, ref: str) -> list[TreeEntry]:
        """Recursive tree listing; -z NUL-delimited, quotePath disabled, so
        paths with odd bytes survive."""
        raw = git(self.repo, "ls-tree", "-r", "-z", ref)
        entries = []
        for rec in raw.split(b"\x00"):
            if not rec:
                continue
            meta, _, path = rec.partition(b"\t")
            mode, _, rest = meta.partition(b" ")
            otype, _, sha = rest.partition(b" ")
            entries.append(TreeEntry(
                mode.decode(), otype.decode(), sha.decode(),
                path.decode("utf-8", "surrogateescape"),
            ))
        return entries

    def blob_size(self, sha: str) -> int:
        return int(git_text(self.repo, "cat-file", "-s", sha).strip())

    def cat_blob(self, sha: str) -> bytes:
        return git(self.repo, "cat-file", "blob", sha)

    def read_path(self, ref: str, path: str) -> bytes | None:
        try:
            return git(self.repo, "cat-file", "blob", f"{ref}:{path}")
        except GitError:
            return None

    # ---- commit graph ----------------------------------------------------
    def parents(self, commit: str) -> list[str]:
        out = git_text(self.repo, "rev-list", "--parents", "-n", "1", commit)
        toks = out.split()
        return toks[1:]

    def commits_on(self, ref: str) -> list[str]:
        """All commits reachable from ref, child-first order."""
        out = git_text(self.repo, "rev-list", ref)
        return out.split()

    def diff_deletions(self, ref_a: str, ref_b: str) -> list[str]:
        """Paths deleted (status D) going from ref_a's tree to ref_b's tree."""
        # --no-renames: a path absent in ref_b is a pure deletion (D), not a
        # rename — TF-3 detects the overlay-leak as missing deletions, and a
        # legitimately moved file must not masquerade as a deletion-vs-rename.
        raw = git(self.repo, "diff", "--no-renames", "--name-status", "-z",
                  ref_a, ref_b)
        toks = raw.split(b"\x00")
        out = []
        i = 0
        while i < len(toks):
            status = toks[i]
            if not status:
                i += 1
                continue
            # rename/copy entries carry two paths; D never does
            if status[:1] in (b"R", b"C"):
                i += 3
                continue
            if i + 1 >= len(toks):
                break
            path = toks[i + 1]
            if status[:1] == b"D":
                out.append(path.decode("utf-8", "surrogateescape"))
            i += 2
        return out

    def commit_subject(self, commit: str) -> str:
        """First line of the commit message (used to map a release -> commit when
        the exemplar ships no annotated tags)."""
        return git_text(self.repo, "show", "-s", "--format=%s", commit).strip()

    def tag_object(self, tag: str) -> str:
        """The annotated-tag object sha (not the commit it points to)."""
        return git_text(self.repo, "rev-parse", f"refs/tags/{tag}").strip()

    def commit_meta(self, commit: str) -> dict:
        fmt = "%an%x00%ae%x00%cn%x00%ce%x00%at%x00%ct"
        out = git(self.repo, "show", "-s", f"--format={fmt}", commit)
        an, ae, cn, ce, at, ct = out.split(b"\x00")
        return {
            "author_name": an.decode("utf-8", "surrogateescape"),
            "author_email": ae.decode("utf-8", "surrogateescape"),
            "committer_name": cn.decode("utf-8", "surrogateescape"),
            "committer_email": ce.decode("utf-8", "surrogateescape"),
            "author_date": int(at),
            "committer_date": int(ct.strip()),
        }
