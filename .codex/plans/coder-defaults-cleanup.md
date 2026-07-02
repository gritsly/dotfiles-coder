# Coder Defaults Cleanup Plan

## Goal
Keep Coder-maintained defaults for shell, vim, tmux, bash, and git config, while installing only the requested personal additions.

## Assumptions
- Coder creates a usable `~/.zshrc` before this repository's `setup` runs.
- FZF should not use Oh My Zsh's Debian-oriented `fzf` plugin because the image can lack `/usr/share/doc/fzf/examples/*.zsh`.
- The setup script inserts the zsh user source line after `source $ZSH/oh-my-zsh.sh`, so fzf completion loads after Oh My Zsh initializes completion.
- Debian installs `fd` as `fdfind`, so setup creates a `~/.local/bin/fd` symlink when needed.
- The shell should use `C.UTF-8` and clear unsupported inherited `LC_*` category overrides.
- `Host * / User chris` should live in `~/.ssh/config.user`, included from `~/.ssh/config`, not through a symlink.
- Claude and Codex should receive the same instruction text in their normal config directories.

## Build Steps
1. Remove the generic `*.symlink` installer path.
2. Replace full `.zshrc` management with `dotfiles.codespaces/.zshrc.user`.
3. Update `setup` to:
   - copy `CLAUDE.md` and `AGENTS.md`
   - copy `~/.zshrc.user`
   - insert the source line into the existing `~/.zshrc` after Oh My Zsh loads
   - remove the legacy fzf installer source line from `~/.zshrc`
   - copy `~/.ssh/config.user`
   - append an include line to `~/.ssh/config`
   - set the login shell to zsh
   - install fd, fzf, Claude Code, and Codex
4. Remove tmux, vim, custom theme, Claude settings, ssh symlink, and installer artifacts from the tracked surface.
5. Update `README.md` with the new behavior.

## Verification
1. Run `bash -n setup`.
2. Run `zsh -n dotfiles.codespaces/.zshrc.user`.
3. Run `git status --short`.
4. Inspect the final diff and confirm no removed dotfile category is still referenced by `setup` or `README.md`.
