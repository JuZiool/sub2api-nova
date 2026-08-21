# Nova Fusion Inputs

`fusion.json` defines the three source layers used by the Nova build:

1. Official `Wei-Shaw/sub2api`.
2. Codex quota overdraft `DeanZFC/sub2api-overdraft`.
3. Nova's tracked and working-tree overlay.

Generate a local immutable input snapshot without changing any repository:

```bash
python3 scripts/detect_fusion.py --output build/fusion-detection.json
```

The snapshot records each repository commit, version, dirty paths, the combined Nova overlay hash, and a canonical SHA-256 fingerprint. It does not fetch, merge, build, publish, or modify Git state.

Generate a candidate tree in a separate output directory. The source repositories and the Nova worktree are never changed:

```bash
python3 scripts/fuse_candidate.py --output build/candidate
```

CI can provide clean source checkouts explicitly:

```bash
python3 scripts/detect_fusion.py \
  --official-root build/sources/official \
  --overdraft-root build/sources/overdraft \
  --output build/fusion-detection.json
python3 scripts/fuse_candidate.py \
  --official-root build/sources/official \
  --overdraft-root build/sources/overdraft \
  --output build/candidate
```

Build a local Docker candidate after fusion:

```bash
python3 scripts/build_candidate_image.py --tag sub2api-nova:candidate
```

The builder runs Go tests against the candidate tree. The Dockerfile runs the exact candidate frontend build (`vue-tsc -b && vite build`) before compiling the embedded backend. It only creates a local image and writes `build/candidate-image/build-metadata.json`; it does not run or replace a container.
