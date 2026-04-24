"""PlexRN - TV episode file renamer for Plex-friendly naming."""

import os
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mpg", ".mpeg")

SEASON_FOLDER_RE = re.compile(r"(?:^|[\s._-])(?:season|s)\s*(\d{1,2})(?:$|[\s._-])", re.IGNORECASE)
SEASON_IN_NAME_RE = re.compile(r"(?:^|[\s._-])season\s*(\d{1,2})(?:$|[\s._-])", re.IGNORECASE)
SXXEXX_RE = re.compile(r"\bS(?P<s>\d{1,2})\s*E(?P<e>\d{1,3})\b", re.IGNORECASE)
X_STYLE_RE = re.compile(r"\b(?P<s>\d{1,2})x(?P<e>\d{1,3})\b", re.IGNORECASE)
EPISODE_RE = re.compile(r"(?:\bep(?:isode)?\s*|[\s._-]e)(?P<e>\d{1,3})\b", re.IGNORECASE)
APP_NAME = "PlexRN"
APP_VERSION = "1.0.0"


def resource_path(filename):
    # Support both normal run and PyInstaller onefile extraction.
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, filename)


def is_video_file(filename):
    return filename.lower().endswith(VIDEO_EXTENSIONS)


def list_video_files_recursive(folder):
    files = []
    for dirpath, _, filenames in os.walk(folder):
        for filename in filenames:
            if is_video_file(filename):
                files.append(os.path.join(dirpath, filename))
    return files


def has_video_directly(folder):
    try:
        for name in os.listdir(folder):
            full = os.path.join(folder, name)
            if os.path.isfile(full) and is_video_file(name):
                return True
    except OSError:
        return False
    return False


def detect_show_folders(selected_root):
    show_folders = []

    if has_video_directly(selected_root):
        show_folders.append(selected_root)

    try:
        entries = sorted(os.listdir(selected_root))
    except OSError:
        return show_folders

    for name in entries:
        full = os.path.join(selected_root, name)
        if not os.path.isdir(full):
            continue
        if list_video_files_recursive(full):
            show_folders.append(full)

    # If selected_root itself looks like a show folder that contains season folders,
    # do not treat each season folder as a separate show.
    if not has_video_directly(selected_root):
        season_like_children = 0
        for name in entries:
            full = os.path.join(selected_root, name)
            if not os.path.isdir(full):
                continue
            if parse_season_from_folder_name(name) is not None and list_video_files_recursive(full):
                season_like_children += 1
        if season_like_children > 0:
            return [selected_root]

    # Remove duplicates while preserving order.
    seen = set()
    ordered = []
    for folder in show_folders:
        norm = os.path.normcase(os.path.abspath(folder))
        if norm in seen:
            continue
        seen.add(norm)
        ordered.append(folder)
    return ordered


def parse_season_from_folder_name(folder_name):
    match = SEASON_FOLDER_RE.search(folder_name)
    if not match:
        return None
    return int(match.group(1))


def clean_show_name(folder_name):
    # Remove trailing "Season X" or "SXX" if user selected a season folder by mistake.
    cleaned = re.sub(r"[\s._-]+(?:season|s)\s*\d{1,2}\s*$", "", folder_name, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" ._-")
    return cleaned or folder_name


def parse_season_episode_from_filename(filename_no_ext):
    match = SXXEXX_RE.search(filename_no_ext)
    if match:
        return int(match.group("s")), int(match.group("e"))

    match = X_STYLE_RE.search(filename_no_ext)
    if match:
        return int(match.group("s")), int(match.group("e"))

    season_match = SEASON_IN_NAME_RE.search(filename_no_ext)
    episode_match = EPISODE_RE.search(filename_no_ext)
    season = int(season_match.group(1)) if season_match else None
    episode = int(episode_match.group("e")) if episode_match else None
    return season, episode


