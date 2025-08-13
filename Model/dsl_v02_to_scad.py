
import re
from typing import List, Dict, Any, Tuple

BIG = 10000  # for slicing half-space cubes


def parse_vec3(val: str) -> Tuple[float, float, float]:
    import re
    nums = re.findall(r"[-+]?\d*\.?\d+", val)
    if len(nums) == 3:
        return tuple(float(x) for x in nums)
    raise ValueError(f"Invalid vec3: {val}")


def parse_float(val: str) -> float:
    return float(val)


def parse_params(tokens: List[str]) -> Dict[str, Any]:
    out = {}
    for t in tokens:
        if "=" in t:
            k, v = t.split("=", 1)
            v = v.strip()
            if v.startswith("(") or v.startswith("["):
                out[k] = parse_vec3(v)
            else:
                try:
                    out[k] = parse_float(v)
                except ValueError:
                    out[k] = v
    return out


def sanitize_name(name: str) -> str:
    import re
    name = re.sub(r"[^A-Za-z0-9_]", "_", name.strip())
    if not re.match(r"[A-Za-z_]", name):
        name = f"p_{name}"
    return name


class Primitive:
    def __init__(self, kind: str, params: Dict[str, Any]):
        self.kind = kind.upper()
        self.params = params

    def to_scad(self) -> str:
        pos = self.params.get("position", (0, 0, 0))
        orientation = str(self.params.get("orientation", "z")).lower()

        # base shape code
        if self.kind == "CUBE":
            w = self.params.get("width", 10.0)
            h = self.params.get("height", 10.0)
            d = self.params.get("depth", 10.0)
            shape = f"cube([{w},{d},{h}], center=true);"
            body = f"translate([{pos[0]},{pos[1]},{pos[2]}]) {shape}"
            return body

        if self.kind == "CYLINDER":
            r = self.params.get("radius", 10.0)
            h = self.params.get("height", 10.0)
            shape = f"cylinder(r={r}, h={h}, center=true);"
            # rotate if orientation is x or y
            rot = (90, 0, 0) if orientation == "x" else (0, 90, 0) if orientation == "y" else (0, 0, 0)
            body = shape
            if rot != (0, 0, 0):
                body = f"rotate([{rot[0]},{rot[1]},{rot[2]}]) {body}"
            body = f"translate([{pos[0]},{pos[1]},{pos[2]}]) {body}"
            return body

        if self.kind == "ROD":
            r = self.params.get("radius", 5.0)
            length = self.params.get("length", 50.0)
            # use cylinder oriented by orientation
            shape = f"cylinder(r={r}, h={length}, center=true);"
            rot = (90, 0, 0) if orientation == "x" else (0, 90, 0) if orientation == "y" else (0, 0, 0)
            body = shape
            if rot != (0, 0, 0):
                body = f"rotate([{rot[0]},{rot[1]},{rot[2]}]) {body}"
            pos = self.params.get("position", (0, 0, 0))
            body = f"translate([{pos[0]},{pos[1]},{pos[2]}]) {body}"
            return body

        if self.kind == "SPHERE":
            r = self.params.get("radius", 10.0)
            shape = f"sphere(r={r});"
            body = f"translate([{pos[0]},{pos[1]},{pos[2]}]) {shape}"
            return body

        if self.kind == "TORUS":
            R = self.params.get("major_radius", 20.0)
            r = self.params.get("minor_radius", 5.0)
            shape = f"rotate_extrude() translate([{R},0,0]) circle(r={r});"
            rot = (90, 0, 0) if orientation == "x" else (0, 90, 0) if orientation == "y" else (0, 0, 0)
            body = shape
            if rot != (0, 0, 0):
                body = f"rotate([{rot[0]},{rot[1]},{rot[2]}]) {body}"
            body = f"translate([{pos[0]},{pos[1]},{pos[2]}]) {body}"
            return body

        return f"// Unknown primitive {self.kind}"


class Part:
    def __init__(self, name: str):
        self.name = sanitize_name(name)
        self.items: List[Primitive] = []

    def add(self, prim: Primitive):
        self.items.append(prim)

    def module_scad(self) -> str:
        lines = [f"module {self.name}() {{"]
        for p in self.items:
            lines.append(f"  {p.to_scad()}")
        lines.append("}")
        return "\\n".join(lines)


