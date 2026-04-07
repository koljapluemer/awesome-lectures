(function () {
  const { slug, tags: currentTags } = window.AL_VIEW;

  // — single tag suggest —
  const modal = document.getElementById('tag-modal');
  document.getElementById('suggest-tag-btn').addEventListener('click', () => {
    document.getElementById('tag-input').value = '';
    modal.showModal();
  });
  document.getElementById('tag-cancel').addEventListener('click', () => modal.close());
  modal.addEventListener('click', e => { if (e.target === modal) modal.close(); });
  document.getElementById('tag-submit').addEventListener('click', () => {
    const topic = document.getElementById('tag-input').value.trim();
    if (!topic) return;
    modal.close();
    if (AL_API_BASE === null) return;
    fetch(`${AL_API_BASE}/api/suggestions/topics/${encodeURIComponent(slug)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-AL-Fingerprint': getFingerprint() },
      body: JSON.stringify({ topic }),
    })
      .then(r => { if (r.ok) toast('Tag suggestion submitted, thanks!'); else throw new Error(); })
      .catch(() => toast('Could not submit suggestion', true));
  });

  // — edit tags —
  const editModal = document.getElementById('edit-tags-modal');
  const chipsEl   = document.getElementById('edit-tags-chips');
  const editInput = document.getElementById('edit-tags-input');
  let toRemove, toAdd;

  function renderChips() {
    chipsEl.innerHTML = '';
    currentTags.forEach(tag => {
      const chip = document.createElement('span');
      chip.className = 'edit-chip' + (toRemove.has(tag) ? ' marked' : '');
      chip.innerHTML = `${tag} <button type="button" aria-label="Toggle remove ${tag}">✕</button>`;
      chip.querySelector('button').addEventListener('click', () => {
        toRemove.has(tag) ? toRemove.delete(tag) : toRemove.add(tag);
        renderChips();
      });
      chipsEl.appendChild(chip);
    });
    toAdd.forEach((tag, i) => {
      const chip = document.createElement('span');
      chip.className = 'edit-chip new-tag';
      chip.innerHTML = `${tag} <button type="button" aria-label="Remove ${tag}">✕</button>`;
      chip.querySelector('button').addEventListener('click', () => {
        toAdd.splice(i, 1); renderChips();
      });
      chipsEl.appendChild(chip);
    });
  }

  document.getElementById('edit-tags-btn').addEventListener('click', () => {
    toRemove = new Set(); toAdd = [];
    editInput.value = '';
    renderChips();
    editModal.showModal();
  });
  function commitEditInput() {
    const tag = editInput.value.trim().replace(/,$/, '');
    if (tag && !currentTags.includes(tag) && !toAdd.includes(tag)) { toAdd.push(tag); renderChips(); }
    editInput.value = '';
  }
  editInput.addEventListener('keydown', e => {
    if (e.key !== 'Enter' && e.key !== ',') return;
    e.preventDefault();
    commitEditInput();
  });
  document.getElementById('edit-tags-add').addEventListener('click', commitEditInput);
  document.getElementById('edit-tags-cancel').addEventListener('click', () => editModal.close());
  editModal.addEventListener('click', e => { if (e.target === editModal) editModal.close(); });
  document.getElementById('edit-tags-submit').addEventListener('click', () => {
    const add = toAdd.slice(), remove = [...toRemove];
    editModal.close();
    if (AL_API_BASE === null || (!add.length && !remove.length)) return;
    fetch(`${AL_API_BASE}/api/suggestions/tags/${encodeURIComponent(slug)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-AL-Fingerprint': getFingerprint() },
      body: JSON.stringify({ add, remove }),
    })
      .then(r => { if (r.ok) toast('Tag suggestions submitted, thanks!'); else throw new Error(); })
      .catch(() => toast('Could not submit suggestions', true));
  });

  // — vote on ratings —
  const voteModal  = document.getElementById('vote-modal');
  const voteSlider = document.getElementById('vote-slider');
  const voteNumber = document.getElementById('vote-number');
  let voteField = null;

  voteSlider.addEventListener('input', () => { voteNumber.value = voteSlider.value; });
  voteNumber.addEventListener('input', () => {
    const v = Math.min(10, Math.max(0, parseFloat(voteNumber.value) || 0));
    voteSlider.value = v;
  });

  document.querySelectorAll('.vote-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      voteField = btn.dataset.field;
      document.getElementById('vote-modal-title').textContent = btn.dataset.label;
      const cur = parseFloat(btn.dataset.current) || 5;
      voteSlider.value = cur;
      voteNumber.value = cur;
      voteModal.showModal();
    });
  });

  document.getElementById('vote-cancel').addEventListener('click', () => voteModal.close());
  voteModal.addEventListener('click', e => { if (e.target === voteModal) voteModal.close(); });
  document.getElementById('vote-submit').addEventListener('click', () => {
    const value = Math.min(10, Math.max(0, parseFloat(voteNumber.value) || 0));
    voteModal.close();
    if (AL_API_BASE === null) return;
    fetch(`${AL_API_BASE}/api/ratings/${encodeURIComponent(slug)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-AL-Fingerprint': getFingerprint() },
      body: JSON.stringify({ field: voteField, value }),
    })
      .then(r => { if (r.ok) toast('Rating submitted, thanks!'); else throw new Error(); })
      .catch(() => toast('Could not submit rating', true));
  });
})();
