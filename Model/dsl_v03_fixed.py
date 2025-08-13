
"""
DSL v0.3 -> OpenSCAD (fixed)
Features:
- PART <name>: ... (grouping of primitives and USEs)
- GROUP <name>: ... (alias of PART)
- USE <part> [position=(x,y,z)] [rotate=(rx,ry,rz)] [scale=s]
- MOVE <part> by=(dx,dy,dz)       (creates an instance in assembly)
- ROTATE <part> by=(rx,ry,rz)     (creates an instance in assembly)
- UNION A B AS C
- CUT A B AS C
- INTERSECT A B AS C
- EXTRUDE height=h: <2D shape>    (CIRCLE only for now) inside PART/GROUP
- Primitives: CUBE, CYLINDER, SPHERE, ROD, TORUS, CIRCLE(2D)
- chamfer= on CUBE/CYLINDER

Outputs:
- One SCAD with module per part/boolean result
- 'assembly()' with all instances (USE/MOVE/ROTATE) laid out along X
"""

import re
from typing import Dict, List, Tuple, Optional

def _vec3(v) -> Tuple[float,float,float]:
    if isinstance(v, tuple): return v
    nums = re.findall(r"[-+]?\d*\.?\d+", str(v))
    if len(nums) == 3:
        return (float(nums[0]), float(nums[1]), float(nums[2]))
    return (0.0,0.0,0.0)

def _num(v) -> float:
    try: return float(v)
    except: return 0.0

def _params(tokens: List[str]) -> Dict[str, object]:
    out = {}
    for t in tokens:
        if "=" in t:
            k, v = t.split("=", 1)
            v = v.strip()
            if v.startswith("(") or v.startswith("["):
                out[k] = _vec3(v)
            else:
                try:
                    out[k] = float(v)
                except:
                    out[k] = v
    return out

def _pos_str(v) -> str:
    x,y,z = _vec3(v)
    return f"[{x},{y},{z}]"

def _rot_str(v) -> str:
    x,y,z = _vec3(v)
    return f"[{x},{y},{z}]"

def _sanitize(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]", "_", name.strip())
    if not re.match(r"[A-Za-z_]", name):
        name = "p_" + name
    return name

# ---------- Primitive Emitters ----------

def _emit_primitive(kind: str, params: Dict[str, object]) -> str:
    k = kind.upper()
    chamfer = params.get("chamfer", None)
    if k == "CUBE":
        w = params.get("width", 10)
        d = params.get("depth", 10)
        h = params.get("height", 10)
        pos = _pos_str(params.get("position", (0,0,0)))
        base = f"translate({pos}) cube([{w},{d},{h}], center=true);"
        return _chamfer_wrap(base, chamfer)
    if k == "CYLINDER":
        r = params.get("radius", 5)
        h = params.get("height", 10)
        pos = _pos_str(params.get("position", (0,0,0)))
        base = f"translate({pos}) cylinder(r={r}, h={h}, center=true);"
        return _chamfer_wrap(base, chamfer)
    if k == "SPHERE":
        r = params.get("radius", 5)
        pos = _pos_str(params.get("position", (0,0,0)))
        return f"translate({pos}) sphere(r={r});"
    if k == "ROD":
        r = params.get("radius", 3)
        length = params.get("length", 30)
        pos = _pos_str(params.get("position", (0,0,0)))
        orient = str(params.get("orientation", "z")).lower()
        body = f"cylinder(r={r}, h={length}, center=true);"
        if orient == "x":
            body = f"rotate([0,90,0]) {body}"
        elif orient == "y":
            body = f"rotate([90,0,0]) {body}"
        return f"translate({pos}) {body};"
    if k == "TORUS":
        R = params.get("major_radius", 20)
        r = params.get("minor_radius", 5)
        pos = _pos_str(params.get("position", (0,0,0)))
        body = f"rotate_extrude() translate([{R},0,0]) circle(r={r});"
        return f"translate({pos}) {body}"
    if k == "CIRCLE":  # 2D
        r = params.get("radius", 10)
        # circle is 2D; ignore Z translation
        pos = _vec3(params.get("position", (0,0,0)))
        return f"translate([{pos[0]},{pos[1]}]) circle(r={r});"
    return f"// Unknown primitive {kind}"

def _chamfer_wrap(scad_obj: str, chamfer: Optional[float]) -> str:
    if chamfer is None or chamfer == 0:
        return scad_obj
    # Minkowski with thin cylinder approximates chamfer
    return f"minkowski(){{ {scad_obj} cylinder(r={chamfer}, h=0.01, center=true); }}"

# ---------- Model ----------

