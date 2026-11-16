# Provenance maps

This repository is a rewritten copy of a private original. These two files, written by `git filter-repo`
when the copy was made, map every original hash to its hash here. Both are plain text, with a header line
`old new` (or `old new ref`) followed by one row per object, full 40-character SHA-1 hashes.

| File | Rows | What it maps |
|---|---|---|
| `commit-map` | 67 | every commit of the original → the same commit in this copy |
| `ref-map` | 7 | the original branch heads and the five **tag objects** → their counterparts here |

The maps cover the original history up to its commit `0fdde3c` (copy `da2b9a0`). Commits made in this
copy after that one (such as the one adding this folder) have no original and are not in the maps.

## Translating a hash

Commit messages and `audit_log.jsonl` quote **original** hashes (often abbreviated to 7 or 8 characters).
To find the corresponding commit here:

```bash
# original commit -> this copy (prefix match works for abbreviated hashes)
awk '$1 ~ /^47a0b6f/ {print $2}' provenance/commit-map

# this copy -> original
awk '$2 ~ /^209598f/ {print $1}' provenance/commit-map

# tags: original tag object -> tag object here
grep refs/tags/ provenance/ref-map
```

## Checking the maps yourself

For any row of `commit-map`, the two commits have the same author and committer names and dates and the
same message; their trees are identical except for `audit_log.jsonl`, which differs only as described in
the README's provenance section. Commits before `a79667a` (original) have identical trees. Checking the
left-hand column needs read access to the private original, which is available on request.
