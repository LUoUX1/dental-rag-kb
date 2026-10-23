/**
 * 文本分块器 —— 中英文混合优化，支持结构化标注
 * chunkMarkdown: 按 Markdown 标题(##/###)分块，适用于 Obsidian 结构化笔记
 */
const CHUNK_SIZE = 800;
const OVERLAP = 100;

function chunkText(text, chunkSize = CHUNK_SIZE, overlap = OVERLAP) {
  if (!text || typeof text !== 'string') return [];
  const paragraphs = text.split(/\n\s*\n/).filter((p) => p.trim());
  const chunks = [];
  let current = '';
  let index = 0;

  for (const para of paragraphs) {
    const trimmed = para.trim();
    if ((current + '\n\n' + trimmed).length <= chunkSize) {
      current = current ? current + '\n\n' + trimmed : trimmed;
    } else {
      if (current.trim()) { chunks.push({ id: `c${index}`, text: current.trim(), index }); index++; }
      if (trimmed.length > chunkSize) {
        const sentences = trimmed.split(/(?<=[。！？.!?\n])\s*/).filter(Boolean);
        let sc = '';
        for (const sent of sentences) {
          if ((sc + sent).length > chunkSize) {
            if (sc.trim()) { chunks.push({ id: `c${index}`, text: sc.trim(), index }); index++; }
            sc = sent;
          } else { sc = sc ? sc + sent : sent; }
        }
        current = sc;
      } else { current = trimmed; }
    }
  }
  if (current.trim()) chunks.push({ id: `c${index}`, text: current.trim(), index });

  if (overlap > 0 && chunks.length > 1) {
    for (let i = 1; i < chunks.length; i++) {
      chunks[i].text = chunks[i - 1].text.slice(-overlap) + '\n' + chunks[i].text;
      chunks[i].id = chunks[i].id + 'o';
    }
  }
  return chunks;
}

/**
 * 按 Markdown 标题分块 —— Obsidian 结构化笔记专用
 * 每个 ##/### 标题作为一个语义单元，标题行保留在块内作为上下文
 * 若某章节超过 chunkSize，再按段落/句子二次分割
 * @param {string} text - Markdown 文本
 * @param {number} chunkSize
 * @param {string} titleContext - 笔记标题（注入每块开头，提高 BM25 命中）
 * @returns {Array<{ id, text, index, heading }>}
 */
function chunkMarkdown(text, chunkSize = CHUNK_SIZE, titleContext = '') {
  if (!text || typeof text !== 'string') return [];
  const lines = text.split('\n');

  // 收集章节块：每块以标题行开头
  const sections = [];
  let current = [];
  let currentHeading = '';

  for (const line of lines) {
    const hMatch = line.match(/^(#{1,4})\s+(.+)$/);
    if (hMatch && current.length > 0) {
      sections.push({ heading: currentHeading, text: current.join('\n').trim() });
      current = [];
      currentHeading = line.trim();
    }
    if (hMatch && current.length === 0) {
      currentHeading = line.trim();
    }
    current.push(line);
  }
  if (current.length > 0) {
    sections.push({ heading: currentHeading, text: current.join('\n').trim() });
  }

  // 对每节分块：超长则按段落切
  const prefix = titleContext ? `[${titleContext}] ` : '';
  const chunks = [];
  let index = 0;
  const pushChunk = (secText, heading) => {
    chunks.push({ id: `c${index}`, text: prefix + secText, index, heading });
    index++;
  };
  for (const sec of sections) {
    const secText = sec.text;
    if (secText.length <= chunkSize) {
      pushChunk(secText, sec.heading);
    } else {
      // 按段落拆
      const paras = secText.split(/\n\s*\n/).filter((p) => p.trim());
      let acc = '';
      for (const p of paras) {
        if ((acc + '\n\n' + p).length <= chunkSize) {
          acc = acc ? acc + '\n\n' + p : p;
        } else {
          if (acc.trim()) pushChunk(acc.trim(), sec.heading);
          acc = p;
        }
      }
      if (acc.trim()) pushChunk(acc.trim(), sec.heading);
    }
  }

  return chunks;
}

module.exports = { chunkText, chunkMarkdown };
