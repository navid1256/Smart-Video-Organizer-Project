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
import sys
import os
import re
import shutil
import json
import traceback
import subprocess
import platform
from datetime import datetime
from PIL import Image
import customtkinter as ctk
from tkinter import filedialog, messagebox

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Not running in PyInstaller bundle
        base_path = os.path.abspath(os.path.dirname(__file__))
    
    return os.path.join(base_path, relative_path)
# ----------------------- Settings -----------------------
VIDEO_EXTS = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.ts', '.m4v', '.webm')
ARCHIVE_EXTS = ('.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.srt', '.sub', '.ass')
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
YEAR_REGEX = re.compile(r'\b(19|20)\d{2}\b')
SERIES_REGEX = re.compile(r'(?i)\bS?(\d{1,2})[xE\.\- ]?E?(\d{1,2})\b')  # used for detection
BRACKET_REGEX = re.compile(r'[\(\[\{].*?[\)\]\}]')
UNDO_LOG = "smart_organizer_last_action.json"
CONFIG_FILE = "config.json"
ICONS_DIR = os.path.join(os.path.dirname(__file__), "icons")

# ----------------------- Helper functions -----------------------

def remove_bracketed(text: str) -> str:
    return BRACKET_REGEX.sub('', text)

def normalize_separators(name: str) -> str:
    s = re.sub(r'[._]+', ' ', name)
    s = re.sub(r'[-]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def strip_tags(text: str) -> str:
    s = text
    for p in REMOVE_PATTERNS:
        s = re.sub(p, '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def clean_title_candidate(raw: str) -> str:
    s = remove_bracketed(raw)
    s = normalize_separators(s)
    s = strip_tags(s)
    return s.strip()

def unique_filepath(path: str) -> str:
    """
    If path exists, append ' (1)', ' (2)', ... before extension until unique.
    """
    base, ext = os.path.splitext(path)
    counter = 1
    new_path = path
    while os.path.exists(new_path):
        new_path = f"{base} ({counter}){ext}"
        counter += 1
    return new_path

def open_folder(path: str):
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass

# ----------------------- Core logic -----------------------

def determine_destination(folder_path: str, filename: str, options: dict):
    """
    Return (dest_folder_fullpath, dest_filename, core_title)
    options: {'move_archives': bool, 'create_season_subfolders': bool}
    """
    base, ext = os.path.splitext(filename)
    raw = base
    candidate = clean_title_candidate(raw)
    core_title = "" # هسته اصلی برای تطبیق

    # Series detection (SxxEyy)
    m_series = re.search(r'(?i)\bS(\d{1,2})E(\d{1,2})\b', candidate)
    if m_series:
        season = int(m_series.group(1))
        series_title_raw = candidate[:m_series.start()].strip()
        
        # مدیریت حالتی مثل S01E01.Show.Name.mkv
        if not series_title_raw:
            series_title = clean_title_candidate(re.sub(r'(?i)\bS(\d{1,2})E(\d{1,2})\b', '', candidate))
        else:
            series_title = clean_title_candidate(series_title_raw)

        core_title = series_title.lower() # <--- هسته اصلی
        series_folder = os.path.join(folder_path, series_title.title() or "Unknown Series")
        
        if options.get("create_season_subfolders", False):
            dest_folder = os.path.join(series_folder, f"Season {season:02d}")
        else:
            dest_folder = series_folder
        return dest_folder, filename, core_title # <--- بازگرداندن هسته

    # Movie: detect year
    m_year = re.search(r'[\(\[\{]?(19|20)\d{2}[\)\]\}]?', candidate)
    if m_year:
        year_match = re.search(r'(19|20)\d{2}', m_year.group(0))
        year = year_match.group(0) if year_match else None
        title_part = candidate[:m_year.start()].strip()
        
        # مدیریت حالتی مثل 2025.Movie.Name.mkv
        if not title_part:
            title_part = re.sub(r'[\(\[\{]?(19|20)\d{2}[\)\]\}]?', '', candidate).strip()
            
        title = clean_title_candidate(title_part)
        
        core_title = f"{title.lower()} {year}" if year else title.lower() # <--- هسته اصلی
        folder_name = f"{title.title()} {year}" if year else title.title()
        dest_folder = os.path.join(folder_path, folder_name)
        return dest_folder, filename, core_title # <--- بازگرداندن هسته

    # fallback: no year, no series
    title = clean_title_candidate(candidate)
    core_title = title.lower() # <--- هسته اصلی
    dest_folder = os.path.join(folder_path, title.title() or "Unknown")
    return dest_folder, filename, core_title # <--- بازگرداندن هسته

def scan_folder(folder_path: str, options: dict):
    ops = []
    files = os.listdir(folder_path)
    video_ops = []
    
    # دیکشنری برای نگهداری مقصد هر «هسته اصلی»
    # {core_title: dst_folder}
    video_destinations = {}

    # 1️⃣ مرحله اول: فقط فایل‌های ویدیویی را پردازش کن
    for item in files:
        item_path = os.path.join(folder_path, item)
        if os.path.isfile(item_path):
            ext = os.path.splitext(item)[1].lower()
            if ext in VIDEO_EXTS:
                # دریافت هسته اصلی از تابع اصلاح‌شده
                dst_folder, dst_filename, core_title = determine_destination(folder_path, item, options)
                
                dst_folder = os.path.abspath(dst_folder)
                dst_path = os.path.join(dst_folder, dst_filename)
                
                op = {
                    "src": os.path.abspath(item_path),
                    "dst_folder": dst_folder,
                    "dst_path": dst_path,
                    "filename": item
                }
                
                if os.path.abspath(item_path) != os.path.abspath(dst_path):
                    video_ops.append(op)
                
                # هسته اصلی و پوشه مقصد آن را ثبت می‌کنیم
                if core_title and core_title not in video_destinations:
                    video_destinations[core_title] = dst_folder

    # 2️⃣ مرحله دوم: فایل‌های زیرنویس/آرشیو
    if options.get('move_archives', False):
        for item in files:
            item_path = os.path.join(folder_path, item)
            if os.path.isfile(item_path):
                ext = os.path.splitext(item)[1].lower()
                if ext in ARCHIVE_EXTS:
                    
                    # هسته اصلی فایل زیرنویس/آرشیو را هم پیدا کن
                    _dst_folder, _dst_filename, core_title = determine_destination(folder_path, item, options)
                    
                    # بررسی کن آیا این «هسته» با هسته‌های ویدیویی مطابقت دارد
                    if core_title in video_destinations:
                        # مطابقت پیدا شد! از پوشه مقصد ویدیو استفاده کن
                        dst_folder = video_destinations[core_title]
                        dst_path = os.path.join(dst_folder, item)
                        
                        if os.path.abspath(item_path) != os.path.abspath(dst_path):
                            ops.append({
                                "src": os.path.abspath(item_path),
                                "dst_folder": dst_folder,
                                "dst_path": dst_path,
                                "filename": item
                            })
                    # اگر مطابقت پیدا نکرد (فایل srt/zip تنها بود)،
                    # هیچ کاری نکن و پوشه‌ای برای آن نساز (نادیده گرفته می‌شود)
                    else:
                        continue

    # 3️⃣ ترکیب نهایی (اول آرشیوها، بعد ویدیوها)
    ops.extend(video_ops)
    return ops

def perform_moves(ops, log_action=True):
    moved = []
    errors = []
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
        except Exception as e:
            errors.append((op, str(e), traceback.format_exc()))
    if log_action and moved:
        record = {"timestamp": datetime.utcnow().isoformat(), "moved": moved}
        try:
            with open(UNDO_LOG, 'w', encoding='utf-8') as f:
                json.dump(record, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    return moved, errors

def undo_last_action():
    if not os.path.exists(UNDO_LOG):
        return False, "No undo log found."
    try:
        with open(UNDO_LOG, 'r', encoding='utf-8') as f:
            record = json.load(f)
        moved = record.get('moved', [])
        errors = []
        restored = []

        if not moved:
            # هیچ عملیاتی برای بازگردانی وجود ندارد
            try:
                os.remove(UNDO_LOG)
            except Exception:
                pass
            return True, {"restored": restored, "errors": errors, "root": None}

        # تعیین فولدر ریشه (جایی که فایل‌ها از آنجا جابه‌جا شده بودند)
        # فرض: srcهای اولیه از یک پوشه‌ی مشترک گرفته شده‌اند (معمولاً folder انتخاب‌شده)
        root_candidates = { os.path.dirname(op['src']) for op in moved }
        # اگر چند ریشه داشتند، بهترین حدس commonpath
        try:
            root_folder = os.path.commonpath(list(root_candidates))
        except Exception:
            root_folder = next(iter(root_candidates))

        # 1) بازگرداندن فایل‌ها (معکوس نمودن ترتیب)
        for op in reversed(moved):
            src = op.get('dst_path')
            dst = op.get('src')
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if os.path.exists(src):
                    # اگر مقصد اصلی فعلی وجود داشت، به مسیر یکتا تغییر نام بده
                    final_dst = dst
                    if os.path.exists(final_dst):
                        final_dst = unique_filepath(final_dst)
                    shutil.move(src, final_dst)
                    restored.append({'from': src, 'to': final_dst})
                else:
                    errors.append((src, "Source not found for undo"))
            except Exception as e:
                errors.append((op, str(e)))

        # 2) حذف فولدرهای خالی ساخته‌شده توسط نرم‌افزار
        # ابتدا مجموعه‌ای از فولدرهای مقصد که قبلاً ایجاد شده‌اند تهیه می‌کنیم
        created_dirs = { os.path.dirname(op.get('dst_path')) for op in moved if op.get('dst_path') }
        # مرتب‌سازی به ترتیب عمق (از عمیق‌ترین به کم‌عمق) تا حذف منطقی انجام شود
        for d in sorted(created_dirs, key=lambda p: len(p.split(os.sep)), reverse=True):
            try:
                # حذف دایرکتوری فقط اگر واقعا خالی باشد
                if os.path.isdir(d) and not os.listdir(d):
                    os.rmdir(d)
                # پس از حذف (یا در هر حال)، تلاش کن والد‌های خالی را تا root_folder حذف کنی
                parent = os.path.dirname(d)
                # loop up and remove empty parents, but stop at root_folder (do not remove root_folder)
                while parent and os.path.abspath(parent) != os.path.abspath(root_folder):
                    try:
                        if os.path.isdir(parent) and not os.listdir(parent):
                            os.rmdir(parent)
                            parent = os.path.dirname(parent)
                        else:
                            break
                    except Exception:
                        break
            except Exception:
                # اگر قابل حذف نبود یا خطا رخ داد نادیده بگیر
                pass

        # 3) حذف لاگ Undo
        try:
            os.remove(UNDO_LOG)
        except Exception:
            pass

        return True, {"restored": restored, "errors": errors, "root": root_folder}

    except Exception as e:
        return False, f"Failed to read/undo: {e}"



# ----------------------- GUI -----------------------

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🎬 Smart Video Organizer")
        self.geometry("880x640")
        self.minsize(760, 480)

        # appearance
        ctk.set_default_color_theme("blue")
        # load saved theme
        self.theme_mode = ctk.StringVar(value=self.load_theme_from_config())

        # state variables
        self.folder_path = None
        self.move_archives = ctk.BooleanVar(value=False)
        self.create_seasons = ctk.BooleanVar(value=True)

        # internal
        self.last_preview_ops = []

        # build UI
        
        self._build_ui()

    # ---------- icon loading ----------
    

    # ---------- UI building ----------
    def _build_ui(self):
        # left panel
        left = ctk.CTkFrame(self, width=320)
        left.pack(side="left", fill="y", padx=12, pady=12)

        header_frame = ctk.CTkFrame(left, fg_color="transparent")
        header_frame.pack(fill="x", pady=(4,8))

        title = ctk.CTkLabel(header_frame, text="🎬 Smart Video Organizer", font=ctk.CTkFont(size=18, weight="bold"))
        title.pack(side="left", padx=4)

        theme_switch = ctk.CTkSwitch(header_frame, text="Light/Dark", variable=self.theme_mode,
                                     onvalue="Dark", offvalue="Light", command=self.toggle_theme)
        theme_switch.pack(side="right", padx=4)

        # ---------- Load icons ----------
        # ---------- Load icons ----------
        self.icon_folder = ctk.CTkImage(Image.open(resource_path("icons/folder.ico")), size=(20, 20))
        self.icon_search = ctk.CTkImage(Image.open(resource_path("icons/search.ico")), size=(20, 20))
        self.icon_layers = ctk.CTkImage(Image.open(resource_path("icons/layers.ico")), size=(20, 20))
        self.icon_undo = ctk.CTkImage(Image.open(resource_path("icons/undo.ico")), size=(20, 20))
        self.icon_title = ctk.CTkImage(Image.open(resource_path("icons/titlecase.ico")), size=(20, 20))
        # folder entry + browse
        self.path_entry = ctk.CTkEntry(left, placeholder_text="Select folder with videos...", width=320)
        self.path_entry.pack(pady=6)
        btn_browse = ctk.CTkButton(left, text="Browse", image=self.icon_folder, compound="left", width=200, command=self.select_folder)
        btn_browse.pack(pady=(4, 12))

        # options
        ctk.CTkCheckBox(left, text="Move archives and subtitles (zip/rar/srt)", variable=self.move_archives).pack(anchor="w", pady=6, padx=6)
        ctk.CTkCheckBox(left, text="Create season subfolders for series", variable=self.create_seasons).pack(anchor="w", pady=6, padx=6)

        # action buttons
        ctk.CTkButton(left, text="Scan & Preview", image=self.icon_search, compound="left", width=200, command=self.scan_and_preview).pack(pady=8)
        ctk.CTkButton(left, text="Organize", image=self.icon_layers, compound="left", width=200, command=self.execute_moves).pack(pady=8)
        ctk.CTkButton(left, text="Title Case", image=self.icon_title, compound="left", width=200, command=self.title_case_folders).pack(pady=8)
        ctk.CTkButton(left, text="Undo Last Operation", image=self.icon_undo, compound="left", width=200, fg_color="#FF5C5C", hover=False, command=self.undo_action).pack(pady=8)

        # help box
        help_box = ctk.CTkFrame(left, fg_color=("gray90", "#1e1e1e"))
        help_box.pack(fill="x", expand=False, pady=(12, 6), padx=4)

        help_text = (
            "💡 How to Use\n\n"
            "1. Click Browse to select your video folder.\n\n"
            "2. Options:\n"
            "   • Move archives and subtitles (zip/rar/srt)\n"
            "   • Create season subfolders for series\n\n"
            "3. Click Scan & Preview to see planned moves.\n\n"
            "4. If preview looks good, click Organize to apply changes.\n\n"
            "5. Use Undo Last Operation to revert last move.\n\n"
            "6. Enjoy your organized video collection! 🎉"
        )
        self.help_label = ctk.CTkLabel(help_box, text=help_text, wraplength=260, justify="left")
        self.help_label.pack(padx=10, pady=10)
        # responsive
        def resize_help(e):
            new_wrap = max(220, int(e.width * 0.8))
            self.help_label.configure(wraplength=new_wrap)
        help_box.bind("<Configure>", resize_help)

        # status at bottom-left
        self.status = ctk.CTkLabel(left, text="Ready", anchor="w", fg_color="transparent")
        self.status.pack(side="bottom", fill="x", padx=6, pady=(8,0))

        # right panel (preview / log)
        right = ctk.CTkFrame(self)
        right.pack(side="right", fill="both", expand=True, padx=12, pady=12)

        topbar = ctk.CTkFrame(right)
        topbar.pack(fill="x", pady=(0,8))
        lbl = ctk.CTkLabel(topbar, text="Preview / Log", font=ctk.CTkFont(size=14, weight="bold"))
        lbl.pack(side="left", padx=8)
        ctk.CTkButton(topbar, text="Refresh Preview", width=140, command=self.scan_and_preview).pack(side="right", padx=8)

        self.log_box = ctk.CTkTextbox(right, wrap="none", font=ctk.CTkFont(size=14), corner_radius=6,state="normal")
        self.log_box.pack(fill="both", expand=True)
        # keep log_box in normal state so selection works; block typing keys instead
        self.log_box.configure(state="normal")
        self._bind_copy_shortcut()

    # ---------- Theme persistence ----------
    def load_theme_from_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                theme = cfg.get("theme_mode", "Dark")
                ctk.set_appearance_mode(theme)
                return theme
            except Exception:
                pass
        # default
        ctk.set_appearance_mode("Dark")
        return "Dark"

    def save_theme_to_config(self, theme_mode):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump({"theme_mode": theme_mode}, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def toggle_theme(self):
        current = ctk.get_appearance_mode()
        new_mode = "Dark" if current == "Light" else "Light"
        ctk.set_appearance_mode(new_mode)
        self.theme_mode.set(new_mode)
        self.status.configure(text=f"Theme: {new_mode}")
        self.save_theme_to_config(new_mode)

    # ---------- Helpers ----------
    def _bind_copy_shortcut(self):
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
            # Allow Ctrl+C
            if (event.state & 0x4) and event.keysym.lower() == "c":
                return
            # Block normal typing/pasting/deleting inside the log box
            return "break"

        self.log_box.bind("<Control-c>", copy_event)
        self.log_box.bind("<Control-C>", copy_event)
        self.log_box.bind("<Key>", block_input)

    def log(self, text, clear=False):
        if clear:
            self.log_box.delete("1.0", "end")
        self.log_box.insert("end", f"{text}\n")
        self.log_box.see("end")

    # ---------- Actions ----------
    def select_folder(self):
        folder = filedialog.askdirectory(title="Select Folder Containing Videos")
        if folder:
            self.folder_path = folder
            self.path_entry.delete(0, 'end')
            self.path_entry.insert(0, folder)
            self.log(f"Selected folder: {folder}")
            self.status.configure(text=f"Folder: {folder}")

    def scan_and_preview(self):
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
                self.log("✅ Nothing to move (no matching files or already organized).")
            else:
                self.log(f"Previewing {len(ops)} operations:\n")
                for i, op in enumerate(ops, 1):
                    src = op['src']
                    dst = op['dst_path']
                    self.log(f"{i}. {os.path.basename(src)}\n   -> {dst}\n")
            self.status.configure(text=f"Preview ready: {len(ops)} items.")
        except Exception as e:
            messagebox.showerror("Error", f"Scan failed: {e}")
            self.log(f"Scan error: {traceback.format_exc()}")

    def execute_moves(self):
        folder = self.path_entry.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("Folder required", "Please select a valid folder first.")
            return

        if not self.last_preview_ops:
            # auto-scan if user didn't press Scan
            self.scan_and_preview()
            if not self.last_preview_ops:
                messagebox.showinfo("Nothing to do", "No operations to perform.")
                return

        try:
            moved, errors = perform_moves(self.last_preview_ops, log_action=True)
            self.log(f"\n--- Move completed. {len(moved)} moved, {len(errors)} errors ---")
            for m in moved:
                self.log(f"Moved: {m['src']} -> {m['dst_path']}")
            for e in errors:
                op, err_msg, tb = e
                self.log(f"Error moving {op.get('src')}: {err_msg}")
            self.status.configure(text=f"Done: {len(moved)} moved.")
            messagebox.showinfo("Done", f"✅ {len(moved)} files moved successfully.")

            # open folder to show results
            open_folder(folder)

            # clear preview ops
            self.last_preview_ops = []
        except Exception as e:
            messagebox.showerror("Error", f"Move failed: {e}")
            self.log(f"Move error: {traceback.format_exc()}")

    def title_case_folders(self):
        folder = self.path_entry.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("Folder required", "Please select a valid folder first.")
            return
        
        renamed = []
        errors = []
        
        for name in os.listdir(folder):
            src = os.path.join(folder, name)
            if os.path.isdir(src):
                
                # --- بخش اصلاح‌شده ---
                # مستقیماً از .title() استفاده کن، بدون نرمال‌سازی
                new_name = name.title()
                # --- پایان بخش اصلاح‌شده ---

                if new_name != name:
                    dst = os.path.join(folder, new_name)
                    try:
                        # این منطق برای مدیریت خطای case-insensitive ویندوز
                        # (که در پاسخ قبلی توضیح داده شد) هنوز ضروری است
                        if name.lower() != new_name.lower():
                            # این یک تداخل واقعی است (مثلاً 'file-A' و 'file.a' هر دو به 'File.A' تبدیل شوند)
                            if os.path.exists(dst):
                                errors.append((name, f"Destination '{new_name}' already exists (clash)"))
                                continue # برو سراغ فایل بعدی
                        
                        # تغییر نام را انجام بده (چه فقط case باشد چه نباشد)
                        os.rename(src, dst)
                        renamed.append((name, new_name))

                    except Exception as e:
                        # گرفتن خطاهای دیگر (مثل Permission denied)
                        errors.append((name, str(e)))
        
        self.log("\n--- Title Case Operation ---")
        for r in renamed:
            self.log(f"Renamed: {r[0]} -> {r[1]}")
        for e in errors:
            self.log(f"Error: {e[0]} ({e[1]})")
        
        self.log(f"Completed. {len(renamed)} renamed, {len(errors)} errors.")
        self.status.configure(text=f"Title Case done: {len(renamed)} renamed.")
        messagebox.showinfo("Title Case", f"✅ {len(renamed)} folders renamed to Title Case.")

    def undo_action(self):
        ok, result = undo_last_action()
        if not ok:
            messagebox.showinfo("Undo", result)
            self.log(f"Undo failed: {result}")
            return

        # result باید dict حاوی restored, errors, root باشد
        if isinstance(result, dict):
            restored = result.get('restored', [])
            errors = result.get('errors', [])
            root = result.get('root', None)

            self.log(f"\n--- Undo completed. Restored: {len(restored)}, Errors: {len(errors)} ---")
            for r in restored:
                self.log(f"Restored: {r.get('from')} -> {r.get('to')}")
            for err in errors:
                self.log(f"Undo error: {err}")

            self.status.configure(text=f"Undo completed. Restored: {len(restored)}.")
            messagebox.showinfo("Undo", f"Undo completed. Restored: {len(restored)}. See log for details.")

            # اگر فولدر ریشه مشخص است، آن را باز کن تا کاربر نتیجه را ببیند
            if root and os.path.isdir(root):
                try:
                    open_folder(root)
                except Exception:
                    pass
        else:
            # رشته خطا یا پیام برگشتی
            self.log(f"Undo result: {result}")
            messagebox.showinfo("Undo", str(result))

# ----------------------- Run -----------------------

if __name__ == "__main__":
    app = App()
    app.mainloop()
