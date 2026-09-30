"""
Flowchart Builder — modern neon dark UI on PySide6.
Three independent panels: Source code | Saved schemas | Flowchart scene.
Frameless dialogs everywhere, RU/EN UI, theme-aware syntax highlighting.
"""

from __future__ import annotations
import json
import math
import sys
from pathlib import Path

from PySide6.QtCore import (
    Qt, QRectF, QPointF, QPoint, QEvent, QTimer, QRegularExpression,
)
from PySide6.QtGui import (
    QFont, QPen, QBrush, QColor, QPainter, QPolygonF,
    QSyntaxHighlighter, QTextCharFormat,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QComboBox, QPushButton, QLabel,
    QGraphicsView, QGraphicsScene, QSizePolicy,
    QListWidget, QListWidgetItem, QAbstractItemView, QFileDialog,
    QDialog, QLineEdit, QListView,
)

import logic


DEFAULT_CODE = '''x = int(input())
if x > 0:
    print("positive")
elif x < 0:
    print("negative")
else:
    print("zero")

i = 0
while i < 10:
    print(i)
    i = i + 1

print("done")
'''

BASE_DIR = Path(__file__).resolve().parent
SCHEMAS_DIR = BASE_DIR / "schemas"
SCHEMAS_DIR.mkdir(exist_ok=True)
CONFIG_PATH = BASE_DIR / "config.json"

WINDOW_RADIUS = 16
DIALOG_RADIUS = 14


# ======================================================================
# Translations
# ======================================================================

STRINGS = {
    "en": {
        "app_title": "Flowchart Builder",
        "source_code": "Source code",
        "saved_schemas": "Saved schemas",
        "language": "Language",
        "theme": "Theme",
        "help": "Help",
        "settings": "Settings",
        "convert": "Convert",
        "save": "Save",
        "save_as": "Save As…",
        "load": "Load",
        "delete": "Delete",
        "close": "Close",
        "cancel": "Cancel",
        "ok": "OK",
        "yes": "Yes",
        "no": "No",
        "error": "Error",
        "info": "Information",
        "confirm": "Confirmation",
        "load_title": "Load",
        "save_title": "Save",
        "delete_title": "Delete",
        "select_schema_first": "Select a schema first.",
        "file_missing": "File no longer exists.",
        "failed_save": "Failed to save",
        "failed_load": "Failed to load",
        "failed_delete": "Failed to delete",
        "failed_read": "Failed to read file",
        "schema_name": "Schema name",
        "save_schema_as": "Save schema as",
        "delete_schema_q": "Delete '{name}'?",
        "delete_schema": "Delete schema",
        "load_source_code": "Load source code",
        "unknown_ext": "Unknown extension",
        "unknown_ext_q": "File '{name}' has unknown extension.\nParse as Python? (No = C++)",
        "help_title": "Help — block types",
        "help_subtitle": ("Every block below is drawn using the colors of the current theme.\n"
                          "Switch the theme in Settings and reopen this dialog to see the change."),
        "help_note": ("Arrows connect blocks top-down and bend only at 90°.\n"
                      "Branch labels 'Yes' (green) and 'No' (red) are shown next to every condition."),
        "help_b_start":   "Start / End",
        "help_b_start_d": "Entry and exit of the algorithm. Drawn as an oval.",
        "help_b_process": "Process",
        "help_b_process_d": "Assignment or simple action: x = 5, i += 1. Drawn as a rectangle.",
        "help_b_io":      "Input / Output",
        "help_b_io_d":    "Reading or printing data: input(), print(), cin, cout. Drawn as a parallelogram.",
        "help_b_cond":    "Condition (if / elif / else)",
        "help_b_cond_d":  "Two-way branching. Yes goes to the right, No goes to the left. Drawn as a diamond.",
        "help_b_loop":    "Loop (while / for)",
        "help_b_loop_d":  "Repeating body with a back-arrow. Drawn as a diamond.",
        "settings_title": "Settings",
        "settings_lang": "Language",
        "settings_theme": "Theme",
        "theme_label_en": "English",
        "theme_label_ru": "Russian",
    },
    "ru": {
        "app_title": "Конструктор блок-схем",
        "source_code": "Исходный код",
        "saved_schemas": "Сохранённые схемы",
        "language": "Язык",
        "theme": "Тема",
        "help": "Справка",
        "settings": "Настройки",
        "convert": "Построить",
        "save": "Сохранить",
        "save_as": "Сохранить как…",
        "load": "Загрузить",
        "delete": "Удалить",
        "close": "Закрыть",
        "cancel": "Отмена",
        "ok": "ОК",
        "yes": "Да",
        "no": "Нет",
        "error": "Ошибка",
        "info": "Информация",
        "confirm": "Подтверждение",
        "load_title": "Загрузка",
        "save_title": "Сохранение",
        "delete_title": "Удаление",
        "select_schema_first": "Сначала выберите схему.",
        "file_missing": "Файл больше не существует.",
        "failed_save": "Не удалось сохранить",
        "failed_load": "Не удалось загрузить",
        "failed_delete": "Не удалось удалить",
        "failed_read": "Не удалось прочитать файл",
        "schema_name": "Имя схемы",
        "save_schema_as": "Сохранить схему как",
        "delete_schema_q": "Удалить '{name}'?",
        "delete_schema": "Удалить схему",
        "load_source_code": "Загрузить исходный код",
        "unknown_ext": "Неизвестное расширение",
        "unknown_ext_q": "У файла '{name}' неизвестное расширение.\nРазобрать как Python? (Нет = C++)",
        "help_title": "Справка — типы блоков",
        "help_subtitle": ("Все блоки ниже нарисованы в цветах текущей темы.\n"
                          "Поменяйте тему в Настройках и откройте окно снова, чтобы увидеть разницу."),
        "help_note": ("Стрелки соединяют блоки сверху вниз и поворачивают только под 90°.\n"
                      "Метки 'Yes' (зелёная) и 'No' (красная) показаны рядом с каждым условием."),
        "help_b_start":   "Начало / Конец",
        "help_b_start_d": "Вход и выход алгоритма. Рисуется овалом.",
        "help_b_process": "Процесс",
        "help_b_process_d": "Присваивание или простое действие: x = 5, i += 1. Рисуется прямоугольником.",
        "help_b_io":      "Ввод / Вывод",
        "help_b_io_d":    "Чтение или печать данных: input(), print(), cin, cout. Рисуется параллелограммом.",
        "help_b_cond":    "Условие (if / elif / else)",
        "help_b_cond_d":  "Две ветви. Yes идёт вправо, No — влево. Рисуется ромбом.",
        "help_b_loop":    "Цикл (while / for)",
        "help_b_loop_d":  "Повторяющееся тело с обратной стрелкой. Рисуется ромбом.",
        "settings_title": "Настройки",
        "settings_lang": "Язык",
        "settings_theme": "Тема",
        "theme_label_en": "English",
        "theme_label_ru": "Русский",
    },
}


# ======================================================================
# Palettes
# ======================================================================

