#!/usr/bin/env python3
# smart_video_organizer_final.py
"""
Smart Video Organizer — Final version
Features:
- Movie / Series detection (SxxExx)
- Year detection including forms like "Title (2023)" or "Title 2023"
- Option to create Season subfolders (respected)
- Scan & Preview (dry-run behavior removed as option — Scan acts as preview)
- Title Case button to convert folder names to Title Case
- Persistent theme (config.json)
- Responsive help text wrap
- Button icons (optional icons/ folder)
- Log/Preview supports text selection and Ctrl+C copy
- After Organize, opens selected folder in system file explorer
- Collision avoidance on file moves (appends suffix if needed)
- Undo last operation
"""
from __future__ import annotations
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from PIL import Image
import customtkinter as ctk
from tkinter import filedialog, messagebox

# ----------------------- Configuration / Constants -----------------------
VIDEO_EXTS = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.ts', '.m4v', '.webm')
ARCHIVE_EXTS = ('.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.srt', '.sub', '.ass')

# Patterns commonly found in release filenames that we want to remove when inferring the title.
REMOVE_PATTERNS = [
    r'(?i)\b1080p\b', r'(?i)\b720p\b', r'(?i)\b480p\b', r'(?i)\b2160p\b', r'(?i)\b4k\b',
    r'(?i)\b10bit\b', r'(?i)\b8bit\b', r'(?i)\bHEVC\b', r'(?i)\bx265\b', r'(?i)\bx264\b',
    r'(?i)\bWEB[-_. ]?DL\b', r'(?i)\bWEB[-_. ]?RIP\b', r'(?i)\bWEB[-_. ]?HD\b', r'(?i)\bBRRIP\b',
    r'(?i)\bBLU[-_. ]?RAY\b', r'(?i)\bBDRIP\b', r'(?i)\bHDRIP\b', r'(?i)\bHDTV\b',
    r'(?i)\bCAM\b', r'(?i)\bTS\b', r'(?i)\bTC\b',
    r'(?i)\bPROPER\b', r'(?i)\bREPACK\b', r'(?i)\bLIMITED\b', r'(?i)\bUNRATED\b',
    r'(?i)\bSUBBED\b', r'(?i)\bSOFTSUB\b', r'(?i)\bHARD?SUB\b', r'(?i)\bDUBBED\b',
    r'(?i)\bMULTi\b', r'(?i)\b(\d{1,2}ch)\b', r'(?i)\bAC3\b', r'(?i)\bDD5\.1\b', r'(?i)\bAAC\b',
    r'(?i)\bWEBRip\b', r'(?i)\bHDR\b',
    r'(?i)\bDigiMoviez\b', r'(?i)\b30nama\b', r'(?i)\bYTS\b', r'(?i)\bETRG\b', r'(?i)\bRARBG\b'
]

YEAR_RE = re.compile(r'\b(19|20)\d{2}\b')
SERIES_RE = re.compile(r'(?i)\bS?(\d{1,2})[xE\.\- ]?E?(\d{1,2})\b')
BRACKET_RE = re.compile(r'[\(\[\{].*?[\)\]\}]')

UNDO_LOG = "smart_organizer_last_action.json"
CONFIG_FILE = "config.json"


# ----------------------- Utility functions -----------------------
def resource_path(relative_path: str) -> str:
    """
    Return an absolute path to a bundled resource, supporting PyInstaller's _MEIPASS.
    """
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)


def remove_bracketed(text: str) -> str:
    """Remove any bracketed substring like '(... )' or '[ ... ]' from the text."""
    return BRACKET_RE.sub('', text)


