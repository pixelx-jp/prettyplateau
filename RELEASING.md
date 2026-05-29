# Releasing prettyplateau

Publishing is automated: **push a `vX.Y.Z` tag and CI publishes to PyPI** via
GitHub's OIDC trusted publishing — no tokens or passwords involved.

## Cut a release

1. Bump the version in **both** files (they are tracked separately and must
   stay in lock-step, or the wheel and `prettyplateau.__version__` disagree):
   - `pyproject.toml` → `version = "X.Y.Z"`
   - `src/prettyplateau/_version.py` → `__version__ = "X.Y.Z"`
2. Commit to `main` and push.
3. Tag and push the tag:
   ```bash
   git tag -a vX.Y.Z -m "prettyplateau X.Y.Z"
   git push origin vX.Y.Z
   ```
4. Watch the run: `gh run watch <id>` (workflow: `release.yml`). It builds an
   sdist + wheel, publishes to PyPI, and attaches the artifacts to a GitHub
   Release.
5. Verify: `curl -s https://pypi.org/pypi/prettyplateau/json | python3 -c "import json,sys;print(json.load(sys.stdin)['info']['version'])"`
   (PyPI's JSON index can lag ~30–60 s after the upload step succeeds.)

## One-time setup (already done — recorded for recovery)

PyPI **Trusted Publisher** for the project `prettyplateau`
(pypi.org → project → Manage → Publishing → Add → GitHub):

| Field | Value |
|---|---|
| Owner | `pixelx-jp` |
| Repository name | `prettyplateau` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

The `release.yml` job runs in the `pypi` environment with `id-token: write`;
those must match the trusted-publisher config above. No API tokens are stored.
