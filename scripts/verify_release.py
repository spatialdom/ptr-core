"""Validate distributions and test their installed contents in isolated environments."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import venv
import zipfile
from email.parser import BytesParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify(dist: Path, tag: str | None = None) -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = metadata["project"]["version"]
    if tag is not None and tag != f"v{version}":
        raise ValueError(
            f"Release tag {tag!r} does not match package version {version}."
        )
    wheel = dist / f"ptr_core-{version}-py3-none-any.whl"
    sdist = dist / f"ptr_core-{version}.tar.gz"
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        info = BytesParser().parsebytes(
            archive.read(f"ptr_core-{version}.dist-info/METADATA")
        )
        assert info["Name"] == "ptr-core" and info["Version"] == version
        assert info["License-Expression"] == "MIT"
        assert "ptr_core/py.typed" in names
        assert "ptr_core/geospatial/topology.py" in names
        assert any(name.endswith("/licenses/LICENSE") for name in names)
        assert any(name.endswith("/licenses/THIRD_PARTY_NOTICES.md") for name in names)
        assert all("extra ==" in r for r in info.get_all("Requires-Dist", [])), (
            "Base dependencies must stay empty."
        )
        assert not any(name.startswith(("tests/", "benchmarks/")) for name in names)
    with tarfile.open(sdist) as archive:
        names = set(archive.getnames())
        prefix = f"ptr_core-{version}/"
        assert prefix + "tests/conformance/ptr-v0.1/LICENSE.md" in names
        for revision in ("td-v1", "td-v2"):
            assert prefix + f"benchmarks/corpora/{revision}/corpus.json" in names
        assert prefix + "THIRD_PARTY_NOTICES.md" in names
        assert not any(
            ".benchmark-results/" in name or "/.env" in name for name in names
        )

    # Temp environments contain only the built wheel and its declared extras.
    with tempfile.TemporaryDirectory(prefix="ptr-core-release-") as temporary:
        for profile in ("dev", "dev,geospatial"):
            environment = Path(temporary) / profile.replace(",", "-")
            venv.EnvBuilder(with_pip=True).create(environment)
            python = environment / (
                "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
            )
            subprocess.run(
                [str(python), "-m", "pip", "install", f"{wheel.resolve()}[{profile}]"],
                check=True,
            )
            subprocess.run(
                [
                    str(python),
                    str(ROOT / "scripts/release_smoke.py"),
                    version,
                    "geospatial" if "geospatial" in profile else "base",
                ],
                check=True,
            )
            subprocess.run([str(python), "-m", "pytest"], cwd=ROOT, check=True)
            subprocess.run(
                [
                    str(python),
                    "-m",
                    "benchmarks.technical_description",
                    "--subset",
                    "ci",
                    "--output",
                    str(dist / f"benchmark-{profile.replace(',', '-')}.json"),
                ],
                cwd=ROOT,
                check=True,
            )
    checksums = "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in (wheel, sdist)
    )
    (dist / "SHA256SUMS").write_text(checksums, encoding="utf-8")
    print(
        json.dumps(
            {
                "version": version,
                "ptr_versions": ["0.1"],
                "wheel": wheel.name,
                "sdist": sdist.name,
                "profiles": ["base", "geospatial"],
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--tag")
    args = parser.parse_args()
    verify(args.dist.resolve(), args.tag)
