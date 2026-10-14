"""Compare real local Apple Vision responses with deployed Tesseract responses."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time

import httpx
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.main import app


def run(url, output):
    cases = json.loads((ROOT/'samples/manifest.json').read_text()) + json.loads((ROOT/'samples/photo_manifest.json').read_text())
    commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    report = dict(url=url, local_commit=commit, scope='One actual upload per fixture to each engine; timings are not representative production percentiles.', rows=[], errors=[])
    output = Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)

    def save():
        output.write_text(json.dumps(report,indent=2)+'\n')

    with TestClient(app) as local, httpx.Client(base_url=url.rstrip('/'),timeout=180) as public:
        report['local_health'] = local.get('/api/health').json()
        started = time.perf_counter()
        response = public.get('/api/health')
        report['startup_health_ms'] = round((time.perf_counter()-started)*1000)
        response.raise_for_status()
        report['public_health'] = response.json()
        report['manifest_matches'] = public.get('/api/samples').json() == local.get('/api/samples').json()
        report['static_assets_match'] = {}
        for asset in ['app.js','styles.css']:
            response = public.get('/static/'+asset)
            response.raise_for_status()
            report['static_assets_match'][asset] = response.content == (ROOT/'static'/asset).read_bytes()
        save()
        print('Health:',report['local_health'],report['public_health'],'startup_ms=',report['startup_health_ms'],flush=True)
        for case in cases:
            row = dict(case=case['id'], expected=case['expected_checks'], image_sha256=hashlib.sha256((ROOT/'samples'/case['image']).read_bytes()).hexdigest())
            mime = 'image/jpeg' if case['image'].endswith('.jpg') else 'image/png'
            for name,client in [('local',local),('deployed',public)]:
                started = time.perf_counter()
                try:
                    response = client.post('/api/verify',data={'application':json.dumps(case['application'])},
                                           files={'images':(case['image'],(ROOT/'samples'/case['image']).read_bytes(),mime)})
                    elapsed = round((time.perf_counter()-started)*1000)
                    response.raise_for_status()
                    result = response.json()
                    checks = {check['key']:check['status'] for check in result['checks']}
                    row[name] = dict(http_ms=elapsed,result=result,checks=checks,
                                     expected_differences={key:dict(expected=value,actual=checks.get(key)) for key,value in case['expected_checks'].items() if checks.get(key)!=value})
                except Exception as error:
                    row[name] = dict(error=str(error),http_ms=round((time.perf_counter()-started)*1000))
                    report['errors'].append(dict(case=case['id'],engine=name,error=str(error)))
            if 'checks' in row.get('local',{}) and 'checks' in row.get('deployed',{}):
                row['engine_differences'] = {key:dict(local=value,deployed=row['deployed']['checks'].get(key)) for key,value in row['local']['checks'].items() if row['deployed']['checks'].get(key)!=value}
            report['rows'].append(row)
            save()
            print(case['id'], 'differences=',json.dumps(row.get('engine_differences',{})),
                  'deployed_expected=',json.dumps(row.get('deployed',{}).get('expected_differences',{})),
                  'deployed_ms=',row.get('deployed',{}).get('http_ms'),flush=True)
        report['invalid_upload'] = {}
        for name,client in [('local',local),('deployed',public)]:
            response = client.post('/api/verify',data={'application':'{}'},files={'images':('bad.png',b'not an image','image/png')})
            report['invalid_upload'][name] = dict(status_code=response.status_code,body=response.json())
        for engine in ['local','deployed']:
            timings = sorted(row[engine]['http_ms'] for row in report['rows'] if 'checks' in row.get(engine,{}))
            report[engine+'_summary'] = dict(successful_uploads=len(timings),
                 fixtures_matching_expected=sum(not row[engine]['expected_differences'] for row in report['rows'] if 'checks' in row.get(engine,{})),
                 median_ms=round(statistics.median(timings)) if timings else None,
                 p95_ms=timings[math.ceil(len(timings)*.95)-1] if timings else None,
                 max_ms=max(timings,default=None))
        report['fixtures_with_identical_checks'] = sum(row.get('engine_differences') == {} for row in report['rows'])
        save()
        print('Summary:',json.dumps({key:value for key,value in report.items() if key.endswith('_summary') or key in ['fixtures_with_identical_checks','errors']}),flush=True)
        print('Saved:',output,flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('--output',default=str(ROOT/'docs/deployment-consistency-2026-10-14.json'))
    args = parser.parse_args()
    run(args.url,args.output)
