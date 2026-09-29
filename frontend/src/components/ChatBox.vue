<script setup>
import { nextTick, reactive, ref } from 'vue'
import { requestReply } from '../lib/chatApi.js'
import { renderMarkdown } from '../lib/markdown.js'
import { browserSessionStorage, getOrCreateThreadId, newThreadId } from '../lib/session.js'

const storage = browserSessionStorage()
const threadId = ref(getOrCreateThreadId(storage))
const input = ref('')
const busy = ref(false)
const messageList = ref(null)
const welcome = () => ({
  role: 'assistant',
  content: '你好！我可以帮你查询天气、查看季节提示，或把内容写入文件。\n\n天气查询需配置服务，季节提示可直接使用。地图服务可以按需接入。',
})
const messages = ref([welcome()])
const examples = [
  { label: '查天气', text: '请查询北京的天气。' },
  { label: '季节提示', text: '春季出行有哪些提示？' },
  { label: '写入文件', text: '请把“今天开始学习 MCP Agent”保存到文件。' },
]

async function revealLatestMessage() {
  await nextTick()
  messageList.value?.scrollTo({ top: messageList.value.scrollHeight, behavior: 'smooth' })
}

async function sendMessage() {
  const content = input.value.trim()
  if (!content || busy.value) return
  messages.value.push({ role: 'user', content })
  const answer = reactive({ role: 'assistant', content: '', pending: true })
  messages.value.push(answer)
  input.value = ''
  busy.value = true
  revealLatestMessage()
  try {
    answer.content = await requestReply({
      message: content,
      threadId: threadId.value,
      baseUrl: import.meta.env.VITE_API_BASE_URL || '',
    })
  } catch (error) {
    answer.content = error instanceof TypeError
      ? '无法连接服务，请确认后端已启动、地址配置正确，再重试。'
      : error?.message || '请求未能完成，请稍后重试。'
    answer.failed = true
  } finally {
    answer.pending = false
    busy.value = false
    revealLatestMessage()
  }
}

function startNewConversation() {
  if (busy.value) return
  threadId.value = newThreadId(storage)
  messages.value = [welcome()]
  input.value = ''
  revealLatestMessage()
}

function handleEnter(event) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    sendMessage()
  }
}
</script>

<template>
  <div class="workspace">
    <aside class="sidebar">
      <a class="brand" href="/" aria-label="MCP Agent 首页">
        <span class="brand-mark" aria-hidden="true">M</span>
        <span>MCP Agent <small>工具，让对话更进一步</small></span>
      </a>
      <button class="new-conversation" :disabled="busy" @click="startNewConversation"
        title="清空本页消息，开启独立会话；不会删除后端已有会话">
        <span aria-hidden="true">＋</span> 新对话
      </button>
      <div class="capabilities">
        <p class="eyebrow">可以试试</p>
        <button v-for="example in examples" :key="example.label" :disabled="busy" @click="input = example.text">
          <span>{{ example.label }}</span><span class="example-arrow" aria-hidden="true">↗</span>
        </button>
      </div>
      <p class="sidebar-note">天气查询需配置服务。<br>季节提示可直接使用。<br>文件自动命名并保存到 output。<br>地图服务可按需配置。</p>
    </aside>

    <main class="conversation">
      <header class="conversation-heading">
        <div><p class="eyebrow">一个问题，一次行动</p><h1>让工具参与对话</h1></div>
        <span class="technology-label">ReAct · MCP</span>
      </header>

      <section ref="messageList" class="message-list" aria-label="聊天消息" aria-live="polite"
        aria-relevant="additions text" :aria-busy="busy">
        <article v-for="(message, index) in messages" :key="index" class="message" :class="message.role">
          <p class="message-label">{{ message.role === 'user' ? '你' : '助手' }}</p>
          <div v-if="message.role === 'user'" class="user-content">{{ message.content }}</div>
          <div v-else-if="message.pending" class="pending-content" role="status">
            <span class="spinner" aria-hidden="true"></span>正在理解问题并调用工具…
          </div>
          <div v-else class="markdown-content" :class="{ 'error-content': message.failed }"
            v-html="renderMarkdown(message.content)"></div>
        </article>
      </section>

      <footer class="composer-area">
        <form class="composer" @submit.prevent="sendMessage">
          <label class="sr-only" for="message-input">输入消息</label>
          <textarea id="message-input" v-model="input" rows="2" :disabled="busy"
            placeholder="想查询什么，或希望我完成什么？" @keydown="handleEnter"></textarea>
          <button type="submit" :disabled="busy || !input.trim()" aria-label="发送消息">发送 <span aria-hidden="true">↑</span></button>
        </form>
        <p class="composer-note">Enter 发送 · Shift + Enter 换行 · 新对话会开启独立会话</p>
      </footer>
    </main>
  </div>
</template>

