
# test_v03.py
# Generates a single SCAD file with many spaced test cases.
from pathlib import Path
import dsl_v03_fixed as dsl

def gen():
    cases = []

    # 1. Simple chamfered cube
    cases.append("""
PART t01_cube:
    CUBE width=20 depth=20 height=10 chamfer=2
USE t01_cube
""")

    # 2. Cylinder + chamfer
    cases.append("""
PART t02_cyl:
    CYLINDER radius=8 height=30 chamfer=1.5
USE t02_cyl
""")

    # 3. Rod oriented X
    cases.append("""
PART t03_rodx:
    ROD radius=3 length=60 position=(0,0,0) orientation=x
USE t03_rodx
""")

    # 4. Torus
    cases.append("""
PART t04_torus:
    TORUS major_radius=25 minor_radius=5 position=(0,0,0)
USE t04_torus
""")

    # 5. Extrude circle
    cases.append("""
PART t05_extrude:
    EXTRUDE height=15:
        CIRCLE radius=10
USE t05_extrude
""")

    # 6. Union of cube + cylinder
    cases.append("""
PART t06_cube:
    CUBE width=20 depth=20 height=10
PART t06_cyl:
    CYLINDER radius=9 height=10
UNION t06_cube t06_cyl AS t06_union
USE t06_union
""")

    # 7. Cut cylinder from cube (difference)
    cases.append("""
PART t07_cube:
    CUBE width=30 depth=30 height=15
PART t07_cyl:
    CYLINDER radius=10 height=20
CUT t07_cube t07_cyl AS t07_cut
USE t07_cut
""")

    # 8. Intersect cube & sphere
    cases.append("""
PART t08_cube:
    CUBE width=30 depth=30 height=30
PART t08_sph:
    SPHERE radius=18
INTERSECT t08_cube t08_sph AS t08_inter
USE t08_inter
""")

    # 9. Group using USE
    cases.append("""
PART t09_a:
    CUBE width=20 depth=10 height=10 position=(0,0,0)
PART t09_b:
    CYLINDER radius=5 height=20 position=(0,0,10)
GROUP t09_grp:
    USE t09_a
    USE t09_b
USE t09_grp
""")

    # 10. Multiple USE with transforms
    cases.append("""
PART t10_block:
    CUBE width=10 depth=10 height=10
USE t10_block position=(0,0,0)
USE t10_block position=(0,0,15) rotate=(0,0,45)
USE t10_block position=(0,0,30) rotate=(0,0,90)
""")

    # 11. Rod Y + Torus union
    cases.append("""
PART t11_rody:
    ROD radius=2 length=40 orientation=y
PART t11_torus:
    TORUS major_radius=15 minor_radius=3
UNION t11_rody t11_torus AS t11_join
USE t11_join
""")

    # 12. Pillar on chamfered base
    cases.append("""
PART t12_base:
    CUBE width=40 depth=40 height=6 chamfer=2
PART t12_pillar:
    CYLINDER radius=6 height=30 position=(0,0,3)
UNION t12_base t12_pillar AS t12_plate
USE t12_plate
""")

    full = "\n\n".join(cases)
    model = dsl.parse(full)
    scad = dsl.to_scad(model)
    out = Path("unit_tests_v03_output.scad")
    out.write_text(scad)
    return out

if __name__ == "__main__":
    out = gen()
    print("[+] Wrote", out.resolve())
