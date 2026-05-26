# Release Checklist

Before publishing a GitHub release:

1. Make sure these files are present:
   - `src/novel_extractor.py`
   - `setup.bat`
   - `run_novel_extractor.bat`
   - `update_dependencies.bat`
   - `requirements.txt`
   - `README.md`
   - `LICENSE`
   - `.gitignore`
2. Do not include generated folders:
   - `.venv/`
   - `novel_chapters/`
   - `browser-profile/`
   - `__pycache__/`
3. Test on a clean folder:
   - Download or copy the repo to a new folder.
   - Run `setup.bat`.
   - Open Edge, pass site verification, close Edge.
   - Run `run_novel_extractor.bat`.
