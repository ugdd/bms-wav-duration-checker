"""BMS/BME/BML ファイルから #WAVxx (キー音) 定義を抽出するパーサー。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# BMS本文は通常数百KB程度のテキストファイル。想定外に巨大なファイルを
# 誤って読み込んでメモリを圧迫しないよう上限を設ける。
MAX_BMS_FILE_SIZE = 20 * 1024 * 1024  # 20MB

# 定義行の例: "#WAV01 sound.wav" / 定義番号は 00-99,A0-ZZ の36進2桁
_WAV_DEF_RE = re.compile(r'^#WAV([0-9A-Za-z]{2})\s+(\S.*?)\s*$', re.IGNORECASE)


class BmsFileTooLargeError(Exception):
    """BMSファイルが上限サイズを超えている場合に送出。"""


@dataclass(frozen=True)
class WavDefinition:
    def_id: str        # 2文字の定義番号(大文字に正規化、例: "01", "A1")
    filename: str       # BMS内に記述されたファイル名(相対パス)


def _decode_bms_text(data: bytes) -> str:
    """BMSは Shift_JIS(CP932) が主流だが UTF-8 のファイルも存在するため、
    UTF-8 を優先的に試し、失敗したら CP932 にフォールバックする。"""
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("cp932", errors="replace")


def parse_wav_definitions(bms_path: Path) -> list[WavDefinition]:
    """BMS/BME/BMLファイルを読み込み、#WAVxx定義を抽出する(定義番号昇順)。"""
    size = bms_path.stat().st_size
    if size > MAX_BMS_FILE_SIZE:
        raise BmsFileTooLargeError(
            f"ファイルサイズが上限({MAX_BMS_FILE_SIZE // (1024 * 1024)}MB)を"
            f"超えています: {size:,} bytes"
        )

    text = _decode_bms_text(bms_path.read_bytes())

    definitions: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("#"):
            continue
        m = _WAV_DEF_RE.match(line)
        if not m:
            continue
        def_id, filename = m.groups()
        # 同じ定義番号が複数回出現した場合、BMS仕様上は後勝ち
        definitions[def_id.upper()] = filename.strip()

    return [
        WavDefinition(def_id=def_id, filename=filename)
        for def_id, filename in definitions.items()
    ]
