"""Evidence-based comparisons, deliberately separate from OCR and presentation."""
import re
import unicodedata
from difflib import SequenceMatcher, unified_diff

WARNING = (
    'GOVERNMENT WARNING: (1) According to the Surgeon General, women should not '
    'drink alcoholic beverages during pregnancy because of the risk of birth '
    'defects. (2) Consumption of alcoholic beverages impairs your ability to '
    'drive a car or operate machinery, and may cause health problems.'
)
FIELD_NAMES = {
    'brand': 'Brand name', 'class_type': 'Class / type', 'abv': 'Alcohol content',
    'net_contents': 'Net contents', 'producer': 'Producer / bottler',
    'address': 'Producer address', 'country': 'Country of origin',
}
CLASS_TERMS = re.compile(r'\b(?:whisk(?:e)?y|bourbon|vodka|gin|rum|wine|beer|lager|ale|tequila|brandy|prosecco)\b', re.I)


def normalize(text):
    text = unicodedata.normalize('NFKC', text).replace('’', "'").replace('‘', "'")
    return re.sub(r'\s+', ' ', text).strip().casefold()


def possible_class_reading_error(expected, observed):
    left, right = normalize(expected), normalize(observed)
    return bool(left != right and min(len(left),len(right)) >= 10 and
                abs(len(left)-len(right)) <= 2 and SequenceMatcher(None,left,right).ratio() >= .93)


def number(text):
    found = re.search(r'\d+(?:\.\d+)?', str(text))
    return float(found.group()) if found else None


def volume(text):
    found = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(ml|milliliters?|l|liters?|litres?|fl\.?\s*oz\.?)\s*', normalize(text))
    if not found:
        return None
    unit = found[2]
    factor = 1 if unit.startswith('m') else 29.5735295625 if unit.startswith('f') else 1000
    return round(float(found[1]) * factor, 3)


def check(key, status, expected, observed, reason):
    return dict(key=key, label=FIELD_NAMES.get(key, key.replace('_', ' ').capitalize()),
                status=status, expected=expected, observed=observed, reason=reason)


class TextEvidence:
    """Align OCR tokens to the normalized text; score only the relevant span."""
    def __init__(self, text, words, fallback):
        self.text = normalize(text)
        self.fallback = fallback
        self.has_word_data = bool(words)
        self.spans = []
        cursor = 0
        for word in words or []:
            token = normalize(word.get('text', ''))
            if not token:
                continue
            start = self.text.find(token, cursor)
            if start < 0:
                continue
            end = start + len(token)
            self.spans.append((start, end, max(0, min(1, float(word.get('confidence', 0))))))
            cursor = end

    def score(self, start, end):
        if not self.spans:
            return 0.0 if self.has_word_data else self.fallback
        relevant = [(left, right, score) for left, right, score in self.spans if left < end and right > start]
        # Incomplete evidence is uncertain, even if the available tokens are clear.
        if not relevant or any(not self.text[index].isspace() and not any(left <= index < right for left, right, _ in relevant) for index in range(start, end)):
            return 0.0
        return min(score for _, _, score in relevant)

    def phrase_score(self, phrase):
        match = re.search(r'(?<!\w)' + re.escape(normalize(phrase)) + r'(?!\w)', self.text)
        return self.score(*match.span()) if match else 0.0


