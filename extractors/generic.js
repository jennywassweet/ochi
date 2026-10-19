// ==Extractor==
// @name        generic
// @match       *
// @require     lib/Readability-readerable.js
// @require     lib/Readability.js
// @description Fallback for any page: title + readable text. Article-like pages (news, blogs, docs) are reduced to the article with Mozilla Readability; everything else gets the page's main text. Add ochi_mode=page or ochi_mode=article to the URL to force one.
// ==/Extractor==

async function extract() {
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const mode = new URL(location.href).searchParams.get('ochi_mode');  // page | article | (auto)

  // the page's main text minus navigation and chrome, one line per block element
  // (a detached copy has no layout, so innerText would run everything into one line)
  const semantic = document.querySelector('article') || document.querySelector('main');
  const BLOCK = 'address,article,aside,blockquote,dd,div,dl,dt,figcaption,figure,footer,h1,h2,h3,h4,h5,h6,header,'
    + 'li,main,nav,ol,p,pre,section,table,td,th,tr,ul';
  const pageText = () => {
    const root = (semantic || document.body).cloneNode(true);
    root.querySelectorAll('script,style,noscript,template,nav,footer,aside,form,iframe,svg,header [role=navigation]')
      .forEach(n => n.remove());
    const lines = [];
    let line = '', block;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let node; (node = walker.nextNode());) {
      const b = node.parentElement.closest(BLOCK);
      if (b !== block) { lines.push(clean(line)); line = ''; block = b; }
      line += node.textContent;
    }
    lines.push(clean(line));
    return lines.filter(Boolean).join('\n');
  };

  // Readability's article HTML -> lines, one per block, headings marked (parsed detached: nothing loads or runs)
  const articleText = html => {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const blocks = doc.body.querySelectorAll('h1,h2,h3,h4,h5,h6,p,li,blockquote,pre,figcaption,td,th,dt,dd');
    const lines = [...blocks]
      .filter(el => !el.parentElement.closest('p,li,blockquote,pre,td,th,dd'))  // innermost text only once
      .map(el => {
        const t = el.tagName === 'PRE' ? el.textContent.trim() : clean(el.textContent);
        const h = /^H(\d)$/.exec(el.tagName);
        return t && (h ? `${'#'.repeat(+h[1] + 1)} ${t}` : el.tagName === 'LI' ? `- ${t}` : t);
      })
      .filter(Boolean);
    return lines.length ? lines.join('\n') : clean(doc.body.textContent);
  };

  const plain = pageText();
  let article = null;
  if (mode !== 'page' && (mode === 'article' || isProbablyReaderable(document))) {
    try {
      article = new Readability(document.cloneNode(true)).parse();  // works on a copy: the tab is untouched
    } catch (e) {
      article = null;
    }
  }
  const text = article && articleText(article.content || '');
  // trust the article only if it is substantial and, where the page marks its main content (<main>/<article>),
  // keeps a real share of it (listings and index pages fail this); forced article mode: always
  const useArticle = text && (mode === 'article'
    || (text.length >= 500 && (!semantic || text.length >= 0.4 * plain.length)));

  if (!useArticle) return `# ${document.title}\n${location.href}\n[mode: page]\n\n${plain}`;
  const meta = [article.byline, article.siteName, article.publishedTime && article.publishedTime.slice(0, 10)]
    .map(clean).filter(Boolean).join(' · ');
  return `# ${clean(article.title) || document.title}\n${location.href}\n[mode: article${meta ? ' · ' + meta : ''}]\n\n${text}`;
}
