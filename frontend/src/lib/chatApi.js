export function chatEndpoint(baseUrl = '') {
  return baseUrl ? `${baseUrl.replace(/\/+$/, '')}/chat` : '/api/chat'
}

export async function requestReply({ message, threadId, baseUrl = '', fetchImpl = globalThis.fetch }) {
  const response = await fetchImpl(chatEndpoint(baseUrl), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, thread_id: threadId }),
  })

  if (!response.ok) {
    throw new Error(response.status >= 500
      ? `服务暂时不可用（HTTP ${response.status}），请稍后再试。`
      : `请求未被服务接受（HTTP ${response.status}），请检查服务配置后重试。`)
  }

  let data
  try {
    data = await response.json()
  } catch {
    throw new Error('服务返回了无法识别的内容，请稍后再试。')
  }
  if (data?.status === 'empty' || (data?.status === 'success' && !data.content?.trim?.())) {
    return '未获取到回复，请换一种表达或稍后重试。'
  }
  if (data?.status !== 'success' || typeof data.content !== 'string') {
    throw new Error('本次处理未能完成，请检查后端日志与模型、工具配置后重试。')
  }
  return data.content
}
