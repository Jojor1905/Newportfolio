#!/usr/bin/env python3
"""Detect white paper against a brown/tan scan surround; save a lossless PNG.

Requires Pillow: python3 -m pip install Pillow
Usage: python3 scripts/crop_certificate.py INPUT OUTPUT.png [--inset 5]
The input is never changed. No scan-specific crop coordinates are stored.
Designed for approximately axis-aligned scans with white paper margins.
"""
import argparse
import json
import statistics
from pathlib import Path

from PIL import Image, ImageOps


def quantile(values, fraction):
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def detect_paper(image):
    width, height = image.size
    if min(width, height) < 100:
        raise ValueError('Scan is too small for reliable boundary detection.')
    pixels = image.load()
    step = max(1, int((width * height / 40000) ** 0.5))
    neutral = [min(pixels[x, y])
               for y in range(height // 5, height * 4 // 5, step)
               for x in range(width // 5, width * 4 // 5, step)
               if max(pixels[x, y]) - min(pixels[x, y]) < 35]
    if not neutral:
        raise ValueError('No neutral white paper found in the central scan area.')
    paper_white = quantile(neutral, 0.85)
    brightness_floor = max(170, paper_white * 0.82)
    color_spread = min(30, paper_white * 0.12)
    run_length = max(5, round(min(width, height) * 0.006))

    def is_paper(x, y):
        pixel = pixels[x, y]
        return min(pixel) >= brightness_floor and max(pixel) - min(pixel) <= color_spread

    def detect_edge(axis, reverse):
        depth_size, lane_size = (width, height) if axis == 'x' else (height, width)
        # Many independent scan lines avoid mistaking text or a signature for an edge.
        lanes = sorted(set(round(lane_size * (0.1 + 0.8 * i / 120)) for i in range(121)))
        offsets = []
        for lane in lanes:
            streak = 0
            for depth in range(int(depth_size * 0.4)):
                position = depth_size - 1 - depth if reverse else depth
                x, y = (position, lane) if axis == 'x' else (lane, position)
                streak = streak + 1 if is_paper(x, y) else 0
                if streak >= run_length:
                    offsets.append(depth - run_length + 1)
                    break
        if len(offsets) < len(lanes) * 0.6:
            raise ValueError('Paper boundary is ambiguous; inspect or straighten this scan manually.')
        low, high = quantile(offsets, 0.05), quantile(offsets, 0.95)
        if high - low > depth_size * 0.06:
            raise ValueError('Paper is too skewed or its edge is obstructed; straighten before cropping.')
        # Reject isolated damaged/noisy lanes, then move inside the surviving edge.
        median = statistics.median(offsets)
        deviation = statistics.median(abs(offset - median) for offset in offsets)
        reliable = [offset for offset in offsets
                    if abs(offset - median) <= max(run_length * 2, deviation * 6)]
        return max(reliable)

    left, right = detect_edge('x', False), width - detect_edge('x', True)
    top, bottom = detect_edge('y', False), height - detect_edge('y', True)
    if (right - left) * (bottom - top) < width * height * 0.4:
        raise ValueError('Detected paper is unexpectedly small; refusing a potentially destructive crop.')
    return (left, top, right, bottom)


def crop_certificate(source, output, inset=5):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError('Output must differ from the source; keep the raw scan as backup.')
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}. Choose a new filename.')
    if output.suffix.lower() != '.png':
        raise ValueError('Use a .png output to preserve pixels without JPEG recompression.')
    if not 0 <= inset <= 10:
        raise ValueError('Safety inset must be between 0 and 10 pixels.')
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original).convert('RGB')
    detected = detect_paper(image)
    left, top, right, bottom = detected
    box = (left + inset, top + inset, right - inset, bottom - inset)
    if box[2] <= box[0] or box[3] <= box[1]:
        raise ValueError('Safety inset would remove the paper.')
    cropped = image.crop(box)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        cropped.save(stream, format='PNG')
    report = dict(source=str(source), output=str(output), before=image.size,
                  detected_paper_box=detected, inset=inset, crop_box=box,
                  after=cropped.size)
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--inset', type=int, default=5,
                        help='Small inward margin after boundary detection (0-10px; default 5).')
    args = parser.parse_args()
    crop_certificate(args.source, args.output, args.inset)
