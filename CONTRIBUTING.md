# Contributing to JPGFLY

JPGFLY is both an artwork and a software system. Changes should preserve the distinction between the project’s fiction/voice and what the implementation actually does.

## Principles

- Keep the server authoritative for painting decisions and physical events.
- The browser may render and replay; it should not become a hidden artistic brain.
- Do not describe visual proxies as literal biological measurements.
- Do not claim consciousness or sentience.
- Never commit secrets or private user data.

## Development setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run locally:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 4673
```

## Before submitting a change

```powershell
$env:JPGFLY_AUTONOMOUS_STUDIO="false"
$env:JPGFLY_TEXT_PROVIDER="procedural"

.\.venv\Scripts\python.exe -m py_compile app.py brain_provider.py server_mechanics.py flm_text_provider.py experience_memory.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
npm.cmd test
```

For behavior changes, add or update a regression test.

## Writing and UI copy

Keep public copy concise and accurate. The artistic voice can be strange, erotic, philosophical, funny, technical, or poetic, but project documentation should clearly distinguish metaphor from implementation.

## Line endings

The repository uses LF for source/docs and CRLF for PowerShell scripts through `.gitattributes`.

## Security-sensitive changes

Changes to HTTP controls, archive integrity, prompt construction, local model bridges, signing, credentials, or network exposure should include a short threat-model note in the pull request.