def verify(text, expected, confidence=1.0, visual_checks=None, words=None):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    flat = re.sub(r'\s+', ' ', text).strip()
    evidence = TextEvidence(text, words, confidence)
    checks = []
    before_warning = re.split(r'government\s+warning', flat, flags=re.I)[0]
    normalized_label = normalize(before_warning)
    # Numeric declarations can be below the warning or on another uploaded side.
    # The standard warning contains no percentages or volume declarations.
    abvs = list(re.finditer(r'(?<![\w.])(\d+(?:\.\d+)?)\s*%', evidence.text))
    volumes = list(re.finditer(r'\b\d+(?:\.\d+)?\s*(?:ml|milliliters?|liters?|litres?|l|fl\.?\s*oz\.?)\b', evidence.text))

    for key, label in FIELD_NAMES.items():
        target = str(expected.get(key, '')).strip()
        if key == 'country' and not expected.get('imported'):
            checks.append(check(key, 'not_applicable', '', '', 'Not required by this prototype for a domestic product.'))
            continue
        if not target:
            checks.append(check(key, 'needs_review', '', '', 'Enter the application value to compare this field.'))
            continue
        if key == 'abv':
            wanted = number(target)
            matched = [item for item in abvs if wanted is not None and float(item[1]) == wanted]
            match = bool(matched)
            observed = ', '.join(item[1] + '%' for item in abvs)
            local_confidence = max((evidence.score(*item.span()) for item in matched or abvs), default=0)
        elif key == 'net_contents':
            wanted = volume(target)
            matched = [item for item in volumes if wanted is not None and volume(item[0]) == wanted]
            match = bool(matched)
            observed = ', '.join(item[0] for item in volumes)
            local_confidence = max((evidence.score(*item.span()) for item in matched or volumes), default=0)
        else:
            match = bool(re.search(r'(?<!\w)' + re.escape(normalize(target)) + r'(?!\w)', normalized_label))
            if key == 'brand':
                observed = lines[0] if lines else ''
                # Do not mistake a matching producer name for the label's brand.
                match = normalize(observed) == normalize(target)
            elif match:
                observed = next((line for line in lines if normalize(target) in normalize(line)), target)
            elif key == 'class_type':
                # Match whole words: "gin" inside "Origine" is not a spirit.
                # Prefer a wine/beer/spirit designation over Prosecco marketing.
                candidates = [part.strip() for line in lines for part in re.split(r'\s+[-–]\s+', line) if CLASS_TERMS.search(part)]
                observed = next((part for part in candidates if re.search(r'\b(?:wine|beer|whisk(?:e)?y|bourbon|vodka|gin|rum|lager|ale|tequila|brandy)\b', part, re.I)), candidates[0] if candidates else '')
            elif key == 'producer':
                observed = next((line for line in lines if re.search(r'bottled|produced|distilled|brewed|imported', line, re.I)), '')
            else:
                observed = ''
            local_confidence = evidence.phrase_score(target if match else observed) if observed else 0
        uncertain = local_confidence < .8
        reading_error = key == 'class_type' and not match and possible_class_reading_error(target, observed)
        ambiguous_numbers = key in {'abv', 'net_contents'} and len({float(item[1]) if key == 'abv' else volume(item[0]) for item in (abvs if key == 'abv' else volumes) if evidence.score(*item.span()) >= .8}) > 1
        status = 'needs_review' if uncertain or ambiguous_numbers or reading_error else 'matches' if match else 'mismatch' if observed else 'needs_review'
        reason = ('Multiple readable values were found for this field. Confirm which one belongs to the application.' if ambiguous_numbers else
                  'The class/type reading has a small spelling difference that may be an OCR error. Confirm it on the image.' if reading_error else
                  'This field was not located reliably. Check the relevant image text or upload a clearer photo.' if uncertain else
                  'Matches after normalizing capitalization, whitespace, apostrophe style, or equivalent volume units.' if match else
                  'The readable label value differs from the application.' if observed else
                  'The application value was not located. Check all label surfaces and the extracted text.')
        finding = check(key, status, target, observed, reason)
        finding['ocr_confidence'] = round(local_confidence, 3)
        checks.append(finding)

    heading = re.search(r'government\s+warning\s*:', flat, re.I)
    if heading:
        tail = flat[heading.start():]
        end = re.search(r'health\s+problems\.', tail, re.I)
        observed_warning = tail[:end.end()] if end else tail
        exact = observed_warning.casefold() == WARNING.casefold()
        warning_uncertain = evidence.phrase_score(observed_warning) < .8
        heading_uncertain = evidence.phrase_score(heading.group()) < .8
        checks.append(check('warning_text', 'needs_review' if warning_uncertain else 'matches' if exact else 'mismatch',
                            WARNING, observed_warning, 'Wording and punctuation match; line wrapping is ignored.' if exact else
                            'Warning wording or punctuation differs. Confirm against the label image.'))
        caps = heading.group() == 'GOVERNMENT WARNING:'
        checks.append(check('warning_heading', 'needs_review' if heading_uncertain else 'matches' if caps else 'mismatch',
                            'GOVERNMENT WARNING:', heading.group(), 'Heading is uppercase with the required colon.' if caps else
                            'Heading must read GOVERNMENT WARNING: in uppercase.'))
    else:
        observed_warning = ''
        checks.append(check('warning_text', 'needs_review' if confidence < .8 or not flat else 'mismatch', WARNING, '',
                            'Warning was not located. Confirm that all label surfaces are uploaded.'))
        checks.append(check('warning_heading', 'needs_review', 'GOVERNMENT WARNING:', '', 'Heading was not located.'))
    if visual_checks:
        checks.extend(visual_checks)
    checks.append(check('warning_format', 'needs_review', 'Separate continuous paragraph; readable contrast', '',
                        'Confirm the warning is separate from surrounding information, arranged as one paragraph, and readily legible.'))
    size = volume(expected.get('net_contents', ''))
    minimum = 1 if size is not None and size <= 237 else 2 if size is not None and size <= 3000 else 3 if size is not None else None
    checks.append(check('warning_size', 'needs_review', f'At least {minimum} mm' if minimum else 'Container-dependent minimum', '',
                        'Physical text size requires reliable artwork dimensions or a scale reference.'))
    overall = 'mismatch' if any(c['status'] == 'mismatch' for c in checks) else 'needs_review' if any(c['status'] == 'needs_review' for c in checks) else 'matches'
    diff = '\n'.join(unified_diff(WARNING.split(), observed_warning.split(), fromfile='Required warning', tofile='Label warning', lineterm=''))
    return dict(status=overall, checks=checks, extracted_text=text, warning_diff=diff,
                confidence=round(confidence, 3), minimum_warning_size_mm=minimum)
