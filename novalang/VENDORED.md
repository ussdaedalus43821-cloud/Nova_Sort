# Vendored NovaLang

Copied unmodified from the Nova_Lang repository, branch `develop`, commit **f458f1d**
(the merge of pull request 1: `\033` is an error in all three lexers, with the other fixes of that pull request).

| File | Purpose |
| --- | --- |
| `novalang.py` | the interpreter, bytecode VM and CLI |
| `novalang.nova` | the self-hosted interpreter, run by `--bootstrap` |
| `bootstrap.py` | loader for the self-hosted engine |
| `LICENSE` | upstream licence |

To update, copy the same files from a newer commit and re-run `python3 tests/run_suite.py`.
