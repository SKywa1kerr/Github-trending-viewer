export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[char]);
}

export function safeExternalUrl(value) {
  try {
    const url = new URL(String(value ?? ''));
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.toString() : '#';
  } catch {
    return '#';
  }
}

export function formatChatText(text) {
  let html = escapeHtml(text ?? '');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/`(.+?)`/g, '<code>$1</code>');
  html = html.replace(/\n/g, '<br>');
  return html;
}

export function formatReadmeHtml(text) {
  if (!text) return '';

  let normalized = String(text);
  normalized = normalized.replace(/(^|\n)(\d+)[)\uff09\u3001]\s*/g, '$1$2. ');
  normalized = normalized.replace(/(^|\n)[\u2022\u00b7]\s*/g, '$1- ');
  normalized = normalized.replace(/\n{3,}/g, '\n\n').trim();

  const lines = normalized.split('\n').filter((line) => line.trim());
  let html = '';

  for (const line of lines) {
    const numbered = line.match(/^(\d+)\.\s*(.+)/);
    if (numbered) {
      html += `<div class="readme-point"><span class="readme-point-num">${escapeHtml(numbered[1])}</span><span class="readme-point-text">${escapeHtml(numbered[2].trim())}</span></div>`;
      continue;
    }

    if (line.startsWith('- ')) {
      html += `<div class="readme-point"><span class="readme-point-num">•</span><span class="readme-point-text">${escapeHtml(line.slice(2).trim())}</span></div>`;
      continue;
    }

    html += `<div class="readme-intro">${escapeHtml(line.trim())}</div>`;
  }

  return html;
}