PALETTES = {
    "cyberpunk": {
        "label_en": "Cyberpunk", "label_ru": "Киберпанк",
        "bg_main": "#100016",
        "bg_panel_rgb": (26, 8, 40),
        "border_soft": "rgba(255,255,255,0.06)",
        "text_primary": "#F5E9FF",
        "text_secondary": "#C9A9E0",
        "text_muted": "#8A6FA8",
        "accent": "#E945C6",
        "accent_soft": "rgba(233,69,198,0.22)",
        "accent_neon": "#22D3EE",
        "danger": "#FB7185",
        "scene_bg": "#0F0018",
        "arrow": "#D9B3E8",
        "shape_start":  ("#123028", "#34D399", "#DBFFF0"),
        "shape_end":    ("#3A1230", "#F472B6", "#FFE0F4"),
        "shape_process":("#26113E", "#A855F7", "#F3E9FF"),
        "shape_io":     ("#0F2F3A", "#22D3EE", "#DEFBFF"),
        "shape_cond":   ("#3A2410", "#FBBF24", "#FFF3D6"),
        "shape_loop":   ("#2A1240", "#E945C6", "#FFE0FA"),
        "hl_kw": "#FF7EDB", "hl_type": "#5FD3D3", "hl_str": "#98D982",
        "hl_num": "#F2C97A", "hl_com": "#7A8296", "hl_dec": "#F0A868",
        "hl_func": "#C9A6FF", "hl_self": "#FF9AA2", "hl_op": "#FFD166",
    },
    "red_neon": {
        "label_en": "Red Neon", "label_ru": "Красный неон",
        "bg_main": "#080001",
        "bg_panel_rgb": (22, 2, 4),
        "border_soft": "rgba(255,40,40,0.14)",
        "text_primary": "#FFE2E2",
        "text_secondary": "#F08080",
        "text_muted": "#8B3030",
        "accent": "#FF2020",
        "accent_soft": "rgba(255,32,32,0.30)",
        "accent_neon": "#FF5252",
        "danger": "#FF3333",
        "scene_bg": "#0A0001",
        "arrow": "#E06666",
        "shape_start":  ("#0F2A18", "#3DDB7D", "#E6FFEE"),
        "shape_end":    ("#4A0008", "#FF0000", "#FFE0E0"),
        "shape_process":("#380004", "#FF2020", "#FFE8E8"),
        "shape_io":     ("#2A0600", "#FF6B00", "#FFEBD6"),
        "shape_cond":   ("#3A2200", "#FFB000", "#FFF3D6"),
        "shape_loop":   ("#3A0020", "#FF0088", "#FFE0F0"),
        "hl_kw": "#FF5555", "hl_type": "#FFB86B", "hl_str": "#C8E68A",
        "hl_num": "#FFC46B", "hl_com": "#9A6868", "hl_dec": "#FF8A4C",
        "hl_func": "#FFA8B0", "hl_self": "#FF6B6B", "hl_op": "#FFE066",
    },
    "midnight": {
        "label_en": "Midnight Blue", "label_ru": "Полночный синий",
        "bg_main": "#080B18",
        "bg_panel_rgb": (14, 18, 34),
        "border_soft": "rgba(255,255,255,0.06)",
        "text_primary": "#E8EEF9",
        "text_secondary": "#94A3C4",
        "text_muted": "#5E6B85",
        "accent": "#5B8DEF",
        "accent_soft": "rgba(91,141,239,0.22)",
        "accent_neon": "#7DD3FC",
        "danger": "#F87171",
        "scene_bg": "#0B0F1E",
        "arrow": "#93A4C4",
        "shape_start":  ("#1F3A2E", "#4ADE80", "#E8FFF1"),
        "shape_end":    ("#3A1F2A", "#F472B6", "#FFE8F3"),
        "shape_process":("#1E2A4A", "#6E9BFF", "#E8EEF9"),
        "shape_io":     ("#1E3A3F", "#4DD4C8", "#E5FFFC"),
        "shape_cond":   ("#3A3320", "#FBBF24", "#FFF7E0"),
        "shape_loop":   ("#332043", "#C084FC", "#F7ECFF"),
        "hl_kw": "#7DA6FF", "hl_type": "#5FD3D3", "hl_str": "#98D982",
        "hl_num": "#F2C97A", "hl_com": "#7A8296", "hl_dec": "#F0A868",
        "hl_func": "#C9A6FF", "hl_self": "#FF9AA2", "hl_op": "#FFD166",
    },
    "emerald": {
        "label_en": "Emerald", "label_ru": "Изумруд",
        "bg_main": "#05130F",
        "bg_panel_rgb": (10, 28, 24),
        "border_soft": "rgba(255,255,255,0.06)",
        "text_primary": "#E6FFF4",
        "text_secondary": "#8CC9B2",
        "text_muted": "#5F8B7A",
        "accent": "#34D399",
        "accent_soft": "rgba(52,211,153,0.22)",
        "accent_neon": "#5EEAD4",
        "danger": "#F87171",
        "scene_bg": "#071814",
        "arrow": "#8FC7B2",
        "shape_start":  ("#123027", "#34D399", "#DBFFF0"),
        "shape_end":    ("#2A1A2A", "#F472B6", "#FFE6F2"),
        "shape_process":("#0F2A2F", "#22D3EE", "#DBFBFF"),
        "shape_io":     ("#0F2F26", "#5EEAD4", "#DEFFF7"),
        "shape_cond":   ("#3A2E10", "#FBBF24", "#FFF4D9"),
        "shape_loop":   ("#1C2A40", "#60A5FA", "#E3EEFF"),
        "hl_kw": "#7EE8B5", "hl_type": "#5EEAD4", "hl_str": "#B6F7A8",
        "hl_num": "#F2C97A", "hl_com": "#6E9988", "hl_dec": "#FFB86B",
        "hl_func": "#A0E8FF", "hl_self": "#FF9AA2", "hl_op": "#FFE066",
    },
    "sunset": {
        "label_en": "Sunset", "label_ru": "Закат",
        "bg_main": "#180A0F",
        "bg_panel_rgb": (34, 16, 22),
        "border_soft": "rgba(255,255,255,0.06)",
        "text_primary": "#FFEDE0",
        "text_secondary": "#D8A790",
        "text_muted": "#8B6656",
        "accent": "#FB923C",
        "accent_soft": "rgba(251,146,60,0.22)",
        "accent_neon": "#FBBF24",
        "danger": "#F87171",
        "scene_bg": "#160A0E",
        "arrow": "#D6A88E",
        "shape_start":  ("#123027", "#34D399", "#DBFFF0"),
        "shape_end":    ("#3A1A26", "#FB7185", "#FFE0E8"),
        "shape_process":("#2E1A0E", "#FBBF24", "#FFF3D9"),
        "shape_io":     ("#0F2F2E", "#2DD4BF", "#DEFBF7"),
        "shape_cond":   ("#3A2210", "#FB923C", "#FFEBD5"),
        "shape_loop":   ("#2A1230", "#C084FC", "#F7E8FF"),
        "hl_kw": "#FFB86B", "hl_type": "#5EEAD4", "hl_str": "#C8E68A",
        "hl_num": "#FFD166", "hl_com": "#9A8574", "hl_dec": "#FF9B57",
        "hl_func": "#FFD9B0", "hl_self": "#FF9AA2", "hl_op": "#FFE066",
    },
    "graphite": {
        "label_en": "Graphite", "label_ru": "Графит",
        "bg_main": "#0D0F14",
        "bg_panel_rgb": (20, 23, 30),
        "border_soft": "rgba(255,255,255,0.07)",
        "text_primary": "#E5E9F0",
        "text_secondary": "#9AA5B8",
        "text_muted": "#6B7280",
        "accent": "#94A3B8",
        "accent_soft": "rgba(148,163,184,0.20)",
        "accent_neon": "#CBD5E1",
        "danger": "#F87171",
        "scene_bg": "#111318",
        "arrow": "#A8B3C7",
        "shape_start":  ("#1A2A22", "#4ADE80", "#E8FFF1"),
        "shape_end":    ("#2A1C24", "#F472B6", "#FFE8F3"),
        "shape_process":("#1F2A3D", "#93C5FD", "#E8EEF9"),
        "shape_io":     ("#1A2B2E", "#5EEAD4", "#E5FFFC"),
        "shape_cond":   ("#2E2919", "#FBBF24", "#FFF7E0"),
        "shape_loop":   ("#2A203A", "#C084FC", "#F7ECFF"),
        "hl_kw": "#93C5FD", "hl_type": "#7DD3FC", "hl_str": "#A7E8A0",
        "hl_num": "#F2C97A", "hl_com": "#6B7280", "hl_dec": "#FFB86B",
        "hl_func": "#C4B5FD", "hl_self": "#FF9AA2", "hl_op": "#FCD34D",
    },
}

DEFAULT_PALETTE = "cyberpunk"

YES_COLOR = "#00E676"
NO_COLOR  = "#FF1744"


# ======================================================================
# Config
# ======================================================================

def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(data: dict) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


_cfg = load_config()
ui_language = _cfg.get("language", "en")
if ui_language not in STRINGS:
    ui_language = "en"
theme_key = _cfg.get("theme", DEFAULT_PALETTE)
if theme_key not in PALETTES:
    theme_key = DEFAULT_PALETTE


def set_language(lang: str):
    global ui_language
    ui_language = lang if lang in STRINGS else "en"
    cfg = load_config()
    cfg["language"] = ui_language
    save_config(cfg)


def set_theme(key: str):
    cfg = load_config()
    cfg["theme"] = key
    save_config(cfg)


def tr(key: str) -> str:
    return STRINGS.get(ui_language, STRINGS["en"]).get(key, key)


# ======================================================================
# Syntax highlighting
# ======================================================================

