<template>
  <el-drawer
    v-model="visible"
    title="AI 策略助手"
    direction="rtl"
    size="40%"
    :before-close="handleClose"
  >
    <div class="ai-drawer">
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
        title="代码已通过沙箱校验"
        type="success"
        show-icon
        :closable="false"
        style="margin-top: 12px;"
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

type FailureInfo = {
  error_message: string
  started_at: string
  backtest_id: number
}

const props = defineProps<{
  modelValue: boolean
  currentCode?: string
  strategyId?: number | string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'apply', code: string): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const mode = ref<'generate' | 'refine' | 'repair'>('generate')
const prompt = ref('')
const loading = ref(false)
const lastCode = ref('')
const validated = ref(false)
const validationError = ref('')
const errorMsg = ref('')
const failureInfo = ref<FailureInfo | null>(null)

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

watch(() => props.modelValue, (v) => {
  if (v) {
    // 抽屉打开时清空旧错误（保留 lastCode 便于再次"采用"）
    errorMsg.value = ''
  }
})

function _resetState() {
  errorMsg.value = ''
  validationError.value = ''
  validated.value = false
  failureInfo.value = null
}

async function run() {
  _resetState()
  loading.value = true
  try {
    let resp: StrategyAiResponse
    if (mode.value === 'generate') {
      resp = await aiGenerateStrategy({ prompt: prompt.value }) as any
    } else if (mode.value === 'refine') {
      resp = await aiRefineStrategy({
        prompt: prompt.value,
        code: props.currentCode || '',
      }) as any
    } else {
      resp = await aiRepairStrategy({
        strategy_id: props.strategyId!,
        code: props.currentCode || undefined,
      }) as any
    }

    if (resp.code === 0 || resp.code === -2) {
      lastCode.value = resp.data?.code || ''
      validated.value = !!resp.data?.validated
      validationError.value = resp.data?.validation_error || ''
      failureInfo.value = resp.data?.failure || null
      if (resp.code === -2) {
        // 仍展示代码，但提示需要修复
        ElMessage.warning('AI 生成的代码未通过沙箱校验，请人工检查或重试')
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
  emit('apply', lastCode.value)
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
