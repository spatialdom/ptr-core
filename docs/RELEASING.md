# Public distribution and releases

PTR Core software is MIT licensed and versioned independently of PTR's format.
PTR specification compatibility is exposed as
`SUPPORTED_PTR_VERSIONS = ("0.1",)`; records still use `ptr_version: "0.1"`.
Library versions do not silently upgrade the record format. Python support is
3.11, 3.12, and 3.13 as covered by CI.

Versioning follows semantic-versioning intent: patch releases repair compatible
behavior, minor releases may change the pre-1.0 API with documented migration,
and a future 1.0 defines a stable compatibility commitment. Development SHA
consumers can encounter unreleased behavior changes within a recorded version;
release tags/assets must never be reassigned or replaced. Future incompatible
changes after publication require a new minor version. Supported PTR versions
are documented separately from library API compatibility.

## Current publication gates

Prepare v0.1.1 on the existing `depenndecies-cleanup` branch and merge through
the reviewed PR before publication. Keep the default branch unchanged. The wheel
and source archive must correspond to the same reviewed merged commit and
package version.

The prepublication audit on 2026-10-07 covered 18 reachable commits, 175 unique
file blobs, and 108 log files from eight available Actions runs. A scan for
recognized private-key/GitHub/AWS/PyPI/Slack credential patterns found no matches.
This pattern scan is not proof against every possible secret. Tracked files
contain Core implementation, documentation and synthetic/public test inputs;
no product database, user documents, uploaded source files, or OCR/model code is
included. Current Core APIs are independent of extractor schemas (#26), and
the complete public export inventory reflects the API naming review (#28).

Vendored public PTR fixtures carry CC BY 4.0 attribution and the original license
notice. Synthetic benchmark inputs are authored for Core. Migration fixtures
originate in private PTR Extract; their provenance declares synthetic data, but
that private revision has no redistribution license declaration. On 2026-10-07,
the maintainer approved making PTR Core public after this PR, following review
of the fixture provenance and historical copies. This approval covers public
distribution of the copies in Core under its MIT license; it does not make the
producer repository public or grant a license to its other contents.

GitHub reported PTR Core as public during PR review on 2026-10-07. The remaining
artifact publication gate is **merge of the release-preparation PR**. After
merge, build/tag the reviewed merged commit and publish the verified GitHub
release. PyPI publication remains conditional on an approved publisher being
configured.

Changing GitHub visibility exposes source history, issues, and available Actions
logs to the public. Only `spatialdom/ptr-core` is approved for this visibility
change; PTR is already public and PTR Extract remains private. Current history must be reviewed
again if additional commits or repository content arrive before publication.

## Build and verification

```bash
python -m pip install -e ".[dev,geospatial,release]"
ruff check .
mypy
pytest
python -m build
python -m twine check dist/*
python scripts/verify_release.py --tag v0.1.1
```

The verification script checks wheel/sdist metadata and required licenses,
version/tag agreement, `py.typed`, the optional-module package contents, and
absence of mandatory runtime dependencies. It installs the wheel into separate
base and geospatial environments, smoke-tests installed paths, runs the full
test suite and CI parser benchmark in both, and writes `dist/SHA256SUMS`.
Build from a clean reviewed checkout; do not distribute unrelated stale files
from `dist`. Source archives include test provenance and benchmarks; wheels
contain the reusable library and license notices.

The `Release artifacts` workflow runs on version tags or manual dispatch. It
builds and verifies distributions, retains them as Actions artifacts, and for
tags creates a **draft** GitHub release. It does not change repository visibility,
publish drafts, or upload to PyPI. Re-running an existing tag does not overwrite
a release; use a new version rather than replacing published assets.

After the PR is merged and artifact review is complete, create an annotated version tag
at the reviewed branch commit, push that tag, and publish the verified draft.
Enable immutable releases where the repository supports them, and never move a
published tag. Verify an anonymous download/install of the released wheel and
the GitHub tag after publication. The release notes provide exact artifact URLs.

No PyPI upload token, publishing environment, or trusted-publisher configuration
is currently established here. GitHub wheel/sdist assets are the initial
installable release path. Once an approved PyPI publisher is ready, configure it
for this repository/workflow, publish the same reviewed version, verify index
metadata and a clean indexed install, then use `ptr-core==0.1.1` in installation
instructions. Do not claim a PyPI release based solely on building a wheel.

## Parcel Plotter #178 handoff

Keep the application's existing pin until the public release is downloadable.
Its workspace may have unrelated in-progress changes; do not overwrite them.
Use the explicit extra and the released wheel's verified hash in its backend
dependency declaration when PyPI is unavailable:

```text
ptr-core[geospatial] @ https://github.com/spatialdom/ptr-core/releases/download/v0.1.1/ptr_core-0.1.1-py3-none-any.whl#sha256=<verified-wheel-sha256>
```

After a verified PyPI publication, prefer `ptr-core[geospatial]==0.1.1`. Docker,
CI, and local installs must consume the same immutable declaration. Retest
parser/validation/compute/georeferencing/CRS/export paths against the installed
artifact and check existing health/version metadata. Migrate external-candidate
review through a caller-owned adapter before advancing past the neutral-intake
change; a dependency pin alone cannot perform that migration. PTR Extract keeps
its separate private dependency and versioning. Do not close #178 before the
released dependency is integrated and its application tests pass.
