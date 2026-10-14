"""Real image-to-result smoke test, not a mocked OCR performance claim."""
import argparse
import asyncio
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.main import prepare_image
from app.ocr import read_image
from app.rules import verify
from app.formatting import analyze_format
from app.refinement import refine_class_type


async def benchmark(repeats):
    cases = json.loads((ROOT / 'samples/manifest.json').read_text()) + json.loads((ROOT / 'samples/photo_manifest.json').read_text())
    rows = []
    for repeat in range(repeats):
        for case in cases:
            started = time.perf_counter()
            image = prepare_image((ROOT / 'samples' / case['image']).read_bytes())
            text, confidence, provider, words = await read_image(image)
            visual = analyze_format(image, words)
            result = verify(text, case['application'], confidence, visual, words=words)
            result = await refine_class_type([image],[(text,confidence,provider,words)],case['application'],result)
            elapsed = round((time.perf_counter() - started) * 1000)
            checks = {item['key']:item['status'] for item in result['checks']}
            row = dict(case=case['id'], repeat=repeat + 1, elapsed_ms=elapsed, status=result['status'],
                       expected_status=case['expected_status'], correct=result['status'] == case['expected_status'] and all(checks.get(key) == value for key, value in case['expected_checks'].items()),
                       confidence=confidence, checks=checks, extracted_text=text, provider=provider, visual_evidence=visual)
            rows.append(row)
            print(f"{case['id']:24} {elapsed:5} ms  {result['status']:13} expected={case['expected_status']} confidence={confidence:.2f}")
    timings = sorted(row['elapsed_ms'] for row in rows)
    result = dict(scope='Local image preparation + real OCR + pixel font-weight estimates + rules. Excludes HTTP upload/network/browser and Azure hosting.',
                  runs=len(rows), correct=sum(row['correct'] for row in rows),
                  median_ms=round(statistics.median(timings)), p95_ms=timings[max(0, __import__('math').ceil(len(timings) * .95) - 1)],
                  under_five_seconds=sum(value <= 5000 for value in timings), rows=rows)
    output = ROOT / 'docs/local-benchmark.json'
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(f"\n{result['correct']}/{len(rows)} expected per-check and overall outcomes. Median {result['median_ms']} ms; p95 {result['p95_ms']} ms.")
    print(f'Report: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repeats', type=int, default=1)
    asyncio.run(benchmark(parser.parse_args().repeats))
