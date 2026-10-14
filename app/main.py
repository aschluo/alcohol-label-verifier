import asyncio
from io import BytesIO
import json
from pathlib import Path
import time

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError

from .ocr import OCRError, provider_name, read_image
from .rules import verify
from .formatting import analyze_format
from .refinement import refine_class_type

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title='Label Check', version='0.2.0')
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
app.mount('/samples', StaticFiles(directory=ROOT / 'samples'), name='samples')
ocr_slots = asyncio.Semaphore(2)
Image.MAX_IMAGE_PIXELS = 20_000_000


@app.get('/')
def home():
    return FileResponse(ROOT / 'static/index.html')


@app.get('/api/health')
def health():
    return {'status': 'ok', 'ocr_provider': provider_name()}


@app.get('/api/samples')
def samples():
    controlled = json.loads((ROOT / 'samples/manifest.json').read_text())
    return controlled + json.loads((ROOT / 'samples/photo_manifest.json').read_text())


def prepare_image(data):
    try:
        image = Image.open(BytesIO(data))
        if image.format not in {'JPEG', 'PNG', 'WEBP'}:
            raise HTTPException(415, 'Use a JPG, PNG, or WebP image.')
        if image.width * image.height > Image.MAX_IMAGE_PIXELS:
            raise HTTPException(400, 'Use an image under 20 megapixels.')
        image.load()
        image = ImageOps.exif_transpose(image).convert('RGB')
        image.thumbnail((2200, 2200))
        output = BytesIO()
        image.save(output, format='PNG')
        return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise HTTPException(400, 'This image could not be read. Use a valid image under 20 megapixels.') from error


@app.post('/api/verify')
async def verify_label(images: list[UploadFile] = File(...), application: str = Form(...)):
    started = time.perf_counter()
    try:
        expected = json.loads(application)
        if not isinstance(expected, dict):
            raise ValueError()
        if any(not isinstance(value, (str, bool)) for value in expected.values()):
            raise ValueError()
        if any(len(str(value)) > 500 for value in expected.values()):
            raise ValueError()
        if 'imported' in expected and not isinstance(expected['imported'], bool):
            raise ValueError()
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(422, 'Application fields must be a JSON object containing text fields and an imported boolean.')
    if not 1 <= len(images) <= 6:
        raise HTTPException(400, 'Upload between one and six images for one application.')
    prepared = []
    for upload in images:
        data = await upload.read(10 * 1024 * 1024 + 1)
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(413, 'Each image must be 10 MB or smaller.')
        prepared.append(await asyncio.to_thread(prepare_image, data))

    async def recognize(data):
        async with ocr_slots:
            return await read_image(data)

    try:
        results = await asyncio.gather(*(recognize(data) for data in prepared))
    except OCRError as error:
        raise HTTPException(503, str(error)) from error
    text = '\n'.join(result[0] for result in results)
    confidence = min(result[1] for result in results)
    visual_checks = None
    for data, ocr in zip(prepared, results):
        if len(ocr) > 3:
            findings = await asyncio.to_thread(analyze_format, data, ocr[3])
            if any(finding.get('evidence') for finding in findings):
                if visual_checks is not None:
                    # Multiple warning statements require checking each separately.
                    for finding in visual_checks:
                        finding.update(status='needs_review', reason='Multiple warning headings were found. Inspect the formatting of each warning.')
                    break
                visual_checks = findings
    if visual_checks is None:
        visual_checks = analyze_format(prepared[0], [])
    words = [word for ocr in results if len(ocr) > 3 for word in ocr[3]]
    result = verify(text, expected, confidence, visual_checks, words=words)
    result = await refine_class_type(prepared,results,expected,result,recognize)
    result['elapsed_ms'] = round((time.perf_counter() - started) * 1000)
    result['ocr_provider'] = results[0][2]
    result['image_count'] = len(images)
    return result
