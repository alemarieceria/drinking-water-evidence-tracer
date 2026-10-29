# Superpowers skills

Installed from [obra/superpowers](https://github.com/obra/superpowers) at
commit [`2ce8aa15d05bd57213e6f746f953aafb7ded7a8b`](https://github.com/obra/superpowers/commit/2ce8aa15d05bd57213e6f746f953aafb7ded7a8b).

All 15 upstream `skills/` directories are copied here, including their supporting
files. Each skill is directly discoverable at `<skill-name>/SKILL.md` within this
project. This installs the skill files only; upstream plugin hooks and integrations
are not installed. Project instructions in `AGENTS.md` still apply.

The upstream MIT license is preserved in [SUPERPOWERS-LICENSE](SUPERPOWERS-LICENSE).
To update, use the skill-installer helper with `--repo obra/superpowers`, a reviewed
`--ref`, all upstream skill paths, and `--dest .agents/skills`. The helper refuses
to overwrite existing skills; review and replace the existing copies deliberately,
then update this revision and rerun the project checks.