class Instance:
    def __init__(self, part_name: str, translate=(0, 0, 0), rotate=(0, 0, 0), scale=None, label=None):
        self.part_name = sanitize_name(part_name)
        self.translate = translate
        self.rotate = rotate
        self.scale = scale
        self.label = label  # optional, for comments


class CutOp:
    def __init__(self, target_part: str, cutter_primitive: Primitive, instance_offset=(0, 0, 0)):
        self.target_part = sanitize_name(target_part)
        self.cutter_primitive = cutter_primitive
        self.instance_offset = instance_offset  # for spacing in assembly


class SliceOp:
    def __init__(self, target_part: str, axis: str, at: float, offset_pair=((0, 0, 0), (0, 0, 0))):
        self.target_part = sanitize_name(target_part)
        self.axis = axis.upper()
        self.at = at
        self.offset_pair = offset_pair  # positions for the two slice results


class DSLModel:
    def __init__(self):
        self.parts: Dict[str, Part] = {}
        self.instances: List[Instance] = []
        self.cuts: List[CutOp] = []
        self.slices: List[SliceOp] = []


TOP_LEVEL = ("PART", "USE", "MOVE", "ROTATE", "CUT", "SLICE")


def parse_dsl_v02(text: str) -> DSLModel:
    model = DSLModel()

    lines = [l.rstrip() for l in text.splitlines()]
    i = 0
    current_part: Part = None

    # helpers
    def flush_part():
        nonlocal current_part
        if current_part:
            model.parts[current_part.name] = current_part
            current_part = None

    while i < len(lines):
        raw = lines[i].strip()
        i += 1
        if not raw or raw.startswith("#"):
            continue

        tokens = raw.split()
        key = tokens[0].upper()

        if key == "PART":
            # begin part
            flush_part()
            name = raw.split("PART", 1)[1].strip().rstrip(":")
            current_part = Part(name)
            # consume subsequent indented lines until next top-level or EOF
            while i < len(lines):
                nxt = lines[i]
                stripped = nxt.strip()
                if not stripped or stripped.startswith("#"):
                    i += 1
                    continue
                first = stripped.split()[0].upper()
                if first in TOP_LEVEL:
                    break  # top-level next; stop part
                # treat as primitive line
                prim_tokens = stripped.split()
                kind = prim_tokens[0].upper()
                params = parse_params(prim_tokens[1:])
                current_part.add(Primitive(kind, params))
                i += 1
            flush_part()
            continue

        # outside parts: instances and ops
        if key == "USE":
            # USE part position=(..) rotate=(..) scale=..
            name = tokens[1]
            params = parse_params(tokens[2:])
            pos = params.get("position", (0, 0, 0))
            rot = params.get("rotate", (0, 0, 0))
            scale = params.get("scale", None)
            model.instances.append(Instance(name, pos, rot, scale, label=f"USE {name}"))
            continue

        if key == "MOVE":
            # MOVE <part> by=(dx,dy,dz) -> we will create an instance if none exists yet
            name = tokens[1]
            params = parse_params(tokens[2:])
            by = params.get("by", (0, 0, 0))
            model.instances.append(Instance(name, by, (0, 0, 0), None, label=f"MOVE {name}"))
            continue

        if key == "ROTATE":
            name = tokens[1]
            params = parse_params(tokens[2:])
            by = params.get("by", (0, 0, 0))
            # represent as a zero-translate instance with rotation
            model.instances.append(Instance(name, (0, 0, 0), by, None, label=f"ROTATE {name}"))
            continue

        if key == "CUT":
            # CUT part WITH: <primitive...>
            # Example: CUT plate WITH: CYLINDER radius=5 height=10 position=(0,0,0)
            rest = raw.split(None, 2)
            if len(rest) < 3:
                continue
            target = rest[1]
            # Expect "WITH:" next tokens
            import re
            m = re.search(r"WITH:\s*(.+)$", raw, flags=re.IGNORECASE)
            cutter_line = None
            if m:
                cutter_line = m.group(1).strip()
            else:
                # try next line as cutter
                if i < len(lines):
                    cutter_line = lines[i].strip()
                    i += 1
            if cutter_line:
                ptoks = cutter_line.split()
                kind = ptoks[0].upper()
                params = parse_params(ptoks[1:])
                model.cuts.append(CutOp(target, Primitive(kind, params)))
            continue

        if key == "SLICE":
            # SLICE part along=Z at=2.5
            name = tokens[1]
            params = parse_params(tokens[2:])
            axis = str(params.get("along", "Z")).upper()
            at = float(params.get("at", 0.0))
            model.slices.append(SliceOp(name, axis, at))
            continue

        # unknown top-level
        # ignore silently

    return model


