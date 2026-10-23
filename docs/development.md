# Developing mthds-plugins

The build script, the checks and the unit tests are a small Python project, `mthds-plugins-tools`, which `make install` installs into `.venv` with uv. The build itself is described in [Build targets](build-targets.md).

## The Python interpreter

The development interpreter is the one `.python-version` names at the repository root. The Makefile hands that version to every uv command it runs, and uv reads the same file when it runs outside the Makefile, so the next `make` rebuilds an environment that was made on another Python onto the pinned one. To try another version, run `PYTHON_VERSION=<version> make install`, for example `PYTHON_VERSION=3.14 make install`, and the next plain `make install` returns the environment to the pin. The CI workflows read the same file, so a pull request is checked and tested on the version you develop on.
