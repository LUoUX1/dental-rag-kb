/**
 * 口腔医学知识库 API 路由（Obsidian 内容源）
 *
 * POST /api/kb/index        — 文档索引（text/table/image）
 * POST /api/kb/ask          — RAG 问答（非流式）
 * POST /api/kb/ask-stream   — RAG 问答（SSE 流式）
 * GET  /api/kb/docs         — 已索引文档列表
 * GET  /api/kb/images/:filename — 图片文件
 * GET  /api/kb/health       — 健康检查
 */
const express = require('express');
const { chunkText, chunkMarkdown } = require('../utils/chunker');
const { embed, embedBatch } = require('../utils/embedding');
const { store, search, hybridSearch, expandByDoc, listDocs } = require('../utils/vectordb');
const { callDeepSeek, callDeepSeekStream } = require('../utils/llm');
const fs = require('fs');
const path = require('path');

const router = express.Router();
const IMAGE_DIR = path.join(__dirname, '..', 'data', 'images');

const DENTAL_SYSTEM_PROMPT = `你是一位资深的口腔医学知识助手。请根据提供的口腔医学资料片段回答用户的问题。

规则：
1. 只根据提供的片段内容回答，不要编造信息。没有相关信息的，如实说明。
2. 涉及分类、分期、对比等需要结构化展示的内容，请使用 Markdown 表格。
3. 引用来源时注明"根据 [片段X]"，有 frontmatter 元数据（分类/标签）时一并说明。
4. 回答末尾列出本次参考的片段编号及简要摘要。
5. 用专业但易懂的中文回答。
6. 片段标注【状态:待审核】或【状态:待更新】时，回答中必须提醒该内容未经权威来源审核/可能过时，建议以最新教材或指南为准。`;

/** 将二维数组转 Markdown 表格 */
function formatTableAsMarkdown(data) {
  if (!data || data.length === 0) return '(空表格)';
  const header = data[0];
  const rows = data.slice(1);
  let md = '| ' + header.join(' | ') + ' |\n';
  md += '| ' + header.map(() => '---').join(' | ') + ' |\n';
  for (const row of rows) {
    md += '| ' + row.map((c) => (c || '').replace(/\|/g, '\\|')).join(' | ') + ' |\n';
  }
  return md;
}

/** 构建 RAG 上下文 */
function buildContext(topChunks) {
  return topChunks
    .map((c, i) => {
      const typeTag = c.collection === 'table' ? '[表格]' : c.collection === 'image' ? '[图片描述]' : '';
      const metaTag = c.chunk.category ? `(分类:${c.chunk.category})` : '';
      // 状态标注：待审核/待更新的内容提示模型谨慎引用
      const status = c.meta?.status;
      const statusTag = status && status !== '稳定' ? `【状态:${status}】` : '';
      return `[片段${i + 1}${typeTag}${metaTag}${statusTag} 来源:${c.docId}]\n${c.chunk.text}`;
    })
    .join('\n\n---\n\n');
}

