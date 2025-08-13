import sys
from prompty.prmpt_to_dsl_v01 import parse_prompt_to_dsl
from Model.dsl_v04_to_scad import parse as dsl_parse, to_scad

if __name__ == "__main__":
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        prompt = input("Enter your prompt: ")

    print("[Step 1] Converting prompt to DSL...")
    dsl_code = parse_prompt_to_dsl(prompt)
    print("[Generated DSL]\n" + dsl_code)

    print("[Step 2] Converting DSL to OpenSCAD...")
    model = dsl_parse(dsl_code)
    scad_code = to_scad(model)

    out_file = "output_from_prompt.scad"
    with open(out_file, "w") as f:
        f.write(scad_code)
    print(f"[Done] SCAD file written to {out_file}")

