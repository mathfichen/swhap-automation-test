"""APPLY stage — write a ``BuildPlan`` into refs via git plumbing (D4).

Plumbing only — ``hash-object`` / ``mktree`` / ``update-ref`` — never a worktree
or index, so no umask / mtime / locale nondeterminism enters (crit-M5). Commit and
annotated-tag objects are composed byte-for-byte and written with
``git hash-object --literally -t commit|tag`` (see ``gitio``), never ``commit-tree``
/ ``mktag``, so git's date *front-end* is never consulted (the crit-M3 pre-1970
failure class). Bit-reproducibility (D4) is guaranteed by:

- deterministic tree assembly (``git mktree`` canonical-orders entries; explicit
  modes; ``.emptydir`` for empty dirs; symlinks as 120000 blobs);
- the author-date line = the per-release CSV date written straight into the object
  body as raw ``@<epoch> ±HHMM`` (pre-1970 epochs are negative, crit-M3) — NOT a
  ``GIT_AUTHOR_DATE`` env var (env vars are not load-bearing; ``gitio`` writes the
  raw epoch into the commit/tag body directly);
- the committer-date line and the tagger date = the single fixed curation
  timestamp, likewise written into the object body, not via ``GIT_COMMITTER_DATE``;
- stable identity strings, fixed offset formatting, no wall-clock anywhere.

Identical inputs ⇒ identical commit **and** annotated-tag object SHA-1s, across
runs and machines and regardless of the run-id (the run-id appears only in ref
*names*, never in object bytes). Writes land in ``refs/heads/candidate/**`` +
``refs/tags/candidate/**`` (or ``refs/scratch/**`` for the rebuild-compare
primitive) — never ``SourceCode``/``main`` directly (D3 interim).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..gitio import GitRunner
from ..model import TreeEntry
from .plan import (
    CANDIDATE_BRANCH_TEMPLATE,
    CANDIDATE_TAG_TEMPLATE,
    SCRATCH_BRANCH_TEMPLATE,
    SCRATCH_TAG_TEMPLATE,
    BuildPlan,
)


@dataclass
class BuildResult:
    model: str
    run_id: str
    scratch: bool
    branch_ref: str
    branch_tip: str
    commits: list[dict] = field(default_factory=list)  # index, dirname, commit, tree, parent
    tags: list[dict] = field(default_factory=list)  # release_tag, tag, tag_ref, commit

    def commit_oids(self) -> list[str]:
        return [c["commit"] for c in self.commits]

    def tag_oids(self) -> list[str]:
        return [t["tag"] for t in self.tags]


def _build_tree(git: GitRunner, entries: tuple[TreeEntry, ...]) -> str:
    """Assemble one git tree object from a flat ``TreeEntry`` list (deterministic)."""
    root: dict = {}
    for e in entries:
        comps = [c for c in e.path.split("/") if c]
        node = root
        for c in comps[:-1]:
            cb = c.encode("utf-8", "surrogateescape")
            child = node.get(cb)
            if child is None or child[0] != "tree":
                child = ("tree", {})
                node[cb] = child
            node = child[1]
        leaf = comps[-1].encode("utf-8", "surrogateescape")
        oid = git.hash_blob(e.content)
        node[leaf] = ("blob", e.mode, oid)
    return _mktree_recursive(git, root)


def _mktree_recursive(git: GitRunner, node: dict) -> str:
    entries = []
    for name_b, child in node.items():
        if child[0] == "blob":
            entries.append((child[1], "blob", child[2], name_b))
        else:
            sub = _mktree_recursive(git, child[1])
            entries.append(("040000", "tree", sub, name_b))
    return git.mktree(entries)


def execute_plan(git: GitRunner, plan: BuildPlan, run_id: str, *, scratch: bool = False) -> BuildResult:
    # committer + tagger date = the single fixed curation timestamp (D4).
    committer = (plan.curator.name, plan.curator.email, plan.curation_epoch, plan.curation_offset)
    tagger = committer

    commit_oids: list[str] = []
    commits: list[dict] = []
    tags: list[dict] = []

    for step in plan.steps:
        tree = _build_tree(git, step.entries)
        parents = [commit_oids[step.parent_index]] if step.parent_index is not None else []
        author = (step.author.name, step.author.email, step.author_date.epoch, step.author_date.offset)
        commit = git.write_commit(
            tree,
            parents=parents,
            message=step.message.encode("utf-8", "surrogateescape"),
            author=author,
            committer=committer,
        )
        commit_oids.append(commit)
        commits.append(
            {
                "index": step.index,
                "dirname": step.dirname,
                "commit": commit,
                "tree": tree,
                "parent": parents[0] if parents else None,
            }
        )
        tag_obj = git.write_tag(
            commit,
            tag=step.release_tag,
            tagger=tagger,
            message=f"Version {step.release_tag}".encode("utf-8", "surrogateescape"),
        )
        tags.append({"release_tag": step.release_tag, "tag": tag_obj, "commit": commit})

    tip = commit_oids[-1]
    if scratch:
        branch_ref = SCRATCH_BRANCH_TEMPLATE.format(run_id=run_id, model=plan.model)
        tag_template = SCRATCH_TAG_TEMPLATE
    else:
        branch_ref = CANDIDATE_BRANCH_TEMPLATE.format(model=plan.model, run_id=run_id)
        tag_template = CANDIDATE_TAG_TEMPLATE

    git.update_ref(branch_ref, tip)
    for t in tags:
        ref = tag_template.format(model=plan.model, run_id=run_id, tag=t["release_tag"])
        git.update_ref(ref, t["tag"])
        t["tag_ref"] = ref

    return BuildResult(
        model=plan.model,
        run_id=run_id,
        scratch=scratch,
        branch_ref=branch_ref,
        branch_tip=tip,
        commits=commits,
        tags=tags,
    )
