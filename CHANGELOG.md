# Changelog

All notable changes to the `science-cli` tool will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to Semantic Versioning.

---

## [2.1.1] - 2026-05-21

### Added
- Created `issues.md` tracking footprint with Obsidian Kanban compatibility.
- Integrated active session bootstrapping via `.memory/active_session_context.md` for rapid initialization.

### Changed
- Configured Ruff rules to strictly enforce clean imports and code syntax.

---

## [2.1.0] - 2026-05-05

### Added
- Integrated basic SQLite database connectivity to read local memristor metrics.
- Added textual plotting interfaces using `rich` and `matplotlib`.