def build_plan_for_show(show_folder, ask_conflict_policy):
    show_name = clean_show_name(os.path.basename(os.path.normpath(show_folder)))
    videos = list_video_files_recursive(show_folder)
    videos.sort()

    if not videos:
        return [], [], []

    # If there are no season folders anywhere in the show, default to S01.
    found_any_season_folder = False
    for path in videos:
        rel = os.path.relpath(path, show_folder)
        parts = rel.split(os.sep)[:-1]
        for part in parts:
            if parse_season_from_folder_name(part) is not None:
                found_any_season_folder = True
                break
        if found_any_season_folder:
            break

    rename_plan = []
    errors = []
    skipped = []
    conflict_policy = None

    for old_path in videos:
        file_name = os.path.basename(old_path)
        name_no_ext, ext = os.path.splitext(file_name)

        season_from_folder = None
        rel = os.path.relpath(old_path, show_folder)
        parts = rel.split(os.sep)[:-1]
        for part in reversed(parts):
            season_candidate = parse_season_from_folder_name(part)
            if season_candidate is not None:
                season_from_folder = season_candidate
                break

        season_from_name, episode = parse_season_episode_from_filename(name_no_ext)
        if episode is None:
            errors.append(f"Missing episode number -> {rel}")
            continue

        chosen_season = season_from_folder
        if chosen_season is None:
            chosen_season = season_from_name

        if season_from_folder is not None and season_from_name is not None and season_from_folder != season_from_name:
            if conflict_policy is None:
                conflict_policy = ask_conflict_policy(show_name)
            if conflict_policy == "f":
                chosen_season = season_from_folder
            elif conflict_policy == "n":
                chosen_season = season_from_name
            else:
                skipped.append(f"Season conflict (skipped) -> {rel}")
                continue

        if chosen_season is None:
            if found_any_season_folder:
                errors.append(f"Could not determine season -> {rel}")
                continue
            chosen_season = 1

        new_name = f"{show_name} S{chosen_season:02d}E{episode:02d}{ext}"
        rename_plan.append((old_path, new_name, chosen_season))

    return rename_plan, errors, skipped


def apply_plan(show_folder, plan, logger=print):
    renamed = 0
    for old_path, new_name, _season in plan:
        new_path = os.path.join(os.path.dirname(old_path), new_name)
        if os.path.abspath(old_path) == os.path.abspath(new_path):
            continue
        if os.path.exists(new_path):
            logger(f"  Skip exists: {os.path.relpath(new_path, show_folder)}")
            continue
        try:
            os.rename(old_path, new_path)
            renamed += 1
            logger(f"  Renamed: {os.path.basename(old_path)} -> {new_name}")
        except PermissionError as exc:
            logger(f"  Skip locked file: {os.path.relpath(old_path, show_folder)} ({exc})")
        except OSError as exc:
            logger(f"  Rename failed: {os.path.relpath(old_path, show_folder)} ({exc})")
    return renamed


def group_plan_by_season(plan):
    grouped = {}
    for old_path, new_name, season in plan:
        grouped.setdefault(season, []).append((old_path, new_name, season))
    return grouped


class PlexRenameApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self._set_app_icon()
        self.root.geometry("1100x760")
        self.root.minsize(900, 620)
        self.selected_folder = tk.StringVar()
        self.is_running = False
        self.workflow = None
        self.awaiting_decision = False
        self.logo_img = None
        self._build_ui()

    def _set_app_icon(self):
        icon_path = resource_path("Icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except tk.TclError:
                pass

    def _build_ui(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        base_bg = "#050505"
        card_bg = "#0a0a0a"
        style.configure("TFrame", background=base_bg)
        style.configure("Card.TFrame", background=card_bg)
        style.configure("TopCard.TFrame", background="#060606")
        style.configure("TLabel", background=base_bg, foreground="#e8eef9")
        style.configure("Card.TLabel", background=card_bg, foreground="#e8eef9")
        style.configure("TopCard.TLabel", background=card_bg, foreground="#e8eef9")
        style.configure("Header.TLabel", font=("Segoe UI Semibold", 20), foreground="#f8fbff")
        style.configure("SubHeader.TLabel", font=("Segoe UI", 10), foreground="#a5a7ab")
        style.configure("Muted.TLabel", foreground="#8e939a")
        style.configure("StatusPill.TLabel", background="#1b1b1b", foreground="#ffca28", font=("Segoe UI", 9, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=(14, 8))
        style.configure("Secondary.TButton", font=("Segoe UI", 10), padding=(12, 8))
        style.configure("Danger.TButton", font=("Segoe UI Semibold", 10), padding=(12, 8))
        style.configure("TEntry", fieldbackground="#101010", foreground="#f8fbff", insertcolor="#f8fbff", padding=8)
        style.map(
            "Accent.TButton",
            background=[("active", "#ffc107"), ("!disabled", "#ffbf00"), ("disabled", "#5b4f24")],
            foreground=[("!disabled", "#111111"), ("disabled", "#b8b19b")],
        )
        style.map(
            "Secondary.TButton",
            background=[("active", "#2a2a2a"), ("!disabled", "#1d1d1d"), ("disabled", "#151515")],
            foreground=[("!disabled", "#f3f4f6"), ("disabled", "#747474")],
        )
        style.map(
            "Danger.TButton",
            background=[("active", "#5f5f5f"), ("!disabled", "#474747"), ("disabled", "#252525")],
            foreground=[("!disabled", "#f3f4f6"), ("disabled", "#8e8e8e")],
        )
        style.configure("Vertical.TScrollbar", troughcolor="#090909", background="#2a2a2a", arrowcolor="#f3f4f6")
        style.configure("TSeparator", background="#202020")

        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        action_bar = ttk.Frame(main, style="Card.TFrame", padding=10)
        action_bar.pack(side="bottom", fill="x")
        self.prompt_lbl = ttk.Label(action_bar, text="No action needed.", style="Card.TLabel")
        self.prompt_lbl.pack(side="left")
        self.apply_btn = ttk.Button(
            action_bar,
            text="Apply Season",
            style="Accent.TButton",
            command=self.on_apply_season,
            state="disabled",
        )
        self.apply_btn.pack(side="right")
        self.skip_btn = ttk.Button(
            action_bar,
            text="Skip Season",
            style="Danger.TButton",
            command=self.on_skip_season,
            state="disabled",
        )
        self.skip_btn.pack(side="right", padx=(0, 8))

        content = ttk.Frame(main, style="TFrame")
        content.pack(side="top", fill="both", expand=True, pady=(0, 8))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(2, weight=1)

        header = ttk.Frame(content, style="TopCard.TFrame", padding=6)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self._load_logo(header)

        controls = ttk.Frame(content, style="Card.TFrame", padding=8)
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        row = ttk.Frame(controls, style="Card.TFrame")
        row.pack(fill="x")
        self.path_entry = ttk.Entry(row, textvariable=self.selected_folder)
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=4)
        ttk.Button(row, text="Browse", command=self.choose_folder, style="Secondary.TButton").pack(side="left", padx=(8, 0))
        self.run_btn = ttk.Button(row, text="Start Rename", command=self.start_run, style="Accent.TButton")
        self.run_btn.pack(side="left", padx=(8, 0))

        meta_row = ttk.Frame(controls, style="Card.TFrame")
        meta_row.pack(fill="x", pady=(10, 0))
        ttk.Label(meta_row, text="Status", style="Muted.TLabel").pack(side="left")
        self.status_lbl = ttk.Label(meta_row, text="Idle", style="StatusPill.TLabel", padding=(10, 3))
        self.status_lbl.pack(side="left", padx=(8, 12))
        ttk.Label(meta_row, text="Review all planned renames in the log before applying.", style="Muted.TLabel").pack(side="left")

        self.progress = ttk.Progressbar(controls, mode="indeterminate")
        self.progress.pack(fill="x", pady=(6, 0))

        log_card = ttk.Frame(content, style="Card.TFrame", padding=1)
        log_card.grid(row=2, column=0, sticky="nsew", pady=(0, 6))
        log_header = ttk.Frame(log_card, style="Card.TFrame", padding=(10, 8))
        log_header.pack(fill="x")
        ttk.Label(log_header, text="Activity Log", style="Card.TLabel").pack(side="left")
        ttk.Separator(log_card, orient="horizontal").pack(fill="x")

        log_frame = ttk.Frame(log_card, style="Card.TFrame", padding=10)
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(
            log_frame,
            bg="#090909",
            fg="#e6e6e6",
            insertbackground="#e6e6e6",
            relief="flat",
            bd=0,
            font=("Cascadia Mono", 10),
            wrap="word",
            padx=10,
            pady=10,
        )
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(log_frame, orient="vertical", style="Vertical.TScrollbar", command=self.log_text.yview)
        scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.tag_configure("title", foreground="#79c0ff", font=("Cascadia Mono", 10, "bold"))
        self.log_text.tag_configure("good", foreground="#ffca28")
        self.log_text.tag_configure("warn", foreground="#ffdd7d")
        self.log_text.tag_configure("bad", foreground="#ff8f8f")

    def _load_logo(self, parent):
        logo_path = resource_path("logo.png")
        if not os.path.exists(logo_path):
            return
        try:
            if Image is not None and ImageTk is not None:
                src = Image.open(logo_path)
                target_width = 220
                ratio = target_width / float(src.width)
                target_height = max(1, int(src.height * ratio))
                resized = src.resize((target_width, target_height), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(resized)
            else:
                img = tk.PhotoImage(file=logo_path)
                self.logo_img = img.subsample(6, 6)
            label = tk.Label(parent, image=self.logo_img, bg="#060606", bd=0, highlightthickness=0)
            label.pack(anchor="center", pady=(0, 2))
        except tk.TclError:
            self.logo_img = None

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Select a show folder or a folder containing multiple shows")
        if folder:
            self.selected_folder.set(folder)

    def log(self, text=""):
        tag = None
        low = text.lower()
        if "renamed:" in low or "done." in low:
            tag = "good"
        elif "error" in low or "failed" in low or "locked file" in low:
            tag = "bad"
        elif "skip" in low:
            tag = "warn"

        if text.startswith("=== ") or text.startswith("Planned renames for"):
            self.log_text.insert("end", text + "\n", "title")
        elif tag:
            self.log_text.insert("end", text + "\n", tag)
        else:
            self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.root.update_idletasks()

    def set_status(self, text):
        self.status_lbl.configure(text=text)
        self.root.update_idletasks()

    def ask_conflict_policy(self, show_name):
        prompt = (
            f"Season conflict found in '{show_name}'.\n\n"
            "Type:\n"
            "F = use folder season\n"
            "N = use filename season\n"
            "S = skip conflicting files"
        )
        while True:
            answer = simpledialog.askstring("Season Conflict", prompt, parent=self.root)
            if answer is None:
                return "s"
            answer = answer.strip().lower()
            if answer in ("f", "n", "s"):
                return answer
            messagebox.showerror("Invalid Input", "Please enter F, N, or S.")

    def set_action_prompt(self, text, enabled):
        self.prompt_lbl.configure(text=text)
        state = "normal" if enabled else "disabled"
        self.apply_btn.configure(state=state)
        self.skip_btn.configure(state=state)
        self.awaiting_decision = enabled

    def start_run(self):
        if self.is_running:
            return
        folder = self.selected_folder.get().strip()
        if not folder:
            messagebox.showwarning("Folder Required", "Please choose a folder before starting.")
            return
        if not os.path.isdir(folder):
            messagebox.showerror("Invalid Folder", "The selected path is not a valid folder.")
            return

        self.is_running = True
        self.run_btn.configure(state="disabled")
        self.set_status("Running...")
        self.progress.start(10)
        self.set_action_prompt("Preparing rename plan...", False)
        self.workflow = self.workflow_steps(folder)
        self.root.after(20, lambda: self.advance_workflow(None))

    def workflow_steps(self, root_folder):
        self.log(f"{APP_NAME} v{APP_VERSION}")
        self.log(f"Root: {root_folder}")

        show_folders = detect_show_folders(root_folder)
        if not show_folders:
            self.log("No shows with video files found.")
            return

        total_renamed = 0
        for show_folder in show_folders:
            show_name = clean_show_name(os.path.basename(os.path.normpath(show_folder)))
            self.log("")
            self.log(f"=== Show: {show_name} ===")

            plan, errors, skipped = build_plan_for_show(show_folder, self.ask_conflict_policy)
            if not plan and not errors and not skipped:
                self.log("No video files found in this show.")
                continue

            if errors:
                self.log("Errors (skipped):")
                for item in errors:
                    self.log(f"  - {item}")

            if skipped:
                self.log("Skipped:")
                for item in skipped:
                    self.log(f"  - {item}")

            if not plan:
                self.log("No valid rename targets for this show.")
                continue

            grouped = group_plan_by_season(plan)
            season_keys = sorted(grouped.keys())
            renamed_in_show = 0

            for season in season_keys:
                season_plan = grouped[season]
                self.log("")
                self.log(f"Planned renames for Season {season:02d}:")
                for old_path, new_name, _ in season_plan:
                    rel_old = os.path.relpath(old_path, show_folder)
                    self.log(f'  "{rel_old}" -> "{new_name}"')

                apply_this = yield {
                    "type": "confirm_season",
                    "show_name": show_name,
                    "show_folder": show_folder,
                    "season": season,
                    "plan": season_plan,
                }
                if apply_this:
                    renamed_now = apply_plan(show_folder, season_plan, logger=self.log)
                    renamed_in_show += renamed_now
                    total_renamed += renamed_now
                    self.log(f"Renamed {renamed_now} file(s) for season S{season:02d}.")
                else:
                    self.log(f"Skipped season S{season:02d}.")

            self.log(f"Renamed {renamed_in_show} file(s) in '{show_name}'.")

        self.log("")
        self.log(f"Done. Total renamed files: {total_renamed}")
        yield {"type": "finished", "total": total_renamed}

    def advance_workflow(self, decision):
        if self.workflow is None:
            return
        try:
            if decision is None:
                step = next(self.workflow)
            else:
                step = self.workflow.send(decision)
        except StopIteration:
            self._finish_run()
            return

        if step.get("type") == "confirm_season":
            season = step["season"]
            show_name = step["show_name"]
            self.set_action_prompt(
                f"Review log for {show_name} S{season:02d}, then choose Apply or Skip.",
                True,
            )
        elif step.get("type") == "finished":
            total = step["total"]
            messagebox.showinfo("Finished", f"Done.\nTotal renamed files: {total}", parent=self.root)
            self._finish_run()

    def on_apply_season(self):
        if not self.awaiting_decision:
            return
        self.set_action_prompt("Applying selected season...", False)
        self.root.after(20, lambda: self.advance_workflow(True))

    def on_skip_season(self):
        if not self.awaiting_decision:
            return
        self.set_action_prompt("Skipping selected season...", False)
        self.root.after(20, lambda: self.advance_workflow(False))

    def _finish_run(self):
        self.is_running = False
        self.workflow = None
        self.progress.stop()
        self.run_btn.configure(state="normal")
        self.set_action_prompt("No action needed.", False)
        self.set_status("Idle")


def main():
    root = tk.Tk()
    app = PlexRenameApp(root)
    root.configure(background="#050505")
    root.mainloop()


if __name__ == "__main__":
    main()
