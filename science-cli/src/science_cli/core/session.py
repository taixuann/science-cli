"""Session state: current project, protocol, history."""

import json
from pathlib import Path
from datetime import datetime

SESSION_DIR = Path.home() / ".config" / "science-cli"
SESSION_FILE = SESSION_DIR / "session.json"


def _ensure_session_dir():
    SESSION_DIR.mkdir(parents=True, exist_ok=True)


def _default_session():
    return {
        "last_project": "",
        "last_protocol": "",
        "last_step": "",
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
            return json.load(f)
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
    # Clear protocol/step context when switching projects —
    # the old project's protocol should not carry over to the new one.
    sess["last_protocol"] = ""
    sess["last_step"] = ""
    save_session(sess)


def set_last_protocol(name: str):
    sess = load_session()
    sess["last_protocol"] = name
    save_session(sess)


def set_last_step(name: str):
    sess = load_session()
    sess["last_step"] = name
    save_session(sess)


def clear_last_protocol():
    """Clear the active protocol and step from session state.

    After calling this, the REPL prompt returns to project-level only,
    and plot/analyze commands no longer auto-reference a protocol.
    """
    sess = load_session()
    sess["last_protocol"] = ""
    sess["last_step"] = ""
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
