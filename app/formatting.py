"""Conservative pixel-template font-weight estimates for supported clean artwork.

This reads image pixels and OCR coordinates, never fixture identifiers or fonts
declared by the uploader. Unsupported fonts/photos remain Needs review.
"""
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import re

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat

FONT_PAIRS = [
    ('/System/Library/Fonts/Supplemental/Arial.ttf', '/System/Library/Fonts/Supplemental/Arial Bold.ttf'),
    ('/System/Library/Fonts/Supplemental/Times New Roman.ttf', '/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf'),
    ('/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf', '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf'),
    ('/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf', '/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf'),
    ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
]


@lru_cache(maxsize=4096)
def template(text, path, size=64):
    font = ImageFont.truetype(path, size)
    box = font.getbbox(text)
    image = Image.new('L', (box[2] - box[0] + 8, box[3] - box[1] + 8))
    ImageDraw.Draw(image).text((4 - box[0], 4 - box[1]), text, font=font, fill=255)
    image = image.point(lambda value: 255 if value >= 128 else 0)
    return image.crop(image.getbbox())


def word_crop(image, word):
    if 'pixel_box' in word:
        x1, y1, x2, y2 = word['pixel_box']
    else:
        x1, y1, x2, y2 = word['box']
        x1, x2, y1, y2 = x1 * image.width, x2 * image.width, y1 * image.height, y2 * image.height
    # OCR boxes sometimes include whitespace or clip antialiased edges.
    bounds = (max(0, int(x1)-1), max(0, int(y1)-1), min(image.width, int(x2)+2), min(image.height, int(y2)+2))
    if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
        return None
    crop = image.crop(bounds)
    if crop.width < 3 or crop.height < 12:
        return None
    histogram = crop.histogram()
    total = sum(histogram)
    low = next((i for i in range(256) if sum(histogram[:i+1]) >= total * .08), 0)
    high = next((i for i in range(256) if sum(histogram[:i+1]) >= total * .85), 255)
    if high - low < 100:
        return None
    mask = crop.point(lambda value: 255 if value < (low + high) / 2 else 0)
    bounds = mask.getbbox()
    return mask.crop(bounds) if bounds else None


def font_weight(image, word):
    if word.get('confidence', 0) < .9:
        return {'style': 'unknown'}
    crop = word_crop(image, word)
    if crop is None:
        return {'style': 'unknown'}
    scores = {'regular': 0.0, 'bold': 0.0}
    for regular, bold in FONT_PAIRS:
        for style, path in [('regular', regular), ('bold', bold)]:
            if not Path(path).is_file():
                continue
            reference = template(word['text'], path)
            # Large aspect-ratio differences indicate another font or a clipped box.
            ratio = (reference.width / reference.height) / (crop.width / crop.height)
            if not .88 <= ratio <= 1.12:
                continue
            estimated_size = round(64 * crop.height / reference.height)
            for size in range(max(8, estimated_size-2), min(160, estimated_size+2)+1):
                rendered = template(word['text'], path, size)
                rendered = rendered.resize(crop.size, Image.Resampling.LANCZOS).point(lambda value: 255 if value >= 128 else 0)
                intersection = ImageStat.Stat(ImageChops.multiply(rendered, crop)).sum[0]
                denominator = ImageStat.Stat(rendered).sum[0] + ImageStat.Stat(crop).sum[0]
                score = 2 * intersection / denominator if denominator else 0
                scores[style] = max(scores[style], score)
    best = max(scores, key=scores.get)
    margin = scores[best] - scores['regular' if best == 'bold' else 'bold']
    style = best if scores[best] >= .90 and margin >= .055 else 'unknown'
    return dict(style=style, fit=round(scores[best], 3), margin=round(margin, 3))


def analyze_format(image_bytes, words):
    result = dict(key='warning_bold', label='Warning heading bold', status='needs_review',
                  expected='GOVERNMENT WARNING: in bold type', observed='',
                  reason='Font weight could not be established from this image. Upload clear artwork or inspect the heading.', evidence=[])
    start = next((i for i in range(len(words)-1) if words[i]['text'].upper() == 'GOVERNMENT' and words[i+1]['text'].upper().rstrip(':') == 'WARNING'), None)
    if start is None:
        return [result, dict(key='warning_body_style', label='Warning body font', status='needs_review',
                             expected='Warning body in nonbold type', observed='',
                             reason='Warning body coordinates are unavailable; inspect the image.', evidence=[])]
    with Image.open(BytesIO(image_bytes)) as source:
        image = source.convert('L')
        heading = [font_weight(image, word) for word in words[start:start+2]]
        result['evidence'] = heading
        styles = [item['style'] for item in heading]
        if all(style == 'bold' for style in styles):
            result.update(status='matches', observed='Both heading words estimated as bold',
                          reason='Image pixels closely match supported bold-font templates. This is a font-weight estimate for clear artwork.')
        elif 'regular' in styles:
            result.update(status='mismatch', observed='Heading contains a word estimated as nonbold',
                          reason='Image pixels closely match a regular-font template. The government warning heading must be bold; confirm on the image.')
        body = []
        for word in words[start+2:]:
            if len(re.sub(r'\W', '', word['text'])) >= 4:
                body.append((word['text'], font_weight(image, word)))
            if word['text'].casefold().rstrip('.') == 'problems':
                break
        bold_words = [text for text, item in body if item['style'] == 'bold']
        # A positive regular-body result would require every character, including
        # small punctuation and numbering. Sampling only supports a failure flag.
        body_result = dict(key='warning_body_style', label='Warning body font', status='needs_review',
                           expected='Warning body in nonbold type', observed='',
                           reason='No confident bold words found in the sampled body. Confirm the entire body is nonbold.',
                           evidence=[dict(text=text, **item) for text, item in body])
        if bold_words:
            body_result.update(status='mismatch', observed='Words estimated as bold: ' + ', '.join(bold_words),
                               reason='The body may not be bold. Confirm these image-based font-weight findings on the label.')
        return [result, body_result]
