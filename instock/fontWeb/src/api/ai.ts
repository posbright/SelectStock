import request from './request'

export interface AiOverrides {
  provider?: string
  api_base?: string
  api_key?: string
  model?: string
  temperature?: number
  max_tokens?: number
  timeout?: number
}

export interface GenerateRequest extends AiOverrides {
  prompt: string
}

export interface RefineRequest extends AiOverrides {
  prompt: string
  code: string
}

export interface RepairRequest extends AiOverrides {
  strategy_id: number | string
  code?: string
}

export interface ChatRequest extends AiOverrides {
  prompt: string
  system?: string
  scene?: string
  agent?: string
}

export interface StrategyAiResponse {
  code: number  // 0=ok, -2=validation_failed, -1=error, 429=rate_limit
  msg?: string
  data?: {
    code: string
    raw: string
    validated: boolean
    validation_error?: string
    model?: string
    repair_attempts?: number
    failure?: {
      error_message: string
      started_at: string
      backtest_id: number
    }
  }
}

export function aiGenerateStrategy(data: GenerateRequest) {
  return request({ url: '/api/ai/strategy/generate', method: 'post', data })
}

export function aiRefineStrategy(data: RefineRequest) {
  return request({ url: '/api/ai/strategy/refine', method: 'post', data })
}

export function aiRepairStrategy(data: RepairRequest) {
  return request({ url: '/api/ai/strategy/repair', method: 'post', data })
}

export function aiChat(data: ChatRequest) {
  return request({ url: '/api/ai/chat', method: 'post', data })
}

// SSE 事件类型（B1）
export type AiStreamEvent =
  | { type: 'chunk'; text: string }
  | { type: 'repair'; attempt: number }
  | { type: 'done'; code: string; raw: string; validated: boolean; validation_error?: string; model?: string; repair_attempts?: number }
  | { type: 'error'; code: number; msg: string }

/**
 * 流式生成策略代码。基于 fetch + ReadableStream 解析 SSE。
 * 调用方通过 onEvent 接收每个事件；返回 Promise 在流结束/出错时 resolve/reject。
 */
export async function aiGenerateStrategyStream(
  data: GenerateRequest,
  onEvent: (ev: AiStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch('/instock/api/ai/strategy/generate/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(data),
    signal,
  })
  if (!resp.ok || !resp.body) {
    throw new Error(`HTTP ${resp.status}`)
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    // SSE 事件以空行分隔
    let idx: number
    while ((idx = buf.indexOf('\n\n')) !== -1) {
      const raw = buf.slice(0, idx).trim()
      buf = buf.slice(idx + 2)
      if (!raw.startsWith('data:')) continue
      const payload = raw.slice(5).trim()
      try {
        onEvent(JSON.parse(payload) as AiStreamEvent)
      } catch (e) {
        // ignore malformed event
      }
    }
  }
}
