"""
DSL v0.4 -> OpenSCAD

Features
- PART / GROUP blocks
- USE / MOVE / ROTATE (instances)
- UNION / CUT / INTERSECT produce new parts with geometry **inlined** (no module calls inside booleans)
- Nested booleans supported
- EXTRUDE height=...: <2D> (currently CIRCLE)
- Primitives: CUBE, CYLINDER, SPHERE, ROD, TORUS, CIRCLE (2D)
- chamfer= on CUBE & CYLINDER via Minkowski
- Assembly auto-layout so test shapes appear side-by-side

Example DSL:
    PART a:
        CUBE width=30 depth=30 height=10
    PART b:
        CYLINDER radius=8 height=12
    CUT a b AS a_minus_b
    USE a
    USE b
    USE a_minus_b
"""

import re
from typing import List, Dict, Optional, Tuple

# ---------- Helpers ----------

def _safe_vec3(v) -> Tuple[float, float, float]:
    """
    Very defensive (avoids recursion issues from weird objects).
    Accepts tuples/lists or strings like '(x,y,z)' / '[x,y,z]'.
    Falls back to (0,0,0).
    """
    # Try unpacking as tuple/list
    try:
        x, y, z = v
        return float(x), float(y), float(z)
    except Exception:
        pass

    # Try parsing from string
    try:
        s = "" if v is None else str(v)
        nums = re.findall(r"[-+]?\d*\.?\d+", s)
        if len(nums) >= 3:
            return float(nums[0]), float(nums[1]), float(nums[2])
    except Exception:
        pass

    return 0.0, 0.0, 0.0

def _params(tokens: List[str]) -> Dict[str, object]:
    out = {}
    for t in tokens:
        if "=" in t:
            k, v = t.split("=", 1)
            v = v.strip()
            if v.startswith("(") or v.startswith("["):
                out[k] = _safe_vec3(v)
            else:
                try:
                    out[k] = float(v)
                except Exception:
                    out[k] = v
    return out

def _sanitize(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]", "_", name.strip())
    if not re.match(r"[A-Za-z_]", name):
        name = "p_" + name
    return name

def _pos_str(v) -> str:
    x, y, z = _safe_vec3(v)
    return f"[{x},{y},{z}]"

# ---------- AST ----------

class Node: ...
class Prim(Node):
    def __init__(self, kind: str, params: Dict[str, object]):
        self.kind = kind.upper()
        self.params = params

class Use(Node):
    def __init__(self, name: str, translate=(0, 0, 0), rotate=(0, 0, 0), scale=None):
        self.name = _sanitize(name)
        self.translate = translate
        self.rotate = rotate
        self.scale = scale

class Extrude(Node):
    def __init__(self, height: float, child2d: 'Prim'):
        self.height = height
        self.child2d = child2d

class Boolean(Node):
    def __init__(self, op: str, left: Use, right: Use):
        self.op = op  # 'union' | 'difference' | 'intersection'
        self.left = left
        self.right = right

class MultiUnion(Node):
    def __init__(self, names: List[str]):
        self.names = [_sanitize(n) for n in names]

class Part:
    def __init__(self, name: str, is_boolean=False):
        self.name = _sanitize(name)
        self.nodes: List[Node] = []
        self.is_boolean = is_boolean  # boolean parts are emitted with inlined geometry

class Instance:
    def __init__(self, target: str, translate=(0, 0, 0), rotate=(0, 0, 0), scale=None, label=None):
        self.target = _sanitize(target)
        self.translate = translate
        self.rotate = rotate
        self.scale = scale
        self.label = label or target

class Model:
    def __init__(self):
        self.parts: Dict[str, Part] = {}
        self.instances: List[Instance] = []

    def get_or_create(self, name: str) -> Part:
        key = _sanitize(name)
        if key not in self.parts:
            self.parts[key] = Part(key)
        return self.parts[key]

# ---------- Emit ----------

def _chamfer_wrap(obj_scad: str, chamfer: Optional[float]) -> str:
    if chamfer is None or chamfer == 0:
        return obj_scad
    return f"minkowski() {{ {obj_scad} cylinder(r={chamfer}, h=0.01, center=true); }}"

