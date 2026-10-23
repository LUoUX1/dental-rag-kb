/**
 * 向量数据库 —— 多集合文件型存储（text/table/image）
 * 与 ai-learner 版同构，但按集合分目录
 */
const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, '..', 'data', 'vectors');

function sanitize(name) {
  return name.replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 64);
}

function ensureDir(collection, docId) {
  const dir = path.join(DATA_DIR, collection, sanitize(docId));
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  return dir;
}

/** 存储向量：chunks 为 [{ id, text, index, ...extra }]
 * Q10 版本记录：覆盖前自动备份旧版到 versions/ 目录
 */
function store(collection, docId, fileName, chunks, vectors, extraMeta = {}) {
  const dir = ensureDir(collection, docId);

  // ── 版本备份：若已存在旧版，先复制到 versions/ ──
  const chunksPath = path.join(dir, 'chunks.json');
  if (fs.existsSync(chunksPath)) {
    const verDir = path.join(dir, 'versions');
    fs.mkdirSync(verDir, { recursive: true });
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    try {
      fs.copyFileSync(chunksPath, path.join(verDir, `chunks.${stamp}.json`));
      fs.copyFileSync(path.join(dir, 'vectors.json'), path.join(verDir, `vectors.${stamp}.json`));
      // 只保留最近 10 个版本，防止无限膨胀
      const vfiles = fs.readdirSync(verDir).filter((f) => f.endsWith('.json'));
      if (vfiles.length > 20) {
        vfiles.sort().slice(0, vfiles.length - 20).forEach((f) => fs.unlinkSync(path.join(verDir, f)));
      }
      console.log(`[VectorDB] 📦 版本备份: ${collection}/${docId} @ ${stamp}`);
    } catch (e) {
      console.error(`[VectorDB] 版本备份失败:`, e.message);
    }
  }

  fs.writeFileSync(path.join(dir, 'meta.json'), JSON.stringify({
    docId, fileName, collection, chunkCount: chunks.length,
    createdAt: fs.existsSync(path.join(dir, 'meta.json'))
      ? JSON.parse(fs.readFileSync(path.join(dir, 'meta.json'), 'utf-8')).createdAt
      : new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    ...extraMeta,
  }));
  fs.writeFileSync(path.join(dir, 'chunks.json'), JSON.stringify(chunks));
  fs.writeFileSync(path.join(dir, 'vectors.json'), JSON.stringify(vectors));
  console.log(`[VectorDB] ${collection}/${docId}: ${chunks.length} chunks stored`);
  return { collection, docId, chunkCount: chunks.length };
}

/** 跨集合检索 */
function search(queryVec, topK = 5, collections = ['text', 'table', 'image']) {
  const allResults = [];
  for (const collection of collections) {
    const collDir = path.join(DATA_DIR, collection);
    if (!fs.existsSync(collDir)) continue;
    const docDirs = fs.readdirSync(collDir);
    for (const docId of docDirs) {
      const chunksPath = path.join(collDir, docId, 'chunks.json');
      const vectorsPath = path.join(collDir, docId, 'vectors.json');
      if (!fs.existsSync(chunksPath) || !fs.existsSync(vectorsPath)) continue;
      try {
        const chunks = JSON.parse(fs.readFileSync(chunksPath, 'utf-8'));
        const vectors = JSON.parse(fs.readFileSync(vectorsPath, 'utf-8'));
        let meta = {};
        try { meta = JSON.parse(fs.readFileSync(path.join(collDir, docId, 'meta.json'), 'utf-8')); } catch {}
        for (let i = 0; i < vectors.length; i++) {
          const score = cosineSimilarity(queryVec, vectors[i]);
          allResults.push({ chunk: chunks[i], score, docId, collection, meta });
        }
      } catch (e) {
        console.error(`[VectorDB] 读取 ${collection}/${docId} 失败:`, e.message);
      }
    }
  }
  allResults.sort((a, b) => b.score - a.score);
  return allResults.slice(0, topK);
}

