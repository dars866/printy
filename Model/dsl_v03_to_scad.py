import re
from pathlib import Path

# ----------------------------
# Registry for parts
# ----------------------------
parts = {}
scad_modules = []

# ----------------------------
# Helpers
# ----------------------------
def parse_params(parts_list):
    params = {}
    for p in parts_list:
        if "=" in p:
            key, val = p.split("=")
            try:
                params[key] = float(val.strip("()"))
            except ValueError:
                params[key] = val
    return params

def parse_pos(val):
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", str(val))
    return f"[{','.join(nums)}]" if nums else "[0,0,0]"

def chamfer_wrap(scad_obj, chamfer):
    return f"minkowski(){{ {scad_obj} cylinder(r={chamfer},h=0.01); }}"

# ----------------------------
# SCAD Emitters
# ----------------------------
def emit_shape(cmd, params):
    cmd = cmd.upper()
    scad = ""
    chamfer = params.get("chamfer", None)

    if cmd == "CUBE":
        w = params.get("width", 10)
        d = params.get("depth", 10)
        h = params.get("height", 10)
        pos = parse_pos(params.get("position", "(0,0,0)"))
        shape = f"translate({pos}) cube([{w},{d},{h}], center=true);"
        scad = chamfer_wrap(shape, chamfer) if chamfer else shape

    elif cmd == "CYLINDER":
        r = params.get("radius", 5)
        h = params.get("height", 10)
        pos = parse_pos(params.get("position", "(0,0,0)"))
        shape = f"translate({pos}) cylinder(r={r}, h={h}, center=true);"
        scad = chamfer_wrap(shape, chamfer) if chamfer else shape

    elif cmd == "SPHERE":
        r = params.get("radius", 5)
        pos = parse_pos(params.get("position", "(0,0,0)"))
        scad = f"translate({pos}) sphere(r={r});"

    elif cmd == "CIRCLE":  # 2D shape for EXTRUDE
        r = params.get("radius", 5)
        pos = parse_pos(params.get("position", "(0,0)"))
        scad = f"translate({pos}) circle(r={r});"

    return scad

# ----------------------------
# DSL Parser
# ----------------------------
def parse_dsl(dsl):
    lines = dsl.strip().splitlines()
    current_part = None
    current_shapes = []
    in_extrude = False
    extrude_height = 0

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"): continue

        tokens = line.split()
        cmd = tokens[0].upper()

        if cmd == "PART" or cmd == "GROUP":
            if current_part:
                parts[current_part] = current_shapes
            current_part = tokens[1].rstrip(":")
            current_shapes = []

        elif cmd == "USE":
            part_name = tokens[1]
            params = parse_params(tokens[2:])
            pos = parse_pos(params.get("position", "(0,0,0)"))
            rot = parse_pos(params.get("rotate", "(0,0,0)"))
            current_shapes.append(f"translate({pos}) rotate({rot}) {part_name}();")

        elif cmd == "UNION" or cmd == "CUT" or cmd == "INTERSECT":
            a, b, _, new_name = tokens[1], tokens[2], tokens[3], tokens[4]
            op_map = {"UNION":"union", "CUT":"difference", "INTERSECT":"intersection"}
            scad_modules.append(f"module {new_name}(){{ {op_map[cmd]}(){{ {a}(); {b}(); }} }}")
            parts[new_name] = [f"{new_name}();"]

        elif cmd == "EXTRUDE":
            in_extrude = True
            extrude_height = parse_params(tokens[1:]).get("height", 10)

        elif cmd.endswith(":"):
            pass  # ignore labels without keyword

        elif in_extrude:
            shape_scad = emit_shape(cmd, parse_params(tokens[1:]))
            current_shapes.append(f"linear_extrude(height={extrude_height}) {{ {shape_scad} }}")
            in_extrude = False

        else:
            current_shapes.append(emit_shape(cmd, parse_params(tokens[1:])))

    if current_part:
        parts[current_part] = current_shapes

# ----------------------------
# SCAD Builder
# ----------------------------
def build_scad():
    scad_code = []
    for name, shapes in parts.items():
        body = "\n".join(shapes)
        scad_code.append(f"module {name}(){{ {body} }}")
    scad_code.extend(scad_modules)
    # Scene layout
    scene_calls = []
    x_off = 0
    for name in parts.keys():
        scene_calls.append(f"translate([{x_off},0,0]) {name}();")
        x_off += 150
    scad_code.append("\n".join(scene_calls))
    return "\n\n".join(scad_code)

# ----------------------------
# Example
# ----------------------------
if __name__ == "__main__":
    dsl_code = """
    PART base_plate:
        CUBE width=100 depth=60 height=5 chamfer=3

    PART pillar:
        CYLINDER radius=5 height=80

    UNION base_plate pillar AS plate_with_pillar

    GROUP final_assembly:
        USE plate_with_pillar
        EXTRUDE height=10:
            CIRCLE radius=30
    """
    parse_dsl(dsl_code)
    scad = build_scad()
    Path("v03_output.scad").write_text(scad)
    print("[+] Generated v03_output.scad")
