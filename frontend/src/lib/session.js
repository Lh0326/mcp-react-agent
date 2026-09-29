const STORAGE_KEY = 'mcp-react-agent.thread-id'
export const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export function createThreadId() {
  if (globalThis.crypto.randomUUID) return globalThis.crypto.randomUUID()
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export function browserSessionStorage() {
  try {
    return globalThis.sessionStorage
  } catch {
    return undefined
  }
}

// Storage can be unavailable in private or restricted browser contexts.
// The caller keeps the returned UUID in memory for the current page.
export function newThreadId(storage) {
  const threadId = createThreadId()
  try {
    storage?.setItem(STORAGE_KEY, threadId)
  } catch {
    // Continue using the in-memory session if browser storage is blocked.
  }
  return threadId
}

export function getOrCreateThreadId(storage) {
  try {
    const saved = storage?.getItem(STORAGE_KEY)
    if (typeof saved === 'string' && UUID_PATTERN.test(saved)) return saved
  } catch {
    // Generate an independent session instead of using a shared fallback ID.
  }
  return newThreadId(storage)
}
