"""
Pure logic: code normalizers, rule-based parser, tree layout, code generator,
variable extraction for code-aware suggestions.

Block text conventions (what user sees inside flowchart shapes):
  process    :  language-neutral statement, e.g. "x = 0" / 'name = "Bob"'
  input      :  variable name(s), e.g. "x" / "x, y" / "name:string, age:int"
  output     :  expression(s) to print, e.g. "x" / '"Hello"' / "x, y"
  condition  :  expression, e.g. "x > 0"            (no if keyword)
  loop       :  expression, e.g. "i < 10"           (no while keyword)

The exact original line (if parsed from source) is stored in code_text /
code_lang and reused verbatim when generating for the same language.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


# ----------------------------------------------------------------------
# Data model
# ----------------------------------------------------------------------

@dataclass
class NLine:
    text: str
    indent: int
    skip: bool = False


class Node:
    __slots__ = ("kind", "text", "true_branch", "false_branch", "body", "id",
                 "code_text", "code_lang")
    _counter = 0

    def __init__(self, kind: str, text: str = ""):
        Node._counter += 1
        self.id = Node._counter
        self.kind = kind
        self.text = text
        self.true_branch: List["Node"] = []
        self.false_branch: List["Node"] = []
        self.body: List["Node"] = []
        self.code_text = ""
        self.code_lang = ""

    def clear_code(self):
        self.code_text = ""
        self.code_lang = ""

    def __repr__(self):
        return f"Node({self.id}, {self.kind!r}, {self.text!r})"


@dataclass
class Shape:
    kind: str
    text: str
    cx: float
    top: float
    w: float
    h: float
    node_id: int = 0


@dataclass
class Conn:
    start: Tuple[float, float]
    end: Tuple[float, float]
    arrow: bool = True


@dataclass
class Label:
    text: str
    x: float
    y: float
    color: str = "black"
    align: str = "left"


@dataclass
class Canvas:
    shapes: List[Shape] = field(default_factory=list)
    conns: List[Conn] = field(default_factory=list)
    labels: List[Label] = field(default_factory=list)
    min_x: float = 0.0
    min_y: float = 0.0
    max_x: float = 0.0
    max_y: float = 0.0


# ----------------------------------------------------------------------
# Tree helpers
# ----------------------------------------------------------------------

def iter_children(node: Node):
    yield from node.true_branch
    yield from node.false_branch
    yield from node.body


def find_node(tree: List[Node], target_id: int) -> Optional[Node]:
    for node in tree:
        if node.id == target_id:
            return node
        for child in iter_children(node):
            r = find_node([child], target_id)
            if r is not None:
                return r
    return None


def find_parent_list(tree: List[Node], target_id: int) -> Optional[List[Node]]:
    for node in tree:
        if node.id == target_id:
            return tree
        for lst in (node.true_branch, node.false_branch, node.body):
            r = find_parent_list(lst, target_id)
            if r is not None:
                return r
    return None


def remove_node(tree: List[Node], target_id: int) -> Optional[Node]:
    lst = find_parent_list(tree, target_id)
    if lst is None:
        return None
    for i, n in enumerate(lst):
        if n.id == target_id:
            return lst.pop(i)
    return None


def new_tree() -> List[Node]:
    return [Node("start", "Start"), Node("end", "End")]


# ----------------------------------------------------------------------
# Normalizers
# ----------------------------------------------------------------------

def normalize_python(source: str) -> List[NLine]:
    out: List[NLine] = []
    for raw in source.splitlines():
        idx = raw.find("#")
        if idx >= 0:
            raw = raw[:idx]
        line = raw.replace("\t", "    ")
        stripped = line.strip()
        if not stripped:
            continue
        n_spaces = len(line) - len(line.lstrip(" "))
        out.append(NLine(stripped, n_spaces // 4, False))
    return out


def normalize_cpp(source: str) -> List[NLine]:
    out: List[NLine] = []
    depth = 0
    for raw in source.splitlines():
        s = raw
        idx = s.find("//")
        if idx >= 0:
            s = s[:idx]
        s = s.strip()
        if not s:
            continue
        while s.startswith("}"):
            depth = max(0, depth - 1)
            s = s[1:].strip()
            if not s:
                break
        if not s:
            continue
        if s.endswith(";"):
            s = s[:-1].rstrip()
        opens = False
        if s.endswith("{"):
            opens = True
            s = s[:-1].rstrip()
        if not s:
            if opens:
                depth += 1
            continue
        out.append(NLine(s, depth, False))
        if opens:
            depth += 1
    return out


# ----------------------------------------------------------------------
# Parser
# ----------------------------------------------------------------------

def _is_input(t: str) -> bool:
    tl = t.lower().replace(" ", "")
    return any(p in tl for p in (
        "input(", "scanf(", "cin>>", "getline(", "gets(", "fgets(",
    ))


def _is_output(t: str) -> bool:
    tl = t.lower().replace(" ", "")
    return any(p in tl for p in ("print(", "printf(", "cout<<", "puts("))


def _is_cpp_func_sig(t: str) -> bool:
    if t.startswith(("if", "while", "for", "else", "switch",
                     "return", "using", "typedef", "do", "case",
                     "break", "continue")):
        return False
    if "(" not in t or ")" not in t:
        return False
    if not t.rstrip().endswith(")"):
        return False
    m = re.match(r"^[A-Za-z_][\w:<>,\s\*&]*\s+[A-Za-z_~][\w:]*\s*\([^()]*\)\s*$", t)
    return bool(m)


# --- IO extraction -------------------------------------------------------

def _py_input_from(text: str):
    m = re.match(r"^([\w\s,]+?)\s*=\s*map\s*\(\s*int\s*,\s*input\(\)\.split\(\)\s*\)\s*$", text)
    if m:
        return ", ".join(p.strip() for p in m.group(1).split(",") if p.strip())
    m = re.match(r"^([\w\s,]+?)\s*=\s*input\(\)\.split\(\)\s*$", text)
    if m:
        return ", ".join(p.strip() for p in m.group(1).split(",") if p.strip())
    m = re.match(r"^(\w+)\s*=\s*(?:int\s*\(\s*)?input\s*\(", text)
    if m:
        return m.group(1)
    return text


def _py_output_from(text: str):
    m = re.match(r"^print\s*\((.*)\)\s*$", text)
    if m:
        return m.group(1).strip()
    return text


def _cpp_input_from(text: str):
    m = re.match(r"^cin\s*>>\s*(.*?)\s*$", text)
    if m:
        parts = [p.strip() for p in m.group(1).split(">>") if p.strip()]
        return ", ".join(parts) if parts else text
    m = re.search(r"scanf\([^,]+,\s*(.+)\)", text)
    if m:
        names = re.findall(r"&?\s*(\w+)", m.group(1))
        return ", ".join(names) if names else text
    return text


def _cpp_output_from(text: str):
    m = re.match(r"^cout\s*<<\s*(.*?)\s*$", text)
    if m:
        inner = m.group(1)
        inner = re.sub(r"<<\s*endl\s*$", "", inner).strip()
        inner = re.sub(r'<<\s*"\\n"\s*$', "", inner).strip()
        parts = [p.strip() for p in inner.split("<<") if p.strip()]
        readable = [p for p in parts if p not in ('" "', '"\\t"')]
        return ", ".join(readable) if readable else inner
    m = re.match(r"^printf\s*\((.*)\)\s*$", text)
    if m:
        return m.group(1).strip()
    return text


_CPP_TYPES = (
    "int", "long", "short", "float", "double", "char", "bool",
    "string", "auto", "size_t", "unsigned", "signed",
    "int8_t", "int16_t", "int32_t", "int64_t",
    "uint8_t", "uint16_t", "uint32_t", "uint64_t",
)
_CPP_TYPE_PATTERN = "|".join(re.escape(t) for t in _CPP_TYPES)


def _cpp_process_display(text: str) -> str:
    """Strip C++ type prefix (e.g. 'int x = 0' -> 'x = 0')."""
    t = text.strip().rstrip(";").strip()
    m = re.match(
        r"^(?:const\s+|static\s+|unsigned\s+|signed\s+)*"
        r"(?:" + _CPP_TYPE_PATTERN + r")\s+(.+)$", t)
    if m:
        return m.group(1)
    return text


RULES = [
    {"name": "cpp_preproc",     "match": lambda t: t.startswith("#"),                               "kind": "skip"},
    {"name": "cpp_using",       "match": lambda t: t.startswith("using namespace"),                  "kind": "skip"},
    {"name": "cpp_return",      "match": lambda t: (t == "return" or t.startswith("return ")
                                                    or t.startswith("return(") or t.startswith("return;")),
                                                                                                     "kind": "skip"},
    {"name": "py_def_or_class", "match": lambda t: (t.startswith("def ") or t.startswith("class "))
                                                   and t.rstrip().endswith(":"),                     "kind": "skip"},
    {"name": "cpp_func_sig",    "match": _is_cpp_func_sig,                                           "kind": "skip"},
    {"name": "py_pass",         "match": lambda t: t == "pass",                                      "kind": "skip"},
    {"name": "py_break_cont",   "match": lambda t: t in ("break", "continue"),                       "kind": "skip"},
    {"name": "if",              "match": lambda t: t.startswith("if ") or t.startswith("if("),        "kind": "if"},
    {"name": "elif",            "match": lambda t: t.startswith("elif ") or t.startswith("else if "), "kind": "elif"},
    {"name": "else",            "match": lambda t: t == "else" or t == "else:"
                                                   or t.startswith("else "),                         "kind": "else"},
    {"name": "while",           "match": lambda t: t.startswith("while ") or t.startswith("while("), "kind": "while"},
    {"name": "for",             "match": lambda t: t.startswith("for ") or t.startswith("for("),     "kind": "for"},
    {"name": "input",           "match": _is_input,                                                   "kind": "input"},
    {"name": "output",          "match": _is_output,                                                  "kind": "output"},
]


def _balanced_parens(s: str) -> bool:
    d = 0
    for c in s:
        if c == "(":
            d += 1
        elif c == ")":
            d -= 1
            if d < 0:
                return False
    return d == 0


def _extract_condition(text: str) -> str:
    t = text.strip()
    while t.endswith((":", "{")):
        t = t[:-1].rstrip()
    low = t.lower()
    for kw in ("else if", "elif", "if", "while", "for"):
        if low.startswith(kw + " ") or low.startswith(kw + "(") or low == kw:
            t = t[len(kw):].strip()
            break
    if t.startswith("(") and t.endswith(")"):
        inner = t[1:-1]
        if _balanced_parens(inner):
            t = inner.strip()
    return t if t else text


def parse_sequence(lines: List[NLine], i: int, indent: int, is_cpp: bool):
    nodes: List[Node] = []
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.indent < indent:
            break
        if line.indent > indent:
            i += 1
            continue

        text = line.text
        matched = None
        for rule in RULES:
            try:
                ok = rule["match"](text)
            except Exception:
                ok = False
            if ok:
                matched = rule
                break

        if matched is None:
            display = _cpp_process_display(text) if is_cpp else text
            node = Node("process", display)
            node.code_text = text
            node.code_lang = "cpp" if is_cpp else "python"
            nodes.append(node)
            i += 1
            continue

        kind = matched["kind"]

        if kind == "skip":
            body, i2 = parse_sequence(lines, i + 1, indent + 1, is_cpp)
            nodes.extend(body)
            i = i2 if i2 != i + 1 else i + 1

        elif kind in ("if", "elif"):
            node, i = parse_if_chain(lines, i, indent, is_cpp)
            nodes.append(node)

        elif kind == "else":
            body, i = parse_sequence(lines, i + 1, indent + 1, is_cpp)
            nodes.extend(body)

        elif kind in ("while", "for"):
            cond = _extract_condition(text)
            node = Node("loop", cond)
            node.code_text = text
            node.code_lang = "cpp" if is_cpp else "python"
            body, i = parse_sequence(lines, i + 1, indent + 1, is_cpp)
            node.body = body
            nodes.append(node)

        elif kind == "input":
            display = _cpp_input_from(text) if is_cpp else _py_input_from(text)
            node = Node("input", display)
            node.code_text = text
            node.code_lang = "cpp" if is_cpp else "python"
            nodes.append(node)
            i += 1

        elif kind == "output":
            display = _cpp_output_from(text) if is_cpp else _py_output_from(text)
            node = Node("output", display)
            node.code_text = text
            node.code_lang = "cpp" if is_cpp else "python"
            nodes.append(node)
            i += 1

        else:
            display = _cpp_process_display(text) if is_cpp else text
            node = Node("process", display)
            node.code_text = text
            node.code_lang = "cpp" if is_cpp else "python"
            nodes.append(node)
            i += 1

    return nodes, i


def parse_if_chain(lines: List[NLine], i: int, indent: int, is_cpp: bool):
    text = lines[i].text
    cond = _extract_condition(text)
    node = Node("condition", cond)
    node.code_text = text
    node.code_lang = "cpp" if is_cpp else "python"

    body, i = parse_sequence(lines, i + 1, indent + 1, is_cpp)
    node.true_branch = body

    if i < len(lines) and lines[i].indent == indent:
        nxt = lines[i].text
        low = nxt.lower()
        if low.startswith("elif ") or low.startswith("else if "):
            sub, i = parse_if_chain(lines, i, indent, is_cpp)
            node.false_branch = [sub]
        elif nxt == "else" or nxt == "else:" or low.startswith("else "):
            else_body, i = parse_sequence(lines, i + 1, indent + 1, is_cpp)
            node.false_branch = else_body
    return node, i


# ----------------------------------------------------------------------
# Layout
# ----------------------------------------------------------------------

CHAR_W = 7.5
PAD = 24.0
HGAP = 60.0
VGAP = 35.0
_IO_KINDS = ("input", "output")


def node_size(node: Node) -> Tuple[float, float]:
    text = node.text
    tw = len(text) * CHAR_W + PAD
    if node.kind in ("start", "end"):
        w = max(100.0, tw + 30); h = 42.0
    elif node.kind == "process" or node.kind in _IO_KINDS:
        w = max(140.0, tw); h = 42.0
    elif node.kind in ("condition", "loop"):
        w = max(180.0, tw * 1.8); h = 80.0
    else:
        w, h = 140.0, 42.0
    return w, h


def _shape_kind_for(node: Node) -> str:
    return "io" if node.kind in _IO_KINDS else node.kind


def chain_extents(chain: List[Node]) -> Tuple[float, float]:
    left = 0.0
    right = 0.0
    for node in chain:
        if node.kind in ("start", "end", "process") or node.kind in _IO_KINDS:
            w, _ = node_size(node)
            left = max(left, w / 2)
            right = max(right, w / 2)
        elif node.kind == "condition":
            dw, _ = node_size(node)
            left = max(left, dw / 2)
            right = max(right, dw / 2)
            tl, tr = chain_extents(node.true_branch)
            fl, fr = chain_extents(node.false_branch)
            if node.true_branch:
                right = max(right, dw / 2 + HGAP + tl + tr)
            else:
                right = max(right, dw / 2 + HGAP)
            if node.false_branch:
                left = max(left, dw / 2 + HGAP + fl + fr)
            else:
                left = max(left, dw / 2 + HGAP)
        elif node.kind == "loop":
            dw, _ = node_size(node)
            left = max(left, dw / 2)
            right = max(right, dw / 2)
            if node.body:
                bl, br = chain_extents(node.body)
                left = max(left, bl)
                right = max(right, br)
                right = max(right, max(dw / 2, br) + HGAP)
    return left, right


def layout_chain(chain, x, y_top, shapes, conns, labels):
    if not chain:
        return None, None
    first_entry = None
    prev_exit = None
    y = y_top
    for node in chain:
        entry, exit_ = layout_node(node, x, y, shapes, conns, labels)
        if first_entry is None:
            first_entry = entry
        if prev_exit is not None:
            conns.append(Conn(prev_exit, entry, arrow=True))
        prev_exit = exit_
        y = exit_[1] + VGAP
    return first_entry, prev_exit


def layout_node(node: Node, x: float, y_top: float, shapes, conns, labels):
    if node.kind in ("start", "end", "process") or node.kind in _IO_KINDS:
        w, h = node_size(node)
        shapes.append(Shape(_shape_kind_for(node), node.text, x, y_top, w, h, node.id))
        return (x, y_top), (x, y_top + h)

    if node.kind == "condition":
        dw, dh = node_size(node)
        shapes.append(Shape("condition", node.text, x, y_top, dw, dh, node.id))
        tl, tr = chain_extents(node.true_branch)
        fl, fr = chain_extents(node.false_branch)
        true_x = x + dw / 2 + HGAP + tl
        false_x = x - dw / 2 - HGAP - fr
        branch_top = y_top + dh + VGAP

        t_entry = t_exit = f_entry = f_exit = None
        if node.true_branch:
            t_entry, t_exit = layout_chain(node.true_branch, true_x, branch_top,
                                           shapes, conns, labels)
        if node.false_branch:
            f_entry, f_exit = layout_chain(node.false_branch, false_x, branch_top,
                                           shapes, conns, labels)

        candidates = [branch_top]
        if t_exit: candidates.append(t_exit[1])
        if f_exit: candidates.append(f_exit[1])
        join_y = max(candidates) + VGAP

        yes_start = (x + dw / 2, y_top + dh / 2)
        conns.append(Conn(yes_start, (true_x, yes_start[1]), arrow=False))
        if t_entry:
            conns.append(Conn((true_x, yes_start[1]), t_entry, arrow=True))
            conns.append(Conn(t_exit, (true_x, join_y), arrow=False))
        else:
            conns.append(Conn((true_x, yes_start[1]), (true_x, join_y), arrow=False))
        conns.append(Conn((true_x, join_y), (x, join_y), arrow=False))

        no_start = (x - dw / 2, y_top + dh / 2)
        conns.append(Conn(no_start, (false_x, no_start[1]), arrow=False))
        if f_entry:
            conns.append(Conn((false_x, no_start[1]), f_entry, arrow=True))
            conns.append(Conn(f_exit, (false_x, join_y), arrow=False))
        else:
            conns.append(Conn((false_x, no_start[1]), (false_x, join_y), arrow=False))
        conns.append(Conn((false_x, join_y), (x, join_y), arrow=False))

        labels.append(Label("Yes", x + dw / 2 + 10, y_top + dh / 2 - 22, "yes", "left"))
        labels.append(Label("No",  x - dw / 2 - 10, y_top + dh / 2 - 22, "no",  "right"))
        return (x, y_top), (x, join_y)

    if node.kind == "loop":
        dw, dh = node_size(node)
        shapes.append(Shape("loop", node.text, x, y_top, dw, dh, node.id))
        if node.body:
            body_top = y_top + dh + VGAP
            b_entry, b_exit = layout_chain(node.body, x, body_top,
                                           shapes, conns, labels)
            conns.append(Conn((x, y_top + dh), b_entry, arrow=True))
            _, br = chain_extents(node.body)
            back_x = x + max(dw / 2, br) + HGAP
            mid_y = b_exit[1] + VGAP
            exit_y = b_exit[1] + 2 * VGAP
            conns.append(Conn(b_exit, (x, exit_y), arrow=False))
            conns.append(Conn((x, mid_y), (back_x, mid_y), arrow=False))
            conns.append(Conn((back_x, mid_y), (back_x, y_top + dh / 2), arrow=False))
            conns.append(Conn((back_x, y_top + dh / 2),
                              (x + dw / 2, y_top + dh / 2), arrow=True))
            return (x, y_top), (x, exit_y)
        else:
            exit_y = y_top + dh + VGAP
            conns.append(Conn((x, y_top + dh), (x, exit_y), arrow=False))
            return (x, y_top), (x, exit_y)

    w, h = node_size(node)
    shapes.append(Shape("process", node.text, x, y_top, w, h, node.id))
    return (x, y_top), (x, y_top + h)


def build_layout(tree: List[Node]) -> Canvas:
    left, right = chain_extents(tree)
    x0 = left + 20.0
    y0 = 20.0
    shapes: List[Shape] = []
    conns: List[Conn] = []
    labels: List[Label] = []
    layout_chain(tree, x0, y0, shapes, conns, labels)

    min_x = min((s.cx - s.w / 2 for s in shapes), default=0)
    max_x = max((s.cx + s.w / 2 for s in shapes), default=0)
    min_y = min((s.top for s in shapes), default=0)
    max_y = max((s.top + s.h for s in shapes), default=0)
    for c in conns:
        min_x = min(min_x, c.start[0], c.end[0])
        max_x = max(max_x, c.start[0], c.end[0])
        min_y = min(min_y, c.start[1], c.end[1])
        max_y = max(max_y, c.start[1], c.end[1])
    for lb in labels:
        min_x = min(min_x, lb.x)
        max_x = max(max_x, lb.x)
        min_y = min(min_y, lb.y)
        max_y = max(max_y, lb.y)
    return Canvas(shapes, conns, labels, min_x, min_y, max_x, max_y)


# ----------------------------------------------------------------------
# Entry points
# ----------------------------------------------------------------------

def build_tree(source: str, language: str) -> List[Node]:
    lang = (language or "python").strip().lower()
    is_cpp = lang in ("c++", "cpp", "c")
    lines = normalize_cpp(source) if is_cpp else normalize_python(source)
    nodes, _ = parse_sequence(lines, 0, 0, is_cpp)
    return [Node("start", "Start")] + nodes + [Node("end", "End")]


def build(source: str, language: str) -> Canvas:
    return build_layout(build_tree(source, language))


# ----------------------------------------------------------------------
# Code generation
# ----------------------------------------------------------------------

CPP_HEADER = """#include <iostream>
#include <string>
using namespace std;