<style scoped>
.workspace { display: flex; max-width: 1440px; min-height: 100dvh; margin: auto; }
.sidebar { width: 258px; flex-shrink: 0; padding: 36px 24px 26px; border-right: 1px solid #e2e7e4; background: #f0f3ef; display: flex; flex-direction: column; }
.brand { display: flex; align-items: center; gap: 12px; color: #203d32; font-weight: 700; font-size: 18px; text-decoration: none; }
.brand-mark { display: grid; place-items: center; width: 40px; height: 40px; border-radius: 11px; background: #203d32; color: #fff; font-size: 22px; }
.brand small { display: block; margin-top: 3px; color: #768378; font-size: 10px; font-weight: 400; }
.new-conversation { display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: 40px; padding: 13px; background: #fff; border: 1px solid #d6dfd8; border-radius: 9px; color: #274c3a; font-weight: 600; }
.new-conversation:hover:enabled { background: #e4ede6; }
.new-conversation span { font-size: 19px; }
.capabilities { margin-top: 42px; }
.eyebrow { margin: 0 0 9px; color: #758179; font-size: 11px; letter-spacing: 0.08em; }
.capabilities button { width: 100%; display: flex; justify-content: space-between; border: 0; padding: 14px 0; background: none; color: #44584b; text-align: left; border-bottom: 1px solid #e0e6df; font-size: 14px; }
.example-arrow { color: #839185; }
.capabilities button:hover:enabled { color: #13714b; }
.sidebar-note { margin-top: auto; padding-top: 50px; color: #849084; font-size: 11px; line-height: 1.95; }
.conversation { flex: 1; min-width: 0; height: 100dvh; display: flex; flex-direction: column; background: #fafbf8; }
.conversation-heading { flex-shrink: 0; display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 0 48px; padding: 34px 0 24px; border-bottom: 1px solid #e5e9e2; }
h1 { font-size: 24px; letter-spacing: -0.02em; color: #233a2d; font-weight: 600; }
.technology-label { color: #738274; border: 1px solid #dce4d9; padding: 6px 10px; border-radius: 6px; font-size: 11px; white-space: nowrap; }
.message-list { overflow-y: auto; min-height: 0; flex: 1; padding: 34px 48px; scrollbar-width: thin; scrollbar-color: #cdd8cc transparent; }
.message { margin-bottom: 28px; }
.message-label { margin-bottom: 10px; color: #4f6958; font-size: 12px; font-weight: 600; }
.user .message-label { color: #8b937f; }
.user-content { padding: 16px 20px; background: #edf1e8; border: 1px solid #e3e9dc; border-radius: 10px; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 15px; line-height: 1.7; }
.markdown-content { color: #35453c; font-size: 15px; line-height: 1.85; overflow-wrap: anywhere; }
.pending-content { display: flex; align-items: center; gap: 10px; color: #7c897e; font-size: 13px; padding: 8px 0; }
.spinner { width: 14px; height: 14px; border: 2px solid #dce7db; border-top-color: #498264; border-radius: 50%; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-content { color: #925440; }
.composer-area { flex-shrink: 0; padding: 12px 48px 24px; }
.composer { display: flex; gap: 14px; align-items: flex-end; background: #fff; padding: 16px; border: 1px solid #dce4d7; border-radius: 12px; box-shadow: 0 3px 18px #334b2910; }
.composer:focus-within { border-color: #82a18b; }
textarea { width: 100%; min-width: 0; flex: 1; resize: none; border: 0; outline: none; background: transparent; color: #344a3c; font-size: 14px; line-height: 1.7; }
textarea::placeholder { color: #9aa397; }
.composer button { background: #284e3b; border: 0; padding: 11px 15px; border-radius: 8px; color: #fff; white-space: nowrap; }
.composer button:hover:enabled { background: #1b6a43; }
.composer button span { margin-left: 5px; }
.composer-note { text-align: center; font-size: 10px; color: #939d8e; margin-top: 12px; }
button:disabled { opacity: 0.45; cursor: not-allowed; }
button:focus-visible, .brand:focus-visible { outline: 2px solid #40835c; outline-offset: 3px; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; border: 0; }
:deep(.markdown-content p) { margin: 0 0 12px; }
:deep(.markdown-content p:last-child) { margin-bottom: 0; }
:deep(.markdown-content a) { color: #16734b; text-underline-offset: 3px; }
:deep(.markdown-content ul), :deep(.markdown-content ol) { padding-left: 24px; margin: 10px 0; }
:deep(.markdown-content blockquote) { border-left: 3px solid #a1b79d; padding-left: 16px; margin: 14px 0; color: #6a7b6c; }
:deep(.markdown-content code) { padding: 2px 5px; border-radius: 4px; background: #e9eee5; font-family: Consolas, monospace; font-size: 0.9em; }
:deep(.markdown-content pre) { max-width: 100%; overflow-x: auto; padding: 16px; margin: 14px 0; background: #243b2e; border-radius: 9px; }
:deep(.markdown-content pre code) { padding: 0; background: transparent; color: #e2eddf; }
:deep(.markdown-content img) { max-width: 100%; border-radius: 8px; }
:deep(.markdown-content table) { display: block; overflow-x: auto; border-collapse: collapse; margin: 14px 0; }
:deep(.markdown-content th), :deep(.markdown-content td) { padding: 8px 12px; border: 1px solid #dce4d7; }
@media (max-width: 760px) {
  .workspace { display: block; }
  .sidebar { width: 100%; padding: 16px 20px; flex-direction: row; align-items: center; justify-content: space-between; border-right: 0; border-bottom: 1px solid #e2e7e4; }
  .brand { font-size: 16px; }
  .brand-mark { width: 32px; height: 32px; font-size: 18px; }
  .brand small, .capabilities, .sidebar-note { display: none; }
  .new-conversation { margin: 0; padding: 8px 12px; font-size: 12px; }
  .conversation { height: calc(100dvh - 71px); }
  .conversation-heading { margin: 0 22px; padding: 24px 0 18px; }
  h1 { font-size: 21px; }
  .message-list { padding: 26px 22px; }
  .composer-area { padding: 10px 16px 18px; }
  .composer { padding: 12px; gap: 8px; }
  .composer button { padding: 10px 12px; }
}
@media (prefers-reduced-motion: reduce) { .spinner { animation: none; } }
</style>
