# Python Coding Standards

## Commands

### Linting & Type Checking

After making code changes, always run:
```bash
make agent-check   # fix-unused-imports, format, lint, pyright, mypy, shared-ref checks
make agent-test    # Silent on success, full output on failure
```

### Other Useful Targets

- `make install` — Create venv + install all deps (uses uv)
- `make li` — Lock + install
- `make check` — Aggregate shared, Claude, and Codex validation
- `make tp` — Run tests with prints (`make tp TEST=test_function_name` to filter)
- `make fui` — Fix unused imports only
- `make cleanderived` — Remove caches/compiled files (useful when linters get confused)
- `make reinstall` / `make ri` — Clean env and reinstall from scratch

## Python Version Compatibility

- Supports Python 3.10+ (`requires-python = ">=3.10"`). Never use features introduced after Python 3.10 without a compatibility fallback.
- Common pitfalls:
  - `datetime.UTC` was added in Python 3.11. Use `datetime.timezone.utc` instead.
  - `StrEnum` was added in Python 3.11. Use `enum.StrEnum` with a `try/except` or conditional import for 3.10 support.
  - `type` statement (PEP 695) was added in Python 3.12. Use `TypeAlias` from `typing` instead.
  - `ExceptionGroup` / `except*` was added in Python 3.11. Avoid unless using the `exceptiongroup` backport.

## Variables, Loops and Indexes

- Variable names should have a minimum length of 3 characters. No exceptions: name your `for` loop indexes like `index_foobar`, your exceptions `exc` or more specific like `validation_error`, and use `for key, value in ...` for key/value pairs.
- When looping on the keys of a dict, use `for key in the_dict` rather than `for key in the_dict.keys()`.
- Avoid inline for loops, unless it's ultra-simple and holds on one line.
- If you have a variable that will get its value differently through different code paths, declare it first with a type, e.g. `pipe_code: str` but DO NOT give it a default value like `pipe_code: str = ""` unless it's really justified. We want the variable to be unbound until all paths are covered, and the linters will help us avoid bugs this way.

## Enums

- When defining enums related to string values, always inherit from `StrEnum`.
- When you need the enum value as a string, just use `enum_var` itself — that is the point of `StrEnum`.
- Never test equality to an enum value: use match/case, even to single out 1 case out of 10 cases. To avoid heavy match/case code in awkward places, add `@property` methods to the enum class such as `is_foobar()`.
- As our match/case constructs over enums are always exhaustive, NEVER add a default `case _: ...`. Otherwise, you won't pass linting.

## Optionals

- Don't write `a = b if b else c`, write `a = b or c` instead.

## Imports

- Import all necessary libraries at the top of the file.
- Do not import libraries in functions or classes unless in very specific cases.
- Do not bother with ordering imports or removing unused imports — Ruff handles it.
- `if TYPE_CHECKING:` blocks must always be the **last** block in the imports section.
- Do NOT fill `__init__.py` files with re-exports. Always use direct full-path imports.

## Typing

- Every function parameter must be typed.
- Every function return must be typed.
- Use type hints for all variables where type is not obvious.
- Use lowercase generic types: `dict[]`, `list[]`, `tuple[]`.
- Use `Field(default_factory=...)` for mutable defaults.
- Use `# pyright: ignore[specificError]` or `# type: ignore` only as a last resort. Prefer `cast()` or creating a new typed variable.

## Error Handling

- Always catch exceptions at the place where you can add useful context.
- Use try/except blocks with specific exceptions.
- NEVER catch the generic `Exception`, only catch specific exceptions, except at CLI entry points.
- Always add `from exc` to exception raise statements.
- Always write the error message as a variable before raising:

```python
try:
    self.setup()
except SomeSpecificError as exc:
    msg = "Useful context about what went wrong"
    raise OurError(msg) from exc
```

## Writing Tests

- NEVER USE `unittest.mock`. Use `pytest-mock`: `from pytest_mock import MockerFixture`.
- NEVER put more than one `TestClass` into a test module.
- Name test files with `test_` prefix.
- Always group tests into a test class.
- Use parametrize for multiple test cases.
- Use strong asserts: test value, not just type and presence.
- Do NOT add `__init__.py` files to test directories.

## Documentation

```python
def process_data(input_path: str, limit: int) -> list[str]:
    """Process and filter data from a file.

    Args:
        input_path: Path to the source file
        limit: Maximum number of items to return

    Returns:
        Filtered list of strings
    """
```
