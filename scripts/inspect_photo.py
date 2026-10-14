"""Inspect a real photo using exactly the app's image/OCR/formatting pipeline."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.main import prepare_image
from app.ocr import read_image
from app.formatting import analyze_format
from app.rules import verify
from app.refinement import refine_class_type


async def inspect(path, output):
    started = time.perf_counter()
    image = prepare_image(Path(path).read_bytes())
    text, confidence, provider, words = await read_image(image)
    application = dict(brand='PROSECCO', class_type='Italian Sparkling Wine', abv='11',
                       net_contents='750 mL', producer='Mionetto Spa', address='Valdobbiadene',
                       imported=True, country='Italy')
    result = verify(text, application, confidence, analyze_format(image, words), words=words)
    result = await refine_class_type([image],[(text,confidence,provider,words)],application,result)
    result.update(application=application, words=words, ocr_provider=provider,
                  elapsed_ms=round((time.perf_counter()-started)*1000))
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(result, indent=2)+'\n')
    print(text)
    print(f'\nConfidence: {confidence}; elapsed: {result["elapsed_ms"]} ms')
    print([(item['key'], item['status'], item['observed']) for item in result['checks']])
    print('Low-confidence words:', [(word['text'], word['confidence']) for word in words if word['confidence'] < .8])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('image')
    parser.add_argument('--output', default=str(ROOT / '.cache/photo-inspection.json'))
    args = parser.parse_args()
    asyncio.run(inspect(args.image, args.output))
