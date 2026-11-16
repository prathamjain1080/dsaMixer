# homework/

Put your course homework here, with one folder per **course week**:

```
homework/
  week4/
    hw1.ipynb          # whatever the course gives you: notebooks, PDFs, notes
    assignment.pdf
    STATUS.md          # written by the agents, don't edit by hand
```

Then, in Claude Code:
- `/homework-plan 4` reads the folder, breaks each homework into 30–90 minute steps, writes `STATUS.md` and puts the steps on your board.
- `/homework-sync 4` checks your saved notebooks and ticks off the steps that are done.

The agents only plan and track. They never write solutions, and they only edit `STATUS.md`. See "Homework workflow" in `CLAUDE.md` for the details.

Coursework and private settings in this folder are git-ignored, so your work and your course's material stay on your machine. The shared environment helper and templates described below are tracked.

## Separate environment for practice notebooks

Practice settings belong in **`homework/.env`**, separate from the app's root `.env`. A blank local file is provided on this machine; fill in your practice database URL and the API/model settings you use. On a fresh clone, copy `homework/.env.example` to `homework/.env`. Never put real credentials in the example file.

Install the loader dependency into the notebook's own kernel (which may differ from the app's `.venv`):

```python
%pip install python-dotenv
```

The existing week 4 notebooks now load the homework environment in their setup cell. Restart the kernel and run that cell again after editing the file. The loader returns a dictionary, so use `env["DATABASE_URL"]` or `env.get("QDRANT_API_KEY")`; it does not copy credentials into the process environment. Missing keys never fall back to the app's `.env` or inherited shell variables. `${VARIABLE}` interpolation is disabled; enter literal values.

For a new notebook, add this setup cell before creating clients or database connections. Start Jupyter from the project directory or any folder inside `homework/`:

```python
import sys
from pathlib import Path

homework_dir = next(
    p / "homework" for p in (Path.cwd(), *Path.cwd().parents)
    if (p / "homework" / "homework_env.py").is_file()
)
if str(homework_dir) not in sys.path:
    sys.path.insert(0, str(homework_dir))
from homework_env import load_homework_env

env = load_homework_env()
database_url = env["DATABASE_URL"]
# Pass env["OPENROUTER_API_KEY"] explicitly when creating your API client.
```

`homework/.env` and all coursework remain git-ignored. Only this README, the loader, `.env.example` and `requirements.txt` are shared.
