# Label Check — AI-powered alcohol label verification

Standalone Python 3 / FastAPI proof of concept. Upload label images and enter the corresponding application values. Actual machine-learning OCR reads the pixels; deterministic rules compare the text. The app reports Matches, Mismatch, or Needs review with observed text and reasons. No COLA connection or database is required.

**Live demo:** https://alcohol-label-verifier-bhte.onrender.com/

**Source:** https://github.com/aschluo/alcohol-label-verifier

Deployed on Render's Free Docker service with Tesseract. Free instances sleep when idle, so the first request can take 50 seconds or more. Public smoke checks passed on October 13, 2026; two image uploads took approximately 4.8–5.9 seconds including HTTP time. This does not consistently meet the five-second target. See [deployment verification](docs/deployment-verification.md).

## Run locally

Python 3.12+ recommended. From this project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Choose a local OCR engine:

**macOS with Apple's command-line developer tools** (no cloud credentials):

```bash
mkdir -p .cache/clang
swiftc -module-cache-path .cache/clang scripts/vision_ocr.swift -o .cache/vision-ocr
```

**Linux / Windows:** install Tesseract 5 and its English language pack, ensuring `tesseract` is on PATH. On Debian/Ubuntu: `sudo apt-get install tesseract-ocr tesseract-ocr-eng`.

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Select a prepared test label to populate the image and expected application data, or upload your own JPG/PNG/WebP. Up to six images are combined for **one application**, so front and back can be checked together. Camera capture is offered by compatible mobile browsers through a native file input; unsupported devices show the file picker. HEIC is not supported in this first version.

## Test and benchmark

```bash
python scripts/generate_samples.py
python -m pytest -q
python scripts/benchmark.py --repeats 3
```

Twelve reproducible raster test labels and ground-truth application data are included in `samples/`. Python/Pillow draws the exact text and font weights. No hidden text metadata is used for OCR or formatting checks. Fixtures cover correct text, brand capitalization, ABV mismatch, missing/changed warning, heading capitalization, nonbold or partially bold heading, bold warning body, equivalent volumes, missing punctuation, and heavy blur.

A thirteenth case, `samples/prosecco_photo.jpg`, is the user-supplied real bottle photo. `samples/photo_manifest.json` contains illustrative application inputs and expected per-field results. The input brand `PROSECCO` reflects the user's text-comparison test; this is not a claim that Prosecco is the regulatory brand or an actual COLA application. Its unreadable warning must not downgrade the clearly read 11% ABV and 750 mL volume. A captured OCR transcript in `tests/fixtures/prosecco_ocr.json` reproduces that regression without depending on an OCR engine in unit tests. Source webpage was not provided.

The benchmark uses real image bytes, OCR, and comparison rules. It writes `docs/local-benchmark.json`. Its timings exclude HTTP upload and browser/network time; the UI separately measures request-to-response time. Local Apple Vision results do **not** establish Azure Tesseract accuracy or latency. A five-second target must be measured again on the deployed app, with warm/cold requests and representative photos.

## Architecture and tools

- **FastAPI / Uvicorn:** upload endpoint, static interface, health endpoint.
- **Pillow:** validate images, correct EXIF rotation, resize large images, generate controlled labels.
- **Apple Vision locally on macOS; Tesseract in Linux/Azure:** actual pretrained OCR without third-party ML endpoint calls.
- **Python rules:** conservative capitalization/whitespace/apostrophe normalization for fields, numerical ABV checks, equivalent metric volume units, exact warning words and punctuation.
- **Pixel-based font-weight estimates:** OCR word coordinates identify the warning heading and body. Cropped pixels are compared with regular and bold templates at native pixel sizes. The heading passes only when both words confidently match bold templates; regular heading words and confidently bold body words are flagged. Uncertain or unsupported styles require review.
- **Vanilla HTML/CSS/JavaScript:** large controls, explicit labels, keyboard focus, readable status text, local assets, JSON report export. No frontend CDN dependencies.
- **pytest:** behavior and API error cases. Separate real-image benchmark catches OCR failures.

OCR is the AI component. This version does not use an LLM. Recognizing that capitalization does not change brand identity is a deterministic rule; ambiguous semantic differences are left for the reviewer. It never silently repairs warning text.

## Scope and assumptions

