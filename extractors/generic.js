// ==Extractor==
// @name        generic
// @match       *
// @description Fallback for any page: title + readable main text
// ==/Extractor==

async function extract() {
  const root = (document.querySelector('article') || document.querySelector('main') || document.body).cloneNode(true);
  root.querySelectorAll('script,style,noscript,nav,footer,aside,form,iframe,svg,header [role=navigation]')
      .forEach(n => n.remove());
  const text = root.innerText
    .split('\n').map(s => s.replace(/\s+/g, ' ').trim()).filter(Boolean)
    .join('\n');
  return `# ${document.title}\n${location.href}\n\n${text}`;
}
