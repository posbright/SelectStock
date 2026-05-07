<template>
  <div class="settings-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>AI 研判配置</span>
          <div>
            <el-button type="primary" size="small" @click="openCreate">新增配置</el-button>
            <el-button size="small" @click="loadList">刷新</el-button>
          </div>
        </div>
      </template>

      <el-alert type="warning" show-icon :closable="false" style="margin-bottom: 12px">
        <strong>安全提示：</strong> API Key 不会保存在数据库或前端响应中，仅通过
        <code>api_key_ref</code> 引用环境变量名。请在服务器 <code>.env</code> 中设置对应变量
        （默认 <code>INSTOCK_AI_API_KEY</code>）。Gate 默认关闭，开启前请在回测/模拟盘中验证。
      </el-alert>

      <el-table :data="rows" stripe border size="small">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="source_type" label="来源" width="90" />
        <el-table-column prop="provider" label="Provider" width="140" />
        <el-table-column prop="model_name" label="Model" />
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
              {{ row.enabled ? '启用' : '关闭' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="作为 Gate" width="90">
          <template #default="{ row }">
            <el-tag :type="row.enabled_as_gate ? 'warning' : 'info'" size="small">
              {{ row.enabled_as_gate ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="API Key" width="100">
          <template #default="{ row }">
            <el-tag :type="row.api_key_is_configured ? 'success' : 'danger'" size="small">
              {{ row.api_key_is_configured ? '已注入' : '未注入' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="config_version" label="版本" width="70" />
        <el-table-column label="操作" width="170">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑 AI 配置' : '新增 AI 配置'" width="780">
      <el-form :model="form" label-width="140px">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="例如：默认模拟盘 Pre-Buy" />
        </el-form-item>
        <el-form-item label="来源类型">
          <el-select v-model="form.source_type">
            <el-option label="模拟交易 (paper)" value="paper" />
            <el-option label="回测 (backtest)" value="backtest" />
            <el-option label="实盘 (live)" value="live" />
            <el-option label="全部 (all)" value="all" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源 ID">
          <el-input v-model.number="form.source_id" placeholder="留空表示该来源类型下所有" clearable />
        </el-form-item>
        <el-form-item label="启用 AI 研判">
          <el-switch v-model="form.enabled" />
        </el-form-item>
        <el-form-item label="作为交易 Gate">
          <el-switch v-model="form.enabled_as_gate" />
          <span class="hint">开启后买入需 score ≥ 阈值；卖出需 score ≤ 阈值</span>
        </el-form-item>
        <el-form-item label="失败时拒绝交易">
          <el-switch v-model="form.fail_closed" />
          <span class="hint">默认关（失败放行）；开启后 AI 失败将拒绝下单</span>
        </el-form-item>

        <el-divider content-position="left">模型 / 接入</el-divider>
        <el-form-item label="Provider">
          <el-select v-model="form.provider">
            <el-option label="OpenAI Compatible" value="openai_compatible" />
            <el-option label="OpenAI" value="openai" />
            <el-option label="DeepSeek" value="deepseek" />
            <el-option label="Qwen" value="qwen" />
          </el-select>
        </el-form-item>
        <el-form-item label="Model">
          <el-input v-model="form.model_name" placeholder="例如 gpt-4o-mini / deepseek-chat" />
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="form.base_url" placeholder="例如 https://api.deepseek.com" />
        </el-form-item>
        <el-form-item label="api_key_ref">
          <el-input v-model="form.api_key_ref" placeholder="环境变量名，例如 INSTOCK_AI_API_KEY" />
        </el-form-item>

        <el-divider content-position="left">Prompt</el-divider>
        <el-form-item label="System Prompt">
          <el-input v-model="form.system_prompt" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="User Prompt 模板">
          <el-input v-model="form.user_prompt_template" type="textarea" :rows="6"
                    placeholder="可使用 {{ code }}, {{ indicators }}, {{ kline_window }} 等占位符" />
        </el-form-item>

        <el-divider content-position="left">参数</el-divider>
        <el-form-item label="Temperature">
          <el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" />
        </el-form-item>
        <el-form-item label="Max Tokens">
          <el-input-number v-model="form.max_tokens" :min="1" :max="32000" :step="64" />
        </el-form-item>
        <el-form-item label="超时（秒）">
          <el-input-number v-model="form.timeout_seconds" :min="1" :max="300" :step="1" />
        </el-form-item>
        <el-form-item label="重试次数">
          <el-input-number v-model="form.retry_count" :min="0" :max="5" :step="1" />
        </el-form-item>
        <el-form-item label="Buy 阈值">
          <el-input-number v-model="form.buy_threshold" :min="0" :max="100" :step="1" />
        </el-form-item>
        <el-form-item label="Sell 阈值">
          <el-input-number v-model="form.sell_threshold" :min="0" :max="100" :step="1" />
          <span class="hint">score ≤ 阈值视为通过卖出/减仓</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listAIConfigs, saveAIConfig, deleteAIConfig, AIDecisionConfig,
} from '@/api/settings'

const rows = ref<AIDecisionConfig[]>([])
const dialogVisible = ref(false)
const saving = ref(false)

const emptyForm = (): AIDecisionConfig => ({
  name: '', enabled: false, source_type: 'paper',
  provider: 'openai_compatible', api_key_ref: 'INSTOCK_AI_API_KEY',
  temperature: 0.2, max_tokens: 2048, timeout_seconds: 20, retry_count: 1,
  buy_threshold: 70, sell_threshold: 40, enabled_as_gate: false, fail_closed: false,
})
const form = ref<AIDecisionConfig>(emptyForm())

const loadList = async () => {
  const res = await listAIConfigs()
  rows.value = res?.data || []
}

const openCreate = () => {
  form.value = emptyForm()
  dialogVisible.value = true
}

const openEdit = (row: AIDecisionConfig) => {
  form.value = { ...row }
  dialogVisible.value = true
}

const onSave = async () => {
  saving.value = true
  try {
    const res = await saveAIConfig(form.value)
    if (!res.ok) { ElMessage.error(res.error || '保存失败'); return }
    ElMessage.success('保存成功，配置版本：' + res.data.config_version)
    dialogVisible.value = false
    await loadList()
  } finally {
    saving.value = false
  }
}

const onDelete = async (row: AIDecisionConfig) => {
  if (!row.id) return
  await ElMessageBox.confirm(`确定删除配置 #${row.id} (${row.name})？`, '提示', { type: 'warning' })
  await deleteAIConfig(row.id)
  ElMessage.success('已删除')
  await loadList()
}

onMounted(loadList)
</script>

<style scoped>
.settings-page { padding: 16px }
.card-header { display: flex; justify-content: space-between; align-items: center }
.hint { color: #909399; font-size: 12px; margin-left: 8px }
</style>
