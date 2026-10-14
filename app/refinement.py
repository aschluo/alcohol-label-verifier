"""One bounded, unseeded image reread for near-matching class/type text."""
import asyncio
from io import BytesIO
import re

from PIL import Image

from .ocr import OCRError, read_image
from .rules import normalize, possible_class_reading_error, verify


def class_crop(image_bytes, words, phrase):
    tokens = [normalize(word.get('text','')) for word in words]
    joined = ' '.join(tokens)
    match = re.search(r'(?<!\w)' + re.escape(normalize(phrase)) + r'(?!\w)', joined)
    if not match:
        return None
    relevant = []
    cursor = 0
    with Image.open(BytesIO(image_bytes)) as image:
        for word,token in zip(words,tokens):
            end = cursor + len(token)
            if cursor < match.end() and end > match.start():
                if 'pixel_box' in word:
                    relevant.append(word['pixel_box'])
                elif 'box' in word:
                    x1,y1,x2,y2 = word['box']
                    relevant.append([x1*image.width,y1*image.height,x2*image.width,y2*image.height])
                else:
                    return None
            cursor = end + 1
        if not relevant:
            return None
        left,top = min(box[0] for box in relevant), min(box[1] for box in relevant)
        right,bottom = max(box[2] for box in relevant), max(box[3] for box in relevant)
        height = bottom-top
        if height <= 0 or right <= left:
            return None
        # Padding includes letters clipped by the initial word segmentation.
        horizontal,vertical = max(24,round(height*1.4)), max(8,round(height*.5))
        bounds = (max(0,int(left)-horizontal), max(0,int(top)-vertical),
                  min(image.width,int(right)+horizontal),min(image.height,int(bottom)+vertical))
        crop = image.crop(bounds)
        if crop.width < 8 or crop.height < 8:
            return None
        crop = crop.resize((crop.width*2,crop.height*2),Image.Resampling.LANCZOS)
        crop.thumbnail((2200,1200))
        output = BytesIO()
        crop.save(output,format='PNG')
        return output.getvalue()


async def refine_class_type(images, readings, application, result, recognize=None):
    initial = next(item for item in result['checks'] if item['key'] == 'class_type')
    if not possible_class_reading_error(initial['expected'],initial['observed']):
        return result
    recognize = recognize or read_image
    for image,reading in zip(images,readings):
        if len(reading) < 4:
            continue
        crop = await asyncio.to_thread(class_crop,image,reading[3],initial['observed'])
        if crop is None:
            continue
        try:
            reread = await asyncio.wait_for(recognize(crop),timeout=2)
        except (OCRError,asyncio.TimeoutError):
            initial['reason'] += ' The targeted second read was unavailable or timed out.'
            return result
        verdict = verify(reread[0],{'class_type':initial['expected']},reread[1],words=reread[3] if len(reread)>3 else None)
        refined = next(item for item in verdict['checks'] if item['key'] == 'class_type')
        attempt = dict(field='class_type',initial_text=initial['observed'],reread_text=reread[0],
                       result=refined['status'],method='Padded, enlarged image crop; no expected text supplied to OCR')
        result['reading_attempts'] = [attempt]
        if refined['status'] == 'matches':
            # Keep the primary transcript intact; report the separate pixel read.
            matched = re.search(r'(?<!\w)'+re.escape(initial['expected']).replace(r'\ ',r'\s+')+r'(?!\w)',reread[0],re.I)
            initial.update(status='matches',observed=matched.group() if matched else refined['observed'],
                           initial_observed=attempt['initial_text'],ocr_confidence=refined['ocr_confidence'],
                           reason='Matches in a targeted second OCR reading of the label image. The first reading omitted or misread a character.')
        else:
            initial.update(status='needs_review',reason='The targeted second read did not resolve the small text difference. Confirm the class/type on the image.')
        result['status'] = ('mismatch' if any(item['status']=='mismatch' for item in result['checks']) else
                            'needs_review' if any(item['status']=='needs_review' for item in result['checks']) else 'matches')
        return result
    return result
