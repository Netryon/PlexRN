# PlexRN

PlexRN is a Windows desktop tool that renames TV episodes into clean Plex naming:

`TV Show Name SxxExx.ext`

It is built for real-world messy libraries and supports both single-show folders and parent folders that contain multiple shows.

## Highlights

- Renames episodes to `Show Name SxxExx.ext`
- Uses the show folder name as the final series title
- Detects season/episode from folders and file names
- Handles season conflicts with user choice (folder vs file name vs skip)
- Confirms changes season-by-season before renaming
- Skips invalid files and continues safely
- Handles locked files without crashing
- Includes a modern GUI with live preview log

## Supported Video Formats

`.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, `.mpg`, `.mpeg`

## Recommended folder layout (best results)

PlexRN uses the **show folder name** as the series title in the final filename. For the cleanest output and the clearest log preview, follow these conventions:

1. **One show per top-level folder, named exactly like the show**  
   Use a folder whose name is only the series title (for example `The Boys`), and put that show’s episodes inside it.  
   If the top-level folder name includes extra words (for example release group or site names), those words are not used in the final filename, but **extra folders in the path can still make the log preview look noisy** when episodes sit deep inside unrelated subfolders.

2. **Multiple seasons: use one subfolder per season under the show folder**  
   Put each season in its own folder under the main show folder, and name that subfolder so it clearly matches the season (for example `Season 1`, `Season 2`, `S03`).  
   That keeps seasons unambiguous and makes the rename plan easier to review before you apply it.

Example layout:

```text
The Boys/
  Season 1/
    ...episodes...
  Season 2/
    ...episodes...
```

## Repository layout (what you ship)

This repository is intentionally split into two audiences:

### For most users (Windows)

Use the **prebuilt Windows folders** included in the repo (folder contains `PlexRN.exe` plus the supporting files needed for that build to run).

- Open the dist folder from the build.
- Run `PlexRN.exe`.
- Do **not** delete `logo.png` or `Icon.ico` from that folder if they are present (they are used by the app).

> Folder names may vary by release (for example different packaging options). Pick the user folder you intend to ship and ignore the developer folder below.

### For developers / contributors

The `Python script/` folder contains the editable source and assets:

```text
Python script/
  Plex Naming v3.py
  logo.png
  Icon.ico
```

## Quick start (developers)

### Requirements

- Python 3.10+
- Pillow (recommended for high-quality logo scaling)

### Install

```powershell
python -m pip install pillow
```

### Run

```powershell
python "Python script\Plex Naming v3.py"
```

## Maintainer notes (optional): building a Windows EXE

If you maintain releases and need to rebuild `PlexRN.exe`, use PyInstaller from `Python script/`.

```powershell
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name "PlexRN" --icon "Icon.ico" --add-data "logo.png;." --add-data "Icon.ico;." "Plex Naming v3.py"
```

Typical output:

- `dist\PlexRN.exe`

## How It Works

1. Choose a show folder or a folder containing multiple shows.
2. PlexRN scans videos recursively.
3. A season-by-season rename plan is shown in the log.
4. Review and choose **Apply Season** or **Skip Season**.
5. Only approved changes are applied.

## Behavior Notes

- Files without a detectable episode number are skipped.
- If no season is found and no season folder exists, season defaults to `S01`.
- Existing target files are never overwritten.

## License

This project is licensed under the [MIT License](LICENSE).