function listDocs(collection = null) {
  const docs = [];
  const collections = collection ? [collection] : ['text', 'table', 'image'];
  for (const coll of collections) {
    const collDir = path.join(DATA_DIR, coll);
    if (!fs.existsSync(collDir)) continue;
    for (const docId of fs.readdirSync(collDir)) {
      try {
        const meta = JSON.parse(fs.readFileSync(path.join(collDir, docId, 'meta.json'), 'utf-8'));
        docs.push(meta);
      } catch {}
    }
  }
  return docs;
}

/**
 * 按文档取回所有块（供同文档块扩展用）
 * @param {string} collection
 * @param {string} docId
 * @returns {Array<{chunk, docId, collection, meta, vec}>}
 */
function getDocChunks(collection, docId) {
  const dir = path.join(DATA_DIR, collection, sanitize(docId));
  const chunksPath = path.join(dir, 'chunks.json');
  const vectorsPath = path.join(dir, 'vectors.json');
  const metaPath = path.join(dir, 'meta.json');
  if (!fs.existsSync(chunksPath) || !fs.existsSync(vectorsPath)) return [];

  try {
    const chunks = JSON.parse(fs.readFileSync(chunksPath, 'utf-8'));
    const vectors = JSON.parse(fs.readFileSync(vectorsPath, 'utf-8'));
    let meta = {};
    try { meta = JSON.parse(fs.readFileSync(metaPath, 'utf-8')); } catch {}
    return chunks.map((chunk, i) => ({ chunk, docId, collection, meta, vec: vectors[i] }));
  } catch (e) {
    console.error(`[VectorDB] getDocChunks ${collection}/${docId} 失败:`, e.message);
    return [];
  }
}

/**
 * 同文档块扩展：对每个命中文档，取该文档内与查询最相关的 extraPerDoc 个块补充进结果
 * 扩展块排序用 BM25 + 向量混合（弥补纯向量对中文措辞差异的弱匹配）
 * @param {string} query - 原始查询文本（用于 BM25）
 * @param {number[]} queryVec
 * @param {Array} topChunks - hybridSearch 的结果
 * @param {number} extraPerDoc - 每个命中文档额外补充块数
 */
