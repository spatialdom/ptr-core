"""Load optional backends only when a capability requests them."""

from importlib import import_module
from types import ModuleType

from ptr_core.errors import MissingOptionalDependencyError


def require_dependency(module: str, *, capability: str) -> ModuleType:
    try:
        return import_module(module)
    except ModuleNotFoundError as exc:
        dependency = module.split(".")[0]
        if exc.name != dependency:
            # Preserve failures inside an installed backend; these are not a
            # missing-extra condition and need their original traceback.
            raise
        raise MissingOptionalDependencyError(dependency, capability) from exc
