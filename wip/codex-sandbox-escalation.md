# Codex Sandbox Escalation Handoff

## Context

We observed that MTHDS bundle validation works inside the Codex sandbox, but running a bundle can fail when Pipelex tries to fetch remote configuration.

The specific failing command was:

```bash
mthds-agent run bundle ./mthds-wip/job_offer_cv_screening/ --dry-run --mock-inputs
```

It failed with:

```json
{
  "error": true,
  "error_type": "RemoteConfigFetchError",
  "message": "Failed to fetch remote configuration from https://pipelex-config.s3.eu-west-3.amazonaws.com/pipelex_remote_config_10.json after 5 attempts: [Errno 8] nodename nor servname provided, or not known",
  "hint": "Check internet connection and firewall settings, or disable pipelex_gateway in backends.toml",
  "error_domain": "config"
}
```

This is an environment/configuration issue, not a `.mthds` bundle schema issue. In the same session:

- `mthds-agent validate bundle ... --graph` succeeded.
- `mthds-agent inputs bundle ...` succeeded.
- `mthds-agent run bundle ... --dry-run --mock-inputs` failed because execution startup attempted a network fetch blocked by the sandbox.

## Key Constraint

A Codex skill or plugin cannot force commands to run outside the sandbox.

The skill can only instruct the Codex agent to request sandbox escalation through the shell tool. The user, and possibly Codex auto-review, still controls whether that request is approved.

So plugin instructions should not say "run outside the sandbox directly." They should say "request escalation before running this command."

## Recommended Skill Guidance

For MTHDS run commands, add guidance like this to the skill:

```md
When executing `mthds-agent run bundle ...`, request sandbox escalation before running it. Pipelex may fetch remote config during runner startup, and this fails in Codex sandboxes with blocked network access.

Use the shell tool with:

- `sandbox_permissions`: `"require_escalated"`
- `justification`: `"Do you want to allow this MTHDS run outside the sandbox so Pipelex can fetch remote config?"`
- `prefix_rule`: `["mthds-agent", "run", "bundle"]`

Do not request escalation for validation or input-schema generation unless those commands fail for sandbox-related reasons.
```

## Recommended Workflow

For MTHDS plugin skills, use this split:

1. Run environment checks normally.
2. Build and edit `.mthds` bundles normally.
3. Run `mthds-agent validate bundle ... --graph` inside the sandbox.
4. Run `mthds-agent inputs bundle ...` inside the sandbox.
5. For `mthds-agent run bundle ...`, request escalation up front when execution is part of the task.
6. If a non-escalated run is attempted and fails with `RemoteConfigFetchError`, DNS failure, connection failure, or blocked network symptoms, rerun with `sandbox_permissions: "require_escalated"`.

## Example Tool Call Shape

The agent should call the shell tool roughly like this:

```json
{
  "cmd": "mthds-agent run bundle /path/to/bundle_dir/ --dry-run --mock-inputs",
  "sandbox_permissions": "require_escalated",
  "justification": "Do you want to allow this MTHDS run outside the sandbox so Pipelex can fetch remote config?",
  "prefix_rule": ["mthds-agent", "run", "bundle"]
}
```

The exact command can vary, but the prefix rule should stay narrow. Avoid broad prefix rules such as `["mthds-agent"]` because they approve too much.

## What The Skill Should Avoid

- Do not imply that a plugin manifest can bypass sandboxing.
- Do not claim that skill instructions are guaranteed to be honored.
- Do not use broad escalation prefixes for convenience.
- Do not request escalation for every MTHDS command by default.
- Do not treat remote config fetch failures as bundle validation failures.

## Suggested User-Facing Explanation

If the run fails inside the sandbox, the agent can explain it this way:

> The bundle validated successfully, but execution startup failed because Pipelex tried to fetch remote configuration and the current Codex sandbox blocks that network path. This is not a schema error in the `.mthds` file. I need to rerun `mthds-agent run bundle ...` with sandbox escalation so the runner can access remote config.

## Practical Policy

Escalate only where the command genuinely needs capabilities the sandbox does not provide.

For this plugin, that means:

- Safe inside sandbox: `mthds-agent validate bundle`, `mthds-agent inputs bundle`, local file edits, local bundle assembly.
- Usually needs escalation: `mthds-agent run bundle` when Pipelex Gateway or remote config is enabled.
- Escalate after failure: any command that fails with DNS, registry, network, remote config, or permission errors that are plausibly sandbox-caused.

