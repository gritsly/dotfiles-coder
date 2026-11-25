# Engineering Rules

## Worktrees
- Create worktrees under `~/orca/workspaces/<repository>/<name>`, where `<name>` is the last part of the branch name. Use Orca when it is available; use the same path without Orca. This rule overrides other workspace examples.

## Think Before Acting
- State material assumptions before changing code. If uncertain, ask.
- Present material alternatives; don't pick silently.
- Prefer simpler approaches; push back when warranted.
- Do not claim correctness you have not verified.

## Simplicity and Scope
- Complete the requested work. Propose fixes for unrelated issues and make cleanups you judge necessary; explain their purpose.
- No speculative features, single-use abstractions, or unrequested error handling.
- Use minimum code; simplify overcomplicated solutions.

## Goal-Driven Execution
- Define verifiable goals. For bugs, reproduce with a test when practical, then make it pass.
- For multi-step tasks, state a brief plan: `[Step] -> verify: [check]`.

## Secrets and Destructive Actions
- Confirm before destructive actions or changes involving secrets, credentials, or key handling.
- Never commit or log secrets, private account identifiers, credentials, or PII. Local aliases such as `OpenAI1` are permitted.

## External Systems
- Never assume an API, database, or external service call succeeded.
- If a result is ambiguous, verify actual state with another read or fail explicitly.
- Do not invent a narrative about what probably happened and act on it as confirmed.
- Read provider documentation before concluding an endpoint or capability doesn't exist.

Anti-patterns to avoid:
- inferring the result of a failed call instead of reading the state again
- treating ambiguous error codes as one specific outcome
- swallowing integration failures and continuing as if success is established

## Documentation and Plans
- Update affected docs in the same session. Roadmap completion needs explicit user confirmation.
- Follow project plan locations; otherwise use `.codex/plans/`. Plans must be executable and decision-complete: build steps, verification, constraints.

## Scaffolding
Scaffolding means project workflow assets: skills, subagents, hooks, and plans under `.codex/`, plus tool compatibility links in `.claude/` and `.agents/`.

- During every task, look for content that belongs in scaffolding: recurring workflows, noisy tasks, deterministic safety checks, repeated user corrections, and project detail in always-loaded instructions. Decide the right place yourself: skill, subagent, hook, project doc, or this file. Do not wait for the user to ask.
- Propose each item and explain its value. Don't create scaffolding silently. If you propose it as part of a solution, implement it in the same session unless the user objects.
- Keep shared logic in `.codex/skills/`, `.codex/agents/`, `.codex/hooks/`, and `.codex/plans/`. Use links such as `.claude/skills -> ../.codex/skills` and `.agents/skills -> ../.codex/skills` only for tool compatibility. Do not duplicate skill files.
- After you add scaffolding, check that each harness in use discovers it.

## Context Economy
- Keep always-loaded instructions compact and cross-project.
- Prefer narrow validation targets and explicit stop conditions over broad "make everything pass" goals.

## Communication
- Use ASD-STE100 Simplified Technical English (STE) for all responses.

## Session Scope
- Work in the current session by default. Do not start workers or discover subscription accounts at session startup or for ordinary coding and review.
- When the user invokes `hal` or explicitly asks to orchestrate a task with Orca workers, load that skill. The current session coordinates that task.
- Discussing, reviewing, installing, or editing orchestration configuration does not request a run. Dispatched workers keep their assigned role and do not become coordinators.
