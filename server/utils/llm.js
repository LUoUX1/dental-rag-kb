/**
 * DeepSeek API 调用模块（非流式 + 流式，503 重试）
 */
const DEEPSEEK_BASE = 'https://api.deepseek.com';
const MODEL = 'deepseek-chat';

function hasValidApiKey(apiKey) {
  return Boolean(apiKey && apiKey.startsWith('sk-') && apiKey.length >= 20 && !apiKey.includes('your-api-key'));
}

async function callDeepSeek(systemPrompt, userContent, maxTokens = 4096) {
  const apiKey = process.env.DEEPSEEK_API_KEY;
  if (!hasValidApiKey(apiKey)) throw new Error('请在 .env 中设置有效的 DEEPSEEK_API_KEY');
  const { default: axios } = await import('axios');

  const MAX_RETRIES = 3;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const response = await axios.post(
        `${DEEPSEEK_BASE}/v1/chat/completions`,
        {
          model: MODEL,
          messages: [
            { role: 'system', content: systemPrompt },
            { role: 'user', content: userContent },
          ],
          temperature: 0.7,
          max_tokens: maxTokens,
        },
        {
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
          timeout: 120_000,
        }
      );
      const content = response.data?.choices?.[0]?.message?.content;
      if (!content) throw new Error('DeepSeek API 未返回有效内容');
      return content;
    } catch (err) {
      // 503 / 网络错误 / TLS断连 都重试（指数退避）
      const retriable = err.response?.status === 503 || !err.response || err.code === 'ECONNABORTED' || err.code === 'ECONNRESET' || /socket|network|TLS|ETIMEDOUT/i.test(err.message || '');
      if (attempt < MAX_RETRIES && retriable) {
        const waitMs = 1000 * (2 ** attempt);
        console.warn(`[LLM] DeepSeek 调用失败(${err.message?.slice(0, 80)})，${waitMs}ms 后重试 (${attempt + 1}/${MAX_RETRIES})`);
        await new Promise((r) => setTimeout(r, waitMs));
        continue;
      }
      throw err;
    }
  }
}

async function callDeepSeekStream(systemPrompt, userContent, onChunk, maxTokens = 4096) {
  const apiKey = process.env.DEEPSEEK_API_KEY;
  if (!hasValidApiKey(apiKey)) throw new Error('请在 .env 中设置有效的 DEEPSEEK_API_KEY');

  const MAX_RETRIES = 2;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    let resp;
    try {
      resp = await fetch(`${DEEPSEEK_BASE}/v1/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
        body: JSON.stringify({
          model: MODEL,
          messages: [
            { role: 'system', content: systemPrompt },
            { role: 'user', content: userContent },
          ],
          temperature: 0.7,
          max_tokens: maxTokens,
          stream: true,
        }),
        signal: AbortSignal.timeout(120_000),
      });
    } catch (fetchErr) {
      // 网络/TLS 瞬时错误也重试
      if (attempt < MAX_RETRIES) {
        const waitMs = 1000 * (2 ** attempt);
        console.warn(`[LLM] DeepSeek 连接失败(${fetchErr.message.slice(0, 80)})，${waitMs}ms 后重试 (${attempt + 1}/${MAX_RETRIES})`);
        await new Promise((r) => setTimeout(r, waitMs));
        continue;
      }
      throw new Error(`DeepSeek API 连接失败: ${fetchErr.message}`);
    }

    if ((resp.status === 503 || resp.status === 429) && attempt < MAX_RETRIES) {
      const waitMs = 1500 * (attempt + 1);
      console.warn(`[LLM] DeepSeek ${resp.status}，${waitMs}ms 后重试 (${attempt + 1}/${MAX_RETRIES})`);
      await new Promise((r) => setTimeout(r, waitMs));
      continue;
    }
    if (!resp.ok) {
      const errText = await resp.text();
      throw new Error(`DeepSeek API 错误 ${resp.status}: ${errText.slice(0, 200)}`);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 1);
        if (!line.startsWith('data:')) continue;
        const data = line.slice(5).trim();
        if (data === '[DONE]') return;
        try {
          const json = JSON.parse(data);
          const delta = json.choices?.[0]?.delta?.content;
          if (delta) onChunk(delta);
        } catch {}
      }
    }
    return;
  }
}

module.exports = { callDeepSeek, callDeepSeekStream, MODEL };
