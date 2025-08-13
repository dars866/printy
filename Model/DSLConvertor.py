import re
import subprocess
from pathlib import Path

# -------------------
# DSL to OpenSCAD Map
# -------------------
def dsl_to_openscad(dsl_text):
    scad_lines = []
    objects = {}

    for line in dsl_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        tokens = line.split()
        cmd = tokens[0].upper()

        if cmd == "CUBE":
            params = parse_params(tokens[1:])
            w = params.get("width", 10)
            h = params.get("height", 10)
            d = params.get("depth", 10)
            pos = parse_pos(params.get("position", "(0,0,0)"))
            scad_lines.append(
                f"translate({pos}) cube([{w},{d},{h}], center=true);"
            )

        elif cmd == "CYLINDER":
            params = parse_params(tokens[1:])
            r = params.get("radius", 10)
            h = params.get("height", 10)
            pos = parse_pos(params.get("position", "(0,0,0)"))
            scad_lines.append(
                f"translate({pos}) cylinder(r={r}, h={h}, center=true);"
            )

        elif cmd == "SPHERE":
            params = parse_params(tokens[1:])
            r = params.get("radius", 10)
            pos = parse_pos(params.get("position", "(0,0,0)"))
            scad_lines.append(
                f"translate({pos}) sphere(r={r});"
            )

        elif cmd == "ROD":
            params = parse_params(tokens[1:])
            r = params.get("radius", 5)
            length = params.get("length", 50)
            pos = parse_pos(params.get("position", "(0,0,0)"))
            scad_lines.append(
                f"translate({pos}) cylinder(r={r}, h={length}, center=true);"
            )

        elif cmd == "TORUS":
            params = parse_params(tokens[1:])
            R = params.get("major_radius", 20)
            r = params.get("minor_radius", 5)
            pos = parse_pos(params.get("position", "(0,0,0)"))
            scad_lines.append(
                f"translate({pos}) rotate_extrude() translate([{R},0,0]) circle(r={r});"
            )

        else:
            print(f"Unknown command: {cmd}")

    return "\n".join(scad_lines)


# -------------------
# Helper Functions
# -------------------
def parse_params(parts):
    params = {}
    for p in parts:
        if "=" in p:
            key, val = p.split("=")
            try:
                params[key] = float(val.strip("()"))
            except ValueError:
                params[key] = val
    return params

def parse_pos(pos_str):
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", pos_str)
    return f"[{','.join(nums)}]"

# -------------------
# Main Usage
# -------------------
if __name__ == "__main__":
    # Example DSL
    dsl_code = """
    # Dumbbell Example
    CYLINDER radius=30 height=15 position=(0,0,0)
    CYLINDER radius=30 height=15 position=(200,0,0)
    ROD radius=10 length=200 position=(0,0,0)
    """

    scad_code = dsl_to_openscad(dsl_code)

    # Save .scad file
    scad_file = Path("output.scad")
    scad_file.write_text(scad_code)
    print(f"[+] OpenSCAD file generated: {scad_file.resolve()}")

    # Optional: Export to STL using OpenSCAD CLI
    # Make sure you have OpenSCAD installed and added to PATH
    stl_file = Path("output.stl")
    subprocess.run([
        "openscad",
        "-o", str(stl_file),
        str(scad_file)
    ])
    print(f"[+] STL file generated: {stl_file.resolve()}")
