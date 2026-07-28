"""BMS 音源長さチェッカー

BMS/BME/BML譜面ファイル内の #WAVxx (キー音) 定義を読み込み、
各定義番号・音源ファイル名・音源ファイルの再生時間を一覧表示するツール。
長すぎる音源を誤って譜面に割り当てないよう、長さでソートして確認できる。
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from audio_duration import (
    STATUS_ERROR,
    STATUS_MISSING,
    STATUS_OK,
    STATUS_UNSUPPORTED,
    SoundInfo,
    get_sound_info,
)
from bms_parser import BmsFileTooLargeError, parse_wav_definitions
from settings import load_theme, save_theme

APP_TITLE = "BMS 音源長さチェッカー"

THEMES = {
    "dark": {
        "bg": "#1e1e2e",
        "bg_alt": "#262637",
        "fg": "#e4e4ef",
        "fg_muted": "#9a9ab0",
        "select": "#3b4261",
        "warn": "#e0af68",
        "error": "#f7768e",
    },
    "light": {
        "bg": "#f5f5fa",
        "bg_alt": "#ffffff",
        "fg": "#1f1f2e",
        "fg_muted": "#5c5c70",
        "select": "#d7defa",
        "warn": "#c9660a",
        "error": "#c92a2a",
    },
}

_COLUMNS = ("def_id", "filename", "duration", "status")
_HEADINGS = {
    "def_id": "定義番号",
    "filename": "ファイル名",
    "duration": "長さ",
    "status": "状態",
}
_STATUS_LABELS = {
    STATUS_OK: "OK",
    STATUS_MISSING: "見つかりません",
    STATUS_UNSUPPORTED: "非対応形式",
    STATUS_ERROR: "エラー",
}


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "---"
    minutes = int(seconds // 60)
    secs = seconds - minutes * 60
    return f"{minutes}:{secs:06.3f}"


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("880x560")
        self.root.minsize(640, 400)

        self.theme_name = load_theme()
        self.colors = THEMES[self.theme_name]
        self.root.configure(bg=self.colors["bg"])

        self._queue: queue.Queue = queue.Queue()
        self._busy = False
        self._current_results: list[SoundInfo] = []
        self._sort_column = "def_id"
        self._sort_reverse = False

        self._build_style()
        self._build_widgets()
        self._apply_treeview_tags()
        self.root.after(50, self._poll_queue)

    # ------------------------------------------------------------------
    # UI構築
    # ------------------------------------------------------------------
    def _build_style(self) -> None:
        c = self.colors
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background=c["bg"])
        style.configure("TLabel", background=c["bg"], foreground=c["fg"])
        style.configure("Muted.TLabel", background=c["bg"], foreground=c["fg_muted"])
        style.configure(
            "TButton",
            background=c["bg_alt"],
            foreground=c["fg"],
            borderwidth=0,
            focusthickness=0,
            padding=6,
        )
        style.map(
            "TButton",
            background=[("active", c["select"]), ("disabled", c["bg_alt"])],
            foreground=[("disabled", c["fg_muted"])],
        )
        style.configure(
            "TEntry",
            fieldbackground=c["bg_alt"],
            foreground=c["fg"],
            insertcolor=c["fg"],
            borderwidth=0,
        )
        style.configure(
            "Treeview",
            background=c["bg_alt"],
            fieldbackground=c["bg_alt"],
            foreground=c["fg"],
            rowheight=24,
            borderwidth=0,
        )
        style.map("Treeview", background=[("selected", c["select"])])
        style.configure(
            "Treeview.Heading",
            background=c["bg"],
            foreground=c["fg"],
            borderwidth=1,
            relief="flat",
        )
        style.map("Treeview.Heading", background=[("active", c["select"])])

    def _apply_treeview_tags(self) -> None:
        c = self.colors
        self.tree.tag_configure(STATUS_OK, foreground=c["fg"])
        self.tree.tag_configure(STATUS_MISSING, foreground=c["warn"])
        self.tree.tag_configure(STATUS_UNSUPPORTED, foreground=c["fg_muted"])
        self.tree.tag_configure(STATUS_ERROR, foreground=c["error"])

    def _theme_button_text(self) -> str:
        return "ライトモードに切替" if self.theme_name == "dark" else "ダークモードに切替"

    def _toggle_theme(self) -> None:
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.colors = THEMES[self.theme_name]
        save_theme(self.theme_name)

        self.root.configure(bg=self.colors["bg"])
        self._build_style()
        self._apply_treeview_tags()
        self.theme_btn.configure(text=self._theme_button_text())

    def _build_widgets(self) -> None:
        top = ttk.Frame(self.root, padding=(10, 10, 10, 6))
        top.pack(side="top", fill="x")

        ttk.Label(top, text="BMSファイル:").pack(side="left")

        self.path_var = tk.StringVar()
        self.path_entry = ttk.Entry(top, textvariable=self.path_var, state="readonly")
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(6, 6))

        self.browse_btn = ttk.Button(top, text="参照...", command=self._browse)
        self.browse_btn.pack(side="left")

        self.theme_btn = ttk.Button(
            top, text=self._theme_button_text(), command=self._toggle_theme
        )
        self.theme_btn.pack(side="left", padx=(6, 0))

        # Treeview + スクロールバー
        tree_frame = ttk.Frame(self.root, padding=(10, 0, 10, 0))
        tree_frame.pack(side="top", fill="both", expand=True)

        self.tree = ttk.Treeview(
            tree_frame, columns=_COLUMNS, show="headings", selectmode="browse"
        )
        self.tree.column("def_id", width=90, anchor="center", stretch=False)
        self.tree.column("filename", width=420, anchor="w")
        self.tree.column("duration", width=110, anchor="e", stretch=False)
        self.tree.column("status", width=200, anchor="w")
        self._update_headings()

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        # ステータスバー
        bottom = ttk.Frame(self.root, padding=(10, 6, 10, 10))
        bottom.pack(side="bottom", fill="x")
        self.status_var = tk.StringVar(value="BMS/BME/BMLファイルを選択してください")
        ttk.Label(bottom, textvariable=self.status_var, style="Muted.TLabel").pack(side="left")

    def _update_headings(self) -> None:
        for col in _COLUMNS:
            arrow = ""
            if col == self._sort_column:
                arrow = " ▼" if self._sort_reverse else " ▲"
            self.tree.heading(
                col,
                text=_HEADINGS[col] + arrow,
                command=lambda c=col: self._on_heading_click(c),
            )

    # ------------------------------------------------------------------
    # ファイル読み込み
    # ------------------------------------------------------------------
    def _browse(self) -> None:
        path_str = filedialog.askopenfilename(
            title="BMS/BME/BMLファイルを選択",
            filetypes=[
                ("BMS譜面ファイル", "*.bms *.bme *.bml"),
                ("すべてのファイル", "*.*"),
            ],
        )
        if not path_str:
            return
        self._load_file(Path(path_str))

    def _load_file(self, path: Path) -> None:
        if self._busy:
            return
        self.path_var.set(str(path))
        self._set_busy(True)
        self.status_var.set(f"読み込み中: {path.name}")
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._current_results = []

        thread = threading.Thread(target=self._load_worker, args=(path,), daemon=True)
        thread.start()

    def _load_worker(self, path: Path) -> None:
        try:
            defs = parse_wav_definitions(path)
        except BmsFileTooLargeError as e:
            self._queue.put(("error", str(e)))
            return
        except (OSError, UnicodeError) as e:
            self._queue.put(("error", f"ファイルの読み込みに失敗しました:\n{e}"))
            return

        base_dir = path.parent
        total = len(defs)
        results: list[SoundInfo] = []
        for i, d in enumerate(defs, 1):
            results.append(get_sound_info(d.def_id, d.filename, base_dir))
            if i % 20 == 0 or i == total:
                self._queue.put(("progress", i, total))

        self._queue.put(("done", results))

    def _poll_queue(self) -> None:
        try:
            while True:
                msg = self._queue.get_nowait()
                kind = msg[0]
                if kind == "progress":
                    _, i, total = msg
                    self.status_var.set(f"解析中... {i}/{total}")
                elif kind == "done":
                    self._on_load_done(msg[1])
                elif kind == "error":
                    self._set_busy(False)
                    self.status_var.set("エラーが発生しました")
                    messagebox.showerror(APP_TITLE, msg[1])
        except queue.Empty:
            pass
        self.root.after(50, self._poll_queue)

    def _on_load_done(self, results: list[SoundInfo]) -> None:
        self._current_results = results
        self._set_busy(False)
        total = len(results)
        ok = sum(1 for r in results if r.status == STATUS_OK)
        missing = sum(1 for r in results if r.status == STATUS_MISSING)
        problem = total - ok - missing
        self.status_var.set(
            f"定義 {total} 件中 OK: {ok} / 見つからない: {missing} / その他: {problem}"
        )
        self._populate_tree()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.browse_btn.configure(state="disabled" if busy else "normal")

    # ------------------------------------------------------------------
    # ソート・表示
    # ------------------------------------------------------------------
    def _sort_key(self, info: SoundInfo):
        if self._sort_column == "def_id":
            return int(info.def_id, 36)
        if self._sort_column == "filename":
            return info.declared_filename.lower()
        if self._sort_column == "duration":
            return info.duration_seconds if info.duration_seconds is not None else -1.0
        return (info.status, info.message)

    def _on_heading_click(self, column: str) -> None:
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False
        self._update_headings()
        self._populate_tree()

    def _populate_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        ordered = sorted(
            self._current_results, key=self._sort_key, reverse=self._sort_reverse
        )
        for idx, info in enumerate(ordered):
            status_text = _STATUS_LABELS.get(info.status, info.status)
            if info.message:
                status_text = f"{status_text} ({info.message})"
            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    info.def_id,
                    info.declared_filename,
                    format_duration(info.duration_seconds),
                    status_text,
                ),
                tags=(info.status,),
            )


def main() -> None:
    root = tk.Tk()
    App(root)
    try:
        root.mainloop()
    except Exception as e:  # noqa: BLE001 - GUIアプリのトップレベル防御
        messagebox.showerror(APP_TITLE, f"予期しないエラーが発生しました:\n{e}")
        raise


if __name__ == "__main__":
    main()
