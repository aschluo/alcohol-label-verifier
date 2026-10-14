import pytest
from app.rules import WARNING, verify

APPLICATION = dict(brand="Stone's Throw", class_type='Kentucky Straight Bourbon Whiskey', abv='45',
                   net_contents='750 mL', producer='Old Tom Distillery LLC', address='Frankfort, Kentucky', imported=False)
TEXT = "STONE'S THROW\nKentucky Straight Bourbon Whiskey\n45% Alc./Vol. (90 Proof)\n750 mL\nBottled by Old Tom Distillery LLC\nFrankfort, Kentucky\n" + WARNING


def checks(text=TEXT, application=None, confidence=1):
    return {item['key']: item for item in verify(text, application or APPLICATION, confidence)['checks']}


def test_capitalization_and_curly_apostrophe_match():
    assert checks(TEXT.replace("STONE'S", 'STONE’S'))['brand']['status'] == 'matches'


def test_brand_substring_does_not_match():
    assert checks(TEXT.replace("STONE'S THROW", "STONE'S THROWBACK"))['brand']['status'] == 'mismatch'


def test_producer_name_does_not_substitute_for_brand():
    application = {**APPLICATION, 'brand':'Old Tom Distillery'}
    assert checks(application=application)['brand']['status'] == 'mismatch'


def test_abv_difference_is_flagged():
    assert checks(TEXT.replace('45%', '40%'))['abv']['status'] == 'mismatch'


def test_equivalent_volume_units():
    assert checks(TEXT.replace('750 mL', '0.75 L'))['net_contents']['status'] == 'matches'


@pytest.mark.parametrize('changed', [WARNING.replace('machinery,', 'machinery'), WARNING.replace('birth defects', 'birth problems'), WARNING.replace('(2)', '2')])
def test_warning_wording_and_punctuation_are_strict(changed):
    assert checks(TEXT.replace(WARNING, changed))['warning_text']['status'] == 'mismatch'


def test_warning_heading_case_is_strict():
    assert checks(TEXT.replace('GOVERNMENT WARNING:', 'Government Warning:'))['warning_heading']['status'] == 'mismatch'


def test_warning_body_all_caps_and_line_wrap_are_allowed():
    result = checks(TEXT.replace(WARNING, WARNING.upper().replace(' WOMEN ', '\nWOMEN\n')))
    assert result['warning_text']['status'] == 'matches'


def test_missing_warning_is_flagged():
    assert checks(TEXT.replace(WARNING, ''))['warning_text']['status'] == 'mismatch'


def test_low_confidence_never_confidently_passes():
    result = checks(confidence=0.5)
    assert all(item['status'] != 'matches' for item in result.values())


def test_formatting_and_physical_size_require_review():
    result = checks()
    assert result['warning_format']['status'] == 'needs_review'
    assert result['warning_size']['expected'] == 'At least 2 mm'
    assert verify(TEXT, APPLICATION)['status'] == 'needs_review'


@pytest.mark.parametrize('size,minimum', [('237 mL',1),('238 mL',2),('3 L',2),('3.1 L',3)])
def test_container_size_boundaries(size, minimum):
    assert verify(TEXT, {**APPLICATION, 'net_contents':size})['minimum_warning_size_mm'] == minimum


def test_import_requires_country():
    assert checks(application={**APPLICATION, 'imported':True})['country']['status'] == 'needs_review'


def test_domestic_country_is_not_applicable():
    assert checks()['country']['status'] == 'not_applicable'
