# JupyterQt — Development Guidelines

## Language and naming
- All code in **Python 3.11+**
- Class methods: **camelCase** (e.g. `buildUi`, `onCellAdded`)
- Private methods: leading underscore + camelCase (e.g. `_buildUi`, `_onCellAdded`)
- Properties: **snake_case** (e.g. `list_of_widgets`)
- Private properties: leading underscore + **snake_case** (e.g. `_private_list_of_widgets`)
- Variables in functions: **snake_case**
- Qt signal attributes: **snake_case** (e.g. `cell_output_appended`) — do not rename
- Dataclass fields: **camelCase** (e.g. `cellId`, `notebookId`)

## Line width
- Max linewith shall be 200 characters
- Prefer method headers in one line, not breaking the line

## Section dividers inside classes
Use this exact format — total line width 144 characters, fill character is `#`:

```python
    # #########################################################################################################################################
    # commands
```

Example:
```python
class Foo:
    # #########################################################################################################################################
    # Public API
    
    def doSomething(self): ...

    # #########################################################################################################################################
    # Private helpers
    
    def _helper(self): ...
```

Not like this:
```python
# ---------- Section ----------   ← wrong fill character and style
# --- Section ---                 ← too short
```

## Comments
- Only add comments where the logic is not self-evident
- No docstrings on methods unless explicitly requested
- Do not add type-annotation comments (`# type: ignore` excepted)

## General
- Do not remove or silence existing debug `print` statements unless explicitly asked
- Do not remove comments and docstrings on your own
- Do not add error handling, fallbacks, or validation beyond what is needed
- Do not refactor surrounding code when fixing a bug or adding a feature
- Prefer editing existing files over creating new ones
