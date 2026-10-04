---
name: mthds-design
description: Design a new MTHDS method bundle (.mthds files) top-down, contract-first. Use when the user says "design a method", "build a method", "create a pipeline", "build a workflow", "new .mthds file", "make a method", "write a method that does X", "turn this workflow into MTHDS", or wants any new method from scratch. Construction adapts to complexity — a shallow, fully understood graph is written directly as one runnable bundle, and deep, uncertain or staged work goes stepwise, one validated signature at a time.
min_mthds_version: 0.29.0
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob

---

# Design a MTHDS bundle top-down at the right depth

Design a new `.mthds` method **contract-first**, directly or stepwise (step 3). A change to an existing method is `/mthds-edit`'s.

> **No backend setup needed**: designing and validating never run the method, so no inference backend or API key is required.

## Guards

- **Every claimed checkpoint or completion state comes from `mthds-agent validate bundle` over the whole bundle directory**, never from reading the files.
- **Never write `inputs.json`.** When the user provides files or paths, or wants to run with real data, invoke `/mthds-inputs`: it resolves paths relative to `inputs.json` rather than the working directory, formats placeholders and copies files, which a hand-written file gets wrong.
- **This skill never runs a method**: a run needs inputs and spends inference credit.

## Process

### 1. Capture the contract

Read the [MTHDS language reference](../shared/mthds-reference.md) **before writing**: it is the syntax source of truth. For what it places outside the authoring subset (`dict` field types, `PipeStructure` and the like), write the closest in-scope equivalent and call out the deviation.

Fix the **input concept(s)**, the **output concept** and the **description**, precise enough to implement against, and specify every boundary concept fully now. Shape each concept from all its known consumers: it must be structured if any consumer field-reads it (`$x.field`, a construct `from = "x.field"`), and can stay simple otherwise. Declare each concept exactly once, complete, owned by the root boundary or by the controller that introduces it.

**Announce the captured contract in one line** (inputs → output, one-sentence semantics), with the bundle home of step 2 in the same line, before writing, without waiting for a reply. Discuss only genuine ambiguity, or when the user asks to collaborate.

### 2. The bundle home

A path the user named wins. Otherwise the bundle goes in `mthds-wip/<bundle_dir>/`, `<bundle_dir>` being the `domain` with any dot turned into an underscore, and its root file is `bundle.mthds`. Do not ask the user for the location.

### 3. Infer the construction mode

**Never ask the user to choose the workflow.**

- **Direct** when the complete graph can be authored without placeholders or speculative contracts: the graph is one concrete operator; or one top-level controller whose children are concrete leaf operators; no child is a controller unless the whole nested graph and every contract is fixed and a direct layout is still clearly safer; every branch, iteration, mapping and intermediate owner is decided; every concept shape can be fixed from its consumers; every pipe can be concrete in the first coherent artifact. One controller is a strong fast-path signal, not a rule. Pipe count is secondary: cross-branch concept dependencies, uncertain ownership, or unresolved child contracts make even a lone controller stepwise.
- **Stepwise** otherwise, and even where direct holds, for a large graph that benefits from independently valid review checkpoints or on an explicit request for a scaffold, partial design, staged work, or a resumable intermediate result: read [stepwise.md](references/stepwise.md) before writing any file.

When borderline, take the simplest path that can be written **completely** and validated confidently.

### 4. Direct construction

Design the whole graph in memory, then write `bundle.mthds` top-down — metadata, concepts, the concrete main pipe, its leaves — with concept codes checked library-wide and explicit `inputs` and `output` on every pipe. Write it with your agent's file tools, never through the shell, so the plugin's hook checks it. More than one file only at a natural module boundary, never one per pipe, and every file of the bundle declares the same `domain`. Include **no temporary `PipeSignature` declarations**. Leave `model` out unless the user asks for a model, a setting or a kind of behaviour, or the pipe's input is one the default model cannot read, such as a web page for a `PipeExtract`, or the pipe is a `PipeJudge`, which always names one; then look the reference up as the language reference's [model section](../shared/mthds-reference.md#model-references) says. **If the design would need a placeholder or a guessed contract, or writing or validation exposes an unresolved structural boundary**, stop extending the draft and read [stepwise.md](references/stepwise.md) before changing any file.

### 5. Validate

```bash
mthds-agent validate bundle mthds-wip/<bundle_dir>/bundle.mthds -L mthds-wip/<bundle_dir>/ --graph
```

`-L` loads every `.mthds` file beneath the bundle directory and keeps the project's other bundles out of its namespace. Read the Markdown verdict it prints. On errors, fix from the error list and its locators, which name the offending file, then validate again; [error handling](../shared/error-handling.md) says how to recover by error domain.

### 6. The runnable gate and delivery

For a completed method, validation **without** `--allow-signatures` must pass and print the `✅ … this method is runnable.` line: this verdict is the runnable gate, so fix and re-validate until it passes. Then:

1. **Project the input schema**: run `mthds-agent inputs bundle mthds-wip/<bundle_dir>/bundle.mthds -L mthds-wip/<bundle_dir>/` and show the user the inputs the method expects. Do not save it to `inputs.json`: preparing inputs is `/mthds-inputs`'s.
2. **The flowchart**: say that validation wrote an interactive flowchart, `dry_run.html`, next to the bundle.

## Stops

| Condition | Do this |
|---|---|
| an error in the `input` domain | the bundle is wrong: fix it and validate again |
| an error in the `config` or `runtime` domain | report it, and retry once before stopping: the environment is at fault, not the bundle |
| validation fails twice on the same construct, or the contract itself looks wrong | pause and show the user |

## References

- [MTHDS language reference](../shared/mthds-reference.md): before writing any `.mthds` file.
- [stepwise.md](references/stepwise.md): stepwise at step 3 or 4.
- [Native content types](../shared/native-content-types.md): a native's fields, for `$var.field` and `from`.
- [Error handling](../shared/error-handling.md): recovering from a CLI error by its domain.
- [MTHDS agent guide](../shared/mthds-agent-guide.md): CLI syntax and output formats, `--allow-signatures` included.

---

## Workspace check (silent — never comment)

In this environment the bundle home is always `mthds-wip/<bundle_dir>/`, even when the user names another path: step 2's "a path the user named wins" does not apply here. After finishing, make sure the finished method is in the right workspace: `bundle.mthds` must be under `mthds-wip/<bundle_dir>/`. If it ended up anywhere else, move it (with its `inputs/` and any library dir) into `mthds-wip/<bundle_dir>/`. Do this silently — never mention it, unless the user named the other path, and then say in one line where the method is.

---

## Method summary (on request only)

After a successful build, do **not** volunteer a walkthrough of the method — no pipeline-flow diagram, no step-by-step breakdown of the pipes, no "here's what it does" narration. The platform renders the method visually, so a written summary here is redundant noise.

Confirm completion in one line (e.g. "Built and validated `<name>`."). Never hide problems: still surface any validation **errors, warnings, or fixes** plainly.

Give the full summary (flow + steps) **only when the user explicitly asks** — "explain it", "summarize", "what does it do", "walk me through".
