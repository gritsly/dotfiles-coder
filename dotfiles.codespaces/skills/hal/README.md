# HAL router

`scripts/hal.py` chooses a worker route from live quota data and runs Orca's `worker-start`. `SKILL.md` tells the coordinator how to call it. This file explains the routing rules. Tests: `python3 -m unittest tests/test_hal.py` from the repository root.

## Goal

Use one Claude subscription and one Codex subscription evenly and at a steady pace through the week. Waste no weekly quota and no banked reset. Claude has the larger limits, so it runs the coordinator and does the work first. Codex reviews Claude's work and takes work when Claude is off. Claude keeps 5-hour room for the coordinator.

## Usage sources

- Codex: `codex app-server`, `account/rateLimits/read`, with the current `CODEX_HOME`.
- Claude: `GET https://api.anthropic.com/api/oauth/usage?cedar_ember=1&skip_spend=1` with the OAuth token from `$CLAUDE_CONFIG_DIR/.credentials.json`. The request uses Claude Code's User-Agent, because the server reports reset grants (`cedar_ember`) only to Claude Code. The weekly window is seven days.
- Expired Claude token (HTTP 401): HAL never refreshes the token itself, because a refresh rotates the refresh token that Claude Code stores. It runs `claude -p /usage --no-session-persistence --setting-sources ''`, which refreshes the token under Claude Code's lock without a model request, and reads usage again. If that fails, Claude is unavailable.
- Any other read error makes the route unavailable.

## Weekly pace

One pace line for both accounts, from each account's own reset time. It starts 24 hours ahead and reaches 100 % at the weekly refresh. In a seven-day window it starts at 12.5 %, reaches 18.8 % after 12 hours and 56.3 % at mid-week. An account above its line is off until the line reaches its use.

## 5-hour start limits

| Account | Work (plan, implement, research) | Review |
| --- | --- | --- |
| Claude | 80 % | 90 % |
| Codex | 60 % | 99 % |

Claude keeps at least the last 10 % for the coordinator. Each account keeps room above its work limit, so that it can still review the other account's work after the other account took over.

Rush mode does not change these limits. A start limit cannot stop a worker that is already running.

## Rush mode and banked resets

An account rushes when:

- it has at least 2 banked resets (Claude: 1, because its grants expire; Codex keeps one for an emergency),
- twice the normal weekly rate would reach 100 % at least 60 hours before its refresh, and
- it would reach 100 % before its first banked reset expires (Claude grants have `ends_at`, Codex credits have `expiresAt`).

A rush account skips weekly pacing. It does not change the route order: Codex in rush would use its 5-hour window on work and then have no room for reviews. At 100 % weekly use, HAL reads usage again, checks rush again, and redeems one reset with a fixed key per account and week:

- Codex: `account/rateLimitResetCredit/consume`.
- Claude: `POST /api/organizations/{org}/reset_rate_limits` with `{program: "cedar_ember", grant_id, request_id}`. Only grants that are usable now, not paused, and clear `seven_day` count.

After the attempt, HAL reads usage again and starts only if the start limits pass.

## Route order

| Task | Order |
| --- | --- |
| Plan, implementation, research | Claude → Codex |
| Review of Claude work | Codex → Claude |
| Review of Codex work | Claude → Codex |

`--prefer codex` puts Codex first for work. `--route` skips the order.

## Models

Claude model for work:

| Role | Small | Normal | Complex |
| --- | --- | --- | --- |
| Plan | Opus, high | Fable, medium | Fable, high |
| Plan with `--security` | Opus, high | Mythos, medium | Mythos, high |
| Implement, research | Opus, medium | Opus, high | Fable, medium |
| Implement, research with `--security` | Opus, medium | Opus, high | Mythos, medium |

Opus is the default worker, and Fable takes complex work. A plan runs one step above work of the same size. Pass `--security` when security hardening is necessary or is the main idea of the task; Mythos then takes the place of Fable.

A Codex model of similar strength reviews Claude work, or takes the work when Claude is off:

| Claude model and effort | Codex |
| --- | --- |
| Up to Opus medium | Sol, medium |
| Above Opus medium, below Fable medium | Sol, high |
| Fable medium | Sol, xhigh |
| Fable high and above, Mythos | Astra, medium |

Astra stops at medium effort, because higher effort uses the Codex limits too quickly. A Claude review of Codex work uses Opus medium for Sol up to medium, Opus high for Sol high, Fable medium for Sol xhigh and above, and Fable high for Astra. The fallback reviewer in the same family uses the implementer's model and effort in a fresh session.

The first output line of a start gives `--review-of MODEL:EFFORT` for the review.

## Pause

When a start finds no route, each blocking limit gives the time it passes: the 5-hour reset, the weekly reset, or the time the pace line reaches the weekly use. A route that two limits block opens at the later time. HAL prints the earliest opening as `hal: next opening <ISO time>`. Read errors give no time. The coordinator commits and pushes, reports the time, and stops. HAL does not wake it.
