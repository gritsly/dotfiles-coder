# Coder Defaults

This repository keeps Coder's default home-directory files in place and applies only small user-specific additions.

`setup` installs:

- `${CLAUDE_CONFIG_DIR:-~/.claude}/CLAUDE.md`
- `${CODEX_HOME:-~/.codex}/AGENTS.override.md`
- `~/.zshrc.user`, sourced from the existing `~/.zshrc` after Oh My Zsh loads
- `~/.ssh/ssh_config.user`, included by the devcontainer's existing SSH setup
- `C.UTF-8` as the interactive shell locale
- zsh as the login shell
- `fd`, installed through `fd-find` when needed
- personal aliases, functions, and fzf settings for the devcontainer-provided tools

It does not replace the default `.zshrc`, `.vimrc`, `.tmux.conf`, `.bashrc`, or `.gitconfig`.

The shared agent instruction source is `dotfiles.codespaces/.codex/AGENTS.override.md`. Codex loads it as personal global guidance while the company-managed `/workspaces/AGENTS.md` remains workspace guidance. The installer copies the same source to Claude's `CLAUDE.md` path.