def scad_for_instance(inst: Instance, idx: int) -> str:
    # Wrap module call in transforms
    call = f"{inst.part_name}();"
    if inst.scale:
        call = f"scale([{inst.scale},{inst.scale},{inst.scale}]) {call}"
    if inst.rotate != (0, 0, 0):
        call = f"rotate([{inst.rotate[0]},{inst.rotate[1]},{inst.rotate[2]}]) {call}"
    if inst.translate != (0, 0, 0):
        call = f"translate([{inst.translate[0]},{inst.translate[1]},{inst.translate[2]}]) {call}"
    return f"// Instance {idx}: {inst.label or inst.part_name}\n{call}\n"


def scad_for_cut(op: CutOp, idx: int, x_offset: float) -> str:
    # Place each cut result apart via x_offset
    return (
        f"// Cut result {idx} for {op.target_part}\n"
        f"translate([{x_offset},0,0]) difference() {{\n"
        f"  {op.target_part}();\n"
        f"  {op.cutter_primitive.to_scad()}\n"
        f"}}\n"
    )


def scad_for_slice(op: SliceOp, idx: int, x_offset: float) -> str:
    # Create two intersections using big cubes as half-spaces along axis at 'at'
    axis = op.axis
    at = op.at
    # large cubes positioned to create half-spaces
    if axis == "Z":
        top = (
            f"intersection() {{ {op.target_part}(); "
            f"translate([{-BIG/2},{-BIG/2},{at}]) cube([{BIG},{BIG},{BIG}], center=false); }}"
        )
        bottom = (
            f"intersection() {{ {op.target_part}(); "
            f"translate([{-BIG/2},{-BIG/2},{-BIG}]) cube([{BIG},{BIG},{at+BIG}], center=false); }}"
        )
    elif axis == "Y":
        top = (
            f"intersection() {{ {op.target_part}(); "
            f"translate([{-BIG/2},{at},{-BIG/2}]) cube([{BIG},{BIG},{BIG}], center=false); }}"
        )
        bottom = (
            f"intersection() {{ {op.target_part}(); "
            f"translate([{-BIG/2},{-BIG},{-BIG/2}]) cube([{BIG},{at+BIG},{BIG}], center=false); }}"
        )
    else:  # X
        top = (
            f"intersection() {{ {op.target_part}(); "
            f"translate([{at},{-BIG/2},{-BIG/2}]) cube([{BIG},{BIG},{BIG}], center=false); }}"
        )
        bottom = (
            f"intersection() {{ {op.target_part}(); "
            f"translate([{-BIG},{-BIG/2},{-BIG/2}]) cube([{at+BIG},{BIG},{BIG}], center=false); }}"
        )
    # place them apart
    return (
        f"// Slice result {idx} for {op.target_part} along {axis} at {at}\n"
        f"translate([{x_offset},0,0]) {{ {top} }}\n"
        f"translate([{x_offset+80},0,0]) {{ {bottom} }}\n"
    )


def model_to_scad(model) -> str:
    out = ["// Generated by DSL v0.2 parser\n$fn=72; // smoothness\n"]
    # modules for parts
    for p in model.parts.values():
        out.append(p.module_scad())
        out.append("")
    # assembly: lay out instances, cuts, slices spaced along X
    out.append("module assembly(){")
    x = 0.0
    # instances
    for idx, inst in enumerate(model.instances, 1):
        out.append(f"  translate([{x},0,0]) {{")
        out.append("    " + scad_for_instance(inst, idx).replace("\\n", "\\n    ").rstrip())
        out.append("  }")
        x += 80.0
    # cuts
    for idx, c in enumerate(model.cuts, 1):
        out.append("  " + scad_for_cut(c, idx, x).replace("\\n", "\\n  ").rstrip())
        x += 120.0
    # slices
    for idx, s in enumerate(model.slices, 1):
        out.append("  " + scad_for_slice(s, idx, x).replace("\\n", "\\n  ").rstrip())
        x += 200.0
    out.append("}")
    out.append("assembly();")
    return "\\n".join(out)
