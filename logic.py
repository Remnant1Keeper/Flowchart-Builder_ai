"""
Pure logic: code normalizers, rule-based parser, tree layout.
No Qt Widgets, only dataclasses with float coords.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class NLine:
    text: str
    indent: int
    skip: bool = False


class Node:
    __slots__ = ("kind", "text", "true_branch", "false_branch", "body")

    def __init__(self, kind: str, text: str = ""):
        self.kind = kind
        self.text = text
        self.true_branch: List[Node] = []
        self.false_branch: List[Node] = []
        self.body: List[Node] = []


@dataclass
class Shape:
    kind: str
    text: str
    cx: float
    top: float
    w: float
    h: float


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
        indent = n_spaces // 4
        out.append(NLine(stripped, indent, False))
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
# Rule-based parser
# ----------------------------------------------------------------------

def _is_io(t: str) -> bool:
    tl = t.lower().replace(" ", "")
    return any(p in tl for p in (
        "input(", "print(", "printf(", "scanf(",
        "cin>>", "cout<<", "getline(", "puts(", "gets(",
    ))


def _is_cpp_func_sig(t: str) -> bool:
    if t.startswith(("if", "while", "for", "else", "switch",
                     "return", "using", "typedef", "do", "case", "break", "continue")):
        return False
    if "(" not in t or ")" not in t:
        return False
    if not t.rstrip().endswith(")"):
        return False
    m = re.match(r"^[A-Za-z_][\w:<>,\s\*&]*\s+[A-Za-z_~][\w:]*\s*\([^()]*\)\s*$", t)
    return bool(m)


RULES = [
    {"name": "cpp_preproc",     "match": lambda t: t.startswith("#"),                                   "kind": "skip"},
    {"name": "py_def_or_class", "match": lambda t: (t.startswith("def ") or t.startswith("class "))
                                                   and t.rstrip().endswith(":"),                        "kind": "skip"},
    {"name": "cpp_func_sig",    "match": _is_cpp_func_sig,                                              "kind": "skip"},
    {"name": "py_pass",         "match": lambda t: t == "pass",                                         "kind": "skip"},
    {"name": "py_break_cont",   "match": lambda t: t in ("break", "continue"),                          "kind": "skip"},
    {"name": "if",              "match": lambda t: t.startswith("if ") or t.startswith("if("),           "kind": "if"},
    {"name": "elif",            "match": lambda t: t.startswith("elif ") or t.startswith("else if "),    "kind": "elif"},
    {"name": "else",            "match": lambda t: t == "else" or t == "else:"
                                                   or t.startswith("else "),                            "kind": "else"},
    {"name": "while",           "match": lambda t: t.startswith("while ") or t.startswith("while("),    "kind": "while"},
    {"name": "for",             "match": lambda t: t.startswith("for ") or t.startswith("for("),        "kind": "for"},
    {"name": "io",              "match": _is_io,                                                        "kind": "io"},
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


def parse_sequence(lines: List[NLine], i: int, indent: int):
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
            nodes.append(Node("process", text))
            i += 1
            continue

        kind = matched["kind"]

        if kind == "skip":
            body, i2 = parse_sequence(lines, i + 1, indent + 1)
            nodes.extend(body)
            i = i2 if i2 != i + 1 else i + 1

        elif kind in ("if", "elif"):
            node, i = parse_if_chain(lines, i, indent)
            nodes.append(node)

        elif kind == "else":
            body, i = parse_sequence(lines, i + 1, indent + 1)
            nodes.extend(body)

        elif kind in ("while", "for"):
            cond = _extract_condition(text)
            node = Node("loop", cond)
            body, i = parse_sequence(lines, i + 1, indent + 1)
            node.body = body
            nodes.append(node)

        elif kind == "io":
            nodes.append(Node("io", text))
            i += 1

        else:
            nodes.append(Node("process", text))
            i += 1

    return nodes, i


def parse_if_chain(lines: List[NLine], i: int, indent: int):
    text = lines[i].text
    cond = _extract_condition(text)
    node = Node("condition", cond)

    body, i = parse_sequence(lines, i + 1, indent + 1)
    node.true_branch = body

    if i < len(lines) and lines[i].indent == indent:
        nxt = lines[i].text
        low = nxt.lower()
        if low.startswith("elif ") or low.startswith("else if "):
            sub, i = parse_if_chain(lines, i, indent)
            node.false_branch = [sub]
        elif nxt == "else" or nxt == "else:" or low.startswith("else "):
            else_body, i = parse_sequence(lines, i + 1, indent + 1)
            node.false_branch = else_body
    return node, i


# ----------------------------------------------------------------------
# Layout
# ----------------------------------------------------------------------

CHAR_W = 7.5
PAD = 24.0
HGAP = 60.0
VGAP = 35.0


def node_size(node: Node) -> Tuple[float, float]:
    text = node.text
    tw = len(text) * CHAR_W + PAD
    if node.kind in ("start", "end"):
        w = max(100.0, tw + 30)
        h = 42.0
    elif node.kind in ("process", "io"):
        w = max(140.0, tw)
        h = 42.0
    elif node.kind in ("condition", "loop"):
        w = max(180.0, tw * 1.8)
        h = 80.0
    else:
        w, h = 140.0, 42.0
    return w, h


def chain_extents(chain: List[Node]) -> Tuple[float, float]:
    left = 0.0
    right = 0.0
    for node in chain:
        if node.kind in ("start", "end", "process", "io"):
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
    if node.kind in ("start", "end", "process", "io"):
        w, h = node_size(node)
        shapes.append(Shape(node.kind, node.text, x, y_top, w, h))
        return (x, y_top), (x, y_top + h)

    if node.kind == "condition":
        dw, dh = node_size(node)
        shapes.append(Shape("condition", node.text, x, y_top, dw, dh))

        tl, tr = chain_extents(node.true_branch)
        fl, fr = chain_extents(node.false_branch)

        true_x = x + dw / 2 + HGAP + tl
        false_x = x - dw / 2 - HGAP - fr
        branch_top = y_top + dh + VGAP

        t_entry = t_exit = None
        f_entry = f_exit = None
        if node.true_branch:
            t_entry, t_exit = layout_chain(node.true_branch, true_x, branch_top,
                                           shapes, conns, labels)
        if node.false_branch:
            f_entry, f_exit = layout_chain(node.false_branch, false_x, branch_top,
                                           shapes, conns, labels)

        candidates = [branch_top]
        if t_exit:
            candidates.append(t_exit[1])
        if f_exit:
            candidates.append(f_exit[1])
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
        shapes.append(Shape("loop", node.text, x, y_top, dw, dh))

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
    shapes.append(Shape("process", node.text, x, y_top, w, h))
    return (x, y_top), (x, y_top + h)


def build_layout(root_nodes: List[Node]) -> Canvas:
    start_node = Node("start", "Start")
    end_node = Node("end", "End")
    chain = [start_node] + root_nodes + [end_node]

    left, right = chain_extents(chain)
    x0 = left + 20.0
    y0 = 20.0

    shapes: List[Shape] = []
    conns: List[Conn] = []
    labels: List[Label] = []
    layout_chain(chain, x0, y0, shapes, conns, labels)

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


def build(source: str, language: str) -> Canvas:
    lang = (language or "python").strip().lower()
    if lang in ("c++", "cpp", "c"):
        lines = normalize_cpp(source)
    else:
        lines = normalize_python(source)

    nodes, _ = parse_sequence(lines, 0, 0)
    return build_layout(nodes)