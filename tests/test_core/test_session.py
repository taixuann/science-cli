"""Tests for core/session.py — 3-level state memory."""

from science_cli.core.session import (
    load_session,
    save_session,
    set_last_project,
    set_last_protocol,
    set_last_step,
    save_project_state,
    load_project_state,
    save_protocol_state,
    load_protocol_state,
    save_step_state,
    load_step_state,
    clear_project_state,
    clear_protocol_state,
    clear_step_state,
    save_context_state,
    restore_context_state,
    get_active_theme,
    set_active_theme,
    add_history,
    get_history,
)


class TestSessionState:
    """Session state loading/saving."""

    def test_load_session_returns_dict(self, mock_session):
        sess = load_session()
        assert isinstance(sess, dict)
        assert "last_project" in sess
        assert "last_step" in sess

    def test_save_session_persists(self, mock_session):
        save_session({"last_project": "test-proj", "last_step": ""})
        sess = load_session()
        assert sess["last_project"] == "test-proj"


class TestThreeLevelMemory:
    """3-level state memory (project → protocol → step)."""

    def test_set_last_step(self, mock_session):
        set_last_step("step-4")
        sess = load_session()
        assert sess["last_step"] == "step-4"

    def test_set_last_protocol(self, mock_session):
        set_last_protocol("protocol-1")
        sess = load_session()
        assert sess["last_protocol"] == "protocol-1"

    def test_set_last_project(self, mock_session):
        set_last_project("my-project")
        sess = load_session()
        assert sess["last_project"] == "my-project"

    def test_save_project_state(self, mock_session):
        save_project_state({"my-project": {"last_protocol": "p1"}})
        state = load_project_state()
        assert "my-project" in state

    def test_save_protocol_state(self, mock_session):
        save_protocol_state({"p1": {"last_step": "s1"}})
        state = load_protocol_state()
        assert state["p1"]["last_step"] == "s1"

    def test_save_step_state(self, mock_session):
        save_step_state({"s1": {"last_file": "data.csv"}})
        state = load_step_state()
        assert state["s1"]["last_file"] == "data.csv"

    def test_clear_project_state(self, mock_session):
        sess = {"project_state": {"p1": {}}}
        clear_project_state(sess)
        assert sess["project_state"] == {}

    def test_clear_protocol_state(self, mock_session):
        sess = {"protocol_state": {"p1": {}}}
        clear_protocol_state(sess)
        assert sess["protocol_state"] == {}

    def test_clear_step_state(self, mock_session):
        sess = {"step_state": {"s1": {}}}
        clear_step_state(sess)
        assert sess["step_state"] == {}


class TestSessionFeatures:
    """Session features: theme, history, context save/restore."""

    def test_theme_default(self, mock_session):
        assert get_active_theme() == "publication-acs"

    def test_set_theme(self, mock_session):
        set_active_theme("dark")
        assert get_active_theme() == "dark"

    def test_add_history(self, mock_session):
        add_history("test command")
        history = get_history()
        assert len(history) == 1
        assert history[0] == "test command"

    def test_history_limit(self, mock_session):
        for i in range(250):
            add_history(f"cmd-{i}")
        history = get_history()
        assert len(history) <= 200

    def test_save_context_state(self, mock_session):
        set_last_project("p")
        set_last_protocol("pr")
        set_last_step("s")
        save_context_state()
        sess = load_session()
        assert sess["last_project"] == "p"

    def test_restore_context_state(self, mock_session):
        save_project_state({"p": {"last_protocol": "pr"}})
        restore_context_state()
        state = load_project_state()
        assert state["p"]["last_protocol"] == "pr"
