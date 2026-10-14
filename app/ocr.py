"""Real OCR: local Apple Vision on macOS or Tesseract on Linux/Azure."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]


class OCRError(Exception):
    pass


def provider_name():
    configured = os.getenv('OCR_PROVIDER', 'auto')
    if configured == 'auto':
        return 'apple_vision' if (ROOT / '.cache/vision-ocr').exists() else 'tesseract'
    return configured


async def read_image(image_bytes):
    provider = provider_name()
    with tempfile.TemporaryDirectory(prefix='label-ocr-') as directory:
        path = Path(directory) / 'label.png'
        path.write_bytes(image_bytes)
        if provider == 'apple_vision':
            binary = ROOT / '.cache/vision-ocr'
            if not binary.exists():
                raise OCRError('Local OCR is not prepared. Run the macOS setup command in the README.')
            command = [str(binary), str(path)]
        elif provider == 'tesseract':
            binary = shutil.which('tesseract')
            if not binary:
                raise OCRError('OCR is unavailable. Install Tesseract or run the macOS setup command in the README.')
            command = [binary, str(path), 'stdout', '-l', 'eng', '--psm', '11', 'tsv']
        else:
            raise OCRError('Unsupported OCR_PROVIDER. Choose auto, apple_vision, or tesseract.')
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=8)
        except (asyncio.TimeoutError, asyncio.CancelledError) as error:
            process.kill()
            await process.wait()
            if isinstance(error, asyncio.CancelledError):
                raise
            raise OCRError('Image reading timed out. Try a clearer, cropped label image.') from error
        if process.returncode:
            raise OCRError('Image reading failed. Try a clearer image or check the OCR setup.')
        if provider == 'apple_vision':
            result = json.loads(stdout)
            return result['text'], result['confidence'], provider, result.get('words', [])
        import csv
        import io
        lines = {}
        words = []
        confidences = []
        for word in csv.DictReader(io.StringIO(stdout.decode()), delimiter='\t'):
            if word.get('text', '').strip():
                key = tuple(word[field] for field in ('page_num', 'block_num', 'par_num', 'line_num'))
                lines.setdefault(key, []).append(word['text'])
                confidences.append(max(0, float(word['conf'])) / 100)
                words.append(dict(text=word['text'], confidence=confidences[-1],
                                  pixel_box=[int(word['left']), int(word['top']), int(word['left']) + int(word['width']), int(word['top']) + int(word['height'])]))
        return '\n'.join(' '.join(line) for line in lines.values()), min(confidences, default=0), provider, words
