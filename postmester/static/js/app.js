/* PostMester — Frontend JS */

const form = document.getElementById('postForm');
const photoInput = document.getElementById('photoInput');
const uploadZone = document.getElementById('uploadZone');
const uploadPlaceholder = document.getElementById('uploadPlaceholder');
const photoPreview = document.getElementById('photoPreview');
const removePhoto = document.getElementById('removePhoto');
const descriptionInput = document.getElementById('description');
const charCount = document.getElementById('charCount');
const generateBtn = document.getElementById('generateBtn');
const btnText = generateBtn.querySelector('.btn-text');
const btnLoading = generateBtn.querySelector('.btn-loading');
const result = document.getElementById('result');
const resultPost = document.getElementById('resultPost');
const resultHashtags = document.getElementById('resultHashtags');
const errorBox = document.getElementById('errorBox');
const errorText = document.getElementById('errorText');
const copyBtn = document.getElementById('copyBtn');
const copyAllBtn = document.getElementById('copyAllBtn');
const regenerateBtn = document.getElementById('regenerateBtn');

let currentPost = '';
let currentHashtags = '';

// ── Photo upload ───────────────────────────────────────
photoInput.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (file) showPreview(file);
});

uploadZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadZone.classList.add('dragover');
});
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file && file.type.startsWith('image/')) {
    const dt = new DataTransfer();
    dt.items.add(file);
    photoInput.files = dt.files;
    showPreview(file);
  }
});

function showPreview(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    photoPreview.src = e.target.result;
    photoPreview.classList.remove('hidden');
    uploadPlaceholder.classList.add('hidden');
    removePhoto.classList.remove('hidden');
  };
  reader.readAsDataURL(file);
}

removePhoto.addEventListener('click', (e) => {
  e.stopPropagation();
  photoInput.value = '';
  photoPreview.classList.add('hidden');
  uploadPlaceholder.classList.remove('hidden');
  removePhoto.classList.add('hidden');
});

// ── Char count ─────────────────────────────────────────
descriptionInput.addEventListener('input', () => {
  charCount.textContent = descriptionInput.value.length;
});

// ── Pills ──────────────────────────────────────────────
function setupPills(groupId, inputId) {
  const group = document.getElementById(groupId);
  const input = document.getElementById(inputId);
  group.querySelectorAll('.pill').forEach(pill => {
    pill.addEventListener('click', () => {
      group.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      input.value = pill.dataset.value;
    });
  });
}
setupPills('platformGroup', 'platformInput');
setupPills('toneGroup', 'toneInput');

// ── Form submit ────────────────────────────────────────
form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const description = descriptionInput.value.trim();
  if (!description) {
    showError('Beskriv venligst jobbet — bare to ord er nok!');
    descriptionInput.focus();
    return;
  }

  setLoading(true);
  hideError();
  hideResult();

  try {
    const formData = new FormData(form);
    const response = await fetch('/generate', {
      method: 'POST',
      body: formData,
    });

    const data = await response.json();

    if (!response.ok || data.error) {
      throw new Error(data.error || 'Noget gik galt — prøv igen');
    }

    currentPost = data.post;
    currentHashtags = data.hashtags || '';

    showResult(data);
    result.scrollIntoView({ behavior: 'smooth', block: 'start' });

  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
});

// ── Regenerate ─────────────────────────────────────────
regenerateBtn.addEventListener('click', () => {
  form.dispatchEvent(new Event('submit'));
});

// ── Copy ───────────────────────────────────────────────
copyBtn.addEventListener('click', () => {
  copyToClipboard(currentPost, copyBtn, 'copyBtnText', '✅ Kopieret!', '📋 Kopiér opslag');
});

copyAllBtn.addEventListener('click', () => {
  const full = currentPost + '\n\n' + currentHashtags;
  copyToClipboard(full, copyAllBtn, 'copyAllBtnText', '✅ Kopieret!', '📋 Kopiér med hashtags');
});

function copyToClipboard(text, btn, textId, successMsg, defaultMsg) {
  navigator.clipboard.writeText(text).then(() => {
    btn.classList.add('copied');
    document.getElementById(textId).textContent = successMsg;
    setTimeout(() => {
      btn.classList.remove('copied');
      document.getElementById(textId).textContent = defaultMsg;
    }, 2000);
  }).catch(() => {
    // Fallback
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    document.getElementById(textId).textContent = successMsg;
    setTimeout(() => {
      document.getElementById(textId).textContent = defaultMsg;
    }, 2000);
  });
}

// ── Helpers ────────────────────────────────────────────
function setLoading(loading) {
  generateBtn.disabled = loading;
  btnText.classList.toggle('hidden', loading);
  btnLoading.classList.toggle('hidden', !loading);
}

function showResult(data) {
  resultPost.textContent = data.post;
  if (data.hashtags) {
    resultHashtags.textContent = data.hashtags;
    resultHashtags.classList.remove('hidden');
  } else {
    resultHashtags.classList.add('hidden');
  }
  result.classList.remove('hidden');
}

function hideResult() {
  result.classList.add('hidden');
}

function showError(msg) {
  errorText.textContent = msg;
  errorBox.classList.remove('hidden');
}

function hideError() {
  errorBox.classList.add('hidden');
}
