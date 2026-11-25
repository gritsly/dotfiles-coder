# Coder Defaults

This repository keeps Coder's default home-directory files in place and applies only small user-specific additions.

`setup` installs:

- `${CLAUDE_CONFIG_DIR:-~/.claude}/CLAUDE.md`
- `${CODEX_HOME:-~/.codex}/AGENTS.override.md`
- the global git `user.name`, and `user.email` from `DOTFILES_GIT_EMAIL` or else from the Claude Code login
- the `hal` skill in `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/hal`
- `~/.zshrc.user`, sourced from the existing `~/.zshrc` after Oh My Zsh loads
- `~/.ssh/ssh_config.user`, included by the devcontainer's existing SSH setup
- `C.UTF-8` as the interactive shell locale
- zsh as the login shell
- `fd`, installed through `fd-find` when needed
- personal aliases, functions, and fzf settings for the devcontainer-provided tools

Coder runs `setup` outside a login shell. `setup` therefore sources `/etc/profile.d/config-dirs.sh` when it exists, so `CLAUDE_CONFIG_DIR` and `CODEX_HOME` match the devcontainer.

It does not replace the default `.zshrc`, `.vimrc`, `.tmux.conf`, `.bashrc`, or `.gitconfig`. It sets only the git identity keys in `.gitconfig`.

The `hal` skill coordinates Orca workers: Claude coordinates and does the work first, Codex reviews and takes work when Claude is off, and starts follow live quotas. See `dotfiles.codespaces/skills/hal/README.md`. Tests: `python3 -m unittest tests/test_hal.py`.

The portable agent instruction source is `dotfiles.codespaces/AGENTS.md`. The installer writes it as Codex's `AGENTS.override.md` so it can coexist with a managed `AGENTS.md`, and copies the same source to Claude's `CLAUDE.md` path.
