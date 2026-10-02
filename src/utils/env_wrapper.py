import os
from typing import Any


def get_env_var(key: str, default: Any = None) -> Any:
    """Retrieve and validate an environment variable.

    Args:
        key: str — Name of the environment variable to retrieve.
        default: Any — Value to return when the variable is absent or empty.

    Returns:
        Any — Stripped environment value or supplied default.

    Raises:
        Exception: If the environment variable is absent or contains only whitespace.
    """
    try:
        variable = os.environ[key].strip()
        if not variable:
            if default is not None:
                return default
            raise Exception(f"{key} variable found, but empty")
        return variable
    except KeyError:
        if default is not None:
            return default
        raise Exception(f"{key} variable not found") from None


def get_optional_env_var(key: str) -> str | None:
    var = os.getenv(key)
    if var is None:
        return None
    return var.strip() or None


#: Spellings an operator may reasonably write for "yes" in a helm values file.
_TRUTHY = frozenset({"1", "true", "yes", "on"})
_FALSY = frozenset({"0", "false", "no", "off"})


def get_bool_env_var(key: str, default: bool = False) -> bool:
    """Read a boolean toggle from the environment.

    Args:
        key: str — Name of the environment variable to read.
        default: bool — Value used when the variable is absent or empty.

    Returns:
        bool — Parsed toggle, or the default when the variable is unset.

    Raises:
        ValueError: If the variable is set to something that is not a boolean.
            A misspelled toggle silently taking its default is worse than a
            startup failure that names the variable.
    """
    raw = get_optional_env_var(key)
    if raw is None:
        return default
    lowered = raw.lower()
    if lowered in _TRUTHY:
        return True
    if lowered in _FALSY:
        return False
    raise ValueError(
        f"{key}={raw!r} is not a boolean; expected one of {sorted(_TRUTHY | _FALSY)}"
    )