class Part:
    def __init__(self, name: str):
        self.name = _sanitize(name)
        self.body: List[str] = []  # SCAD lines within module

    def add_line(self, scad: str):
        self.body.append(scad)

    def module_scad(self) -> str:
        inner = "\n  ".join(self.body) if self.body else ""
        return f"module {self.name}() {{\n  {inner}\n}}\n"

class Instance:
    def __init__(self, target: str, translate=(0,0,0), rotate=(0,0,0), scale=None, label=None):
        self.target = _sanitize(target)
        self.translate = translate
        self.rotate = rotate
        self.scale = scale
        self.label = label or target

    def call_scad(self) -> str:
        call = f"{self.target}();"
        if self.scale is not None:
            call = f"scale([{self.scale},{self.scale},{self.scale}]) {call}"
        if self.rotate != (0,0,0):
            call = f"rotate({_rot_str(self.rotate)}) {call}"
        if self.translate != (0,0,0):
            call = f"translate({_pos_str(self.translate)}) {call}"
        return call

class Model:
    def __init__(self):
        self.parts: Dict[str, Part] = {}
        self.instances: List[Instance] = []

    def get_or_create_part(self, name: str) -> Part:
        key = _sanitize(name)
        if key not in self.parts:
            self.parts[key] = Part(key)
        return self.parts[key]

# ---------- Parser ----------

TOP = ("PART","GROUP","USE","MOVE","ROTATE","UNION","CUT","INTERSECT","EXTRUDE")

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
        if not raw or raw.startswith("#"): continue
        toks = raw.split()
        head = toks[0].upper()

        if head in ("PART","GROUP"):
            end_part()
            # name may include trailing ":"
            name = raw.split(None,1)[1].strip().rstrip(":")
            cur = m.get_or_create_part(name)
            continue

        if head == "USE":
            target = toks[1]
            params = _params(toks[2:])
            pos = params.get("position",(0,0,0))
            rot = params.get("rotate",(0,0,0))
            scale = params.get("scale", None)
            if cur:
                # inside a part: inline transformed call
                call = f"translate({_pos_str(pos)}) rotate({_rot_str(rot)}) "
                if scale is not None:
                    call += f"scale([{scale},{scale},{scale}]) "
                call += f"{_sanitize(target)}();"
                cur.add_line(call)
            else:
                # top-level: create instance
                m.instances.append(Instance(target,pos,rot,scale,label=f"USE {target}"))
            continue

        if head == "MOVE":
            target = toks[1]
            params = _params(toks[2:])
            by = params.get("by",(0,0,0))
            m.instances.append(Instance(target,by,(0,0,0),None,label=f"MOVE {target}"))
            continue

        if head == "ROTATE":
            target = toks[1]
            params = _params(toks[2:])
            by = params.get("by",(0,0,0))
            m.instances.append(Instance(target,(0,0,0),by,None,label=f"ROTATE {target}"))
            continue

        if head in ("UNION","CUT","INTERSECT"):
            # Format: UNION A B AS C
            #         CUT A B AS C
            #         INTERSECT A B AS C
            rest = raw.split(None,1)[1]
            mm = re.match(r"\s*([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\s+AS\s+([A-Za-z0-9_]+)", rest, flags=re.I)
            if mm:
                a, b, c = mm.group(1), mm.group(2), mm.group(3)
                out_name = _sanitize(c)
                part = m.get_or_create_part(out_name)
                op = "union" if head=="UNION" else "difference" if head=="CUT" else "intersection"
                part.body = [f"{op}() {{ {_sanitize(a)}(); {_sanitize(b)}(); }}"]
            continue

        if head == "EXTRUDE":
            params = _params(toks[1:])
            pending_extrude = params.get("height", 10.0)
            continue

        # If we reach here inside a PART/GROUP, it's either a primitive or a 2D for extrude
        if cur:
            if pending_extrude is not None:
                # Next line must be a 2D primitive like CIRCLE
                k = toks[0]
                p = _params(toks[1:])
                two_d = _emit_primitive(k, p)
                cur.add_line(f"linear_extrude(height={pending_extrude}) {{ {two_d} }}")
                pending_extrude = None
            else:
                k = toks[0]
                p = _params(toks[1:])
                cur.add_line(_emit_primitive(k, p))
            continue

        # Otherwise ignore unknown top-level lines

    return m

# ---------- SCAD emission ----------

def to_scad(model: Model) -> str:
    out = ["// Generated by DSL v0.3 (fixed)\n$fn=72;\n"]
    # modules
    for name in model.parts:
        out.append(model.parts[name].module_scad())
    # assembly puts each instance apart along X
    out.append("module assembly(){")
    x = 0.0
    for idx, inst in enumerate(model.instances, 1):
        out.append(f"  // Instance {idx}: {inst.label}")
        out.append(f"  translate([{x},0,0]) {inst.call_scad()}")
        x += 120.0
    out.append("}")
    out.append("assembly();")
    return "\n".join(out)
