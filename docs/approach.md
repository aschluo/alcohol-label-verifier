# Brief documentation: approach, tools, and assumptions

## Approach and design decisions

I built Label Check as a small, standalone review assistant: read the label image
with OCR, compare the observed text with the application, and explain each finding
so a human reviewer can decide what to do next.

The interface uses a light green palette intended to feel calm and reduce visual
strain during repeated reviews. This is a design intention, not a measured claim
about stress reduction. On a desktop, the left panel contains the label upload and
preview, while the right panel contains the application information. This supports
a side-by-side comparison of the two inputs; a controlled A/B usability experiment
has not been conducted. The panels stack on smaller screens.

The main comparisons cover **brand name, alcohol content, government warning,
class/type, and net contents**. Producer information and country of origin for
imports are also checked. Brand comparisons tolerate capitalization, spacing, and
apostrophe differences; volume comparisons accept equivalent metric units. Warning
text is checked separately for wording, punctuation, and heading capitalization.
A clear, readable disagreement produces **Mismatch**. Missing, ambiguous, or
low-confidence evidence produces **Needs review**. The review section shows the
application value, observed label text, and reason, rather than treating uncertainty
as a pass. Image-based font estimates assist with warning formatting; physical
size, layout, and uncertain font evidence remain human checks.

## Test-case rationale

I selected cases from my interpretation of the take-home brief, TTB guidance, and
alcohol-label examples, including beer labels. Because I do not consume alcohol
for religious reasons, I relied on written guidance and label artwork rather than
personal product experience. This makes the limits of that interpretation worth
documenting explicitly.

The repository contains twelve reproducible synthetic labels covering matches,
capitalization differences, ABV mismatches, equivalent volumes, missing or changed
warnings, punctuation, heading/body font weight, and blur. The checked-in synthetic
labels use a distilled-spirits example; a thirteenth case is a real Prosecco bottle
photo with illustrative application values. These are test fixtures, not verified
COLA applications or exhaustive beverage-specific compliance examples.

## Tools used

- **Python, FastAPI, and Uvicorn:** upload API, validation, comparison rules, and web serving.
- **Tesseract on Render; Apple Vision locally on macOS:** pretrained OCR reads actual image pixels. No LLM or external cloud OCR endpoint is used.
- **Pillow:** image validation, rotation, resizing, synthetic fixtures, and pixel-based font estimates.
- **HTML, CSS, and JavaScript:** responsive two-panel interface, per-field review results, and downloadable JSON reports.
- **pytest and GitHub Actions:** rule/API regression checks and Linux test runs.
- **Docker and Render:** package OCR and its font dependencies with the app and host the submission demo. HTTP smoke checks measure actual deployed uploads.

## Assumptions and scope

Application values are assumed to be correct, and all uploaded images belong to
one application. The front label should be uploaded first: brand extraction
currently assumes the first OCR line is the brand. English OCR, familiar fonts,
and readable artwork are the primary supported cases. A successful text comparison
does not establish full TTB compliance; beverage-specific exceptions, detailed
placement rules, and physical measurements are not fully implemented. Batch
processing, COLA integration, authentication, and persistent review history are
outside this prototype.

I deferred Azure integration because the brief does not identify which Azure
services, permissions, or deployment patterns are approved in the government
environment. Choosing a product without that information would introduce an
unverified infrastructure assumption. Render provides an accessible demonstration;
the Docker container provides a starting point for later evaluation on approved
infrastructure. The repository's Azure instructions are a proposed template, not
an executed integration.

## Response-time goal

The goal is approximately **five seconds per label on Render**. Six follow-up warm
uploads of two synthetic labels took **4.50–5.13 seconds**, with a **4.66-second
median**. Initial public checks took about 4.8–5.9 seconds, and the browser mismatch
example took 4.57 seconds. These are small smoke checks, not a service-level guarantee. The Free
instance can sleep when idle, adding 50 seconds or more to startup; larger images,
multiple surfaces, and simultaneous requests can also take longer. Deployed
measurements and their scope are recorded in [deployment verification](deployment-verification.md).

## References

- [Take-home brief](https://github.com/treasurytakehome-rgb/instructions)
- [TTB health warning guidance](https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/ds-labeling-home/ds-health-warning)