This milestone focuses on comparing submitted application fields with label text. It is not a complete legal compliance engine. Application values are entered by the user and are assumed to be correct. All submitted images belong to one application. Beverage-specific exceptions, placement rules, class/type taxonomies, ABV tolerances, and allowable address abbreviations are not exhaustively implemented. Country matching is required when the user selects imported.

Brand extraction currently assumes the first OCR line on the first image is the brand, to avoid falsely matching a producer's name elsewhere. Upload the front first. Decorative text above the brand, split brand lines, and complex layouts may produce an incorrect mismatch and require human review; richer positional field extraction is a next step.

The warning comparator ignores whitespace/line wrapping and permits uppercase body text while retaining words and punctuation. The heading must be `GOVERNMENT WARNING:`. Missing or unreadable fields require review; clearly different readable values are mismatches. OCR confidence is assessed on the tokens supporting each field, so a poor warning reading does not downgrade a clear volume or ABV. Incomplete or low-confidence evidence for the field itself still requires review. Conflicting readable numeric declarations also require review. If word evidence is unavailable, the provider-level confidence remains a conservative fallback. The report's top-level `confidence` is the worst document-wide OCR confidence; individual comparison rows include their own `ocr_confidence`. Confidence scores are provider-specific and not a calibrated guarantee.

**Heading boldness is now checked from image pixels, separately from OCR text.** This is a conservative heuristic for clear artwork using supported Arial/Times/Liberation/DejaVu regular and bold font templates, not a general-purpose font recognition model. Scores must meet both a fit threshold and a separation margin. Familiar fonts at readable resolutions are covered by tests; custom fonts, slanted photos, compression, unusual print effects, or low contrast can remain Needs review. A bold-body detector samples words of at least four alphanumeric characters and can flag likely violations; it does not automatically certify the entire body as nonbold. Font scores are similarity measures, not calibrated probabilities.

**Contrast, paragraph separation, and physical size remain manual checks.** Physical minimum type size is displayed using the application's container volume: 1 mm through 237 mL, 2 mm above 237 mL through 3 L, 3 mm above 3 L. Reliable artwork dimensions or scale would be needed to verify millimeters; the app does not invent a pixel-to-mm conversion or trust incidental image DPI. Formatting detection runs on user-uploaded pixels and never reads fixture names or `heading_is_bold` metadata.

Images are processed using temporary files, removed after OCR, and are not retained by the app. No image contents are logged. Sample fixtures are public synthetic data. Limits: six images, 10 MB per image, 20 megapixels, two simultaneous OCR jobs per server process, eight-second OCR timeout. Request parsing/upload occurs before these application limits; an internet deployment should configure an ingress request-size limit as well. No authentication or persistent review history in this prototype.

## Render deployment for submission

The project includes a [Render blueprint](render.yaml) and [deployment and verification instructions](docs/render-deployment.md). Deploy as a **Docker web service** so Tesseract and the font templates are installed. The container binds to `0.0.0.0` and uses Render's `PORT`. No cloud OCR credentials are needed. The blueprint selects the Free plan.

Run `python scripts/smoke_deployment.py https://alcohol-label-verifier-bhte.onrender.com` to repeat the verified health, page, sample, and real OCR upload checks. Render's free services sleep after inactivity, so the first request can take about a minute; deployed timings are separate from the local benchmark.

## Optional Azure deployment

An Azure subscription is required; none is configured yet. The included Dockerfile runs Python and Tesseract together so runtime OCR has no external ML endpoint dependency. See [Azure deployment instructions](docs/azure-deployment.md). The Docker image and Azure deployment have not yet been verified on this machine.

## Next milestones

1. Review UI and run representative real label photos; improve per-field extraction/confidence.
2. Validate Tesseract parity and deploy to Azure; measure warm and cold end-to-end p50/p95.
3. Add a batch queue with a CSV application manifest and per-application image association.
4. Broaden font recognition and body-style coverage, add paragraph-layout checks, and accept reliable artwork dimensions for physical text-size verification.
5. Measure representative warm/cold latency and improve performance on the deployed service; GitHub publication and initial Render verification are complete.

## References

- [Take-home brief](https://github.com/treasurytakehome-rgb/instructions)
- [TTB health warning requirements](https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/ds-labeling-home/ds-health-warning)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
- [Apple Vision text recognition](https://developer.apple.com/documentation/vision/recognizing-text-in-images)
