# src/

Put your **reusable Python code** here as `.py` module files.

Why a module instead of writing everything in the notebook?
- One **single source of truth** — write a function once, use it from the notebook AND the tests.
- No copy-paste drift between notebooks.
- Easier to test (see the `tests/` folder).

Example: a file `src/helpers.py` with a function you import into your notebook:

```python
# in the notebook:
from src.helpers import clean_data
```
