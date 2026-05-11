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
