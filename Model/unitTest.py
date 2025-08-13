import unittest
from pathlib import Path
from Model.DSLConvertor import dsl_to_openscad

class TestDSLtoOpenSCAD(unittest.TestCase):

    def setUp(self):
        self.outputs = []

    def add_case(self, dsl, x_offset):
        scad_code = dsl_to_openscad(dsl)
        # Add a translation so objects are apart
        wrapped_code = f"translate([{x_offset},0,0]) {{\n{scad_code}\n}}\n"
        self.outputs.append(wrapped_code)

    def test_generate_all(self):
        # 25 test cases, each with increasing X offset (50 units apart)
        cases = [
            "CUBE width=10 height=10 depth=10",
            "CUBE width=15 height=5 depth=20",
            "CYLINDER radius=5 height=20",
            "CYLINDER radius=10 height=40",
            "SPHERE radius=8",
            "SPHERE radius=12",
            "ROD radius=3 length=30",
            "ROD radius=6 length=60",
            "TORUS major_radius=15 minor_radius=3",
            "TORUS major_radius=20 minor_radius=5",
            "CUBE width=5 height=15 depth=5",
            "CYLINDER radius=4 height=10",
            "SPHERE radius=5",
            "ROD radius=2 length=20",
            "TORUS major_radius=10 minor_radius=2",
            "CUBE width=8 height=8 depth=20",
            "CYLINDER radius=7 height=15",
            "SPHERE radius=9",
            "ROD radius=4 length=25",
            "TORUS major_radius=12 minor_radius=4",
            "CUBE width=20 height=10 depth=5",
            "CYLINDER radius=15 height=10",
            "SPHERE radius=6",
            "ROD radius=5 length=15",
            "TORUS major_radius=18 minor_radius=6",
        ]

        for i, case in enumerate(cases):
            self.add_case(case, i * 50)  # 50 units apart

        # Combine all cases into a single SCAD file
        final_scad = "// Auto-generated test file with 25 shapes\n" + "".join(self.outputs)

        out_file = Path("test_output.scad")
        out_file.write_text(final_scad)
        print(f"[+] Test OpenSCAD file generated at: {out_file.resolve()}")

if __name__ == "__main__":
    unittest.main()