function expandByDoc(query, queryVec, topChunks, extraPerDoc = 5) {
  const seen = new Set(topChunks.map((c) => `${c.collection}/${c.docId}/${c.chunk.id}`));
  const extra = [];

  // 查询 tokens（BM25 用）
  const queryTokens = tokenize(query);

  // 按文档分组
  const byDoc = {};
  for (const c of topChunks) {
    const key = `${c.collection}/${c.docId}`;
    if (!byDoc[key]) byDoc[key] = [];
    byDoc[key].push(c);
  }

  for (const [key, hits] of Object.entries(byDoc)) {
    const [collection, docId] = key.split('/');
    const allChunks = getDocChunks(collection, docId);
    if (allChunks.length === 0) continue;

    // 高分文档（初始命中分数>0.85）：整篇相关，尽量带出全部块
    const highScoreDoc = hits.some((h) => h.score > 0.85);
    const docExtra = highScoreDoc ? Math.min(extraPerDoc * 3, allChunks.length) : extraPerDoc;

    // 文档内 BM25 分数（用查询 tokens）
    const df = {};
    const N = allChunks.length;
    const tfs = allChunks.map((c) => termFreq(tokenize(c.chunk.text)));
    for (const tf of tfs) for (const t of Object.keys(tf)) df[t] = (df[t] || 0) + 1;
    const avgDl = allChunks.reduce((s, c) => s + (c.chunk.text || '').length, 0) / N;
    const k1 = 1.5, b = 0.75;
    const bm25Scores = allChunks.map((c, i) => {
      const tf = tfs[i];
      const dl = (c.chunk.text || '').length;
      let score = 0;
      for (const t of queryTokens) {
        if (!tf[t]) continue;
        const n = df[t] || 1;
        const idf = Math.log(1 + (N - n + 0.5) / (n + 0.5));
        score += idf * ((tf[t] * (k1 + 1)) / (tf[t] + k1 * (1 - b + b * (dl / avgDl))));
      }
      return score;
    });
    const maxBm25 = Math.max(...bm25Scores, 0.0001);

    // 混合排序：0.5*向量归一 + 0.5*BM25归一
    const scored = allChunks
      .map((c, i) => {
        const vecSim = cosineSimilarity(queryVec, c.vec);
        const bm25Norm = bm25Scores[i] / maxBm25;
        return { ...c, score: vecSim * 0.5 + bm25Norm * 0.5 };
      })
      .filter((c) => !seen.has(`${c.collection}/${c.docId}/${c.chunk.id}`))
      .sort((a, b) => b.score - a.score);

    // 优先取与已命中块相邻的块（index 相近），再按混合分补充
    // 注意：adjacent 是 scored 的子集，必须去重，否则产生重复块
    const hitIndices = new Set(hits.map((h) => h.chunk.index));
    const adjacent = scored
      .filter((c) => hitIndices.has(c.chunk.index - 1) || hitIndices.has(c.chunk.index + 1))
      .sort((a, b) => b.score - a.score);
    const merged = [...adjacent, ...scored];
    const chosenSet = new Map();
    for (const c of merged) {
      if (!chosenSet.has(c.chunk.id)) chosenSet.set(c.chunk.id, c);
    }
    const chosen = [...chosenSet.values()].slice(0, docExtra);

    for (const c of chosen) {
      seen.add(`${c.collection}/${c.docId}/${c.chunk.id}`);
      // 高分文档的扩展块不降权（整篇相关），普通文档降权 0.92
      const finalScore = highScoreDoc ? c.score : c.score * 0.92;
      extra.push({
        chunk: c.chunk,
        score: finalScore,
        docId: c.docId,
        collection: c.collection,
        meta: c.meta,
      });
    }
  }

  return [...topChunks, ...extra].sort((a, b) => b.score - a.score);
}

// ─── 中文 BM25 关键词检索（bigram 分词，弥补语义嵌入对中文的弱项） ───

/** 中文文本 → bigram token 列表（对 CJK 字符两两组合，英文按词） */
function tokenize(text) {
  if (!text) return [];
  const tokens = [];
  const str = String(text);
  // 提取 CJK 连续段和英文/数字连续段
  const cjkRuns = str.match(/[\u4e00-\u9fff]+/g) || [];
  const wordRuns = str.match(/[a-zA-Z0-9]+/g) || [];

  for (const run of cjkRuns) {
    if (run.length === 1) tokens.push(run);
    for (let i = 0; i < run.length - 1; i++) tokens.push(run.slice(i, i + 2));
  }
  for (const w of wordRuns) tokens.push(w.toLowerCase());
  return tokens;
}

/** 统计 token 频率 */
function termFreq(tokens) {
  const tf = {};
  for (const t of tokens) tf[t] = (tf[t] || 0) + 1;
  return tf;
}

/**
 * BM25 混合检索：词面匹配 + 向量语义 加权融合
 * @param {string} query - 原始查询文本
 * @param {number[]} queryVec - 查询向量
 * @param {number} topK
 * @param {string[]} collections
 * @param {number} bm25Weight - BM25 权重（默认 0.4，向量 0.6）
 */
