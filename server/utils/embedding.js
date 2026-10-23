/**
 * 嵌入模型模块 —— @xenova/transformers（hf-mirror 镜像）
 * 中文医学语义用 bge-base-zh（768维），远优于 all-MiniLM（384维英文为主）
 */
const path = require('path');

const MODEL_NAME = 'Xenova/bge-base-zh';
const EMBED_DIM = 768;

let pipelinePromise = null;

function getPipeline() {
  if (!pipelinePromise) {
    pipelinePromise = (async () => {
      const { pipeline, env } = await import('@xenova/transformers');
      env.allowLocalModels = false;
      env.remoteHost = 'https://hf-mirror.com';
      env.cacheDir = path.join(__dirname, '..', 'data', '.cache');
      console.log(`[Embedding] 加载 ${MODEL_NAME} (${EMBED_DIM}维) ...`);
      const pipe = await pipeline('feature-extraction', MODEL_NAME, { quantized: true });
      console.log(`[Embedding] 模型加载完成 (${EMBED_DIM}维)`);
      return pipe;
    })();
  }
  return pipelinePromise;
}

async function embed(text) {
  const pipe = await getPipeline();
  const result = await pipe(text, { pooling: 'mean', normalize: true });
  return Array.from(result.data);
}

async function embedBatch(texts) {
  const pipe = await getPipeline();
  const vectors = [];
  for (let i = 0; i < texts.length; i++) {
    const result = await pipe(texts[i], { pooling: 'mean', normalize: true });
    vectors.push(Array.from(result.data));
    if ((i + 1) % 10 === 0) console.log(`[Embedding] 进度: ${i + 1}/${texts.length}`);
  }
  return vectors;
}

module.exports = { embed, embedBatch };
