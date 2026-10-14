import json
from pathlib import Path
import re
import pytest
from app.rules import verify
from tests.test_rules import APPLICATION, TEXT


def token_evidence(text, low_words=()):
    return [dict(text=token, confidence=.3 if token in low_words else .99) for token in re.findall(r'\S+', text)]


def indexed(result):
    return {check['key']: check for check in result['checks']}


def test_unrelated_uncertain_word_does_not_downgrade_clear_fields():
    text = TEXT + '\nUNREADABLE'
    result = indexed(verify(text, APPLICATION, .3, words=token_evidence(text, ['UNREADABLE'])))
    for key in ['brand','class_type','abv','net_contents','producer','address','warning_text','warning_heading']:
        assert result[key]['status'] == 'matches'


def test_low_confidence_volume_only_affects_volume():
    result = indexed(verify(TEXT, APPLICATION, .3, words=token_evidence(TEXT, ['750'])))
    assert result['net_contents']['status'] == 'needs_review'
    assert result['abv']['status'] == 'matches'
    assert result['warning_text']['status'] == 'matches'


def test_low_confidence_warning_only_affects_warning():
    result = indexed(verify(TEXT, APPLICATION, .3, words=token_evidence(TEXT, ['impairs'])))
    assert result['warning_text']['status'] == 'needs_review'
    assert result['warning_heading']['status'] == 'matches'
    assert result['net_contents']['status'] == 'matches'


def test_missing_token_confidence_cannot_pass_field():
    words = [word for word in token_evidence(TEXT) if word['text'] != '750']
    assert indexed(verify(TEXT, APPLICATION, words=words))['net_contents']['status'] == 'needs_review'


def test_origine_is_not_a_gin_designation():
    text = 'PROSECCO\nDenominazione di Origine Controllata\nItalian Sparkling Wine\n11%\n750 mL'
    application = {**APPLICATION, 'brand':'PROSECCO', 'class_type':'Kentucky Straight Bourbon Whiskey'}
    result = indexed(verify(text, application))['class_type']
    assert result['observed'] == 'Italian Sparkling Wine'
    assert result['status'] == 'mismatch'


@pytest.mark.parametrize('field,text', [('abv',TEXT+'\n40% Alc./Vol.'),('net_contents',TEXT+'\n500 mL')])
def test_conflicting_numbers_require_review(field, text):
    assert indexed(verify(text, APPLICATION)) [field]['status'] == 'needs_review'


def test_real_bottle_photo_readable_fields_match_despite_uncertain_warning():
    capture = json.loads((Path(__file__).parent/'fixtures/prosecco_ocr.json').read_text())
    application = dict(brand='PROSECCO', class_type='Sparkling Wine', abv='11', net_contents='750 mL',
                       producer='Mionetto Spa', address='Valdobbiadene', imported=True, country='Italy')
    result = indexed(verify(capture['extracted_text'], application, capture['confidence'], words=capture['words']))
    for key in ['brand','class_type','abv','net_contents','producer','address','country']:
        assert result[key]['status'] == 'matches'
    assert result['warning_text']['status'] == 'needs_review'


def test_real_bottle_photo_wine_against_bourbon_is_mismatch():
    capture = json.loads((Path(__file__).parent/'fixtures/prosecco_ocr.json').read_text())
    application = {**APPLICATION, 'brand':'PROSECCO', 'abv':'11','class_type':'Kentucky Straight Bourbon Whiskey'}
    result = indexed(verify(capture['extracted_text'], application, capture['confidence'], words=capture['words']))
    assert result['class_type']['status'] == 'mismatch'
    assert 'Sparkling Wine' in result['class_type']['observed']
    assert result['net_contents']['status'] == 'matches'