"""


def _ind(n: int) -> str:
    return "    " * n


def _is_simple_var(name: str) -> bool:
    return bool(re.match(r"^[A-Za-z_]\w*$", name))


def _split_assignment(text: str):
    t = text.strip().rstrip(";").strip()
    m = re.match(r"^([A-Za-z_]\w*)\s*=\s*(.+)$", t)
    if m:
        return m.group(1), m.group(2).strip()
    return None, None


def _guess_type_from_rhs(expr: str) -> str:
    expr = (expr or "").strip().rstrip(";").strip()
    if not expr:
        return "int"
    if (expr.startswith('"') and expr.endswith('"')) or \
       (expr.startswith("'") and expr.endswith("'")):
        return "string"
    if expr.lower() in ("true", "false"):
        return "bool"
    if re.match(r"^-?\d+$", expr):
        return "int"
    if re.match(r"^-?\d+\.\d+([eE][+\-]?\d+)?$", expr):
        return "double"
    if re.match(r"^int\s*\(", expr):
        return "int"
    if re.match(r"^float\s*\(", expr):
        return "double"
    if re.match(r"^str\s*\(", expr):
        return "string"
    return "int"


def _parse_input_vars(text: str):
    """Return list of (name, type). Type defaults to 'int'. Supports `x:string` syntax."""
    if not text.strip():
        return [("x", "int")]
    result = []
    for part in text.split(","):
        p = part.strip()
        if not p:
            continue
        if ":" in p:
            name, tp = p.split(":", 1)
            name, tp = name.strip(), (tp.strip() or "int")
        else:
            name, tp = p, "int"
        if _is_simple_var(name):
            result.append((name, tp))
    return result or [("x", "int")]


def _vars_from_process(text: str, is_cpp: bool) -> List[str]:
    out: List[str] = []
    t = text.strip().rstrip(";").strip()
    if not t:
        return out
    if is_cpp:
        m = re.match(
            r"^(?:const\s+|static\s+|unsigned\s+|signed\s+)*"
            r"(?:" + _CPP_TYPE_PATTERN + r")\s+(.+)$", t)
        if m:
            for part in m.group(1).split(","):
                name = part.split("=")[0].strip().lstrip("*&").strip()
                if _is_simple_var(name):
                    out.append(name)
            return out
        m = re.match(r"^([A-Za-z_]\w*)\s*(?:[+\-*/%]?=)", t)
        if m:
            out.append(m.group(1))
        return out
    m = re.match(r"^([A-Za-z_][\w\s,]*?)\s*(?:=(?!=)|[+\-*/%]=)", t)
    if m:
        for part in m.group(1).split(","):
            name = part.strip()
            if _is_simple_var(name):
                out.append(name)
    return out


def _vars_from_input(text: str) -> List[str]:
    out: List[str] = []
    for part in text.split(","):
        name = part.split(":")[0].strip()
        if _is_simple_var(name):
            out.append(name)
    return out


def vars_defined_by(node: Node, language: str) -> List[str]:
    lang = (language or "python").lower()
    is_cpp = lang in ("c++", "cpp", "c")
    if node.kind == "input":
        return _vars_from_input(node.text)
    if node.kind == "process":
        return _vars_from_process(node.text, is_cpp)
    return []


def collect_variables_before(tree: List[Node], target_id: int,
                             language: str) -> List[str]:
    result: List[str] = []
    seen = set()
    state = {"found": False}

    def add_many(names):
        for n in names:
            if n not in seen:
                seen.add(n)
                result.append(n)

    def walk(nodes):
        for node in nodes:
            if state["found"]:
                return
            if node.id == target_id:
                state["found"] = True
                return
            if node.kind in ("input", "process"):
                add_many(vars_defined_by(node, language))
            elif node.kind == "condition":
                walk(node.true_branch)
                walk(node.false_branch)
            elif node.kind == "loop":
                walk(node.body)

    walk(tree)
    return result


# ----------------------------------------------------------------------
# Code generation: Python
# ----------------------------------------------------------------------

def _gen_py(nodes, target, indent, out):
    ind = _ind(indent)
    for node in nodes:
        if node.kind in ("start", "end"):
            continue

        # verbatim round-trip when parsed from Python
        if node.code_text and node.code_lang == target and \
           node.kind in ("process", "input", "output"):
            out.append(f"{ind}{node.code_text}")
            continue

        if node.kind == "process":
            out.append(f"{ind}{node.text}")
            continue

        if node.kind == "input":
            parts = _parse_input_vars(node.text)
            names = [n for n, _ in parts]
            if len(names) == 1:
                out.append(f"{ind}{names[0]} = int(input())")
            else:
                out.append(f"{ind}{', '.join(names)} = map(int, input().split())")
            continue

        if node.kind == "output":
            parts = [p.strip() for p in node.text.split(",") if p.strip()] or ['"..."']
            out.append(f"{ind}print({', '.join(parts)})")
            continue

        if node.kind == "condition":
            out.append(f"{ind}if {node.text}:")
            if node.true_branch:
                _gen_py(node.true_branch, target, indent + 1, out)
            else:
                out.append(f"{ind}    pass")
            if node.false_branch:
                out.append(f"{ind}else:")
                _gen_py(node.false_branch, target, indent + 1, out)
            continue

        if node.kind == "loop":
            out.append(f"{ind}while {node.text}:")
            if node.body:
                _gen_py(node.body, target, indent + 1, out)
            else:
                out.append(f"{ind}    pass")
            continue


# ----------------------------------------------------------------------
# Code generation: C++ (Allman braces + auto type declarations)
# ----------------------------------------------------------------------

def _gen_cpp(nodes, target, indent, out, declared):
    ind = _ind(indent)
    for node in nodes:
        if node.kind in ("start", "end"):
            continue

        # verbatim round-trip when parsed from C++ (same language)
        if node.code_text and node.code_lang == target and \
           node.kind in ("process", "input", "output"):
            out.append(f"{ind}{node.code_text};")
            for v in (_vars_from_process(node.code_text, True)
                      if node.kind == "process"
                      else _vars_from_input(node.code_text)):
                declared.add(v)
            continue

        if node.kind == "process":
            txt = node.text.strip().rstrip(";")
            var, expr = _split_assignment(txt)
            if var and _is_simple_var(var) and var not in declared:
                tp = _guess_type_from_rhs(expr)
                out.append(f"{ind}{tp} {var} = {expr};")
                declared.add(var)
            else:
                out.append(f"{ind}{txt};")
            continue

        if node.kind == "input":
            parts = _parse_input_vars(node.text)
            for name, tp in parts:
                if name not in declared:
                    out.append(f"{ind}{tp} {name};")
                    declared.add(name)
            names = [n for n, _ in parts]
            out.append(f"{ind}cin >> " + " >> ".join(names) + ";")
            continue

        if node.kind == "output":
            parts = [p.strip() for p in node.text.split(",") if p.strip()] or ['"..."']
            if len(parts) == 1:
                out.append(f"{ind}cout << {parts[0]} << endl;")
            else:
                joined = ' << " " << '.join(parts)
                out.append(f"{ind}cout << {joined} << endl;")
            continue

        if node.kind == "condition":
            out.append(f"{ind}if ({node.text})")
            out.append(f"{ind}{{")
            _gen_cpp(node.true_branch, target, indent + 1, out, declared)
            out.append(f"{ind}}}")
            if node.false_branch:
                out.append(f"{ind}else")
                out.append(f"{ind}{{")
                _gen_cpp(node.false_branch, target, indent + 1, out, declared)
                out.append(f"{ind}}}")
            continue

        if node.kind == "loop":
            out.append(f"{ind}while ({node.text})")
            out.append(f"{ind}{{")
            _gen_cpp(node.body, target, indent + 1, out, declared)
            out.append(f"{ind}}}")
            continue


def generate_code(tree: List[Node], language: str = "python") -> str:
    lang = (language or "python").strip().lower()
    is_cpp = lang in ("c++", "cpp", "c")
    target = "cpp" if is_cpp else "python"

    if is_cpp:
        out: List[str] = []
        declared = set()
        _gen_cpp(tree, target, 1, out, declared)
        body = "\n".join(out) if out else "    // (empty)"
        return (CPP_HEADER +
                "int main()\n"
                "{\n" +
                body + "\n"
                "    return(0);\n"
                "}")
    else:
        out: List[str] = []
        _gen_py(tree, target, 0, out)
        return "\n".join(out)