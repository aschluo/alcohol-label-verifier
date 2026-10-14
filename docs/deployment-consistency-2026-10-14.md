# Deployment consistency check — October 14, 2026

Tested https://alcohol-label-verifier-bhte.onrender.com against the actual local
FastAPI application using Apple Vision. Each engine received exactly the same
image bytes and application JSON for all 13 fixtures. No OCR mocks were used.
The baseline local checkout was commit `d6e2754`. The deployed sample manifest,
JavaScript, and CSS matched the local files. Matching frontend assets does not
prove an exact deployed backend commit or package-version match.

## Results

| Check | Result |
| --- | --- |
| Real image uploads | 13/13 succeeded on both engines; no HTTP/OCR errors |
| Synthetic text comparisons | All 12 synthetic fixtures had the same nonvisual field statuses on both engines |
| Entire per-field result agreement | 2/13 fixtures had identical status rows |
| Overall outcome agreement | 11/13 fixtures agreed |
| Invalid image handling | Both returned HTTP 400 with the same error message |
| Local image-upload median | 595 ms |
| Deployed image-upload median | 4,932 ms |
| Deployed slowest upload | 11,187 ms, the real Prosecco photo |
| First public health request | 12,286 ms; may include startup/network delay |

One request per fixture is an exploratory compatibility check, not a representative
latency benchmark or a production accuracy estimate. The JSON report includes
sample p95 values, but with only 13 heterogeneous fixtures those equal the observed
maximum and should not be treated as an established service-level percentile.

## Gaps

**Heading boldness differs across environments.** Ten clean synthetic fixtures
have a confident bold or nonbold heading classification locally, while the public
service leaves the heading Needs review. The regular and partially bold heading
cases therefore change from overall Mismatch locally to overall Needs review in
deployment. The public service does not falsely mark those headings as compliant,
but it fails to detect the known defect automatically. For the correct fixture,
the deployed pixel-template fit scores were approximately 0.80 and 0.79, below the
required threshold. Font-template availability/shape and OCR crop geometry are
possible causes; their individual contributions have not been isolated.

**The real bottle photo reads substantially worse with deployed Tesseract.** The
Mac reads the entered Prosecco text, Italian Sparkling Wine (using the crop retry),
11% ABV, 750 mL, producer, address, and Italy. Render reads the address and country,
but cannot confidently establish the brand, class/type, ABV, volume, or producer.
The observed brand becomes `2`, and the numeric declarations are absent from its
transcript. Warning text remains Needs review in both environments. This is an OCR
quality difference, not merely a different comparison-rule result.

**The five-second target is not consistent across this deployed set.** The public
median is close to five seconds, but some synthetic uploads exceeded five seconds
and the photo took over eleven seconds. End-to-end timings include HTTP; backend
processing alone for the photo was 10,854 ms. Network time is therefore not the
main cause of this slow photo result.

## Recommended follow-up

1. Make Linux/Tesseract the development acceptance baseline so Mac results cannot
   stand in for deployed accuracy.
2. Evaluate targeted crops, deskew/contrast preprocessing, and Tesseract recognition
   settings on real photos. Retain genuine class mismatches and strict warning rules.
3. Check font-template paths and heading crop quality in the actual Linux container;
   do not lower confidence thresholds solely to make synthetic tests pass.
4. Re-run this complete comparison after changes and document runtime-specific
   expectations. Continue showing Needs review whenever evidence is uncertain.

No deployed application code or hosting configuration was changed by this test.

Raw evidence: [deployment-consistency-2026-10-14.json](deployment-consistency-2026-10-14.json).
Repeat with:

```bash
python scripts/check_consistency.py https://alcohol-label-verifier-bhte.onrender.com
```
