# Python Execution Reference

`python3` and `python` may not be on PATH. Always use `uv` to run Python scripts.

## For pipelex dependencies (reportlab, etc.)

Pipelex is installed via `uv tool install pipelex`, which creates an isolated venv with Python and all pipelex dependencies. Use its Python directly:

```bash
"$(uv tool dir)/pipelex/bin/python" << 'PYEOF'
from reportlab.pdfgen import canvas
c = canvas.Canvas("output.pdf")
c.drawString(100, 750, "Hello")
c.save()
PYEOF
```

## For other packages

Use `uv run --with <package>` to run Python with additional packages in a temporary cached environment:

```bash
uv run --with python-docx python << 'PYEOF'
from docx import Document
doc = Document()
doc.add_heading('Title', 0)
doc.save('output.docx')
PYEOF
```

Multiple packages:
```bash
uv run --with python-docx --with openpyxl python << 'PYEOF'
# both python-docx and openpyxl are available
PYEOF
```
