# Novel Importer

Novel Importer extracts novel chapter text through a visible Microsoft Edge session, translates it with `deep-translator`, and saves translated chapter files locally.

Use this only for content you are allowed to access and archive. Read the [Legal Notice](docs/LEGAL_NOTICE.md) before publishing or using this project.

## Quick Start

1. Download this project and unzip it.
2. Double-click `setup.bat`.
3. Open normal Microsoft Edge, visit the target site, pass any verification, then close Edge.
4. Double-click `run_novel_extractor.bat`.

The setup script creates a local `.venv`, installs Python packages, and installs Playwright browser support.

## Requirements

- Windows
- Python 3.10 or newer
- Microsoft Edge

## Legal Notice

This project does not include or distribute novel content. Users are responsible for complying with copyright law, website terms of service, account rules, and any access restrictions that apply to the content they access.

Do not use this tool to download, redistribute, publish, sell, or share content without permission from the rights holder.


## Run

Interactive mode:

```powershell
.\run_novel_extractor.bat
```

Command-line mode:

```powershell
.\run_novel_extractor.bat --url "https://example.com/novel/123/456" --lang en --count 10
```

## Options

```text
--url                  Starting chapter URL in the format https://domain/novel/<novel_id>/<episode_id>
--lang                 Target language code. Default: en
--count                Number of chapters to process. Default: 1
--output-dir           Output folder. Default: ./novel_chapters
--profile-dir          Custom Edge/Chromium user data folder
--isolated-profile     Use ./browser-profile instead of your normal Edge profile
--system-edge-profile  Use your normal Edge profile. This is the default.
--edge-executable      Path to msedge.exe
--no-cookie-check      Skip the cf_clearance cookie pre-check
```

## Output

Files are written to:

```text
novel_chapters/<novel_id>/
```

Example:

```text
chapter_1_en.txt
chapter_2_en.txt
merged_novel_123_en.txt
failed_chapters.txt
```

`failed_chapters.txt` is created only when one or more chapters fail.

## Browser Profile Workflow

By default, the tool uses your normal Edge profile:

```text
%LOCALAPPDATA%\Microsoft\Edge\User Data
```

Recommended workflow:

1. Open normal Edge yourself.
2. Visit the target site and pass verification manually.
3. Close every Edge window.
4. Run this tool.

If Cloudflare or another verification page loops forever, avoid `--isolated-profile`. Use the default Edge profile workflow above.

## Troubleshooting

If packages are missing, run:

```powershell
.\setup.bat
```

If Edge is not found, pass the browser path:

```powershell
.\run_novel_extractor.bat --edge-executable "C:\Path\To\msedge.exe"
```

If Edge starts and immediately closes, close every Edge process in Task Manager and run the tool again.

## Manual Install

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m playwright install chromium
```