def normalize_separators(name: str) -> str:
    """Replace common filename separators (., _, -) with a single space and trim."""
    s = re.sub(r'[._]+', ' ', name)
    s = re.sub(r'[-]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def strip_release_tags(text: str) -> str:
    """Strip out common release tags defined in REMOVE_PATTERNS."""
    s = text
    for p in REMOVE_PATTERNS:
        s = re.sub(p, '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def clean_title_candidate(raw: str) -> str:
    """
    Produce a cleaned candidate title from a raw filename base.
    Steps:
      - remove bracketed substrings
      - normalize separators
      - strip release tags
    """
    s = remove_bracketed(raw)
    s = normalize_separators(s)
    s = strip_release_tags(s)
    return s.strip()


def unique_filepath(path: str) -> str:
    """
    If 'path' exists, append ' (1)', ' (2)', ... before the extension until unique.
    Returns a new path that does not collide with existing files.
    """
    base, ext = os.path.splitext(path)
    counter = 1
    candidate = path
    while os.path.exists(candidate):
        candidate = f"{base} ({counter}){ext}"
        counter += 1
    return candidate


def open_folder(path: str) -> None:
    """Open the given folder in the OS file explorer, best-effort and cross-platform."""
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        # fail silently; opening folder is convenience only
        pass


# ----------------------- Core file-detection & destination logic -----------------------
def determine_destination(folder_path: str, filename: str, options: Dict) -> Tuple[str, str, str]:
    """
    Determine the destination folder and filename for a given file.
    Returns (dest_folder_fullpath, dest_filename, core_title_key)
    The core_title_key is a normalized lowercase string used to match archive/subtitle files to video files.
    Options keys:
      - move_archives: bool
      - create_season_subfolders: bool
    """
    base, ext = os.path.splitext(filename)
    raw = base
    candidate = clean_title_candidate(raw)
    core_title = ""

    # Series detection like S01E01 or s1e1
    m_series = re.search(r'(?i)\bS(\d{1,2})E(\d{1,2})\b', candidate)
    if m_series:
        season = int(m_series.group(1))
        # The title is the part before the SxxEyy marker
        title_before_marker = candidate[:m_series.start()].strip()

        if not title_before_marker:
            # Example: S01E01.Show.Name.mkv -> remove the SxxEyy and re-clean
            series_title = clean_title_candidate(re.sub(r'(?i)\bS(\d{1,2})E(\d{1,2})\b', '', candidate))
        else:
            series_title = clean_title_candidate(title_before_marker)

        core_title = series_title.lower()
        series_folder = os.path.join(folder_path, series_title.title() or "Unknown Series")

        if options.get("create_season_subfolders", False):
            dest_folder = os.path.join(series_folder, f"Season {season:02d}")
        else:
            dest_folder = series_folder

        return dest_folder, filename, core_title

    # Movie detection: look for a year in the filename
    m_year = re.search(r'[\(\[\{]?(19|20)\d{2}[\)\]\}]?', candidate)
    if m_year:
        # Extract 4-digit year string safely
        year_search = re.search(r'(19|20)\d{2}', m_year.group(0))
        year = year_search.group(0) if year_search else None
        title_part = candidate[:m_year.start()].strip()

        if not title_part:
            # Handle case where filename starts with the year: "2023.Movie.Name.mkv"
            title_part = re.sub(r'[\(\[\{]?(19|20)\d{2}[\)\]\}]?', '', candidate).strip()

        title = clean_title_candidate(title_part)
        core_title = f"{title.lower()} {year}" if year else title.lower()
        folder_name = f"{title.title()} {year}" if year else title.title()
        dest_folder = os.path.join(folder_path, folder_name)
        return dest_folder, filename, core_title

    # Fallback: treat as generic title (no year, no series)
    title = clean_title_candidate(candidate)
    core_title = title.lower()
    dest_folder = os.path.join(folder_path, title.title() or "Unknown")
    return dest_folder, filename, core_title


def scan_folder(folder_path: str, options: Dict) -> List[Dict]:
    """
    Scan the given folder and produce a list of planned operations (without performing them).
    Each operation dict contains: src, dst_folder, dst_path, filename
    If move_archives is True, archives/subtitles that match a video's core title are matched to the video's destination.
    """
    planned_ops: List[Dict] = []
    try:
        entries = os.listdir(folder_path)
    except Exception:
        return planned_ops

    video_ops: List[Dict] = []
    core_title_to_folder: Dict[str, str] = {}

    # First pass: detect video files and decide their destinations
    for name in entries:
        src_path = os.path.join(folder_path, name)
        if not os.path.isfile(src_path):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext not in VIDEO_EXTS:
            continue

        dst_folder, dst_filename, core_key = determine_destination(folder_path, name, options)
        dst_folder = os.path.abspath(dst_folder)
        dst_path = os.path.join(dst_folder, dst_filename)

        op = {
            "src": os.path.abspath(src_path),
            "dst_folder": dst_folder,
            "dst_path": dst_path,
            "filename": name
        }

        # Only schedule moves when source and destination paths differ
        if os.path.abspath(src_path) != os.path.abspath(dst_path):
            video_ops.append(op)

        # store the primary destination for this core key to match archives later
        if core_key and core_key not in core_title_to_folder:
            core_title_to_folder[core_key] = dst_folder

    # Second pass: if configured, match archives/subtitles to known video core titles
    if options.get('move_archives', False):
        for name in entries:
            src_path = os.path.join(folder_path, name)
            if not os.path.isfile(src_path):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in ARCHIVE_EXTS:
                continue

            _, _, core_key = determine_destination(folder_path, name, options)
            if core_key and core_key in core_title_to_folder:
                dst_folder = core_title_to_folder[core_key]
                dst_path = os.path.join(dst_folder, name)
                if os.path.abspath(src_path) != os.path.abspath(dst_path):
                    planned_ops.append({
                        "src": os.path.abspath(src_path),
                        "dst_folder": dst_folder,
                        "dst_path": dst_path,
                        "filename": name
                    })

    # Combine: move archives first, then videos (preserve original ordering where reasonable)
    planned_ops.extend(planned_ops)  # no-op (keeps API compatible)
    planned_ops.extend(video_ops)
    return planned_ops


def perform_moves(ops: List[Dict], log_action: bool = True) -> Tuple[List[Dict], List[Tuple]]:
    """
    Execute the provided move operations.
    Returns a tuple (moved_list, errors_list).
    Each moved entry is an op dict with updated dst_path (after collision resolution).
    Each error entry is a tuple (op, error_message, traceback_text).
    If log_action is True and there are successful moves, an undo log is written to UNDO_LOG.
    """
    moved: List[Dict] = []
    errors: List[Tuple] = []

    for op in ops:
        try:
            os.makedirs(op['dst_folder'], exist_ok=True)
            dst = op['dst_path']
            if os.path.exists(dst):
                dst = unique_filepath(dst)
            shutil.move(op['src'], dst)
            op_copy = op.copy()
            op_copy['dst_path'] = dst
            moved.append(op_copy)
        except Exception as exc:
            errors.append((op, str(exc), traceback.format_exc()))

    if log_action and moved:
        record = {"timestamp": datetime.utcnow().isoformat(), "moved": moved}
        try:
            with open(UNDO_LOG, 'w', encoding='utf-8') as f:
                json.dump(record, f, indent=2, ensure_ascii=False)
        except Exception:
            # Do not fail the operation if logging fails
            pass

    return moved, errors


def undo_last_action() -> Tuple[bool, object]:
    """
    Attempt to undo the last recorded action stored in UNDO_LOG.
    Returns (success_flag, result). If success_flag is True, result is a dict containing restored entries and errors.
    If False, result is an error message string.
    """
    if not os.path.exists(UNDO_LOG):
        return False, "No undo log found."

    try:
        with open(UNDO_LOG, 'r', encoding='utf-8') as f:
            record = json.load(f)
        moved_ops = record.get('moved', [])
        restored: List[Dict] = []
        errors: List[Tuple] = []

        if not moved_ops:
            try:
                os.remove(UNDO_LOG)
            except Exception:
                pass
            return True, {"restored": restored, "errors": errors, "root": None}

        # Guess root folder (where sources originally were)
        root_candidates = {os.path.dirname(op['src']) for op in moved_ops}
        try:
            root_folder = os.path.commonpath(list(root_candidates))
        except Exception:
            root_folder = next(iter(root_candidates))

        # Reverse the moves
        for op in reversed(moved_ops):
            src = op.get('dst_path')
            dst = op.get('src')
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if os.path.exists(src):
                    final_dst = dst
                    if os.path.exists(final_dst):
                        final_dst = unique_filepath(final_dst)
                    shutil.move(src, final_dst)
                    restored.append({'from': src, 'to': final_dst})
                else:
                    errors.append((src, "Source not found for undo"))
            except Exception as exc:
                errors.append((op, str(exc)))

        # Remove empty directories that were created (best-effort)
        created_dirs = {os.path.dirname(op.get('dst_path')) for op in moved_ops if op.get('dst_path')}
        for d in sorted(created_dirs, key=lambda p: len(p.split(os.sep)), reverse=True):
            try:
                if os.path.isdir(d) and not os.listdir(d):
                    os.rmdir(d)
                parent = os.path.dirname(d)
                while parent and os.path.abspath(parent) != os.path.abspath(root_folder):
                    if os.path.isdir(parent) and not os.listdir(parent):
                        os.rmdir(parent)
                        parent = os.path.dirname(parent)
                    else:
                        break
            except Exception:
                # ignore errors while cleaning up directories
                pass

        try:
            os.remove(UNDO_LOG)
        except Exception:
            pass

        return True, {"restored": restored, "errors": errors, "root": root_folder}
    except Exception as exc:
        return False, f"Failed to read/undo: {exc}"


# ----------------------- GUI Application -----------------------
class App(ctk.CTk):
    """Main GUI application using customtkinter."""

    def __init__(self) -> None:
        super().__init__()
        self.title("🎬 Smart Video Organizer")
        self.geometry("1100x740")
        self.minsize(800, 500)

        # Appearance and persistent theme
        ctk.set_default_color_theme("blue")
        self.theme_mode = ctk.StringVar(value=self._load_theme_from_config())

        # State variables
        self.folder_path: Optional[str] = None
        self.move_archives = ctk.BooleanVar(value=False)
        self.create_seasons = ctk.BooleanVar(value=True)

        # Last preview operations (used when performing moves)
        self.last_preview_ops: List[Dict] = []

        # Load UI
        self._build_ui()

    # ---------- Resource / Theme helpers ----------
    def _load_theme_from_config(self) -> str:
        """Load appearance mode from config file if present; default to 'Dark'."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                theme = cfg.get("theme_mode", "Dark")
                ctk.set_appearance_mode(theme)
                return theme
            except Exception:
                pass
        ctk.set_appearance_mode("Dark")
        return "Dark"

    def _save_theme_to_config(self, theme_mode: str) -> None:
        """Persist the chosen theme into CONFIG_FILE (best-effort)."""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump({"theme_mode": theme_mode}, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def toggle_theme(self) -> None:
        """Toggle between Light and Dark appearance modes and save the choice."""
        current = ctk.get_appearance_mode()
        new_mode = "Dark" if current == "Light" else "Light"
        ctk.set_appearance_mode(new_mode)
        self.theme_mode.set(new_mode)
        self.status.configure(text=f"Theme: {new_mode}")
        self._save_theme_to_config(new_mode)

    # ---------- UI construction ----------
    def _build_ui(self) -> None:
        # Left control panel
        left = ctk.CTkFrame(self, width=320)
        left.pack(side="left", fill="y", padx=12, pady=12)

        header_frame = ctk.CTkFrame(left, fg_color="transparent")
        header_frame.pack(fill="x", pady=(4, 8))

        title_label = ctk.CTkLabel(header_frame, text="🎬 Smart Video Organizer", font=ctk.CTkFont(size=18, weight="bold"))
        title_label.pack(side="left", padx=4)

        theme_switch = ctk.CTkSwitch(header_frame, text="Light/Dark", variable=self.theme_mode,
                                     onvalue="Dark", offvalue="Light", command=self.toggle_theme)
        theme_switch.pack(side="right", padx=4)

        # Load icons (best-effort; if icons missing -> allow failure to be caught)
        try:
            self.icon_folder = ctk.CTkImage(Image.open(resource_path("icons/folder.ico")), size=(20, 20))
            self.icon_search = ctk.CTkImage(Image.open(resource_path("icons/search.ico")), size=(20, 20))
            self.icon_layers = ctk.CTkImage(Image.open(resource_path("icons/layers.ico")), size=(20, 20))
            self.icon_undo = ctk.CTkImage(Image.open(resource_path("icons/undo.ico")), size=(20, 20))
            self.icon_title = ctk.CTkImage(Image.open(resource_path("icons/titlecase.ico")), size=(20, 20))
        except Exception:
            # If icons are not present, fall back to no-image buttons
            self.icon_folder = self.icon_search = self.icon_layers = self.icon_undo = self.icon_title = None

        # Folder entry + browse button
        self.path_entry = ctk.CTkEntry(left, placeholder_text="Select folder with videos...", width=320)
        self.path_entry.pack(pady=6)
        btn_browse = ctk.CTkButton(left, text="Browse", image=self.icon_folder, compound="left", width=200, command=self.select_folder)
        btn_browse.pack(pady=(4, 12))

        # Options
        ctk.CTkCheckBox(left, text="Move archives and subtitles (zip/rar/srt)", variable=self.move_archives).pack(anchor="w", pady=6, padx=6)
        ctk.CTkCheckBox(left, text="Create season subfolders for series", variable=self.create_seasons).pack(anchor="w", pady=6, padx=6)

        # Action buttons
        ctk.CTkButton(left, text="Scan & Preview", image=self.icon_search, compound="left", width=200, command=self.scan_and_preview).pack(pady=8)
        ctk.CTkButton(left, text="Organize", image=self.icon_layers, compound="left", width=200, command=self.execute_moves).pack(pady=8)
        ctk.CTkButton(left, text="Title Case Folders", image=self.icon_title, compound="left", width=200, command=self.title_case_folders).pack(pady=8)
        ctk.CTkButton(left, text="Undo Last Operation", image=self.icon_undo, compound="left", width=200, fg_color="#FF5C5C", hover=False, command=self.undo_action).pack(pady=8)

        # Help box with responsive wrapping
        help_box = ctk.CTkFrame(left, fg_color=("gray90", "#1e1e1e"))
        help_box.pack(fill="x", expand=False, pady=(12, 6), padx=6)

        help_text = (
            "💡 How to Use\n\n"
            "1. Click Browse to select your video folder.\n\n"
            "2. Options:\n"
            "   • Move archives and subtitles (zip/rar/srt)\n"
            "   • Create season subfolders for series\n\n"
            "3. Click Scan & Preview to see planned moves.\n\n"
            "4. If preview looks good, click Organize to apply changes.\n\n"
            "5. Use Title Case Folders to rename folders to title case.\n\n"
            "6. Use Undo Last Operation to revert last move.\n\n"
            "7. Enjoy your organized video collection! 🎉")

        self.help_label = ctk.CTkLabel(help_box, text=help_text, wraplength=260, justify="left", font=ctk.CTkFont(size=12))
        self.help_label.pack(padx=20, pady=20)

        # Responsive wrap behavior
        def resize_help(event) -> None:
            new_wrap = max(220, int(event.width * 0.8))
            self.help_label.configure(wraplength=new_wrap)
        help_box.bind("<Configure>", resize_help)

        # Status label
        self.status = ctk.CTkLabel(left, text="Ready", anchor="w", fg_color="transparent")
        self.status.pack(side="bottom", fill="x", padx=6, pady=(8, 0))
        # Right panel: preview / log
        right = ctk.CTkFrame(self)
        right.pack(side="right", fill="both", expand=True, padx=12, pady=12)

        topbar = ctk.CTkFrame(right)
        topbar.pack(fill="x", pady=(0, 8))
        lbl = ctk.CTkLabel(topbar, text="Preview / Log", font=ctk.CTkFont(size=14, weight="bold"))
        lbl.pack(side="left", padx=8)
        ctk.CTkButton(topbar, text="Refresh Preview", width=140, command=self.scan_and_preview).pack(side="right", padx=8)

        self.log_box = ctk.CTkTextbox(right, wrap="none", font=ctk.CTkFont(size=14), corner_radius=6, state="normal")
        self.log_box.pack(fill="both", expand=True)

        # Keep text box in readable state; prevent typing while allowing copy.
        self.log_box.configure(state="normal")
        self._bind_copy_shortcut()

    # ---------- Small UI helpers ----------
    def _bind_copy_shortcut(self) -> None:
        """Allow Ctrl+C to copy selection from the log box, block other edits."""

        def copy_event(event=None):
            try:
                selected = self.log_box.get("sel.first", "sel.last")
                if selected:
                    self.clipboard_clear()
                    self.clipboard_append(selected)
                    self.status.configure(text="Copied to clipboard")
            except Exception:
                pass
            return "break"

        def block_input(event):
            # Allow Ctrl+C but block regular typing/pasting/deleting in the log box
            if (event.state & 0x4) and event.keysym.lower() == "c":
                return
            return "break"

        self.log_box.bind("<Control-c>", copy_event)
        self.log_box.bind("<Control-C>", copy_event)
        self.log_box.bind("<Key>", block_input)

    def log(self, text: str, clear: bool = False) -> None:
        """Append a line to the preview/log textbox."""
        if clear:
            self.log_box.delete("1.0", "end")
        self.log_box.insert("end", f"{text}\n")
                            
        self.log_box.see("end")

    # ---------- Actions ----------
    def select_folder(self) -> None:
        """Open a folder dialog and set the selected path as the working folder."""
        folder = filedialog.askdirectory(title="Select Folder Containing Videos")
        if folder:
            self.folder_path = folder
            self.path_entry.delete(0, 'end')
            self.path_entry.insert(0, folder)
            self.log(f"Selected folder: {folder}", clear=True)
            self.status.configure(text=f"Folder: {folder}")

    def scan_and_preview(self) -> None:
        """Scan the current folder and show the planned operations in the log box."""
        folder = self.path_entry.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("Folder required", "Please select a valid folder first.")
            return
        options = {'move_archives': bool(self.move_archives.get()),
                   'create_season_subfolders': bool(self.create_seasons.get())}
        try:
            ops = scan_folder(folder, options)
            self.last_preview_ops = ops
            self.log_box.delete("1.0", "end")
            if not ops:
                self.log("✅ Nothing to move (no matching files or already organized).", clear=True)
            else:
                self.log(f"Previewing {len(ops)} operations:\n", clear=True)
                for i, op in enumerate(ops, 1):
                    src = op['src']
                    dst = op['dst_path']
                    self.log(f"{i}. {os.path.basename(src)}\n   -> {dst}\n")
                             
            self.status.configure(text=f"Preview ready: {len(ops)} items.")
        except Exception as exc:
            messagebox.showerror("Error", f"Scan failed: {exc}")
            self.log(f"Scan error: {traceback.format_exc()}".strip())
    def execute_moves(self) -> None:
        """Perform the previously previewed moves (or auto-scan if no preview exists)."""
        folder = self.path_entry.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("Folder required", "Please select a valid folder first.")
            return

        if not self.last_preview_ops:
            # If user didn't explicitly preview, do an automatic scan first
            self.scan_and_preview()
            if not self.last_preview_ops:
                messagebox.showinfo("Nothing to do", "No operations to perform.")
                return

        try:
            moved, errors = perform_moves(self.last_preview_ops, log_action=True)
            self.log(f"\n--- Move completed. {len(moved)} moved, {len(errors)} errors ---", clear=False)
            for m in moved:
                self.log(f"Moved: {m['src']} -> {m['dst_path']}")
            for e in errors:
                op, err_msg, tb = e
                self.log(f"Error moving {op.get('src')}: {err_msg}")
            self.status.configure(text=f"Done: {len(moved)} moved.")
            messagebox.showinfo("Done", f"✅ {len(moved)} files moved successfully.")

            # Open folder for convenience
            open_folder(folder)

            # clear preview ops after successful run
            self.last_preview_ops = []
        except Exception as exc:
            messagebox.showerror("Error", f"Move failed: {exc}")
            self.log(f"Move error: {traceback.format_exc()}".strip())

    def title_case_folders(self) -> None:
        """Rename immediate subfolders of the selected folder to Title Case (best-effort)."""
        folder = self.path_entry.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("Folder required", "Please select a valid folder first.")
            return

        renamed: List[Tuple[str, str]] = []
        errors: List[Tuple[str, str]] = []

        for name in os.listdir(folder):
            src = os.path.join(folder, name)
            if not os.path.isdir(src):
                continue

            # Use .title() directly to produce Title Case for folder names
            new_name = name.title()
            if new_name != name:
                dst = os.path.join(folder, new_name)
                try:
                    # Handle potential case-insensitive file-system collisions (Windows)
                    if name.lower() != new_name.lower():
                        if os.path.exists(dst):
                            errors.append((name, f"Destination '{new_name}' already exists (clash)"))
                            continue
                    os.rename(src, dst)
                    renamed.append((name, new_name))
                except Exception as exc:
                    errors.append((name, str(exc)))

        self.log("\n--- Title Case Operation ---", clear=False)
        for r in renamed:
            self.log(f"Renamed: {r[0]} -> {r[1]}")
        for e in errors:
            self.log(f"Error: {e[0]} ({e[1]})")

        self.log(f"Completed. {len(renamed)} renamed, {len(errors)} errors.")
        self.status.configure(text=f"Title Case done: {len(renamed)} renamed.")
        messagebox.showinfo("Title Case", f"✅ {len(renamed)} folders renamed to Title Case.")

    def undo_action(self) -> None:
        """Attempt to undo the last file move operation recorded in the undo log."""
        ok, result = undo_last_action()
        if not ok:
            messagebox.showinfo("Undo", result)
            self.log(f"Undo failed: {result}")
            return

        if isinstance(result, dict):
            restored = result.get('restored', [])
            errors = result.get('errors', [])
            root = result.get('root', None)

            self.log(f"\n--- Undo completed. Restored: {len(restored)}, Errors: {len(errors)} ---", clear=False)
            for r in restored:
                self.log(f"Restored: {r.get('from')} -> {r.get('to')}")
            for err in errors:
                self.log(f"Undo error: {err}")
            self.status.configure(text=f"Undo completed. Restored: {len(restored)}.")
            messagebox.showinfo("Undo", f"Undo completed. Restored: {len(restored)}. See log for details.")

            if root and os.path.isdir(root):
                try:
                    open_folder(root)
                except Exception:
                    pass
        else:
            self.log(f"Undo result: {result}", clear=False)
            messagebox.showinfo("Undo", str(result))


# ----------------------- Entry point -----------------------
def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
