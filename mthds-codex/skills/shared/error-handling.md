# Error Handling Reference

Canonical reference for all `mthds-agent` error types, recovery strategies, and error classification.

## Error Output Format

On failure, `mthds-agent` prints its error report to **stderr** and exits with a non-zero code. `run`, `validate` and `init` print it in Markdown by default, which an agent reads as it is; `--error-format json` gives JSON, and so does `--format json`, which `--error-format` follows when it is omitted. The commands that print JSON on success, `inputs`, `install` and `package`, report their errors in JSON.

## Error Domains

| Domain | Meaning | Who Fixes |
|--------|---------|-----------|
| `input` | Bad .mthds, wrong CLI args, bad JSON | Agent can fix directly |
| `config` | Missing API keys, wrong model routing, environment issues | Environment/config changes needed with the user's consent or assistance |
| `runtime` | Pipeline execution failure, transient errors | Depends on cause |

## Validation Errors

When `mthds-agent validate bundle` reports a list of errors.

### Validation Error Types

From pipelex 0.90.0 the Markdown error report lists each error as `` - `<code>`: <detail> (<location>) ``: match the **Code** column. Before 0.90.0 it numbered each error and titled it in bold with its type in words, such as `1. **Missing Input Variable**` for `missing_input_variable`: match the **Type before 0.90.0** column. Where one code covers several types, the error's detail says which.

| Code | Type before 0.90.0 | Meaning | Fix Strategy |
|------|--------------------|---------|--------------|
| `method.input_undeclared` | `missing_input_variable` | Pipe prompt references a variable not in `inputs` | Add the missing variable to the pipe's `inputs` line |
| `method.input_unused` | `extraneous_input_variable` | Pipe declares an input never used | Remove the unused variable from `inputs` |
| `method.input_concept_mismatch` | `input_stuff_spec_mismatch` | Input concept type doesn't match sub-pipe expectation | Correct the concept type in `inputs` |
| `method.output_concept_mismatch` | `inadequate_output_concept` | Output concept doesn't match connected pipes | Fix the `output` field to the correct concept |
| `method.output_concept_mismatch` | `llm_output_cannot_be_image` | PipeLLM cannot output Image directly | Use PipeImgGen for image generation instead |
| `method.output_multiplicity_mismatch` | `inadequate_output_multiplicity` | Output single/list mismatch | Add or remove `[]` from the output concept |
| `method.cycle` | none: an error headed **Validation Error**, whose message starts `Cycle detected` | Declarations form a cycle, such as concepts that refine or reference one another in a loop | Break the cycle the error names by removing one of its links |
| `method.identifier_invalid` | `invalid_pipe_code_syntax` | Pipe code doesn't follow snake_case | Rename the pipe to valid snake_case |
| `method.concept_unresolved` | `unknown_concept`, `unresolved_concept` | Referenced concept not defined in bundle | Add the concept definition, or fix the typo |
| `method.name_conflict` | `batch_item_name_collision` | `input_item_name` collides with `input_list_name` or an `inputs` key | Rename `input_item_name` to a distinct singular form (e.g., list `"reports"` → item `"report"`) |
| `method.identifier_invalid` | `invalid_input_name` | An input name that is not a plain `snake_case` name, such as a dotted `"invoice.total"` or a dotted `input_list_name`, or a name starting with the reserved prefix `_bound_` | Declare the root with its whole concept and read the field through it in the template, or bind the field to a plain name with a binding step in the calling sequence and declare that name; rename a `_bound_` name |
| `method.binding_step_invalid` | `binding_step_invalid` | A malformed sequence step: `pipe` beside `from`, a binding step without `result` or carrying a pipe step's field, a `from` or `result` outside its grammar, or a binding step or dotted `batch_over` in a `PipeParallel` branch | Give a binding step `from` and a plain `result` only; bind in a sequence step before the `PipeParallel` |
| `method.field_path_unresolved` | `binding_path_unresolved` | A binding path, or a dotted `batch_over`, that the declared structures cannot walk | Fix the segment the message names, using the fields it lists, or bind the value itself |
| `method.optional_unhandled` | `optional_not_handled`, `optional_output_required`, `optional_input_unguarded`, `optional_branch_required_field` | A maybe-absent value, such as a binding over a field that is not `required`, escapes through a boundary that is not optional | Read it through an optional input (`X?`) with a guard, declare the output `?`, or mark the field `required` when the data always carries it |
| `model.unknown` | `unknown_model` | A pipe's `model` (or a `PipeLLM`'s `model_to_structure`) names a model the model deck does not define, or a bare name the deck serves only as another model type; a run refuses the bundle with the same item, raised as `PipeOperatorModelChoiceError` | Write a reference the deck defines: the item carries the deck's close matches, and `mthds-agent models --type <category>` lists the presets, aliases and waterfalls the runner serves |
| `method.schema_violation` | `unknown_validation_error` | Uncategorized validation issue | Read the error's detail, its message before 0.90.0 |

