"""Controlled raster labels: intentional defects have known ground truth."""
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.rules import WARNING

FONT_DIRS = [Path('/System/Library/Fonts/Supplemental'), Path('/usr/share/fonts/truetype/dejavu')]


def font(size, bold=False):
    names = ['Arial Bold.ttf', 'DejaVuSans-Bold.ttf'] if bold else ['Arial.ttf', 'DejaVuSans.ttf']
    for directory in FONT_DIRS:
        for name in names:
            if (directory / name).exists():
                return ImageFont.truetype(str(directory / name), size)
    return ImageFont.load_default(size=size)


APPLICATION = dict(brand='Old Tom Distillery', class_type='Kentucky Straight Bourbon Whiskey',
                   abv='45', net_contents='750 mL', producer='Old Tom Distillery LLC',
                   address='Frankfort, Kentucky', imported=False, country='')
CASES = [
    ('correct', 'Correct text and matching fields', 'All text checks should match. Visual formatting still needs review.', {}, 'needs_review'),
    ('brand_case', 'Brand capitalization difference', "STONE'S THROW on the image matches Stone's Throw in the application.", {'brand': "STONE'S THROW"}, 'needs_review'),
    ('abv_mismatch', 'Alcohol content mismatch', 'Label says 40% ABV; application says 45%.', {'abv': '40'}, 'mismatch'),
    ('missing_warning', 'Missing government warning', 'No warning is printed on this label.', {'warning': ''}, 'mismatch'),
    ('warning_wording', 'Changed warning wording', 'The warning says may cause birth defects rather than the required wording.', {'warning': WARNING.replace('because of the risk of birth defects', 'because it may cause birth defects')}, 'mismatch'),
    ('warning_case', 'Warning heading in title case', 'Government Warning: must be uppercase.', {'warning': WARNING.replace('GOVERNMENT WARNING:', 'Government Warning:')}, 'mismatch'),
    ('warning_not_bold', 'Warning heading without bold type', 'The text matches, but the heading is not bold. The image-based check should flag the heading.', {'bold': False}, 'mismatch'),
    ('warning_mixed_bold', 'Only one heading word is bold', 'GOVERNMENT is bold, but WARNING: is regular. Both words must be bold.', {'mixed_bold': True}, 'mismatch'),
    ('warning_body_bold', 'Warning body in bold type', 'The heading is bold, but the warning body is also bold. The body should be nonbold.', {'body_bold': True}, 'mismatch'),
    ('volume_equivalent', 'Equivalent net contents units', '0.75 L on the label is equivalent to 750 mL in the application.', {'net_contents': '0.75 L'}, 'needs_review'),
    ('missing_punctuation', 'Warning punctuation missing', 'The comma after machinery is removed.', {'warning': WARNING.replace('machinery,', 'machinery')}, 'mismatch'),
    ('blurred', 'Blurry label photo', 'A heavily blurred image should require review rather than confidently pass.', {'blur': True}, 'needs_review'),
]


def generate():
    destination = ROOT / 'samples'
    destination.mkdir(exist_ok=True)
    manifest = []
    for case_id, title, description, changes, status in CASES:
        fields = {**APPLICATION, **changes}
        image = Image.new('RGB', (1500, 1600), '#fcfaf2')
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((40, 40, 1460, 1560), radius=14, outline='#49624a', width=4)
        draw.text((110, 110), fields['brand'].upper(), font=font(68, True), fill='#263e31')
        draw.line((110, 220, 1390, 220), fill='#49624a', width=3)
        draw.text((110, 280), fields['class_type'], font=font(47), fill='#263e31')
        draw.text((110, 410), f"{fields['abv']}% Alc./Vol. ({int(fields['abv']) * 2} Proof)", font=font(48, True), fill='#263e31')
        draw.text((110, 510), fields['net_contents'], font=font(48), fill='#263e31')
        draw.text((110, 660), f"Bottled by {fields['producer']}", font=font(38), fill='#263e31')
        draw.text((110, 725), fields['address'], font=font(38), fill='#263e31')
        warning = fields.get('warning', WARNING)
        if warning:
            draw.line((110, 875, 1390, 875), fill='#49624a', width=2)
            x, y = 110, 940
            for index, word in enumerate(warning.split()):
                weight = (fields.get('bold', True) and not (fields.get('mixed_bold') and index == 1)) if index < 2 else fields.get('body_bold', False)
                face = font(35, weight)
                width = draw.textlength(word + ' ', font=face)
                if x + width > 1390:
                    x, y = 110, y + 56
                draw.text((x, y), word + ' ', font=face, fill='#202921')
                x += width
        if changes.get('blur'):
            image = image.filter(ImageFilter.GaussianBlur(14))
        image.save(destination / f'{case_id}.png')
        application = APPLICATION.copy()
        if case_id == 'brand_case':
            application['brand'] = "Stone's Throw"
        expected_checks = {key: 'matches' for key in ('brand', 'class_type', 'abv', 'net_contents', 'producer', 'address', 'warning_text', 'warning_heading')}
        expected_checks.update(country='not_applicable', warning_format='needs_review', warning_size='needs_review')
        expected_checks['warning_bold'] = 'matches'
        expected_checks['warning_body_style'] = 'needs_review'
        if case_id == 'abv_mismatch':
            expected_checks['abv'] = 'mismatch'
        if case_id in {'missing_warning', 'warning_wording', 'missing_punctuation'}:
            expected_checks['warning_text'] = 'mismatch'
        if case_id == 'missing_warning':
            expected_checks['warning_heading'] = 'needs_review'
            expected_checks['warning_bold'] = 'needs_review'
        if case_id == 'warning_case':
            expected_checks['warning_heading'] = 'mismatch'
        if case_id in {'warning_not_bold', 'warning_mixed_bold'}:
            expected_checks['warning_bold'] = 'mismatch'
        if case_id == 'warning_body_bold':
            expected_checks['warning_body_style'] = 'mismatch'
        if case_id == 'blurred':
            expected_checks = {key: 'not_applicable' if key == 'country' else 'needs_review' for key in expected_checks}
        manifest.append(dict(id=case_id, title=title, description=description, image=f'{case_id}.png',
                             application=application, expected_status=status,
                             expected_checks=expected_checks,
                             fixture_warning=warning,
                             heading_is_bold=fields.get('bold', True) and not fields.get('mixed_bold', False),
                             body_is_bold=fields.get('body_bold', False)))
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Generated {len(manifest)} controlled labels in {destination}')


if __name__ == '__main__':
    generate()
