# Coder Defaults

This repository keeps Coder's default home-directory files in place and applies only small user-specific additions.

`setup` installs:

- `~/.claude/CLAUDE.md`
- `~/.codex/AGENTS.md`
- `~/.zshrc.user`, sourced from the existing `~/.zshrc` after Oh My Zsh loads
- `~/.ssh/config.user`, included from the existing `~/.ssh/config`
- `C.UTF-8` as the interactive shell locale
- zsh as the login shell
- `fd`, installed through `fd-find` when needed
- `fzf`, installed as a binary without modifying shell rc files
- Claude Code and Codex CLI harnesses

It does not replace the default `.zshrc`, `.vimrc`, `.tmux.conf`, `.bashrc`, or `.gitconfig`.
