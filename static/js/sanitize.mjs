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

  const lines = normalized.split('\n').map(line => line.trim()).filter(Boolean);
  let html = '';

  for (const line of lines) {
    const heading = line.match(/^#{1,6}\s+(.+)/);
    if (heading) {
      html += '<h3 class="readme-heading">' + formatReadmeInline(heading[1]) + '</h3>';
      continue;
    }
    const numbered = line.match(/^(\d+)\.\s*(.+)/);
    if (numbered) {
      html += `<div class="readme-point"><span class="readme-point-num">${escapeHtml(numbered[1])}</span><span class="readme-point-text">${formatReadmeInline(numbered[2].trim())}</span></div>`;
      continue;
    }

    if (/^[-*]\s/.test(line)) {
      html += `<div class="readme-point"><span class="readme-point-num">•</span><span class="readme-point-text">${formatReadmeInline(line.slice(2).trim())}</span></div>`;
      continue;
    }

    html += `<p class="readme-intro">${formatReadmeInline(line)}</p>`;
  }

  return html;
}

// Only local emphasis and inline code are introduced after HTML is escaped.
function formatReadmeInline(text) {
  return escapeHtml(text).replace(/`([^`]+)`|\*\*([^*]+)\*\*/g,
    (_, code, strong) => code !== undefined ? '<code>' + code + '</code>' : '<strong>' + strong + '</strong>');
}