class CodeHighlighter(QSyntaxHighlighter):
    def __init__(self, document, language: str = "python", palette: dict = None):
        super().__init__(document)
        self._language = language
        self._palette = palette or PALETTES[DEFAULT_PALETTE]
        self._rules = []
        self._build_rules()

    def set_language(self, language: str):
        if language == self._language:
            return
        self._language = language
        self._build_rules()
        self.rehighlight()

    def set_palette(self, palette: dict):
        self._palette = palette
        self._build_rules()
        self.rehighlight()

    @staticmethod
    def _fmt(color_hex: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
        f = QTextCharFormat()
        f.setForeground(QBrush(QColor(color_hex)))
        if bold:
            f.setFontWeight(QFont.Bold)
        f.setFontItalic(italic)
        return f

    @staticmethod
    def _rx(pattern: str) -> QRegularExpression:
        r = QRegularExpression(pattern)
        r.setPatternOptions(QRegularExpression.MultilineOption)
        return r

    def _add(self, pattern: str, fmt: QTextCharFormat):
        self._rules.append((self._rx(pattern), fmt))

    def _build_rules(self):
        self._rules = []
        p = self._palette

        kw_fmt      = self._fmt(p["hl_kw"], bold=True)
        type_fmt    = self._fmt(p["hl_type"])
        string_fmt  = self._fmt(p["hl_str"])
        number_fmt  = self._fmt(p["hl_num"])
        comment_fmt = self._fmt(p["hl_com"], italic=True)
        decor_fmt   = self._fmt(p["hl_dec"])
        func_fmt    = self._fmt(p["hl_func"])
        self_fmt    = self._fmt(p["hl_self"], italic=True)
        op_fmt      = self._fmt(p["hl_op"], bold=True)

        if self._language == "python":
            keywords = [
                "False", "None", "True", "and", "as", "assert", "async",
                "await", "break", "class", "continue", "def", "del",
                "elif", "else", "except", "finally", "for", "from",
                "global", "if", "import", "in", "is", "lambda", "nonlocal",
                "not", "or", "pass", "raise", "return", "try", "while",
                "with", "yield", "match", "case",
            ]
            builtins = [
                "abs", "all", "any", "bin", "bool", "bytearray", "bytes",
                "callable", "chr", "classmethod", "compile", "complex",
                "dict", "dir", "divmod", "enumerate", "eval", "exec",
                "filter", "float", "format", "frozenset", "getattr",
                "globals", "hasattr", "hash", "help", "hex", "id", "input",
                "int", "isinstance", "issubclass", "iter", "len", "list",
                "locals", "map", "max", "memoryview", "min", "next",
                "object", "oct", "open", "ord", "pow", "print", "property",
                "range", "repr", "reversed", "round", "set", "setattr",
                "slice", "sorted", "staticmethod", "str", "sum", "super",
                "tuple", "type", "vars", "zip", "__import__", "__name__",
            ]
            self._add(r"\b(" + "|".join(keywords) + r")\b", kw_fmt)
            self._add(r"\b(" + "|".join(builtins) + r")\b", type_fmt)
            self._add(r"@\w+(?:\.\w+)*", decor_fmt)
            self._add(
                r"\b(?:0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|"
                r"\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+\-]?\d+)?j?)\b",
                number_fmt,
            )
            self._add(r"\b[rRbBuUfF]{0,3}\"\"\"[\s\S]*?\"\"\"", string_fmt)
            self._add(r"\b[rRbBuUfF]{0,3}'''[\s\S]*?'''", string_fmt)
            self._add(r"\b[rRbBuUfF]{0,3}\"[^\"\n]*\"", string_fmt)
            self._add(r"\b[rRbBuUfF]{0,3}'[^'\n]*'", string_fmt)
            self._add(r"\b(?:def|class)\s+(\w+)", func_fmt)
            self._add(r"\bself\b", self_fmt)
            self._add(r"#[^\n]*", comment_fmt)
        else:
            keywords = [
                "alignas", "alignof", "and", "and_eq", "asm", "auto",
                "bitand", "bitor", "break", "case", "catch", "class",
                "compl", "concept", "const", "consteval", "constexpr",
                "constinit", "const_cast", "continue", "co_await",
                "co_return", "co_yield", "decltype", "default", "delete",
                "do", "dynamic_cast", "else", "enum", "explicit", "export",
                "extern", "false", "for", "friend", "goto", "if",
                "inline", "mutable", "namespace", "new", "noexcept",
                "not", "not_eq", "nullptr", "operator", "or", "or_eq",
                "private", "protected", "public", "register",
                "reinterpret_cast", "requires", "return", "sizeof",
                "static", "static_assert", "static_cast", "struct",
                "switch", "template", "this", "thread_local", "throw",
                "true", "try", "typedef", "typeid", "typename", "union",
                "using", "virtual", "volatile", "while", "xor", "xor_eq",
            ]
            types = [
                "bool", "char", "char8_t", "char16_t", "char32_t",
                "double", "float", "int", "long", "short", "signed",
                "unsigned", "void", "wchar_t", "size_t",
                "int8_t", "int16_t", "int32_t", "int64_t",
                "uint8_t", "uint16_t", "uint32_t", "uint64_t",
                "string", "wstring", "vector", "map", "set", "unordered_map",
                "unordered_set", "pair", "tuple", "array", "list", "deque",
                "stack", "queue", "optional", "variant",
                "shared_ptr", "unique_ptr", "weak_ptr",
                "cout", "cin", "cerr", "clog", "endl", "std",
            ]
            self._add(r"\b(" + "|".join(keywords) + r")\b", kw_fmt)
            self._add(r"\b(" + "|".join(types) + r")\b", type_fmt)
            self._add(r"^\s*#\s*\w+", decor_fmt)
            self._add(
                r"\b(?:0[xX][0-9a-fA-F]+|0[bB][01]+|"
                r"\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?[fFuUlL]*)\b",
                number_fmt,
            )
            self._add(r"\"(?:\\.|[^\"\\])*\"", string_fmt)
            self._add(r"'(?:\\.|[^'\\])*'", string_fmt)
            self._add(r"\b[A-Za-z_]\w*(?=\s*\()", func_fmt)
            self._add(r"//[^\n]*", comment_fmt)
            self._add(r"/\*[\s\S]*?\*/", comment_fmt)

        # operators (both languages)
        op_pattern = (
            r"(\+|-|\*|/|%|==|!=|<=|>=|<|>|=|\+=|-=|\*=|/=|"
            r"&&|\|\||!|&|\||\^|~|<<|>>|->|::|\?|:|\*\*)"
        )
        self._add(op_pattern, op_fmt)

    def highlightBlock(self, text: str):
        for rx, fmt in self._rules:
            it = rx.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


# ======================================================================
# Frameless dialog base
# ======================================================================

class FramelessDialog(QDialog):
    def __init__(self, parent=None, title_text: str = ""):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(True)

        self._drag_pos = None
        self._title_text = title_text

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = QWidget(objectName="DialogHeader")
        self.header.setFixedHeight(46)
        hb = QHBoxLayout(self.header)
        hb.setContentsMargins(18, 0, 10, 0)
        hb.setSpacing(8)

        self.header_label = QLabel(title_text, objectName="DialogTitle")
        hb.addWidget(self.header_label)
        hb.addStretch(1)

        self.btn_close = QPushButton("×", objectName="DialogClose")
        self.btn_close.setFixedSize(38, 30)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setFocusPolicy(Qt.NoFocus)
        self.btn_close.clicked.connect(self.reject)
        hb.addWidget(self.btn_close, 0, Qt.AlignVCenter)

        outer.addWidget(self.header, 0)

        self.body = QWidget(objectName="DialogBody")
        outer.addWidget(self.body, 1)

        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(18, 12, 18, 16)
        self.body_layout.setSpacing(10)

        self._apply_style()

    def _apply_style(self):
        c = PALETTES[theme_key]
        self.setStyleSheet(f"""
        QDialog {{ background: transparent; }}
        QWidget#DialogHeader {{
            background-color: {c['bg_main']};
            border-top-left-radius: {DIALOG_RADIUS}px;
            border-top-right-radius: {DIALOG_RADIUS}px;
            border: 1px solid {c['border_soft']};
            border-bottom: none;
        }}
        QWidget#DialogBody {{
            background-color: {c['bg_main']};
            border-bottom-left-radius: {DIALOG_RADIUS}px;
            border-bottom-right-radius: {DIALOG_RADIUS}px;
            border: 1px solid {c['border_soft']};
            border-top: none;
        }}
        QLabel#DialogTitle {{
            color: {c['text_primary']};
            font-size: 13px;
            font-weight: 600;
        }}
        QPushButton#DialogClose {{
            background: transparent;
            border: none;
            color: {c['danger']};
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            padding: 0px;
        }}
        QPushButton#DialogClose:hover {{
            background-color: rgba(239,68,68,0.28);
            color: #FFE4E6;
        }}
        QPushButton#DialogClose:pressed {{
            background-color: {c['danger']};
            color: #FFFFFF;
        }}
        QLabel {{ color: {c['text_primary']}; }}
        QPushButton {{
            background-color: rgba(255,255,255,0.04);
            border: 1px solid {c['border_soft']};
            border-radius: 10px;
            padding: 7px 16px;
            color: {c['text_primary']};
            font-weight: 600;
            font-size: 12px;
            min-height: 22px;
        }}
        QPushButton:hover {{
            background-color: {c['accent_soft']};
            border: 1px solid {c['accent']};
        }}
        QPushButton:pressed {{
            background-color: {c['accent']};
            color: #0B0F1E;
        }}
        QLineEdit {{
            background-color: rgba(0,0,0,0.32);
            border: 1px solid {c['border_soft']};
            border-radius: 10px;
            padding: 7px 12px;
            color: {c['text_primary']};
        }}
        QLineEdit:focus {{ border: 1px solid {c['accent']}; }}
        QComboBox {{
            background-color: rgba(0,0,0,0.32);
            border: 1px solid {c['border_soft']};
            border-radius: 10px;
            padding: 5px 10px;
            color: {c['text_primary']};
            min-height: 24px;
        }}
        QComboBox:hover, QComboBox:focus {{ border: 1px solid {c['accent']}; }}
        QComboBox::drop-down {{ border: none; width: 20px; }}
        QComboBox QAbstractItemView {{
            background-color: {c['bg_main']};
            color: {c['text_primary']};
            border: 1px solid {c['border_soft']};
            selection-background-color: {c['accent_soft']};
            outline: none;
        }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.header.underMouse():
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)


# ======================================================================
# Message / question helpers
# ======================================================================

def show_message(parent, title: str, text: str):
    dlg = FramelessDialog(parent, title)
    dlg.setMinimumWidth(360)
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    dlg.body_layout.addWidget(lbl)

    btn_row = QHBoxLayout()
    btn_row.addStretch(1)
    ok = QPushButton(tr("ok"))
    ok.clicked.connect(dlg.accept)
    btn_row.addWidget(ok)
    dlg.body_layout.addLayout(btn_row)
    dlg.exec()


def show_question(parent, title: str, text: str) -> bool:
    dlg = FramelessDialog(parent, title)
    dlg.setMinimumWidth(380)
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    dlg.body_layout.addWidget(lbl)

    btn_row = QHBoxLayout()
    btn_row.addStretch(1)
    yes = QPushButton(tr("yes"))
    no = QPushButton(tr("no"))
    yes.clicked.connect(dlg.accept)
    no.clicked.connect(dlg.reject)
    btn_row.addWidget(yes)
    btn_row.addWidget(no)
    dlg.body_layout.addLayout(btn_row)
    return dlg.exec() == QDialog.Accepted


# ======================================================================
# Scene
# ======================================================================

class FlowScene(QGraphicsScene):
    def __init__(self, palette: dict):
        super().__init__()
        self.palette = palette
        self.setBackgroundBrush(QBrush(QColor(palette["scene_bg"])))

    def set_palette(self, palette: dict):
        self.palette = palette
        self.setBackgroundBrush(QBrush(QColor(palette["scene_bg"])))

    def render_canvas(self, canvas):
        self.clear()
        p = self.palette
        for c in canvas.conns:
            self._add_conn(c, p)
        for s in canvas.shapes:
            self._add_shape(s, p)
        for lb in canvas.labels:
            self._add_label(lb, p)

        r = self.itemsBoundingRect()
        if r.isValid() and not r.isEmpty():
            self.setSceneRect(r.adjusted(-60, -60, 60, 60))

    def _font(self, size: int, italic: bool = False, bold: bool = False) -> QFont:
        f = QFont("Segoe UI", size)
        f.setItalic(italic)
        f.setBold(bold)
        return f

    def _shape_colors(self, kind: str):
        p = self.palette
        key = {
            "start": "shape_start",
            "end": "shape_end",
            "process": "shape_process",
            "io": "shape_io",
            "condition": "shape_cond",
            "loop": "shape_loop",
        }.get(kind, "shape_process")
        return p[key]

    def _add_shape(self, s, p: dict):
        fill, stroke, text_color = self._shape_colors(s.kind)
        pen = QPen(QColor(stroke))
        pen.setWidthF(1.8)
        brush = QBrush(QColor(fill))

        if s.kind in ("start", "end"):
            item = self.addEllipse(
                QRectF(s.cx - s.w / 2, s.top, s.w, s.h), pen, brush)
        elif s.kind == "process":
            item = self.addRect(
                QRectF(s.cx - s.w / 2, s.top, s.w, s.h), pen, brush)
        elif s.kind == "io":
            skew = min(20.0, s.w * 0.18)
            poly = QPolygonF([
                QPointF(s.cx - s.w / 2 + skew, s.top),
                QPointF(s.cx + s.w / 2,        s.top),
                QPointF(s.cx + s.w / 2 - skew, s.top + s.h),
                QPointF(s.cx - s.w / 2,        s.top + s.h),
            ])
            item = self.addPolygon(poly, pen, brush)
        elif s.kind in ("condition", "loop"):
            poly = QPolygonF([
                QPointF(s.cx,           s.top),
                QPointF(s.cx + s.w / 2, s.top + s.h / 2),
                QPointF(s.cx,           s.top + s.h),
                QPointF(s.cx - s.w / 2, s.top + s.h / 2),
            ])
            item = self.addPolygon(poly, pen, brush)
        else:
            item = self.addRect(
                QRectF(s.cx - s.w / 2, s.top, s.w, s.h), pen, brush)

        item.setZValue(1)

        txt = self.addSimpleText(s.text, self._font(9))
        txt.setBrush(QBrush(QColor(text_color)))
        br = txt.boundingRect()
        if br.width() > s.w - 12 and s.w > 20:
            scale = max(0.55, (s.w - 12) / max(1.0, br.width()))
            txt.setScale(scale)
            br = txt.boundingRect()
            br = QRectF(br.x() * scale, br.y() * scale,
                        br.width() * scale, br.height() * scale)
        txt.setPos(s.cx - br.width() / 2,
                   s.top + s.h / 2 - br.height() / 2)
        txt.setZValue(2)

    def _add_conn(self, c, p: dict):
        arrow_color = QColor(p["arrow"])
        pen = QPen(arrow_color)
        pen.setWidthF(1.7)
        pen.setCapStyle(Qt.RoundCap)
        x1, y1 = c.start
        x2, y2 = c.end

        if c.arrow:
            dx, dy = x2 - x1, y2 - y1
            L = math.hypot(dx, dy)
            if L > 1.0:
                alen = 10.0
                ux, uy = dx / L, dy / L
                ex, ey = x2 - ux * alen, y2 - uy * alen
                line = self.addLine(x1, y1, ex, ey, pen)
                line.setZValue(0)

                px, py = -uy, ux
                bw = 5.0
                p1 = (ex + px * bw, ey + py * bw)
                p2 = (ex - px * bw, ey - py * bw)
                head = QPolygonF([QPointF(x2, y2),
                                  QPointF(p1[0], p1[1]),
                                  QPointF(p2[0], p2[1])])
                hitem = self.addPolygon(head, pen, QBrush(arrow_color))
                hitem.setZValue(0)
                return
        line = self.addLine(x1, y1, x2, y2, pen)
        line.setZValue(0)

    def _add_label(self, lb, p: dict):
        color = YES_COLOR if lb.align == "left" else NO_COLOR
        txt = self.addSimpleText(lb.text, self._font(10, bold=True))
        txt.setBrush(QBrush(QColor(color)))
        br = txt.boundingRect()
        if lb.align == "right":
            txt.setPos(lb.x - br.width(), lb.y)
        else:
            txt.setPos(lb.x, lb.y)
        txt.setZValue(3)


# ======================================================================
# View
# ======================================================================

class FlowView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene):
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.TextAntialiasing, True)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFrameShape(QGraphicsView.NoFrame)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.15 if delta > 0 else 1.0 / 1.15
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.fit()
            event.accept()
            return
        super().mousePressEvent(event)

    def fit(self):
        r = self.scene().itemsBoundingRect()
        if r.isEmpty():
            return
        self.resetTransform()
        vr = self.viewport().rect()
        if r.width() <= 0 or r.height() <= 0:
            return
        sx = vr.width() / (r.width() + 80)
        sy = vr.height() / (r.height() + 80)
        s = min(sx, sy)
        if s > 1.4:
            s = 1.4
        if s <= 0.05:
            s = 0.05
        self.scale(s, s)
        self.centerOn(r.center())


# ======================================================================
# Splitter
# ======================================================================

class _DividerHandle(QWidget):
    def __init__(self, parent: "SlimSplitter"):
        super().__init__(parent)
        self._parent = parent
        self._hover = False
        self._dragging = False
        self.setAttribute(Qt.WA_Hover, True)
        self.setMouseTracking(True)

    def set_dragging(self, value: bool):
        self._dragging = value
        self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        pal = getattr(self._parent, "palette", None)
        accent = QColor(pal["accent"]) if pal else QColor("#E945C6")
        active = self._hover or self._dragging

        w = self.width()
        h = self.height()
        cx, cy = w / 2.0, h / 2.0

        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(accent if active else QColor(255, 255, 255, 90)))

        if self._parent._orientation == Qt.Horizontal:
            length = max(40.0, h * 0.32)
            radius = 4.0 if active else 3.0
            p.drawRoundedRect(
                QRectF(cx - radius, cy - length / 2.0, radius * 2.0, length),
                radius, radius,
            )
            if active:
                p.setBrush(QBrush(accent))
                for dy in (-length / 2.0 - 10.0, length / 2.0 + 10.0):
                    p.drawEllipse(QPointF(cx, cy + dy), 2.2, 2.2)
        else:
            length = max(40.0, w * 0.32)
            radius = 4.0 if active else 3.0
            p.drawRoundedRect(
                QRectF(cx - length / 2.0, cy - radius, length, radius * 2.0),
                radius, radius,
            )
            if active:
                p.setBrush(QBrush(accent))
                for dx in (-length / 2.0 - 10.0, length / 2.0 + 10.0):
                    p.drawEllipse(QPointF(cx + dx, cy), 2.2, 2.2)


class SlimSplitter(QWidget):
    def __init__(self, first: QWidget, second: QWidget,
                 orientation=Qt.Horizontal, ratio: float = 0.36,
                 parent=None):
        super().__init__(parent)
        self._orientation = orientation
        self._first = first
        self._second = second
        self._ratio = max(0.05, min(0.95, ratio))
        self._handle_width = 22
        self._dragging = False
        self._min_pane = 120

        if orientation == Qt.Horizontal:
            lay = QHBoxLayout(self)
        else:
            lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        lay.addWidget(self._first)
        self._handle = _DividerHandle(self)
        if orientation == Qt.Horizontal:
            self._handle.setFixedWidth(self._handle_width)
            self._handle.setCursor(Qt.SplitHCursor)
        else:
            self._handle.setFixedHeight(self._handle_width)
            self._handle.setCursor(Qt.SplitVCursor)
        self._handle.installEventFilter(self)
        lay.addWidget(self._handle)
        lay.addWidget(self._second)

        if orientation == Qt.Horizontal:
            self._first.setMinimumWidth(self._min_pane)
            self._second.setMinimumWidth(self._min_pane)
        else:
            self._first.setMinimumHeight(self._min_pane)
            self._second.setMinimumHeight(self._min_pane)

    def eventFilter(self, obj, event):
        if obj is self._handle:
            if event.type() == QEvent.MouseButtonPress and \
               event.button() == Qt.LeftButton:
                self._dragging = True
                self._handle.set_dragging(True)
                return True
            elif event.type() == QEvent.MouseMove and self._dragging:
                pos = self._handle.mapTo(self, event.position().toPoint())
                if self._orientation == Qt.Horizontal:
                    self._apply_pos(pos.x())
                else:
                    self._apply_pos(pos.y())
                return True
            elif event.type() == QEvent.MouseButtonRelease and \
                 event.button() == Qt.LeftButton:
                self._dragging = False
                self._handle.set_dragging(False)
                return True
        return super().eventFilter(obj, event)

    def _apply_pos(self, p: int):
        total = (self.width() if self._orientation == Qt.Horizontal
                 else self.height()) - self._handle_width
        if total <= 0:
            return
        p = max(self._min_pane, min(total - self._min_pane, p))
        self._ratio = p / total if total else 0.5
        self._relayout()

    def _relayout(self):
        if self._orientation == Qt.Horizontal:
            total = self.width() - self._handle_width
            if total <= 0:
                return
            first_w = int(total * self._ratio)
            second_w = total - first_w
            self._first.setFixedWidth(first_w)
            self._second.setFixedWidth(second_w)
        else:
            total = self.height() - self._handle_width
            if total <= 0:
                return
            first_h = int(total * self._ratio)
            second_h = total - first_h
            self._first.setFixedHeight(first_h)
            self._second.setFixedHeight(second_h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def showEvent(self, event):
        super().showEvent(event)
        self._relayout()


# ======================================================================
# Block preview + Help dialog
# ======================================================================

class _BlockPreview(QWidget):
    def __init__(self, kind: str, palette: dict, parent=None):
        super().__init__(parent)
        self._kind = kind
        self._palette = palette
        self.setFixedSize(120, 64)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        pal = self._palette
        kind = self._kind
        key = {
            "start": "shape_start",
            "end": "shape_end",
            "process": "shape_process",
            "io": "shape_io",
            "condition": "shape_cond",
            "loop": "shape_loop",
        }.get(kind, "shape_process")

        fill, stroke, _text = pal[key]
        w = self.width() - 16
        h = self.height() - 16
        x = 8.0
        y = 8.0

        pen = QPen(QColor(stroke))
        pen.setWidthF(1.8)
        brush = QBrush(QColor(fill))
        p.setPen(pen)
        p.setBrush(brush)

        if kind in ("start", "end"):
            p.drawEllipse(QRectF(x, y, w, h))
        elif kind == "process":
            p.drawRect(QRectF(x, y, w, h))
        elif kind == "io":
            skew = min(18.0, w * 0.18)
            poly = QPolygonF([
                QPointF(x + skew,     y),
                QPointF(x + w,        y),
                QPointF(x + w - skew, y + h),
                QPointF(x,            y + h),
            ])
            p.drawPolygon(poly)
        elif kind in ("condition", "loop"):
            poly = QPolygonF([
                QPointF(x + w / 2, y),
                QPointF(x + w,     y + h / 2),
                QPointF(x + w / 2, y + h),
                QPointF(x,         y + h / 2),
            ])
            p.drawPolygon(poly)


def _wrap_label(text: str, obj_name: str = "") -> QLabel:
    lbl = QLabel(text)
    if obj_name:
        lbl.setObjectName(obj_name)
    lbl.setWordWrap(True)
    return lbl


class HelpDialog(FramelessDialog):
    def __init__(self, parent, palette: dict):
        super().__init__(parent, tr("help_title"))
        self.palette = palette
        self.setMinimumWidth(640)

        self.body_layout.addWidget(_wrap_label(tr("help_subtitle"), "HelpSubtitle"))

        rows = [
            ("start",     tr("help_b_start"),     tr("help_b_start_d")),
            ("process",   tr("help_b_process"),   tr("help_b_process_d")),
            ("io",        tr("help_b_io"),        tr("help_b_io_d")),
            ("condition", tr("help_b_cond"),      tr("help_b_cond_d")),
            ("loop",      tr("help_b_loop"),      tr("help_b_loop_d")),
        ]
        for kind, name, desc in rows:
            row = QHBoxLayout()
            row.setSpacing(14)
            row.addWidget(_BlockPreview(kind, palette), 0, Qt.AlignVCenter)

            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            text_col.addWidget(_wrap_label(name, "HelpBlockName"))
            text_col.addWidget(_wrap_label(desc, "HelpBlockDesc"))
            text_col.addStretch(1)
            row.addLayout(text_col, 1)
            self.body_layout.addLayout(row)

        self.body_layout.addWidget(_wrap_label(tr("help_note"), "HelpNote"))

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton(tr("close"))
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        self.body_layout.addLayout(btn_row)

        self._apply_help_style()

    def _apply_help_style(self):
        c = self.palette
        self.setStyleSheet(self.styleSheet() + f"""
        QLabel#HelpSubtitle {{ color: {c['text_secondary']}; font-size: 11px; }}
        QLabel#HelpBlockName {{ color: {c['text_primary']}; font-size: 12px; font-weight: 600; }}
        QLabel#HelpBlockDesc {{ color: {c['text_secondary']}; font-size: 11px; }}
        QLabel#HelpNote {{
            color: {c['text_secondary']};
            font-size: 11px;
            padding-top: 8px;
            border-top: 1px solid {c['border_soft']};
        }}
        """)


# ======================================================================
# Settings dialog
# ======================================================================

class SettingsDialog(FramelessDialog):
    def __init__(self, parent, palette: dict, current_theme: str, current_lang: str):
        super().__init__(parent, tr("settings_title"))
        self.palette = palette
        self.setMinimumWidth(420)

        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel(tr("settings_lang")), 0)
        self.lang_combo = QComboBox()
        self.lang_combo.addItem(tr("theme_label_en"), "en")
        self.lang_combo.addItem(tr("theme_label_ru"), "ru")
        for i in range(self.lang_combo.count()):
            if self.lang_combo.itemData(i) == current_lang:
                self.lang_combo.setCurrentIndex(i)
                break
        lang_row.addWidget(self.lang_combo, 1)
        self.body_layout.addLayout(lang_row)

        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel(tr("settings_theme")), 0)
        self.theme_combo = QComboBox()
        for key, p in PALETTES.items():
            label = p["label_ru"] if current_lang == "ru" else p["label_en"]
            self.theme_combo.addItem(label, key)
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == current_theme:
                self.theme_combo.setCurrentIndex(i)
                break
        theme_row.addWidget(self.theme_combo, 1)
        self.body_layout.addLayout(theme_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel = QPushButton(tr("cancel"))
        ok = QPushButton(tr("ok"))
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        self.body_layout.addLayout(btn_row)

    def chosen_lang(self) -> str:
        return self.lang_combo.currentData()

    def chosen_theme(self) -> str:
        return self.theme_combo.currentData()


# ======================================================================
# Name dialog
# ======================================================================

class NameDialog(FramelessDialog):
    def __init__(self, parent, title: str, initial: str = ""):
        super().__init__(parent, title)
        self.setMinimumWidth(380)

        self.edit = QLineEdit(initial)
        self.edit.setPlaceholderText(tr("schema_name") + "...")
        self.body_layout.addWidget(self.edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel = QPushButton(tr("cancel"))
        ok = QPushButton(tr("ok"))
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        self.body_layout.addLayout(btn_row)

        self.edit.setFocus()
        self.edit.selectAll()

    def value(self) -> str:
        return self.edit.text().strip()


# ======================================================================
# Main window
# ======================================================================

class MainWindow(QMainWindow):
    RESIZE_MARGIN = 6
    RESIZE_CORNER = 14

    def __init__(self):
        super().__init__()
        self.palette_key = theme_key
        self.palette = PALETTES[self.palette_key]

        self.setWindowTitle(tr("app_title"))
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.resize(1400, 820)
        self.setMinimumSize(760, 500)

        self._drag_pos = None
        self._is_maximized = False
        self._current_schema_path = None

        self._resize_edge = None
        self._resize_start_geom = None
        self._resize_start_pos = None

        self.scene = FlowScene(self.palette)
        self.view = FlowView(self.scene)

        self._build_ui()
        self._apply_theme()
        self.convert()
        self.update_translations()

        QTimer.singleShot(0, self.view.fit)

    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget(objectName="Root")
        central.setMouseTracking(True)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ---------- title bar ----------
        self.title_bar = QWidget(objectName="TitleBar")
        self.title_bar.setFixedHeight(46)
        tb = QHBoxLayout(self.title_bar)
        tb.setContentsMargins(18, 0, 12, 0)
        tb.setSpacing(0)

        self.title_label = QLabel(tr("app_title"), objectName="TitleLabel")
        tb.addWidget(self.title_label)
        tb.addStretch(1)

        BTN_W, BTN_H = 46, 32
        self.btn_min   = QPushButton("–", objectName="TitleButton")
        self.btn_max   = QPushButton("□", objectName="TitleButton")
        self.btn_close = QPushButton("×", objectName="TitleButtonClose")
        for b in (self.btn_min, self.btn_max, self.btn_close):
            b.setFixedSize(BTN_W, BTN_H)
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
        tb.addWidget(self.btn_min,   0, Qt.AlignVCenter)
        tb.addSpacing(8)
        tb.addWidget(self.btn_max,   0, Qt.AlignVCenter)
        tb.addSpacing(8)
        tb.addWidget(self.btn_close, 0, Qt.AlignVCenter)

        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_max.clicked.connect(self.toggle_max_restore)
        self.btn_close.clicked.connect(self.close)

        root.addWidget(self.title_bar, 0)

        # ---------- controls row ----------
        controls = QWidget(objectName="ControlsBar")
        cl = QHBoxLayout(controls)
        cl.setContentsMargins(10, 6, 10, 6)
        cl.setSpacing(8)

        self.lang_label = QLabel(tr("language"), objectName="FieldLabel")
        cl.addWidget(self.lang_label)
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Python", "C++"])
        cl.addWidget(self.lang_combo)

        self.theme_label = QLabel(tr("theme"), objectName="FieldLabel")
        cl.addWidget(self.theme_label)
        self.theme_combo = QComboBox()
        for key, p in PALETTES.items():
            self.theme_combo.addItem(self._palette_label(p), key)
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == self.palette_key:
                self.theme_combo.setCurrentIndex(i)
                break
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        cl.addWidget(self.theme_combo)

        cl.addStretch(1)

        self.btn_settings = QPushButton(tr("settings"))
        self.btn_settings.clicked.connect(self.open_settings)
        cl.addWidget(self.btn_settings)

        self.btn_help = QPushButton(tr("help"))
        self.btn_help.clicked.connect(self.open_help)
        cl.addWidget(self.btn_help)

        self.btn_convert = QPushButton(tr("convert"))
        self.btn_convert.setObjectName("PrimaryButton")
        self.btn_convert.clicked.connect(self.convert)
        cl.addWidget(self.btn_convert)

        root.addWidget(controls, 0)

        # ---------- panels ----------
        self.editor_panel = self._build_editor_panel()
        self.schemas_panel = self._build_schemas_panel()
        self.scene_panel = self._build_scene_panel()

        self.editor_schemas_split = SlimSplitter(
            self.editor_panel, self.schemas_panel,
            orientation=Qt.Vertical, ratio=0.62,
        )
        self.editor_schemas_split.palette = self.palette

        self.splitter = SlimSplitter(
            self.editor_schemas_split, self.scene_panel,
            orientation=Qt.Horizontal, ratio=0.36,
        )
        self.splitter.palette = self.palette

        root.addWidget(self.splitter, 1)

        self.setCentralWidget(central)
        self._refresh_schemas_list()

    @staticmethod
    def _palette_label(p: dict) -> str:
        return p["label_ru"] if ui_language == "ru" else p["label_en"]

    def _build_editor_panel(self) -> QWidget:
        panel = QWidget(objectName="Panel")
        v = QVBoxLayout(panel)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(6)

        self.editor_label = QLabel(tr("source_code"), objectName="FieldLabel")
        v.addWidget(self.editor_label)

        self.editor = QTextEdit()
        f = QFont("Consolas", 11)
        f.setStyleHint(QFont.Monospace)
        self.editor.setFont(f)
        self.editor.setObjectName("Editor")
        self.editor.setPlainText(DEFAULT_CODE)
        v.addWidget(self.editor, 1)

        self.highlighter = CodeHighlighter(self.editor.document(), "python", self.palette)
        return panel

    def _build_schemas_panel(self) -> QWidget:
        panel = QWidget(objectName="Panel")
        v = QVBoxLayout(panel)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(6)

        self.schemas_label = QLabel(tr("saved_schemas"), objectName="FieldLabel")
        v.addWidget(self.schemas_label)

        self.schemas_list = QListWidget()
        self.schemas_list.setObjectName("SchemasList")
        self.schemas_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.schemas_list.itemDoubleClicked.connect(self._on_schema_activated)
        self.schemas_list.setViewMode(QListView.IconMode)
        self.schemas_list.setFlow(QListView.LeftToRight)
        self.schemas_list.setWrapping(True)
        self.schemas_list.setResizeMode(QListView.Adjust)
        self.schemas_list.setMovement(QListView.Static)
        self.schemas_list.setSpacing(4)
        self.schemas_list.setWordWrap(True)
        v.addWidget(self.schemas_list, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.btn_save_schema = QPushButton(tr("save"))
        self.btn_save_schema.clicked.connect(self.save_schema)
        self.btn_save_as = QPushButton(tr("save_as"))
        self.btn_save_as.clicked.connect(self.save_schema_as)
        self.btn_load_code = QPushButton(tr("load"))
        self.btn_load_code.clicked.connect(self.load_code_from_file)
        self.btn_delete_schema = QPushButton(tr("delete"))
        self.btn_delete_schema.clicked.connect(self.delete_schema)
        btn_row.addWidget(self.btn_save_schema)
        btn_row.addWidget(self.btn_save_as)
        btn_row.addWidget(self.btn_load_code)
        btn_row.addWidget(self.btn_delete_schema)
        v.addLayout(btn_row)

        self.schemas_list.viewport().installEventFilter(self)
        QTimer.singleShot(0, self._update_schema_grid)
        return panel

    def _build_scene_panel(self) -> QWidget:
        panel = QWidget(objectName="Panel")
        v = QVBoxLayout(panel)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(0)
        v.addWidget(self.view)
        return panel

    # ------------------------------------------------------------------
    def update_translations(self):
        self.setWindowTitle(tr("app_title"))
        self.title_label.setText(tr("app_title"))
        self.lang_label.setText(tr("language"))
        self.theme_label.setText(tr("theme"))
        self.btn_settings.setText(tr("settings"))
        self.btn_help.setText(tr("help"))
        self.btn_convert.setText(tr("convert"))
        self.editor_label.setText(tr("source_code"))
        self.schemas_label.setText(tr("saved_schemas"))
        self.btn_save_schema.setText(tr("save"))
        self.btn_save_as.setText(tr("save_as"))
        self.btn_load_code.setText(tr("load"))
        self.btn_delete_schema.setText(tr("delete"))
        for i in range(self.theme_combo.count()):
            key = self.theme_combo.itemData(i)
            if key in PALETTES:
                self.theme_combo.setItemText(i, self._palette_label(PALETTES[key]))

    # ------------------------------------------------------------------
    def open_settings(self):
        dlg = SettingsDialog(self, self.palette, self.palette_key, ui_language)
        if dlg.exec() != QDialog.Accepted:
            return

        new_lang = dlg.chosen_lang()
        new_theme = dlg.chosen_theme()

        if new_lang and new_lang != ui_language:
            set_language(new_lang)

        if new_theme and new_theme in PALETTES:
            self.palette_key = new_theme
            self.palette = PALETTES[new_theme]
            set_theme(new_theme)
            self.scene.set_palette(self.palette)
            self.highlighter.set_palette(self.palette)
            for s in (getattr(self, "splitter", None),
                      getattr(self, "editor_schemas_split", None)):
                if s is not None:
                    s.palette = self.palette
                    s._handle.update()

        self._apply_theme()
        self.update()
        self.update_translations()
        self.convert()

    def open_help(self):
        dlg = HelpDialog(self, self.palette)
        dlg.exec()

    # ------------------------------------------------------------------
    def _update_schema_grid(self):
        try:
            vp = self.schemas_list.viewport().width()
        except Exception:
            vp = 300
        min_cell = 130
        cols = max(1, vp // min_cell)
        cell_w = max(min_cell, (vp - 12) // cols)
        gs = self.schemas_list.gridSize()
        gs.setWidth(cell_w)
        gs.setHeight(46)
        self.schemas_list.setGridSize(gs)

    def eventFilter(self, obj, event):
        if hasattr(self, "schemas_list") and obj is self.schemas_list.viewport():
            if event.type() == QEvent.Resize:
                self._update_schema_grid()
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(self.palette["bg_main"])))
        p.drawRoundedRect(self.rect(), WINDOW_RADIUS, WINDOW_RADIUS)

    def _edge_at(self, pos: QPoint):
        if self._is_maximized:
            return None
        r = self.rect()
        m = self.RESIZE_MARGIN
        c = self.RESIZE_CORNER
        x, y = pos.x(), pos.y()
        left = x <= m
        right = x >= r.width() - m
        top = y <= m
        bottom = y >= r.height() - m
        tl = x <= c and y <= c
        tr = x >= r.width() - c and y <= c
        bl = x <= c and y >= r.height() - c
        br = x >= r.width() - c and y >= r.height() - c
        if tl: return "tl"
        if tr: return "tr"
        if bl: return "bl"
        if br: return "br"
        if left:   return "l"
        if right:  return "r"
        if top:    return "t"
        if bottom: return "b"
        return None

    def _edge_cursor(self, edge):
        return {
            "l": Qt.SizeHorCursor,
            "r": Qt.SizeHorCursor,
            "t": Qt.SizeVerCursor,
            "b": Qt.SizeVerCursor,
            "tl": Qt.SizeFDiagCursor,
            "br": Qt.SizeFDiagCursor,
            "tr": Qt.SizeBDiagCursor,
            "bl": Qt.SizeBDiagCursor,
        }.get(edge, Qt.ArrowCursor)

    def mouseMoveEvent(self, event):
        if self._resize_edge is not None and self._resize_start_geom is not None:
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            g = self._resize_start_geom
            new = g.adjusted(0, 0, 0, 0)
            if "l" in self._resize_edge:
                new.setLeft(g.left() + delta.x())
            if "r" in self._resize_edge:
                new.setRight(g.right() + delta.x())
            if "t" in self._resize_edge:
                new.setTop(g.top() + delta.y())
            if "b" in self._resize_edge:
                new.setBottom(g.bottom() + delta.y())
            if new.width() < self.minimumWidth():
                if "l" in self._resize_edge:
                    new.setLeft(new.right() - self.minimumWidth())
                else:
                    new.setRight(new.left() + self.minimumWidth())
            if new.height() < self.minimumHeight():
                if "t" in self._resize_edge:
                    new.setTop(new.bottom() - self.minimumHeight())
                else:
                    new.setBottom(new.top() + self.minimumHeight())
            self.setGeometry(new)
            event.accept()
            return

        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return

        edge = self._edge_at(event.position().toPoint())
        self.setCursor(self._edge_cursor(edge))
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            edge = self._edge_at(event.position().toPoint())
            if edge is not None:
                self._resize_edge = edge
                self._resize_start_geom = self.geometry()
                self._resize_start_pos = event.globalPosition().toPoint()
                event.accept()
                return
            if self.title_bar.underMouse():
                self._drag_pos = (event.globalPosition().toPoint()
                                  - self.frameGeometry().topLeft())
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resize_edge = None
        self._resize_start_geom = None
        self._resize_start_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.title_bar.underMouse():
            self.toggle_max_restore()
        else:
            super().mouseDoubleClickEvent(event)

    def leaveEvent(self, event):
        self.setCursor(Qt.ArrowCursor)
        super().leaveEvent(event)

    def toggle_max_restore(self):
        if self._is_maximized:
            self.showNormal()
        else:
            self.showMaximized()
        self._is_maximized = not self._is_maximized
        self.update()

    # ------------------------------------------------------------------
    def _on_theme_changed(self, idx: int):
        key = self.theme_combo.itemData(idx)
        if not key or key not in PALETTES:
            return
        self.palette_key = key
        self.palette = PALETTES[key]
        set_theme(key)

        self.scene.set_palette(self.palette)
        if hasattr(self, "highlighter"):
            self.highlighter.set_palette(self.palette)
        for s in (getattr(self, "splitter", None),
                  getattr(self, "editor_schemas_split", None)):
            if s is not None:
                s.palette = self.palette
                s._handle.update()
        self._apply_theme()
        self.update()
        self.convert()

    def _scrollbar_qss(self, c: dict) -> str:
        return f"""
        QScrollBar:vertical {{
            background: transparent;
            width: 16px;
            margin: 6px 4px 6px 4px;
            border: none;
        }}
        QScrollBar::handle:vertical {{
            background: {c['accent_soft']};
            border: 1px solid {c['accent']};
            border-radius: 6px;
            min-height: 40px;
            margin: 0px 2px 0px 2px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {c['accent']}; }}
        QScrollBar::handle:vertical:pressed {{ background: {c['accent_neon']}; }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical,
        QScrollBar::up-arrow:vertical,
        QScrollBar::down-arrow:vertical {{
            background: transparent; border: none; height: 0px; width: 0px;
        }}
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            background: transparent; border: none;
        }}

        QScrollBar:horizontal {{
            background: transparent;
            height: 16px;
            margin: 4px 6px 4px 6px;
            border: none;
        }}
        QScrollBar::handle:horizontal {{
            background: {c['accent_soft']};
            border: 1px solid {c['accent']};
            border-radius: 6px;
            min-width: 40px;
            margin: 2px 0px 2px 0px;
        }}
        QScrollBar::handle:horizontal:hover {{ background: {c['accent']}; }}
        QScrollBar::handle:horizontal:pressed {{ background: {c['accent_neon']}; }}
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal,
        QScrollBar::left-arrow:horizontal,
        QScrollBar::right-arrow:horizontal {{
            background: transparent; border: none; height: 0px; width: 0px;
        }}
        QScrollBar::add-page:horizontal,
        QScrollBar::sub-page:horizontal {{
            background: transparent; border: none;
        }}

        QScrollBar::corner {{ background: transparent; }}
        """

    def _stylesheet(self) -> str:
        c = self.palette
        r, g, b = c["bg_panel_rgb"]
        panel_bg = f"rgba({r},{g},{b},0.96)"

        return f"""
        QMainWindow, QWidget#Root {{ background-color: transparent; }}

        QWidget#TitleBar {{
            background-color: {panel_bg};
            border-radius: 14px;
            border: 1px solid {c['border_soft']};
        }}
        QLabel#TitleLabel {{
            color: {c['text_primary']};
            font-size: 13px;
            font-weight: 600;
        }}

        QPushButton#TitleButton, QPushButton#TitleButtonClose {{
            background: transparent;
            border: none;
            color: {c['text_secondary']};
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            padding: 0px;
            margin: 0px;
            min-width: 0px;
            min-height: 0px;
            max-width: 46px;
            max-height: 32px;
        }}
        QPushButton#TitleButton:hover {{
            background-color: {c['accent_soft']};
            color: {c['text_primary']};
        }}
        QPushButton#TitleButton:pressed {{
            background-color: {c['accent']};
            color: #0B0F1E;
        }}
        QPushButton#TitleButtonClose {{ color: {c['danger']}; }}
        QPushButton#TitleButtonClose:hover {{
            background-color: rgba(239,68,68,0.28);
            color: #FFE4E6;
        }}
        QPushButton#TitleButtonClose:pressed {{
            background-color: {c['danger']};
            color: #FFFFFF;
        }}

        QWidget#ControlsBar {{
            background-color: {panel_bg};
            border-radius: 12px;
            border: 1px solid {c['border_soft']};
        }}

        QWidget#Panel {{
            background-color: {panel_bg};
            border-radius: 16px;
            border: 1px solid {c['border_soft']};
        }}

        QLabel#FieldLabel {{
            color: {c['text_secondary']};
            font-size: 11px;
            letter-spacing: 0.4px;
            text-transform: uppercase;
        }}

        QTextEdit#Editor {{
            background-color: rgba(0,0,0,0.32);
            border: 1px solid {c['border_soft']};
            border-radius: 12px;
            padding: 10px;
            color: {c['text_primary']};
            selection-background-color: {c['accent_soft']};
            selection-color: {c['text_primary']};
        }}
        QTextEdit#Editor:focus {{ border: 1px solid {c['accent']}; }}

        QListWidget#SchemasList {{
            background-color: rgba(0,0,0,0.25);
            border: 1px solid {c['border_soft']};
            border-radius: 12px;
            padding: 6px;
            color: {c['text_primary']};
            outline: none;
        }}
        QListWidget#SchemasList::item {{
            padding: 10px 12px;
            border-radius: 10px;
            margin: 3px;
            background-color: rgba(255,255,255,0.035);
            border: 1px solid rgba(255,255,255,0.05);
            color: {c['text_primary']};
        }}
        QListWidget#SchemasList::item:selected {{
            background-color: {c['accent_soft']};
            border: 1px solid {c['accent']};
            color: {c['text_primary']};
        }}
        QListWidget#SchemasList::item:hover:!selected {{
            background-color: rgba(255,255,255,0.075);
            border: 1px solid {c['accent']};
        }}

        QComboBox {{
            background-color: rgba(0,0,0,0.28);
            border: 1px solid {c['border_soft']};
            border-radius: 10px;
            padding: 5px 10px;
            color: {c['text_primary']};
            min-height: 22px;
        }}
        QComboBox:focus, QComboBox:hover {{ border-color: {c['accent']}; }}
        QComboBox::drop-down {{ border: none; width: 20px; }}
        QComboBox QAbstractItemView {{
            background-color: {c['bg_main']};
            color: {c['text_primary']};
            border: 1px solid {c['border_soft']};
            selection-background-color: {c['accent_soft']};
            outline: none;
        }}

        QLineEdit {{
            background-color: rgba(0,0,0,0.28);
            border: 1px solid {c['border_soft']};
            border-radius: 10px;
            padding: 5px 10px;
            color: {c['text_primary']};
            selection-background-color: {c['accent_soft']};
        }}
        QLineEdit:focus {{ border-color: {c['accent']}; }}

        QPushButton {{
            background-color: rgba(255,255,255,0.04);
            border: 1px solid {c['border_soft']};
            border-radius: 10px;
            padding: 6px 14px;
            color: {c['text_primary']};
            font-size: 12px;
            font-weight: 500;
            min-height: 22px;
        }}
        QPushButton:hover {{
            background-color: {c['accent_soft']};
            border: 1px solid {c['accent']};
        }}
        QPushButton:pressed {{
            background-color: {c['accent']};
            color: #0B0F1E;
        }}

        QPushButton#PrimaryButton {{
            background-color: {c['accent_soft']};
            border: 1px solid {c['accent']};
            color: {c['text_primary']};
            font-weight: 600;
            padding: 8px 16px;
            font-size: 12px;
            border-radius: 10px;
        }}
        QPushButton#PrimaryButton:hover {{
            background-color: {c['accent']};
            color: #0B0F1E;
        }}

        QGraphicsView {{
            background-color: {c['scene_bg']};
            border: none;
            border-radius: 12px;
        }}

        {self._scrollbar_qss(c)}
        """

    def _apply_theme(self):
        app = QApplication.instance()
        if app is None:
            return
        app.setStyleSheet(self._stylesheet())

    # ------------------------------------------------------------------
    def convert(self):
        src = self.editor.toPlainText()
        lang = self.lang_combo.currentText()
        try:
            canvas = logic.build(src, lang)
        except Exception:
            import traceback
            traceback.print_exc(file=sys.stderr)
            canvas = logic.Canvas()
        self.scene.render_canvas(canvas)
        self.view.fit()

    # ------------------------------------------------------------------
    # Schemas
    # ------------------------------------------------------------------
    def _refresh_schemas_list(self):
        self.schemas_list.clear()
        files = sorted(SCHEMAS_DIR.glob("*.json"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        for p in files:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                title = data.get("title") or p.stem
            except Exception:
                title = p.stem
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, str(p))
            item.setToolTip(title)
            self.schemas_list.addItem(item)
        self._update_schema_grid()

    def _ask_name(self, title: str, initial: str):
        dlg = NameDialog(self, title, initial)
        if dlg.exec() == QDialog.Accepted:
            name = dlg.value()
            return name or None
        return None

    def _sanitize_filename(self, name: str) -> str:
        safe = "".join(ch if ch.isalnum() or ch in "-_ ()" else "_" for ch in name)
        return safe.strip() or "schema"

    def save_schema(self):
        if self._current_schema_path is None:
            self.save_schema_as()
            return
        self._write_schema(self._current_schema_path)

    def save_schema_as(self):
        current_title = self._current_schema_path.stem if self._current_schema_path else ""
        name = self._ask_name(tr("save_schema_as"), current_title)
        if not name:
            return
        fname = self._sanitize_filename(name) + ".json"
        path = SCHEMAS_DIR / fname
        self._write_schema(path, title=name)

    def _write_schema(self, path: Path, title: str | None = None):
        if title is None:
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                title = existing.get("title") or path.stem
            except Exception:
                title = path.stem

        data = {
            "title": title,
            "language": self.lang_combo.currentText(),
            "code": self.editor.toPlainText(),
        }
        try:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                            encoding="utf-8")
        except Exception as e:
            show_message(self, tr("error"), f"{tr('failed_save')}: {e}")
            return
        self._current_schema_path = path
        self._refresh_schemas_list()
        for i in range(self.schemas_list.count()):
            it = self.schemas_list.item(i)
            if Path(it.data(Qt.UserRole)) == path:
                self.schemas_list.setCurrentItem(it)
                break

    def _on_schema_activated(self, item: QListWidgetItem):
        self.schemas_list.setCurrentItem(item)
        self.load_schema()

    def load_schema(self):
        item = self.schemas_list.currentItem()
        if not item:
            show_message(self, tr("load_title"), tr("select_schema_first"))
            return
        path = Path(item.data(Qt.UserRole))
        if not path.exists():
            show_message(self, tr("error"), tr("file_missing"))
            self._refresh_schemas_list()
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            show_message(self, tr("error"), f"{tr('failed_load')}: {e}")
            return

        code = data.get("code", "")
        lang = data.get("language", "Python")
        if lang not in ("Python", "C++"):
            lang = "Python"

        self.editor.setPlainText(code)
        idx = self.lang_combo.findText(lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        if hasattr(self, "highlighter"):
            self.highlighter.set_language("cpp" if lang == "C++" else "python")
        self._current_schema_path = path
        self.convert()

    def delete_schema(self):
        item = self.schemas_list.currentItem()
        if not item:
            return
        path = Path(item.data(Qt.UserRole))
        title = f"{tr('delete_schema')} — {path.stem}"
        if not show_question(self, title, tr("delete_schema_q").format(name=path.stem)):
            return
        try:
            path.unlink()
        except Exception as e:
            show_message(self, tr("error"), f"{tr('failed_delete')}: {e}")
            return
        if self._current_schema_path == path:
            self._current_schema_path = None
        self._refresh_schemas_list()

    # ------------------------------------------------------------------
    def load_code_from_file(self):
        path_str, _ = QFileDialog.getOpenFileName(
            self, tr("load_source_code"), str(Path.home()),
            "Source files (*.py *.cpp *.cc *.cxx *.c *.hpp *.hh *.h *.hxx *.ipp);;"
            "Python (*.py);;C++ (*.cpp *.cc *.cxx *.c *.hpp *.hh *.h *.hxx *.ipp);;"
            "All files (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            code = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                code = path.read_text(encoding="latin-1")
            except Exception as e:
                show_message(self, tr("error"), f"{tr('failed_read')}: {e}")
                return
        except Exception as e:
            show_message(self, tr("error"), f"{tr('failed_read')}: {e}")
            return

        ext = path.suffix.lower()
        py_exts = {".py", ".pyw"}
        cpp_exts = {".cpp", ".cc", ".cxx", ".c", ".hpp", ".hh", ".h",
                    ".hxx", ".ipp", ".inl"}
        if ext in py_exts:
            lang = "Python"
        elif ext in cpp_exts:
            lang = "C++"
        else:
            ask = tr("unknown_ext_q").format(name=path.name)
            lang = "Python" if show_question(self, tr("unknown_ext"), ask) else "C++"

        idx = self.lang_combo.findText(lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        if hasattr(self, "highlighter"):
            self.highlighter.set_language("cpp" if lang == "C++" else "python")

        self.editor.setPlainText(code)
        self._current_schema_path = None
        self.convert()


# ======================================================================
# Entry point
# ======================================================================

def run():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())