def _emit_primitive_scad(p: Prim) -> str:
    k = p.kind
    prm = p.params
    chamfer = prm.get("chamfer", None)
    if chamfer is not None:
        try:
            chamfer = float(chamfer)
        except Exception:
            chamfer = None

    if k == "CUBE":
        w = prm.get("width", 10)
        d = prm.get("depth", 10)
        h = prm.get("height", 10)
        pos = _pos_str(prm.get("position", (0, 0, 0)))
        base = f"translate({pos}) cube([{w},{d},{h}], center=true);"
        return _chamfer_wrap(base, chamfer)

    if k == "CYLINDER":
        r = prm.get("radius", 5)
        h = prm.get("height", 10)
        pos = _pos_str(prm.get("position", (0, 0, 0)))
        base = f"translate({pos}) cylinder(r={r}, h={h}, center=true);"
        return _chamfer_wrap(base, chamfer)

    if k == "SPHERE":
        r = prm.get("radius", 5)
        pos = _pos_str(prm.get("position", (0, 0, 0)))
        return f"translate({pos}) sphere(r={r});"

    if k == "ROD":
        r = prm.get("radius", 3)
        length = prm.get("length", 30)
        pos = _pos_str(prm.get("position", (0, 0, 0)))
        orient = str(prm.get("orientation", "z")).lower()
        body = f"cylinder(r={r}, h={length}, center=true);"
        if orient == "x":
            body = f"rotate([0,90,0]) {body}"
        elif orient == "y":
            body = f"rotate([90,0,0]) {body}"
        return f"translate({pos}) {body}"

    if k == "TORUS":
        R = prm.get("major_radius", 20)
        r = prm.get("minor_radius", 5)
        pos = _pos_str(prm.get("position", (0, 0, 0)))
        body = f"rotate_extrude() translate([{R},0,0]) circle(r={r});"
        return f"translate({pos}) {body}"

    if k == "CIRCLE":
        r = prm.get("radius", 10)
        x, y, _ = _safe_vec3(prm.get("position", (0, 0, 0)))
        return f"translate([{x},{y}]) circle(r={r});"

    return f"// Unknown primitive {k};"

def _emit_use_scad(model: Model, u: Use, inline: bool, visited=None) -> str:
    if visited is None:
        visited = set()
    if u.name in visited:
        return f"// Cycle detected: {u.name}"
    visited.add(u.name)
    # Inline referenced part if requested
    if inline:
        inner = _emit_nodes(model, model.parts[u.name].nodes, inline=True, visited=visited)
        call = inner if inner.strip() else f"{u.name}();"
    else:
        call = f"{u.name}();"

    # Apply transforms
    if u.scale is not None:
        call = f"scale([{u.scale},{u.scale},{u.scale}]) {call}"
    rx, ry, rz = _safe_vec3(u.rotate)
    if (rx, ry, rz) != (0.0, 0.0, 0.0):
        call = f"rotate([{rx},{ry},{rz}]) {call}"
    call = f"translate({_pos_str(u.translate)}) {call}"

    if not call.strip().endswith(";"):
        call += ";"
    visited.remove(u.name)
    return call

def _emit_nodes(model: Model, nodes: List[Node], inline: bool, visited=None) -> str:
    if visited is None:
        visited = set()
    out = []
    for n in nodes:
        if isinstance(n, Prim):
            tmp = _emit_primitive_scad(n)
            out.append(tmp if tmp.strip().endswith(";") else tmp + ";")
        elif isinstance(n, Use):
            out.append(_emit_use_scad(model, n, inline, visited))
        elif isinstance(n, Extrude):
            two_d = _emit_primitive_scad(n.child2d)
            out.append(f"linear_extrude(height={n.height}) {{ {two_d} }};")
        elif isinstance(n, Boolean):
            a = _emit_use_scad(model, n.left, inline=True, visited=visited)
            b = _emit_use_scad(model, n.right, inline=True, visited=visited)
            out.append(f"{n.op}() {{ {a} {b} }}")
        elif isinstance(n, MultiUnion):
            # Emit a single union() block with all children
            union_body = "\n  ".join([
                _emit_use_scad(model, Use(name), inline=True, visited=visited)
                for name in n.names
            ])
            out.append(f"union() {{\n  {union_body}\n}}")
        else:
            out.append("// unknown node;")
    return "\n  ".join(out)

