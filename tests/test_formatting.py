from io import BytesIO
from pathlib import Path
import pytest
from PIL import Image, ImageDraw, ImageFont
from app.formatting import analyze_format

FONTS = [
    ('/System/Library/Fonts/Supplemental/Arial.ttf', '/System/Library/Fonts/Supplemental/Arial Bold.ttf'),
    ('/System/Library/Fonts/Supplemental/Times New Roman.ttf', '/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf'),
    ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
]
AVAILABLE = [pair for pair in FONTS if all(Path(path).exists() for path in pair)]


def artwork(pair, heading_bold=True, body_bold=False, size=35, confidence=1, color=0, mixed=False):
    image = Image.new('RGB', (2500, 180), 'white')
    draw = ImageDraw.Draw(image)
    words = []
    x = 15
    for index, text in enumerate(['GOVERNMENT','WARNING:','According','Surgeon','General,','health','problems.']):
        bold = (heading_bold and not (mixed and index == 1)) if index < 2 else body_bold
        font = ImageFont.truetype(pair[int(bold)], size)
        bounds = draw.textbbox((x, 30), text, font=font)
        draw.text((x, 30), text, font=font, fill=(color,color,color))
        words.append(dict(text=text, confidence=confidence, pixel_box=list(bounds)))
        x += draw.textlength(text + ' ', font=font)
    output = BytesIO()
    image.save(output, format='PNG')
    return output.getvalue(), words


@pytest.mark.parametrize('pair', AVAILABLE)
@pytest.mark.parametrize('size', [28,35,52])
def test_supported_bold_heading_matches(pair, size):
    image, words = artwork(pair, size=size)
    assert analyze_format(image, words)[0]['status'] == 'matches'


@pytest.mark.parametrize('pair', AVAILABLE)
def test_regular_heading_is_flagged(pair):
    image, words = artwork(pair, heading_bold=False)
    assert analyze_format(image, words)[0]['status'] == 'mismatch'


def test_mixed_heading_is_flagged():
    image, words = artwork(AVAILABLE[0], mixed=True)
    assert analyze_format(image, words)[0]['status'] == 'mismatch'


def test_bold_body_is_flagged():
    image, words = artwork(AVAILABLE[0], body_bold=True)
    assert analyze_format(image, words)[1]['status'] == 'mismatch'


@pytest.mark.parametrize('kwargs', [{'confidence':.4}, {'color':180}, {'size':9}])
def test_uncertain_images_do_not_pass(kwargs):
    image, words = artwork(AVAILABLE[0], **kwargs)
    assert analyze_format(image, words)[0]['status'] == 'needs_review'


def test_missing_coordinates_require_review():
    image, words = artwork(AVAILABLE[0])
    assert analyze_format(image, [])[0]['status'] == 'needs_review'
