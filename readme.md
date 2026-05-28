# Hardware Specs

Windows-oriented desktop utility for collecting hardware information and exporting it as text or image output.

## Requirements

- Python 3.10+
- Windows for full hardware collection behavior
- Dependencies from `requirements.txt`

## Install

```bash
python setup.py --venv
```

Or manually:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run

```bash
python hardware_specs.py
```

## Notes

The script uses Windows system commands/APIs where available. Non-Windows environments are mainly useful for syntax checks or export QA paths that do not require live hardware collection.