def module_scad(model: Model, part: Part) -> str:
    # For boolean parts we inline geometry when emitting the module body
    inline = part.is_boolean
    body = _emit_nodes(model, part.nodes, inline=inline)
    return f"module {part.name}() {{\n  {body}\n}}\n"

def to_scad(model: Model) -> str:
    pieces = ["// Generated by DSL v0.4\n$fn=72;\n"]
    # Emit all modules
    for name in model.parts:
        pieces.append(module_scad(model, model.parts[name]))

    # Emit assembly (auto-layout along X so everything is visible)
    pieces.append("module assembly(){")
    x = 0.0
    for idx, inst in enumerate(model.instances, 1):
        call = f"{inst.target}();"
        if inst.scale is not None:
            call = f"scale([{inst.scale},{inst.scale},{inst.scale}]) {call}"
        rx, ry, rz = _safe_vec3(inst.rotate)
        if (rx, ry, rz) != (0.0, 0.0, 0.0):
            call = f"rotate([{rx},{ry},{rz}]) {call}"
        pieces.append(f"  // Instance {idx}: {inst.label}")
        pieces.append(f"  translate([{x},0,0]) {call}")
        x += 140.0
    pieces.append("}\nassembly();")
    return "\n".join(pieces)

# ---------- Parser ----------

def parse(text: str) -> Model:
    m = Model()
    lines = [l.rstrip() for l in text.splitlines()]
    i = 0
    cur: Optional[Part] = None
    pending_extrude: Optional[float] = None

    def end_part():
        nonlocal cur
        cur = None

    while i < len(lines):
        raw = lines[i].strip()
        i += 1
        if not raw or raw.startswith("#"):
            continue
        toks = raw.split()
        head = toks[0].upper()

        if head in ("PART", "GROUP"):
            end_part()
            name = raw.split(None, 1)[1].strip().rstrip(":")
            cur = m.get_or_create(name)
            continue

        if head == "USE":
            end_part()  # Ensure top-level USE goes to model.instances
            name = toks[1]
            prm = _params(toks[2:])
            pos = prm.get("position", (0, 0, 0))
            rot = prm.get("rotate", (0, 0, 0))
            scale = prm.get("scale", None)
            if cur:
                cur.nodes.append(Use(name, pos, rot, scale))
            else:
                m.instances.append(Instance(name, pos, rot, scale, label=f"USE {name}"))
            continue

        if head == "MOVE":
            end_part()  # Ensure top-level MOVE goes to model.instances
            name = toks[1]
            prm = _params(toks[2:])
            by = prm.get("by", (0, 0, 0))
            m.instances.append(Instance(name, by, (0, 0, 0), None, label=f"MOVE {name}"))
            continue

        if head == "ROTATE":
            end_part()  # Ensure top-level ROTATE goes to model.instances
            name = toks[1]
            prm = _params(toks[2:])
            by = prm.get("by", (0, 0, 0))
            m.instances.append(Instance(name, (0, 0, 0), by, None, label=f"ROTATE {name}"))
            continue

        if head in ("UNION", "CUT", "INTERSECT"):
            # Syntax: UNION A B AS C   |   CUT A B AS C   |   INTERSECT A B AS C
            rest = raw.split(None, 1)[1]
            mm = re.match(r"\s*([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\s+AS\s+([A-Za-z0-9_]+)", rest, flags=re.I)
            if mm:
                a, b, c = mm.group(1), mm.group(2), mm.group(3)
                op = "union" if head == "UNION" else "difference" if head == "CUT" else "intersection"
                p = m.get_or_create(c)
                p.is_boolean = True
                p.nodes = [Boolean(op, Use(a), Use(b))]
            continue

        if head == "EXTRUDE":
            prm = _params(toks[1:])
            h = prm.get("height", 10.0)
            try:
                pending_extrude = float(h)
            except Exception:
                pending_extrude = 10.0
            continue

        # Inside PART/GROUP: primitives or the 2D child of EXTRUDE
        if cur:
            if pending_extrude is not None:
                kind = toks[0]
                prm = _params(toks[1:])
                prim = Prim(kind, prm)
                cur.nodes.append(Extrude(pending_extrude, prim))
                pending_extrude = None
            else:
                kind = toks[0]
                prm = _params(toks[1:])
                cur.nodes.append(Prim(kind, prm))
            continue

        # Unknown top-level lines are ignored

    return m