## Inference Setup Errors

A live run on a machine where inference was never set up fails on the missing configuration or the missing key, and what fails depends on where the run executes. Editing the `.mthds` file fixes neither: use `/mthds-runner-setup`, which sets up the user's own provider keys or the hosted Pipelex API.

- **A run on this machine** (the default): a runtime that was never initialised fails at boot with a `PipelexSetupError` saying config files are missing and suggesting `pipelex init config`; once it is initialised, the error, whatever its type, says it could not get credentials for an inference backend and names the variable that is missing, such as `OPENAI_API_KEY`.
- **A run on the hosted Pipelex API** (`--hosted`, or `[run] execution` set to `hosted`): the hosted API refuses a missing or rejected `PIPELEX_API_KEY` with a 401 or a 403 (`http_status` 401 or 403), whose hint says to run `pipelex login`. A 403 can also refuse something a valid key may not do: when its message names what this request may not do rather than the key, it is not a key problem, so tell the user what the message says instead of sending them to `pipelex login`. For a refused key, ask the user to run `pipelex login` in their own terminal, or `pipelex login --paste` on a machine with no browser: it saves a new key to `~/.pipelex/.env`. Before repeating the run, check that no `.env` in the directory you run methods from shadows the new key, since pipelex loads that file after `~/.pipelex/.env` and would send its `PIPELEX_API_KEY`, the rejected key included, again: `grep -qE '^[[:space:]]*(export[[:space:]]+)?PIPELEX_API_KEY[[:space:]]*=' .env 2>/dev/null && echo ".env sets PIPELEX_API_KEY"` prints a fixed message, never the value. When it reports the line, never read or print that file's value: ask the user to remove the line, or to replace its value with their new key themselves. A key exported in the shell does not replace one saved in `~/.pipelex/.env` or in that `.env`, which pipelex reads over the shell. Never ask for the key in this conversation.
- **The API runner** (`mthds-agent config get runner` says `api`) cannot run a bundle at all: `mthds-agent run bundle` fails there as an unknown command. Runs go through the pipelex runner, on this machine or on the hosted Pipelex API, which `/mthds-runner-setup` sets up.

## Model & Config Errors

These indicate environment issues, not .mthds file problems. **Cannot be fixed by editing the .mthds file.**

| Error Type | Meaning | Recovery |
|------------|---------|----------|
| `PipeOperatorModelAvailabilityError` | Model is configured but not reachable (missing API key, service down) on a run on this machine | Check that the backend's API key is set: `pipelex-agent doctor` lists each enabled backend with the key variables it is missing, without printing a key (the user can run `pipelex doctor` in their own terminal for the same report), and `/mthds-runner-setup` adds a missing one |
| `FormerReleaseConfigError` | The Pipelex configuration still carries what a former release wrote for the retired Pipelex Gateway: an enabled retired backend, a backend naming `model_specs_section`, or a routing profile sending models to a retired backend. Raised at boot, it names each file | Run `pipelex-agent migrate`, which writes nothing and reports the plan, and show it to the user. With their yes, `pipelex-agent migrate --yes` removes what that release left and keeps a copy of each file it changes; the user can instead run `pipelex migrate` in their own terminal. `mthds-agent` has no `migrate` command |

