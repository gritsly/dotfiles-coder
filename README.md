# Coder Defaults

This repository keeps Coder's default home-directory files in place and applies only small user-specific additions.

`setup` installs:

- `~/.claude/CLAUDE.md`
- `~/.codex/AGENTS.md`
- `~/.zshrc.user`, sourced from the existing `~/.zshrc` before Oh My Zsh loads
- `~/.ssh/config.user`, included from the existing `~/.ssh/config`
- zsh as the login shell
- `fzf`
- Claude Code and Codex CLI harnesses

It does not replace the default `.zshrc`, `.vimrc`, `.tmux.conf`, `.bashrc`, or `.gitconfig`.
