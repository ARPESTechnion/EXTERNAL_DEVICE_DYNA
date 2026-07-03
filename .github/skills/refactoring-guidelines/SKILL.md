---
name: refactoring-guidelines
description: "Use when restructuring modules, deduplicating logic, or renaming APIs in measurement software while preserving behavior and compatibility. Keywords: refactor, backward compatibility, migration, regression."
---

# Refactoring Guidelines

## Workflow

1. Separate structural cleanup from behavior changes when possible.
2. Preserve public APIs or provide explicit migration shims.
3. Keep command sequencing and safety semantics unchanged unless intended.
4. Centralize duplicated constants and helpers.
5. Expand regression tests around touched high-risk areas.

## Validation

- Existing scripts and core workflows still run.
- Compatibility impacts are documented.
- Safety and protocol guarantees are preserved.
- Regression tests cover modified behavior.

## Common Mistakes

- Combining large refactor and feature logic in one opaque change.
- Removing compatibility aliases prematurely.
- Reordering instrument commands without protocol review.

## Project Anchors

- [ScriptParser class](v3/core/script_parser.py#L259)
- [ScriptValidator validate](v3/core/script_parser.py#L388)
- [Keyword allowlist contract](v3/core/script_parser.py#L209)
- [IV curve measurement entry](v3/core/measurements.py#L758)
- [Parser regression tests](v3/tests/test_script_parser.py#L399)
- [Script runner behavior tests](v3/tests/test_script_runner.py#L167)