## Runtime Errors

| Error Type | Meaning | Recovery |
|------------|---------|----------|
| `PipelineExecutionError` | Pipeline failed during execution | Check `pipe_code` and `pipe_stack` in the error JSON |
| `BuildPipeError` | Automated build failed | Check `failure_memory_path` in error JSON for debugging details |
| `MethodEntryError` | `run bundle` or `inputs bundle` could not settle the pipe it acts on. Coded `request.pipe_unspecified`: no pipe was named and the target decides no single pipe to start at, being a bundle file that declares no `main_pipe`, a method's folder whose `METHODS.toml` declares none, or a folder with no manifest whose bundles declare none or several; its message names the bundles concerned, a folder's by their paths in its tree, and its `params.candidates`, when not empty, lists the pipes it could start at. Coded `method.invalid`: the folder holds no `.mthds` bundle at all, with or without `--pipe` (`run bundle` reports this one as an invalid bundle). These codes need pipelex 0.90.0 or later | For `request.pipe_unspecified`, name the pipe with `--pipe`, or keep one `main_pipe` for the method, in one bundle only or in its `METHODS.toml` (see "A Method's Folder as the Target" in the [agent guide](mthds-agent-guide.md)); `validate bundle` never refuses a folder for this. For `method.invalid` on a folder with no bundle, `--pipe` cannot help: point the command at the method's own folder, the one holding its `.mthds` files |
| `FileNotFoundError` | Bundle file or input file not found | Check file paths are correct |
| `JSONDecodeError` | Invalid JSON in inputs | Fix JSON syntax |
| `ArgumentError` | Invalid CLI flag combination | Check command flags (e.g., `--mock-inputs` requires `--dry-run`). When it says `--dry-run` or `--mock-inputs` only apply to a run on this machine, runs execute on the hosted Pipelex API by default: add `--local` and run again. Never `--runner local`, which `mthds-agent` reads as its own option and refuses as an unknown runner |
| `BinaryNotFoundError` | A required binary (e.g., `pipelex-agent`) is not on PATH | Install: `uv tool install pipelex`. Then use `/mthds-runner-setup` to set up inference. |

## Cross-Domain Validation & Library Isolation

Pipelex loads `.mthds` files into a flat namespace. **Always hand the command the method's folder, or name a bundle file with `-L` pointing to its own directory**, to avoid namespace collisions with other bundles in the project:

```bash
# Validate the method's folder: every bundle of it is judged, isolated from other bundles
mthds-agent validate bundle mthds-wip/pipeline_01/

# Run the method's folder (directory mode)
mthds-agent run bundle mthds-wip/pipeline_01/ --dry-run --mock-inputs
```

`validate bundle` judges every bundle of a folder from pipelex 0.89.0 on (see "A Method's Folder as the Target" in the [agent guide](mthds-agent-guide.md)). An older pipelex validates the folder's `bundle.mthds`, else its only `.mthds` file, and refuses a folder holding several `.mthds` files and no `bundle.mthds`: on such a pipelex, name the file declaring the method's `main_pipe` with `-L` pointing to its folder, as in `mthds-agent validate bundle mthds-wip/pipeline_01/bundle.mthds -L mthds-wip/pipeline_01/`, which loads the folder's bundles but dry-runs only that file's pipes.

When a bundle references pipes/concepts from a directory outside the method's folder, add a `-L` flag for it:

```bash
# Judge the method's folder, loading the shared pipes beside it for its bundles to call (their own pipes are not judged)
mthds-agent validate bundle ./my_bundle_dir/ -L ./shared_pipes/
```
