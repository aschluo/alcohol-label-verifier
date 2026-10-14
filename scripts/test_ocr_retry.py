"""Evaluate unseeded OCR on a crop of the real-photo class/type region."""
import asyncio
from io import BytesIO
import json
from pathlib import Path
import sys
from PIL import Image, ImageOps, ImageEnhance

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.main import prepare_image
from app.ocr import read_image


async def run():
    capture = json.loads((ROOT/'tests/fixtures/prosecco_ocr.json').read_text())
    image = Image.open(BytesIO(prepare_image((ROOT/'samples/prosecco_photo.jpg').read_bytes())))
    words = capture['words']
    index = next(i for i,word in enumerate(words) if word['text'] == 'talian')
    boxes = [word['box'] for word in words[index:index+3]]
    bounds = (int(min(box[0] for box in boxes)*image.width)-40,
              int(min(box[1] for box in boxes)*image.height)-15,
              int(max(box[2] for box in boxes)*image.width)+40,
              int(max(box[3] for box in boxes)*image.height)+15)
    crop = image.crop(bounds)
    variants = [('crop',crop), ('enlarged',crop.resize((crop.width*2,crop.height*2))),
                ('grayscale',ImageOps.autocontrast(crop.convert('L')).resize((crop.width*2,crop.height*2))),
                ('inverted',ImageOps.invert(ImageOps.autocontrast(crop.convert('L'))).resize((crop.width*2,crop.height*2)))]
    for name,variant in variants:
        output = BytesIO()
        variant.save(output,format='PNG')
        text,confidence,provider,words = await read_image(output.getvalue())
        print(name,repr(text),confidence,flush=True)


if __name__ == '__main__':
    asyncio.run(run())
