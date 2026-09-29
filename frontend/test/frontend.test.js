import test from 'node:test'
import assert from 'node:assert/strict'
import { getOrCreateThreadId, newThreadId, UUID_PATTERN } from '../src/lib/session.js'
import { requestReply, chatEndpoint } from '../src/lib/chatApi.js'
import { renderMarkdown } from '../src/lib/markdown.js'

function memoryStorage() {
  const items = new Map()
  return { getItem: (key) => items.get(key), setItem: (key, value) => items.set(key, value) }
}

test('a page reuses its saved UUID, while a new conversation and separate storage get independent IDs', () => {
  const storage = memoryStorage()
  const initial = getOrCreateThreadId(storage)
  assert.match(initial, UUID_PATTERN)
  assert.equal(getOrCreateThreadId(storage), initial)
  const next = newThreadId(storage)
  assert.notEqual(next, initial)
  assert.equal(getOrCreateThreadId(storage), next)
  assert.notEqual(getOrCreateThreadId(memoryStorage()), initial)
})

test('blocked or invalid storage never falls back to a shared session', () => {
  const blocked = { getItem() { throw new Error('blocked') }, setItem() { throw new Error('blocked') } }
  const first = getOrCreateThreadId(blocked)
  assert.match(first, UUID_PATTERN)
  assert.notEqual(getOrCreateThreadId(blocked), first)
  const invalid = { getItem: () => 'default', setItem() {} }
  assert.match(getOrCreateThreadId(invalid), UUID_PATTERN)
})

test('each chat request sends its UUID and routes through the proxy or configured backend', async () => {
  const threadId = getOrCreateThreadId(memoryStorage())
  let called
  const reply = await requestReply({ message: '北京天气', threadId, fetchImpl: async (url, options) => {
    called = { url, options }
    return { ok: true, json: async () => ({ status: 'success', content: '晴天' }) }
  } })
  assert.equal(called.url, '/api/chat')
  assert.deepEqual(JSON.parse(called.options.body), { message: '北京天气', thread_id: threadId })
  assert.equal(reply, '晴天')
  assert.equal(chatEndpoint('https://agent.example/'), 'https://agent.example/chat')
})

test('HTTP errors, invalid JSON, empty replies and application failures show useful feedback', async () => {
  const request = (response) => requestReply({ message: 'hi', threadId: 'test', fetchImpl: async () => response })
  await assert.rejects(request({ ok: false, status: 503 }), /服务暂时不可用.*503/)
  await assert.rejects(request({ ok: false, status: 422 }), /请求未被服务接受.*422/)
  await assert.rejects(request({ ok: true, json: async () => { throw new SyntaxError('not json') } }), /无法识别/)
  assert.match(await request({ ok: true, json: async () => ({ status: 'empty' }) }), /未获取到回复/)
  assert.match(await request({ ok: true, json: async () => ({ status: 'success', content: '  ' }) }), /未获取到回复/)
  await assert.rejects(request({ ok: true, json: async () => ({ status: 'error', error: '<script>private stack</script>' }) }), /本次处理未能完成/)
})

test('Markdown escapes raw HTML and rejects dangerous URL schemes', () => {
  const html = renderMarkdown('<script>alert(1)</script><img src=x onerror=alert(1)>')
  assert.ok(!html.includes('<script>'))
  assert.ok(!html.includes('<img'))
  assert.ok(html.includes('&lt;script&gt;'))
  for (const url of ['javascript:alert%281%29', 'JaVaScRiPt:alert%281%29', 'vbscript:evil', 'file:///secret', 'data:text/html;base64,PHNjcmlwdD4=', 'data:image/png;base64,AAAA']) {
    const rendered = renderMarkdown(`[link](${url})\n\n![image](${url})`)
    assert.ok(!rendered.includes('<a '), url)
    assert.ok(!rendered.includes('<img '), url)
  }
  const safe = renderMarkdown('[documentation](https://example.com)\n\n**bold**')
  assert.match(safe, /href="https:\/\/example.com"/)
  assert.match(safe, /rel="noopener noreferrer"/)
  assert.match(safe, /<strong>bold<\/strong>/)
})
