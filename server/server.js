/**
 * 口腔医学知识库（Obsidian版）— Express 后端服务器
 * 端口 3002
 * 内容源：Obsidian Vault（D:\Documents\Obsidian Vault\口腔医学知识库\）
 */
const path = require('path');
const fs = require('fs');
const dotenv = require('dotenv');

// 优先加载 ai-learner 的 .env（已验证有效的 DeepSeek key）
const aiLearnerEnv = path.join(__dirname, '..', '..', 'ai-learner', '.env');
const localEnv = path.join(__dirname, '..', '.env');
dotenv.config({ path: fs.existsSync(aiLearnerEnv) ? aiLearnerEnv : localEnv });

const express = require('express');
const cors = require('cors');
const kbRoutes = require('./routes/kb');

const app = express();
const PORT = process.env.KB_PORT || 3002;

app.use(cors());
app.use(express.json({ limit: '50mb' }));

// 静态文件服务 — 图片访问（供 Discord 渲染）
app.use('/images', express.static(path.join(__dirname, 'data', 'images')));

// 网页版聊天界面（验收演示用）
app.use(express.static(path.join(__dirname, 'public')));

// API 路由
app.use('/api/kb', kbRoutes);

// 全局错误处理
app.use((err, _req, res, _next) => {
  console.error('[DentalKB] 未捕获错误:', err);
  res.status(500).json({ error: '服务器内部错误', detail: err.message });
});

app.listen(PORT, () => {
  const { listDocs } = require('./utils/vectordb');
  const docs = listDocs();
  console.log(`🦷 Dental KB (Obsidian版) 运行在 http://localhost:${PORT}`);
  console.log(`📚 已索引文档: ${docs.length} 个`);
  console.log(`🔑 DeepSeek API: ${process.env.DEEPSEEK_API_KEY ? '已配置' : '⚠️ 未配置'}`);
});
