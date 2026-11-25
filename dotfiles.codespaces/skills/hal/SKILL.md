---
name: hal
description: Apply the user's subscription routing and review policy when the user invokes HAL to run work with Orca workers.
---

# HAL

HAL adds the user's subscription policy to Orca's `orchestration` skill. Load that skill and follow its version-matched guide for every Orca command, but start workers only through HAL's router. If the harness omits the skill, read `~/.agents/skills/orchestration/SKILL.md`. A session with Task and Dispatch IDs is a worker: follow its preamble, not HAL.

Run the coordinator on Claude Opus with medium effort.

## Start workers through the router

`HAL` below means `python3 <this skill's directory>/scripts/hal.py`. Give it the same permissions as Orca commands; it reads live Claude and Codex usage over the network. The router chooses the route, model, and effort, and runs Orca's `worker-start` with the options after `--`. Its first output line names the model, the route, and the skipped routes; Orca's receipt follows. The routing rules are in `README.md` next to this file; read it only to explain or change them. `HAL status` shows each route.

```text
HAL start --role plan|implement|research|review [--size small|normal|complex] [--security] [--prefer claude|codex] [--review-of MODEL:EFFORT] -- --spec-file <file> --worktree current [other worker-start options]
```

- `plan`: the first step of a big project that needs a lot of research and planning. Fable writes the plan to `plan.md` in the plan folder that the workspace instructions name: tasks with scope, size, dependencies, and acceptance checks. Add `--security` when security hardening is necessary or is the main idea of the project; HAL then uses Mythos. Review the plan, then start workers on its tasks.
- `implement` and `research`: Opus, or Sonnet for `small`. They cover security in these tasks, so do not pass `--security`.
- Claude goes first. Codex takes the task when Claude is off, for example when Claude's 5-hour use is above 80 %. Claude reviews can run up to 90 %; the rest is for you.
- `review`: `--review-of` takes `MODEL:EFFORT` from the implementer's first output line. The router picks a model of similar strength in the other family first.
- `--size`: `small` for simple or mechanical work, `complex` for hard design or debugging.
- Do not pass `--agent`. Pass `--prefer` only when the task clearly suits one model family. Pass `--model`, `--effort`, or `--route <route>` only when the user named them.
- Exit code 3 means no route is available. When a limit gives a time, the last line is `hal: next opening <ISO time>`.

When a worker stops on a quota limit, start the task again through the router. Retry once using the live quota check. If the provider reports the same limit again, report the discrepancy and the pending task.

## Commit and push

When you pause on quota (pending tasks get exit code 3 and no worker is running) and when the work is done, in each repository with work: if it is on its default branch, create a branch first. Commit all changes of the Run (never secrets) and push with upstream. Report the branches, the pending tasks, and the earliest `hal: next opening` time if any start printed one. Then end your turn. The user continues the Run in the same session later.

## Lean coordinator

- Do not implement. Plan, dispatch, answer worker questions, and report. Answer directly only when no file change or check is necessary.
- Start independent tasks together so that both subscriptions work in parallel. Each spec gives scope, acceptance criteria, and required checks, and ends with: "Finish with a `worker_done` report of at most 15 lines: outcome, changed files, check results, open issues. Do not paste diffs or logs."
- Do not read diffs or logs; the reviewer does.

## Review

1. When the implementer reports, start one reviewer with `HAL start --role review --review-of <MODEL:EFFORT>`. Give it the spec, the implementer's report, and the required checks. It reviews the diff, fixes defects within scope, runs the checks, and reports in the same format.
2. Use `send` to give the reviewer's report to the implementer only if the reviewer changed behavior or reports a disagreement. The implementer decides and reports. Do not start a second review.
3. Report to the user per task: outcome, checks that passed, failed, or did not run, open findings, and the models used.