function hybridSearch(query, queryVec, topK = 5, collections = ['text', 'table', 'image'], bm25Weight = 0.4) {
  const allDocs = []; // { chunk, docId, collection, meta, vec }
  const docsWithTokens = [];

  for (const collection of collections) {
    const collDir = path.join(DATA_DIR, collection);
    if (!fs.existsSync(collDir)) continue;
    for (const docId of fs.readdirSync(collDir)) {
      const chunksPath = path.join(collDir, docId, 'chunks.json');
      const vectorsPath = path.join(collDir, docId, 'vectors.json');
      if (!fs.existsSync(chunksPath) || !fs.existsSync(vectorsPath)) continue;
      try {
        const chunks = JSON.parse(fs.readFileSync(chunksPath, 'utf-8'));
        const vectors = JSON.parse(fs.readFileSync(vectorsPath, 'utf-8'));
        let meta = {};
        try { meta = JSON.parse(fs.readFileSync(path.join(collDir, docId, 'meta.json'), 'utf-8')); } catch {}

        for (let i = 0; i < vectors.length; i++) {
          const entry = { chunk: chunks[i], docId, collection, meta, vec: vectors[i] };
          allDocs.push(entry);
          docsWithTokens.push({ entry, tf: termFreq(tokenize(chunks[i].text)) });
        }
      } catch (e) {
        console.error(`[VectorDB] 读取 ${collection}/${docId} 失败:`, e.message);
      }
    }
  }

  if (allDocs.length === 0) return [];

  // ── 向量相似度 ──
  for (const d of allDocs) d.vecScore = cosineSimilarity(queryVec, d.vec);

  // ── BM25 分数 ──
  const queryTokens = tokenize(query);
  const N = allDocs.length;
  const df = {};
  for (const { tf } of docsWithTokens) {
    for (const t of Object.keys(tf)) df[t] = (df[t] || 0) + 1;
  }
  const avgDl = allDocs.reduce((s, d) => s + (d.chunk.text || '').length, 0) / N;
  const k1 = 1.5, b = 0.75;

  for (const { entry, tf } of docsWithTokens) {
    const dl = (entry.chunk.text || '').length;
    let score = 0;
    for (const t of queryTokens) {
      if (!tf[t]) continue;
      const n = df[t] || 1;
      const idf = Math.log(1 + (N - n + 0.5) / (n + 0.5));
      score += idf * ((tf[t] * (k1 + 1)) / (tf[t] + k1 * (1 - b + b * (dl / avgDl))));
    }
    entry.bm25Score = score;
  }

  // ── 归一化并融合 ──
  const maxVec = Math.max(...allDocs.map((d) => d.vecScore));
  const maxBm25 = Math.max(...allDocs.map((d) => d.bm25Score));
  for (const d of allDocs) {
    const normVec = maxVec > 0 ? d.vecScore / maxVec : 0;
    const normBm25 = maxBm25 > 0 ? d.bm25Score / maxBm25 : 0;
    d.finalScore = normVec * (1 - bm25Weight) + normBm25 * bm25Weight;
  }

  allDocs.sort((a, b) => b.finalScore - a.finalScore);
  return allDocs.slice(0, topK).map((d) => ({
    chunk: d.chunk,
    score: d.finalScore,
    vecScore: d.vecScore,
    bm25Score: d.bm25Score,
    docId: d.docId,
    collection: d.collection,
    meta: d.meta,
  }));
}

function removeDoc(collection, docId) {
  const dir = path.join(DATA_DIR, collection, sanitize(docId));
  if (fs.existsSync(dir)) { fs.rmSync(dir, { recursive: true }); return true; }
  return false;
}

function dotProduct(a, b) { let s = 0; for (let i = 0; i < a.length; i++) s += a[i] * b[i]; return s; }
function magnitude(v) { let s = 0; for (let i = 0; i < v.length; i++) s += v[i] * v[i]; return Math.sqrt(s); }
function cosineSimilarity(a, b) {
  const mA = magnitude(a), mB = magnitude(b);
  if (mA === 0 || mB === 0) return 0;
  return dotProduct(a, b) / (mA * mB);
}

module.exports = { store, search, hybridSearch, expandByDoc, listDocs, removeDoc };