// ═══════════ 索引 ═══════════
router.post('/index', async (req, res) => {
  try {
    const { text, fileName, docId, type = 'text', tableId, tableData, imageId, imagePath, imagePage, category, tags, source, mdSource, updated, status } = req.body;

    if (!text || typeof text !== 'string' || text.trim().length === 0) {
      return res.status(400).json({ error: '请提供有效的文本内容' });
    }

    const name = fileName || '未命名文档';
    console.log(`[Index] ${type}/${name} (${text.length} chars)`);

    // Obsidian 笔记按 Markdown 标题分块（注入笔记名提高命中），普通文本按段落分块
    let titleContext = '';
    if (mdSource) {
      titleContext = name.replace(/（Obsidian）$/, '').trim();
    }
    const chunks = mdSource ? chunkMarkdown(text, 800, titleContext) : chunkText(text);
    const enrichedChunks = chunks.map((c) => ({
      ...c,
      docId, type,
      tableId: tableId || null, tableData: tableData || null,
      imageId: imageId || null, imagePath: imagePath || null, imagePage: imagePage || null,
      category: category || null, tags: tags || null, source: source || null,
    }));

    const vectors = await embedBatch(enrichedChunks.map((c) => c.text));

    const extraMeta = {};
    if (tableId) extraMeta.tableId = tableId;
    if (tableData) extraMeta.tableData = tableData;
    if (imageId) extraMeta.imageId = imageId;
    if (imagePath) extraMeta.imagePath = imagePath;
    if (category) extraMeta.category = category;
    if (source) extraMeta.source = source;
    if (updated) extraMeta.updated = updated;
    if (status) extraMeta.status = status;

    const result = store(type, docId, name, enrichedChunks, vectors, extraMeta);
    res.json({ ...result, success: true });
  } catch (err) {
    console.error('[Index] 错误:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// ═══════════ RAG 问答（非流式） ═══════════
router.post('/ask', async (req, res) => {
  try {
    const { question } = req.body;
    if (!question || typeof question !== 'string' || question.trim().length === 0) {
      return res.status(400).json({ error: '请输入问题' });
    }

    console.log(`[RAG] 问题: "${question.slice(0, 80)}${question.length > 80 ? '…' : ''}"`);

    const questionVec = await embed(question);
    // 混合检索：BM25 词面匹配(0.4) + 向量语义(0.6)，集合配额文本5/表格2/图片1
    const textChunks = hybridSearch(question, questionVec, 5, ['text']);
    const tableChunks = hybridSearch(question, questionVec, 2, ['table']);
    const imageChunks = hybridSearch(question, questionVec, 1, ['image']);
    // 同文档块扩展：命中的文档补取相邻高相关块，避免"标题命中但内容缺失"
    const expanded = expandByDoc(question, questionVec, [...textChunks, ...tableChunks, ...imageChunks], 5);
    const topChunks = expanded.slice(0, 20);

    if (topChunks.length === 0) {
      return res.json({
        answer: '⚠️ 知识库中没有找到相关信息。请先在 Obsidian 中写入口腔医学笔记并运行 vault_sync.py 同步。',
        sources: [], tables: [], images: [],
      });
    }

    console.log(`[RAG] 检索到 ${topChunks.length} 片段 (最高分=${topChunks[0].score.toFixed(3)})`);

    const context = buildContext(topChunks);
    const answer = await callDeepSeek(DENTAL_SYSTEM_PROMPT, `参考资料：\n\n${context}\n\n用户问题：${question}`, 2048);

    const tables = topChunks
      .filter((c) => c.collection === 'table' && c.chunk.tableData)
      .map((c) => ({
        id: c.chunk.tableId,
        data: c.chunk.tableData,
        markdown: formatTableAsMarkdown(c.chunk.tableData),
        score: Math.round(c.score * 100) / 100,
      }));

    const images = topChunks
      .filter((c) => c.collection === 'image')
      // 相关性过滤：分数必须足够高（≥0.65）且不低于文本最高分的70%，
      // 避免不相关配图（如问牙周炎返回智齿图）
      .filter((c) => {
        const topTextScore = topChunks.filter((x) => x.collection === 'text')[0]?.score ?? 1;
        return c.score >= 0.65 && c.score >= topTextScore * 0.7;
      })
      .map((c) => ({
        id: c.chunk.imageId,
        path: c.chunk.imagePath,
        page: c.chunk.imagePage,
        description: c.chunk.text,
        score: Math.round(c.score * 100) / 100,
        url: c.chunk.imagePath ? `/images/${path.basename(c.chunk.imagePath)}` : null,
      }));

    res.json({
      answer,
      sources: topChunks.map((c) => ({
        id: c.chunk.id,
        text: c.chunk.text.slice(0, 150) + (c.chunk.text.length > 150 ? '…' : ''),
        score: Math.round(c.score * 100) / 100,
        docId: c.docId,
        collection: c.collection,
        category: c.chunk.category,
      })),
      tables,
      images,
    });
  } catch (err) {
    console.error('[RAG] 错误:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// ═══════════ RAG 问答（SSE 流式） ═══════════
router.post('/ask-stream', async (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream; charset=utf-8');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders?.();
  function send(data) { res.write(`data: ${JSON.stringify(data)}\n\n`); }

  const { question } = req.body;
  if (!question || typeof question !== 'string' || question.trim().length === 0) {
    send({ error: '请输入问题' });
    return res.end();
  }

  console.log(`[RAG-Stream] "${question.slice(0, 60)}"`);
  try {
    const questionVec = await embed(question);
    // 混合检索：BM25 + 向量，集合配额文本5/表格2/图片1 + 同文档扩展
    const textChunks = hybridSearch(question, questionVec, 5, ['text']);
    const tableChunks = hybridSearch(question, questionVec, 2, ['table']);
    const imageChunks = hybridSearch(question, questionVec, 1, ['image']);
    const expanded = expandByDoc(question, questionVec, [...textChunks, ...tableChunks, ...imageChunks], 5);
    const topChunks = expanded.slice(0, 20);

    if (topChunks.length === 0) {
      send({ chunk: '⚠️ 知识库中没有找到相关信息。请先在 Obsidian 中写入笔记并同步。' });
      send({ done: true });
      return res.end();
    }

    const tables = topChunks
      .filter((c) => c.collection === 'table' && c.chunk.tableData)
      .map((c) => ({
        id: c.chunk.tableId, data: c.chunk.tableData,
        markdown: formatTableAsMarkdown(c.chunk.tableData),
        score: Math.round(c.score * 100) / 100,
      }));

    const images = topChunks
      .filter((c) => c.collection === 'image')
      // 相关性过滤：分数≥0.65 且不低于文本最高分70%（避免不相关配图）
      .filter((c) => {
        const topTextScore = topChunks.filter((x) => x.collection === 'text')[0]?.score ?? 1;
        return c.score >= 0.65 && c.score >= topTextScore * 0.7;
      })
      .map((c) => ({
        id: c.chunk.imageId, path: c.chunk.imagePath, page: c.chunk.imagePage,
        url: c.chunk.imagePath ? `/images/${path.basename(c.chunk.imagePath)}` : null,
        score: Math.round(c.score * 100) / 100,
      }));

    send({ meta: { tables, images, sourceCount: topChunks.length, topScore: Math.round(topChunks[0].score * 100) / 100 } });

    const context = buildContext(topChunks);
    await callDeepSeekStream(DENTAL_SYSTEM_PROMPT, `参考资料：\n\n${context}\n\n用户问题：${question}`, (chunk) => send({ chunk }), 2048);

    send({ done: true });
    res.end();
  } catch (err) {
    console.error('[RAG-Stream] 错误:', err.message);
    send({ error: err.message });
    res.end();
  }
});

// ═══════════ 其他 ═══════════
router.get('/docs', (_req, res) => { res.json({ docs: listDocs() }); });

router.get('/images/:filename', (req, res) => {
  const filepath = path.join(IMAGE_DIR, req.params.filename);
  if (fs.existsSync(filepath)) res.sendFile(filepath);
  else res.status(404).json({ error: '图片不存在' });
});

router.get('/health', (_req, res) => {
  res.json({ status: 'ok', model: require('../utils/llm').MODEL, docs: listDocs() });
});

module.exports = router;
