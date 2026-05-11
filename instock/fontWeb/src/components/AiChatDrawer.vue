<template>
  <el-drawer
    v-model="visible"
    title="AI 策略助手"
    direction="rtl"
    size="40%"
    :before-close="handleClose"
  >
    <div class="ai-drawer">
      <!-- M5: provider/model + agent 选择 -->
      <div class="ai-pickers">
        <AiModelPicker v-model="modelSel" />
        <AiAgentPicker v-model="agentSel" :default-agent="defaultAgentForMode" />
      </div>

      <!-- 模式切换 -->
      <el-radio-group v-model="mode" size="small" style="margin-bottom: 12px;">
        <el-radio-button value="generate">生成新策略</el-radio-button>
        <el-radio-button value="refine" :disabled="!currentCode">修改当前代码</el-radio-button>
        <el-radio-button value="repair" :disabled="!strategyId">修复失败回测</el-radio-button>
      </el-radio-group>

      <!-- Prompt 输入 -->
      <div v-if="mode !== 'repair'">
        <div class="section-label">
          {{ mode === 'generate' ? '描述你想要的策略' : '描述要修改的内容' }}
        </div>
        <el-input
          v-model="prompt"
          type="textarea"
          :rows="6"
          :placeholder="placeholder"
          maxlength="2000"
          show-word-limit
        />
      </div>
      <div v-else class="section-label">
        将根据该策略最近一次失败的回测错误信息进行修复。
      </div>

      <!-- 操作 -->
      <div class="ai-actions">
        <el-button type="primary" :loading="loading" @click="run" :disabled="!canRun">
          {{ loading ? '生成中...' : '运行' }}
        </el-button>
        <el-button v-if="lastCode" @click="apply">采用结果</el-button>
        <el-button v-if="lastCode" text @click="copyResult">复制</el-button>
      </div>

      <!-- 校验状态 -->
      <el-alert
        v-if="validationError"
        :title="`沙箱校验失败：${validationError}`"
        type="warning"
        show-icon
        :closable="false"
        style="margin-top: 12px;"
      />
      <el-alert
        v-else-if="lastCode && validated"
        :title="repairAttempts > 0
          ? `代码已通过沙箱校验（自动修复 ${repairAttempts} 轮后通过）`
          : '代码已通过沙箱校验'"
        type="success"
        show-icon
        :closable="false"
        style="margin-top: 12px;"
      />
      <el-alert
        v-if="!validated && lastCode && repairAttempts > 0"
        :title="`已自动尝试修复 ${repairAttempts} 轮仍未通过校验，请人工检查后采用。`"
        type="info"
        show-icon
        :closable="false"
        style="margin-top: 8px;"
      />
      <el-alert
        v-if="errorMsg"
        :title="errorMsg"
        type="error"
        show-icon
        :closable="false"
        style="margin-top: 12px;"
      />

      <!-- 失败信息（repair 模式） -->
      <div v-if="failureInfo" class="failure-block">
        <div class="section-label">最近一次失败：</div>
        <pre>{{ failureInfo.error_message }}</pre>
        <div class="meta">回测 ID: {{ failureInfo.backtest_id }} · 时间: {{ failureInfo.started_at }}</div>
      </div>

      <!-- 生成代码预览 -->
      <div v-if="lastCode" class="result-block">
        <div class="section-label">生成结果：</div>
        <pre class="code-preview">{{ lastCode }}</pre>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  aiGenerateStrategy, aiRefineStrategy, aiRepairStrategy,
  type StrategyAiResponse,
} from '../api/ai'
import AiModelPicker from './AiModelPicker.vue'
import AiAgentPicker from './AiAgentPicker.vue'

type FailureInfo = {
  error_message: string
  started_at: string
  backtest_id: number
}

export type AiApplyMeta = {
  source: 'ai'
  ai_prompt: string
  ai_agent: string  // 'strategy_coder' / 'strategy_repairer'
  ai_model?: string
}

const props = defineProps<{
  modelValue: boolean
  currentCode?: string
  strategyId?: number | string
  defaultMode?: 'generate' | 'refine' | 'repair'
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'apply', code: string, meta: AiApplyMeta): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const mode = ref<'generate' | 'refine' | 'repair'>(props.defaultMode || 'generate')

// M5: provider/model/agent 选择（持久化由各 picker 自负责）
const modelSel = ref<{ provider?: string; model?: string }>({})
const agentSel = ref<string>('')
const defaultAgentForMode = computed(() =>
  mode.value === 'repair' ? 'strategy_repairer' : 'strategy_coder')

