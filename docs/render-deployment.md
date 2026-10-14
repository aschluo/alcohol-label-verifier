# Render deployment

Deploy this folder as its own GitHub repository. The Docker runtime installs
Tesseract and the font templates; Render's native Python runtime alone does not.
No API keys, database, or paid OCR provider are required.

## Create the service

1. Push the standalone repository to GitHub, excluding `.venv`, `.cache`, and `.env`.
2. In Render, choose **New > Web Service** and select that repository (or paste its public GitHub URL).
3. Choose **Docker**, branch **main**, region **Virginia**, and the **Free** instance.
4. Leave Root Directory empty for a standalone repository. Use `./Dockerfile` for Dockerfile Path and `.` for Docker Build Context. Leave Docker Command empty so the image's CMD starts the server.
5. Set the health check path to `/api/health`. The image already sets `OCR_PROVIDER=tesseract` and `OMP_THREAD_LIMIT=1`.
6. Create the web service and wait until Render reports **Live**. Copy the public `https://…onrender.com` URL.

Alternatively, create a Render Blueprint using the included `render.yaml`.
It explicitly selects the Free plan; review the resource summary before creating it.

## Verify before submission

From this project directory:

```bash
python scripts/smoke_deployment.py https://YOUR-SERVICE.onrender.com
```

This checks the public page, sample manifest, Tesseract health response, and actual
image uploads for matching fields and an ABV mismatch. It reports HTTP timings;
it does not certify every sample outcome or the five-second performance target.
Then open the URL in a browser and try the prepared labels and a real photo.

Free services spin down after 15 minutes without incoming traffic. The first
request after sleeping can take about a minute. Open the demo before reviewing it
and mention this limitation with the submission. Warm OCR requests also need
measurement on Render's limited free CPU; local Apple Vision timings do not
predict deployed Tesseract timings.

## Submission

Provide the **GitHub repository URL** and **verified Render app URL**. The README
documents setup, architecture, assumptions, and limitations. Confirm that the
repository is accessible to reviewers and that the deployed app reads image pixels.

## Sources

- [Docker on Render](https://render.com/docs/docker)
- [Render web services](https://render.com/docs/web-services)
- [Free service limitations](https://render.com/docs/free)
- [Blueprint specification](https://render.com/docs/blueprint-spec)
