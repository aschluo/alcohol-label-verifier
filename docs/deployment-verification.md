# Deployment verification — October 13, 2026

- Repository: https://github.com/aschluo/alcohol-label-verifier
- Public application: https://alcohol-label-verifier-bhte.onrender.com/
- Render service: `srv-db7f8k59fdbs73e19q1g`
- Runtime: Docker, Tesseract, Free compute, Virginia.
- Render reports the initial deployment Live.
- GitHub's Ubuntu / Python 3.12 test workflow passed. Local tests: 49 passed.

The public health endpoint returned `{"status":"ok","ocr_provider":"tesseract"}`.
The home page and the 13-case sample manifest returned successful responses.
The smoke script uploaded actual sample image bytes to the public `/api/verify` endpoint:

| Sample | Result | Relevant checks | HTTP elapsed |
| --- | --- | --- | --- |
| Correct text | Needs review | Brand, class/type, ABV, volume, producer, address, warning text, and heading matched | 5,882 ms |
| ABV mismatch | Mismatch | ABV mismatch detected; brand, class/type, volume, producer, address, warning text, and heading matched | 4,832 ms |

Warning boldness, body style, layout, and physical type size remained Needs review
in these deployed examples. The service does not certify full regulatory compliance.
Two uploads are a smoke test, not a representative benchmark or p95 estimate.
The five-second target is not consistently met on the Free instance; idle startup
can add 50 seconds or more. Local Apple Vision benchmark results do not establish
Tesseract accuracy or latency on Render.

## Follow-up warm response-time checks

Three consecutive smoke-check runs uploaded both synthetic labels, producing six
successful uploads. All matching-field and ABV-mismatch assertions passed.
HTTP request-to-response times were **4,504–5,133 ms**, with a **4,662 ms median**.
This supports an approximately five-second response-time goal for these warm
examples. It does not establish a strict five-second upper bound, representative
p95, performance on real photos, or idle-startup time. Raw results are in
[render-warm-timings.json](render-warm-timings.json).

Repeat with:

```bash
python scripts/smoke_deployment.py https://alcohol-label-verifier-bhte.onrender.com
```
