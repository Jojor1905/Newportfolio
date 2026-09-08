#!/usr/bin/env python3
"""Extract the centered blue Allmass logo and wordmark from a certificate scan."""
from pathlib import Path
from PIL import Image, ImageOps


def extract(source, output, margin=28):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError("Output must differ from source")
    if output.exists():
        raise FileExistsError(output)
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    width, height = image.size
    left_bound, right_bound = width * 0.28, width * 0.72
    top_bound, bottom_bound = height * 0.04, height * 0.30
    blue = []
    for y in range(round(top_bound), round(bottom_bound)):
        for x in range(round(left_bound), round(right_bound)):
            r, g, b = image.getpixel((x, y))
            if b > 105 and b > r * 1.35 and b > g * 1.12 and r < 150:
                blue.append((x, y))
    if not blue:
        raise ValueError("No centered blue Allmass logo pixels found")
    x0 = max(0, min(x for x, _ in blue) - margin)
    y0 = max(0, min(y for _, y in blue) - margin)
    x1 = min(width, max(x for x, _ in blue) + margin + 1)
    y1 = min(height, max(y for _, y in blue) + margin + 1)
    if x1 - x0 < width * .04 or y1 - y0 < height * .02:
        raise ValueError("Detected logo is unexpectedly small")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        image.crop((x0, y0, x1, y1)).save(stream, "PNG")
    print({"source": str(source), "output": str(output), "before": image.size,
           "crop_box": (x0, y0, x1, y1), "after": (x1-x0, y1-y0)})


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--margin", type=int, default=28)
    args = parser.parse_args()
    extract(args.source, args.output, args.margin)
