# prompt_to_dsl_v01.py
import re


def parse_prompt_to_dsl(prompt: str) -> str:
    """
    Very basic rule-based parser: Converts English prompt into v0.4 DSL
    """
    prompt = prompt.lower()

    # Special case: dumbbell (handle first!)
    def extract_param(param_name, text):
        m = re.search(rf"{param_name}\s*=*\s*(\d+(\.\d+)?)", text)
        if m:
            return float(m.group(1))
        return None

    if "dumbbell" in prompt:
        sphere_r = extract_param("radius", prompt) or 30
        rod_r = extract_param("rod radius", prompt) or extract_param("radius", prompt) or 10
        rod_len = extract_param("length", prompt) or 200
        z_offset = rod_len / 2
        dsl_lines = [
            f"PART S1:",
            f"    SPHERE radius={sphere_r} position=(0,0,{z_offset})",
            f"PART S2:",
            f"    SPHERE radius={sphere_r} position=(0,0,{-z_offset})",
            f"PART R:",
            f"    ROD radius={rod_r} length={rod_len} position=(0,0,0)",
            f"GROUP S1 S2 R AS dumbbell",
            f"USE dumbbell"
        ]
        return "\n".join(dsl_lines)

    dsl_lines = []

    # Keep track of whether to wrap in UNION
    in_union = False
    if "union" in prompt or "combine" in prompt:
        in_union = True
        dsl_lines.append("UNION {")

    # Match shapes
    shape_patterns = [
        ("cube", r"cube|block|box"),
        ("cylinder", r"cylinder|tube"),
        ("sphere", r"sphere|ball"),
        ("rod", r"rod|bar"),
        ("torus", r"torus|ring|donut")
    ]

    # Extract numbers like "radius 20", "20mm", "height 10"
    def extract_param(param_name, text):
        m = re.search(rf"{param_name}\s*=?\s*(\d+(\.\d+)?)", text)
        if m:
            return float(m.group(1))
        return None

    # Try to split into sentences for multiple shapes
    sentences = re.split(r"[.,;]", prompt)

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue

        for shape, pattern in shape_patterns:
            if re.search(pattern, sent):
                # Extract parameters
                params = []
                if shape in ["cube"]:
                    w = extract_param("width", sent) or extract_param("size", sent) or 10
                    h = extract_param("height", sent) or w
                    d = extract_param("depth", sent) or w
                    params.append(f"width={w}")
                    params.append(f"height={h}")
                    params.append(f"depth={d}")

                elif shape in ["cylinder"]:
                    r = extract_param("radius", sent) or 10
                    h = extract_param("height", sent) or 10
                    params.append(f"radius={r}")
                    params.append(f"height={h}")

                elif shape in ["sphere"]:
                    r = extract_param("radius", sent) or 10
                    params.append(f"radius={r}")

                elif shape in ["rod"]:
                    r = extract_param("radius", sent) or 5
                    l = extract_param("length", sent) or 50
                    params.append(f"radius={r}")
                    params.append(f"length={l}")

                elif shape in ["torus"]:
                    R = extract_param("major_radius", sent) or extract_param("radius", sent) or 20
                    r = extract_param("minor_radius", sent) or 5
                    params.append(f"major_radius={R}")
                    params.append(f"minor_radius={r}")

                # Position extraction
                pos_match = re.search(r"position\s*\(([-\d.,\s]+)\)", sent)
                if pos_match:
                    pos = pos_match.group(1)
                    params.append(f"position=({pos})")

                # Default position for separation (avoid overlap)
                if not any("position=" in p for p in params):
                    params.append(f"position=(0,0,{len(dsl_lines) * 50})")

                # Create DSL line
                dsl_lines.append(f"{shape.upper()} " + " ".join(params))
                break

    if in_union:
        dsl_lines.append("}")

    return "\n".join(dsl_lines)


if __name__ == "__main__":
    # Example usage
    prompt = "Make a dumbbell with two spheres of radius 30 mm connected by a rod of radius 10 mm and length 200 mm. Union them."
    dsl_code = parse_prompt_to_dsl(prompt)
    print("[Generated DSL]")
    print(dsl_code)
