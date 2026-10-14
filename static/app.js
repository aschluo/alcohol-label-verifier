const form = document.querySelector('#application');
const filesInput = document.querySelector('#images');
const sampleSelect = document.querySelector('#sample');
const button = document.querySelector('#check-button');
const progress = document.querySelector('#progress');
const errorBox = document.querySelector('#error');
const labels = {matches:'Matches', mismatch:'Mismatch', needs_review:'Needs review', not_applicable:'Not applicable'};
let selectedFiles = [], sampleCases = [], previewUrls = [], report = null, busy = false, selectionVersion = 0;

function showError(message) {errorBox.textContent = message; errorBox.hidden = false;}
function clearResults() {document.querySelector('#results').hidden = true; report = null; errorBox.hidden = true;}
function preview(files) {
  selectedFiles = [...files]; clearResults();
  previewUrls.forEach(URL.revokeObjectURL); previewUrls = [];
  const container = document.querySelector('#previews'); container.replaceChildren();
  document.querySelector('#file-status').textContent = `${files.length} image${files.length === 1 ? '' : 's'} selected.`;
  for (const file of files) {
    const figure = document.createElement('figure'), image = document.createElement('img'), caption = document.createElement('figcaption');
    const url = URL.createObjectURL(file); previewUrls.push(url); image.src = url; image.alt = `Label image: ${file.name}`;
    caption.textContent = file.name; figure.append(image, caption); container.append(figure);
  }
}
function userUpload(files) {
  selectionVersion++; sampleSelect.value = ''; document.querySelector('#sample-description').textContent = '';
  preview(files);
}
filesInput.addEventListener('change', () => userUpload(filesInput.files));
document.querySelector('#camera').addEventListener('change', event => userUpload(event.target.files));
function importedChanged() {
  const imported = form.elements.imported.checked;
  document.querySelector('#country-field').hidden = !imported; form.elements.country.required = imported;
}
form.elements.imported.addEventListener('change', importedChanged);
form.addEventListener('input', clearResults);

async function loadSamples() {
  try {
    const response = await fetch('/api/samples'); if (!response.ok) throw new Error();
    sampleCases = await response.json();
    for (const sample of sampleCases) {const option = document.createElement('option'); option.value = sample.id; option.textContent = sample.title; sampleSelect.append(option);}
  } catch {document.querySelector('#sample-description').textContent = 'Test labels are unavailable. You can still upload your own image.';}
}
sampleSelect.addEventListener('change', async () => {
  const version = ++selectionVersion;
  const sample = sampleCases.find(item => item.id === sampleSelect.value); if (!sample) return;
  clearResults();
  try {
    const response = await fetch(`/samples/${sample.image}`); if (!response.ok) throw new Error('Unable to load the test image.');
    const blob = await response.blob(); if (version !== selectionVersion) return;
    for (const [key, value] of Object.entries(sample.application)) {
      if (key === 'imported') form.elements[key].checked = value; else if (form.elements[key]) form.elements[key].value = value;
    }
    importedChanged(); preview([new File([blob], sample.image, {type:blob.type})]);
    document.querySelector('#sample-description').textContent = sample.description;
  } catch (error) {if (version === selectionVersion) showError(error.message);}
});

function setBusy(value) {
  busy = value;
  document.querySelectorAll('input, select, #check-button').forEach(element => {element.disabled = value;});
  button.firstChild.textContent = value ? 'Reading the label… ' : 'Check label ';
}
function addValue(parent, title, value) {
  if (!value) return;
  const paragraph = document.createElement('p'), span = document.createElement('span'); span.className = 'value-label'; span.textContent = `${title}: `;
  paragraph.append(span, document.createTextNode(value)); parent.append(paragraph);
}
function render(data) {
  const section = document.querySelector('#results'); section.hidden = false;
  document.querySelector('#result-title').textContent = data.status === 'mismatch' ? 'Differences found' : data.status === 'matches' ? 'All checks match' : 'Some checks need your review';
  document.querySelector('#timing').textContent = `${(data.client_elapsed_ms / 1000).toFixed(2)} seconds · ${data.image_count} image${data.image_count === 1 ? '' : 's'}`;
  document.querySelector('#result-description').textContent = 'Review the findings below. Bold-heading estimates use image pixels. Uncertain formatting and physical text size need your review.';
  const checks = document.querySelector('#checks'); checks.replaceChildren();
  for (const check of data.checks) {
    const row = document.createElement('article'), title = document.createElement('div'), heading = document.createElement('h3'), badge = document.createElement('span'), body = document.createElement('div');
    row.className = 'check-row'; heading.textContent = check.label; badge.className = `badge ${check.status}`; badge.textContent = labels[check.status]; title.append(heading, badge);
    addValue(body, 'Application / requirement', check.expected); addValue(body, 'Label', check.observed);
    const reason = document.createElement('p'); reason.className = 'reason'; reason.textContent = check.reason; body.append(reason); row.append(title, body); checks.append(row);
  }
  document.querySelector('#extracted').textContent = data.extracted_text || 'No readable text found.';
  document.querySelector('#reread-details').hidden = !data.reading_attempts?.length;
  document.querySelector('#reread-text').textContent = (data.reading_attempts || []).map(attempt => `Field: ${attempt.field}\nFirst reading: ${attempt.initial_text}\nSecond reading: ${attempt.reread_text}\nMethod: ${attempt.method}`).join('\n\n');
  document.querySelector('#warning-diff').textContent = data.warning_diff;
  document.querySelector('#warning-details').hidden = !data.warning_diff;
  section.focus(); section.scrollIntoView({behavior:'smooth', block:'start'});
}
form.addEventListener('submit', async event => {
  event.preventDefault(); if (busy) return;
  clearResults();
  if (!selectedFiles.length) {showError('Choose a label image first.'); filesInput.focus(); return;}
  if (selectedFiles.length > 6) {showError('Choose up to six images for one application.'); return;}
  if (selectedFiles.some(file => file.size > 10 * 1024 * 1024)) {showError('Each image must be 10 MB or smaller.'); return;}
  const application = Object.fromEntries(new FormData(form)); application.imported = form.elements.imported.checked;
  const payload = new FormData(); payload.append('application', JSON.stringify(application)); selectedFiles.forEach(file => payload.append('images', file));
  const started = performance.now(), controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);
  const reminder = setTimeout(() => {progress.textContent = 'Still reading. This check is taking longer than our five-second target.';}, 5000);
  progress.textContent = 'Reading your images and checking the application…'; setBusy(true);
  try {
    const response = await fetch('/api/verify', {method:'POST', body:payload, signal:controller.signal});
    const data = await response.json(); if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'The application could not be checked. Please try again.');
    data.client_elapsed_ms = Math.round(performance.now() - started); data.application = application;
    report = data; render(data); progress.textContent = '';
  } catch (error) {progress.textContent = ''; showError(error.name === 'AbortError' ? 'The check timed out. Try a clearer image or fewer label images.' : error.message);}
  finally {clearTimeout(timeout); clearTimeout(reminder); setBusy(false);}
});
document.querySelector('#download').addEventListener('click', () => {
  if (!report) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], {type:'application/json'}));
  const link = document.createElement('a'); link.href = url; link.download = 'label-review.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
loadSamples();
