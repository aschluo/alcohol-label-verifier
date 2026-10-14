"""Check a deployed service with actual sample bytes and OCR, without mocks."""
import argparse
import json
from pathlib import Path
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


def run(base_url):
    cases = json.loads((ROOT / 'samples/manifest.json').read_text())
    selected = [case for case in cases if case['id'] in {'correct', 'abv_mismatch'}]
    with httpx.Client(base_url=base_url.rstrip('/'), timeout=180) as client:
        health = client.get('/api/health')
        health.raise_for_status()
        assert health.json()['ocr_provider'] == 'tesseract', health.text
        home = client.get('/')
        home.raise_for_status()
        samples = client.get('/api/samples')
        samples.raise_for_status()
        assert len(samples.json()) == 13
        for case in selected:
            started = time.perf_counter()
            response = client.post('/api/verify',
                data={'application': json.dumps(case['application'])},
                files={'images': (case['image'], (ROOT / 'samples' / case['image']).read_bytes(), 'image/png')})
            response.raise_for_status()
            result = response.json()
            checks = {check['key']: check['status'] for check in result['checks']}
            assert result['ocr_provider'] == 'tesseract'
            assert checks['brand'] == 'matches', result
            assert checks['abv'] == ('mismatch' if case['id'] == 'abv_mismatch' else 'matches'), result
            assert checks['net_contents'] == 'matches', result
            assert checks['warning_text'] == 'matches', result
            print(json.dumps({'case': case['id'], 'status': result['status'],
                'elapsed_ms': round((time.perf_counter() - started) * 1000), 'checks': checks}))
    print('Deployment smoke checks passed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('base_url', help='Public Render URL, including https://')
    run(parser.parse_args().base_url)
