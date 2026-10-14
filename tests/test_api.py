import json
from pathlib import Path
from io import BytesIO
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from PIL import Image
from app.main import app
from app.ocr import OCRError
from app.rules import WARNING

client = TestClient(app)


def image():
    stream = BytesIO()
    Image.new('RGB', (100, 100), 'white').save(stream, format='PNG')
    return stream.getvalue()


def test_home_and_samples():
    assert client.get('/').status_code == 200
    assert len(client.get('/api/samples').json()) == 13


def test_invalid_file_rejected():
    response = client.post('/api/verify', data={'application':'{}'}, files={'images':('bad.png', b'not an image', 'image/png')})
    assert response.status_code == 400


def test_invalid_application_rejected():
    for data in ['null', '[]', '{', '{"brand":123}', '{"imported":"false"}']:
        response = client.post('/api/verify', data={'application':data}, files={'images':('test.png', image(), 'image/png')})
        assert response.status_code == 422


def test_ocr_failure_is_actionable(monkeypatch):
    monkeypatch.setattr('app.main.read_image', AsyncMock(side_effect=OCRError('OCR is unavailable. Install Tesseract.')))
    response = client.post('/api/verify', data={'application':'{}'}, files={'images':('test.png', image(), 'image/png')})
    assert response.status_code == 503
    assert 'Tesseract' in response.json()['detail']


def test_multiple_surfaces_combined(monkeypatch):
    monkeypatch.setattr('app.main.read_image', AsyncMock(side_effect=[('OLD TOM\n45% Alc./Vol.\n750 mL',1,'test'),(WARNING,1,'test')]))
    response = client.post('/api/verify', data={'application':json.dumps({'brand':'Old Tom','abv':'45','net_contents':'750 mL'})},
                           files=[('images',('front.png',image(),'image/png')),('images',('back.png',image(),'image/png'))])
    assert response.status_code == 200
    result = response.json()
    assert result['image_count'] == 2
    checks = {item['key']:item['status'] for item in result['checks']}
    assert checks['brand'] == checks['warning_text'] == 'matches'


def test_too_many_images_rejected():
    response = client.post('/api/verify', data={'application':'{}'}, files=[('images',(f'{i}.png',image(),'image/png')) for i in range(7)])
    assert response.status_code == 400


def test_photo_word_confidence_reaches_comparison_rules(monkeypatch):
    capture = json.loads((Path(__file__).parent/'fixtures/prosecco_ocr.json').read_text())
    monkeypatch.setattr('app.main.read_image', AsyncMock(return_value=(capture['extracted_text'], capture['confidence'], 'test', capture['words'])))
    application = dict(brand='PROSECCO', class_type='Kentucky Straight Bourbon Whiskey', abv='11', net_contents='750 mL')
    response = client.post('/api/verify', data={'application':json.dumps(application)}, files={'images':('test.png',image(),'image/png')})
    assert response.status_code == 200
    checks = {item['key']:item for item in response.json()['checks']}
    assert checks['brand']['status'] == 'matches'
    assert checks['abv']['status'] == 'matches'
    assert checks['net_contents']['status'] == 'matches'
    assert checks['class_type']['status'] == 'mismatch'
    assert checks['warning_text']['status'] == 'needs_review'
