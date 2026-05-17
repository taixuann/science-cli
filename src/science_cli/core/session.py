"""Session state: current project, protocol, history."""

import json
from datetime import datetime
from pathlib import Path

SESSION_DIR = Path.home() / ".config" / "science-cli"
SESSION_FILE = SESSION_DIR / "session.json"


def _ensure_session_dir():
    SESSION_DIR.mkdir(parents=True, exist_ok=True)


def _default_session():
    return {
        "last_project": "",
        "last_protocol": "",
        "last_step": "",
        "project_state": {},       # Project-level metadata for auto-save/restore
        "protocol_state": {},      # Protocol-level metadata for auto-save/restore
        "step_state": {},          # Step-level metadata for auto-save/restore
        "history": [],
        "theme": "publication-acs",
        "fzf_opts": {
            "height": "60%",
            "border": "rounded",
            "layout": "reverse",
            "preview_window": "right:50%:border-sharp",
        },
        "updated": datetime.now().isoformat(),
    }


def load_session() -> dict:
    _ensure_session_dir()
    if not SESSION_FILE.exists():
        sess = _default_session()
        save_session(sess)
        return sess
    try:
        with open(SESSION_FILE) as f:
            sess = json.load(f)
        # Auto-migrate: ensure new keys exist in old session files
        defaults = _default_session()
        changed = False
        for key in defaults:
            if key not in sess:
                sess[key] = defaults[key]
                changed = True
        if changed:
            save_session(sess)
        return sess
    except (json.JSONDecodeError, OSError):
        sess = _default_session()
        save_session(sess)
        return sess


def save_session(session: dict):
    _ensure_session_dir()
    session["updated"] = datetime.now().isoformat()
    with open(SESSION_FILE, "w") as f:
        json.dump(session, f, indent=2)


def set_last_project(name: str):
    sess = load_session()
    sess["last_project"] = name
    save_session(sess)


def set_last_protocol(name: str):
    sess = load_session()
    sess["last_protocol"] = name
    save_session(sess)


def set_last_step(name: str):
    sess = load_session()
    sess["last_step"] = name
    save_session(sess)


def get_fzf_opts() -> dict:
    return load_session().get("fzf_opts", _default_session()["fzf_opts"])


def set_fzf_opts(opts: dict):
    sess = load_session()
    sess["fzf_opts"] = opts
    save_session(sess)


def get_active_theme() -> str:
    return load_session().get("theme", "publication-acs")


def set_active_theme(name: str):
    sess = load_session()
    sess["theme"] = name
    save_session(sess)


def add_history(cmd: str):
    sess = load_session()
    sess.setdefault("history", []).append(cmd)
    if len(sess["history"]) > 200:
        sess["history"] = sess["history"][-200:]
    save_session(sess)


def get_history() -> list:
    return load_session().get("history", [])


# ── 3-Level State Memory ──────────────────────────────────────────
# project_state, protocol_state, and step_state support auto-save/restore
# when closing and reopening context at each level.


def save_project_state(state: dict | None = None) -> None:
    """Merge `state` into the session's project_state dict and persist.

    If `state` is None, no-op (preserves existing project_state).
    Called before closing a project to snapshot metadata.
    """
    if state is None:
        return
    sess = load_session()
    sess.setdefault("project_state", {})
    sess["project_state"] |= state  # dict merge (Python 3.9+)
    save_session(sess)


def load_project_state() -> dict:
    """Return the current project_state dict from the session."""
    return load_session().get("project_state", {})


def clear_project_state(sess: dict) -> None:
    """Clear project_state (called during close -m project)."""
    sess["project_state"] = {}


def save_protocol_state(state: dict | None = None) -> None:
    """Merge `state` into the session's protocol_state dict and persist."""
    if state is None:
        return
    sess = load_session()
    sess.setdefault("protocol_state", {})
    sess["protocol_state"] |= state
    save_session(sess)


def load_protocol_state() -> dict:
    """Return the current protocol_state dict from the session."""
    return load_session().get("protocol_state", {})


def clear_protocol_state(sess: dict) -> None:
    """Clear protocol_state (called during close -m protocol)."""
    sess["protocol_state"] = {}


def save_step_state(state: dict | None = None) -> None:
    """Merge `state` into the session's step_state dict and persist."""
    if state is None:
        return
    sess = load_session()
    sess.setdefault("step_state", {})
    sess["step_state"] |= state
    save_session(sess)


def load_step_state() -> dict:
    """Return the current step_state dict from the session."""
    return load_session().get("step_state", {})


def clear_step_state(sess: dict) -> None:
    """Clear step_state (called during close -m step)."""
    sess["step_state"] = {}


def save_context_state() -> None:
    """Save all 3 levels of context state at once.

    Called before closing a protocol or project to snapshot
    project_state, protocol_state, and step_state simultaneously.
    Current last_project, last_protocol, last_step serve as keys.
    """
    sess = load_session()

    # Ensure all state dicts exist
    for key in ("project_state", "protocol_state", "step_state"):
        sess.setdefault(key, {})

    save_session(sess)


def restore_context_state() -> None:
    """Restore all 3 levels of context state at once.

    Called after opening a project/protocol to reload saved metadata.
    The state dicts are already loaded from session.json — this is a
    convenience function that can trigger side-effects in future (e.g.,
    rebuilding file index, re-loading protocol YAML into memory).
    """
    sess = load_session()
    # Ensure all state dicts exist (for backward compat with old sessions)
    for key in ("project_state", "protocol_state", "step_state"):
        sess.setdefault(key, {})
    # Currently a no-op for side-effects; callers access state dicts directly.
    # Future: could rebuild in-memory caches from the restored dicts.
