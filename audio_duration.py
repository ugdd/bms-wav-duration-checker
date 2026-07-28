"""BMS内の音源ファイル名から実ファイルを安全に解決し、再生時間を取得する。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mutagen import File as MutagenFile

# BMSの#WAV定義は拡張子 .wav でも実体が .ogg/.mp3/.flac であることが多い
# (音声圧縮のため)。定義どおりの拡張子が見つからない場合、この順で
# 同名ファイルを探索する。
_FALLBACK_EXTENSIONS = (".wav", ".ogg", ".mp3", ".flac")

STATUS_OK = "ok"
STATUS_MISSING = "missing"
STATUS_UNSUPPORTED = "unsupported"
STATUS_ERROR = "error"


@dataclass
class SoundInfo:
    def_id: str
    declared_filename: str            # BMSファイル内の記述
    resolved_path: Path | None        # 実際に見つかったファイル(未検出ならNone)
    duration_seconds: float | None
    status: str                       # STATUS_* のいずれか
    message: str = ""


def _resolve_within_base(base_dir: Path, declared_filename: str) -> Path | None:
    """BMS内のファイル名を base_dir 配下に限定して解決する。

    セキュリティ上の注意: declared_filename には ".." や絶対パス、
    シンボリックリンク経由でのフォルダ外参照が含まれる可能性がある
    (悪意あるBMS配布物を想定)。pathlib は絶対パスとの結合で右辺を
    優先してしまう挙動があるため、結合結果そのものではなく、
    resolve() 後の最終パスが base_dir 配下にあるかを必ず確認する。
    """
    base_resolved = base_dir.resolve()
    normalized = declared_filename.replace("\\", "/").lstrip("/")

    try:
        candidate = (base_resolved / normalized).resolve()
    except (OSError, ValueError):
        return None

    try:
        candidate.relative_to(base_resolved)
    except ValueError:
        return None  # base_dir の外を指しているため拒否

    return candidate


def _find_actual_file(base_dir: Path, declared_filename: str) -> Path | None:
    """宣言どおりのファイルが無い場合、拡張子違いの同名ファイルを探す。"""
    declared_path = _resolve_within_base(base_dir, declared_filename)
    if declared_path is None:
        return None

    if declared_path.is_file():
        return declared_path

    stem_path = declared_path.with_suffix("")
    parent = stem_path.parent
    if not parent.is_dir():
        return None

    for ext in _FALLBACK_EXTENSIONS:
        candidate = stem_path.with_suffix(ext)
        if candidate.is_file():
            return candidate

    return None


def get_sound_info(def_id: str, declared_filename: str, base_dir: Path) -> SoundInfo:
    """1件の#WAV定義について、実ファイルを探索し再生時間を取得する。"""
    within_base = _resolve_within_base(base_dir, declared_filename)
    if within_base is None:
        return SoundInfo(
            def_id, declared_filename, None, None, STATUS_ERROR,
            "不正なパス(フォルダ外参照)のため無視しました",
        )

    resolved = _find_actual_file(base_dir, declared_filename)
    if resolved is None:
        return SoundInfo(
            def_id, declared_filename, None, None, STATUS_MISSING,
            "ファイルが見つかりません",
        )

    try:
        audio = MutagenFile(resolved)
    except Exception as e:  # noqa: BLE001 - 未知形式/破損ファイルへの防御的処理
        return SoundInfo(def_id, declared_filename, resolved, None, STATUS_ERROR, str(e))

    if audio is None or audio.info is None or not hasattr(audio.info, "length"):
        return SoundInfo(
            def_id, declared_filename, resolved, None, STATUS_UNSUPPORTED,
            "対応していない音源形式です",
        )

    message = ""
    declared_name = Path(declared_filename).name
    if resolved.name.lower() != declared_name.lower():
        message = f"実体: {resolved.name}"

    return SoundInfo(
        def_id, declared_filename, resolved, float(audio.info.length), STATUS_OK, message
    )