function _overrides() {
  const o: Record<string, any> = {}
  if (modelSel.value.provider) o.provider = modelSel.value.provider
  if (modelSel.value.model) o.model = modelSel.value.model
  return o
}

// 抽屉打开时若指定了 defaultMode，则按指定模式重置（避免用户上次切换的 mode 残留）
watch(() => props.modelValue, (v) => {
  if (v) {
    if (props.defaultMode) {
      mode.value = props.defaultMode
    }
    // 抽屉打开时清空旧错误（保留 lastCode 便于再次"采用"）
    errorMsg.value = ''
  }
})
const prompt = ref('')
const loading = ref(false)
const lastCode = ref('')
const validated = ref(false)
const validationError = ref('')
const errorMsg = ref('')
const failureInfo = ref<FailureInfo | null>(null)
const lastModel = ref('')
const repairAttempts = ref(0)

const placeholder = computed(() => {
  if (mode.value === 'generate') {
    return '例：写一个布林带下轨抄底策略，跌破下轨时买入，回到中轨卖出，持仓不超过 10 只'
  }
  return '例：把持仓数量从 5 只改成 10 只，并加上 5% 止损'
})

const canRun = computed(() => {
  if (loading.value) return false
  if (mode.value === 'repair') return !!props.strategyId
  return prompt.value.trim().length > 0
})

function _resetState() {
  errorMsg.value = ''
  validationError.value = ''
  validated.value = false
  failureInfo.value = null
  repairAttempts.value = 0
}

async function run() {
  _resetState()
  loading.value = true
  try {
    let resp: StrategyAiResponse
    const ov = _overrides()
    if (mode.value === 'generate') {
      resp = await aiGenerateStrategy({ prompt: prompt.value, ...ov }) as any
    } else if (mode.value === 'refine') {
      resp = await aiRefineStrategy({
        prompt: prompt.value,
        code: props.currentCode || '',
        ...ov,
      }) as any
    } else {
      resp = await aiRepairStrategy({
        strategy_id: props.strategyId!,
        code: props.currentCode || undefined,
        ...ov,
      }) as any
    }

    if (resp.code === 0 || resp.code === -2) {
      lastCode.value = resp.data?.code || ''
      validated.value = !!resp.data?.validated
      validationError.value = resp.data?.validation_error || ''
      failureInfo.value = resp.data?.failure || null
      lastModel.value = resp.data?.model || ''
      repairAttempts.value = resp.data?.repair_attempts || 0
      if (resp.code === -2) {
        // 仍展示代码，但提示需要修复
        ElMessage.warning('AI 生成的代码未通过沙箱校验，请人工检查或重试')
      } else if (repairAttempts.value > 0) {
        ElMessage.success(`生成成功（自动修复 ${repairAttempts.value} 轮）`)
      } else {
        ElMessage.success('生成成功')
      }
    } else if (resp.code === 429) {
      errorMsg.value = resp.msg || '触发限流，请稍后再试'
    } else {
      errorMsg.value = resp.msg || 'AI 调用失败'
    }
  } catch (e: any) {
    errorMsg.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}

function apply() {
  if (!lastCode.value) return
  const agent = agentSel.value || defaultAgentForMode.value
  emit('apply', lastCode.value, {
    source: 'ai',
    ai_prompt: prompt.value || (mode.value === 'repair' ? '[repair from last failure]' : ''),
    ai_agent: agent,
    ai_model: lastModel.value || undefined,
  })
  ElMessage.success('已应用到编辑器')
  visible.value = false
}

async function copyResult() {
  if (!lastCode.value) return
  try {
    await navigator.clipboard.writeText(lastCode.value)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

function handleClose(done: () => void) {
  done()
}
</script>

<style scoped>
.ai-drawer { padding: 0 16px; }
.ai-pickers { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
.section-label { font-size: 13px; color: #606266; margin: 12px 0 6px; font-weight: 500; }
.ai-actions { margin-top: 12px; display: flex; gap: 8px; }
.failure-block, .result-block { margin-top: 16px; }
.failure-block pre, .code-preview {
  background: #f5f7fa; border: 1px solid #ebeef5; border-radius: 4px;
  padding: 8px 10px; font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px; line-height: 1.5; max-height: 360px; overflow: auto;
  white-space: pre-wrap; word-break: break-word;
}
.failure-block .meta { font-size: 11px; color: #909399; margin-top: 4px; }
</style>
