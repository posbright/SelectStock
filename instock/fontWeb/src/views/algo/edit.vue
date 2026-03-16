<template>
  <div class="algo-editor">
    <!-- 工具栏 -->
    <div class="editor-toolbar">
      <div class="toolbar-left">
        <el-button text @click="$router.push('/algo/list')"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
        <el-divider direction="vertical" />
        <span class="strategy-name" v-if="!editingName" @dblclick="editingName = true">
          {{ strategy.name || '未命名策略' }}
        </span>
        <el-input v-else v-model="strategy.name" size="small" style="width: 200px;"
                  @blur="editingName = false; doSave()" @keyup.enter="editingName = false; doSave()" />
      </div>
      <div class="toolbar-right">
        <el-button @click="doSave" :icon="DocumentChecked" :loading="saving">
          {{ dirty ? '保存 *' : '已保存' }}
        </el-button>
        <el-divider direction="vertical" />
        <el-date-picker v-model="btDateRange" type="daterange" size="small"
                        range-separator="至" start-placeholder="开始" end-placeholder="结束"
                        value-format="YYYY-MM-DD" style="width: 240px;"
                        :shortcuts="dateShortcuts" />
        <el-input-number v-model="btCash" :min="10000" :step="100000" size="small"
                         style="width: 130px;" :controls="false" />
        <span class="param-label">元</span>
        <el-button type="primary" @click="doRun" :loading="running" :icon="CaretRight">运行回测</el-button>
        <el-button @click="doCreatePaper" :icon="Monitor" :disabled="!strategy.id">创建模拟</el-button>
        <el-button text @click="$router.push('/algo/backtests')">回测历史</el-button>
      </div>
    </div>

    <div class="editor-main">
      <!-- 左：代码 -->
      <div class="code-panel">
        <div class="panel-header">
          <span>策略代码</span>
          <span class="save-hint" v-if="dirty">● 未保存</span>
        </div>
        <textarea v-model="strategy.code" class="code-editor" spellcheck="false" wrap="off"
                  @input="dirty = true" @keydown.ctrl.s.prevent="doSave" />
      </div>
      <!-- 右：结果 -->
      <div class="result-panel" v-if="showResults">
        <el-tabs v-model="activeTab">
          <el-tab-pane label="概览" name="overview">
            <div v-if="btResult?.status === 'error'" style="padding: 12px;">
              <el-alert :title="btResult.message" type="error" show-icon :closable="false" />
            </div>
            <div v-if="btResult?.metrics" class="result-overview">
              <div class="metrics-row">
                <div class="metric" v-for="m in metricCards" :key="m.key">
                  <div class="metric-val" :class="m.cls">{{ m.val }}</div>
                  <div class="metric-lbl">{{ m.label }}</div>
                </div>
              </div>
              <div ref="chartEl" class="nav-chart"></div>
            </div>
          </el-tab-pane>
          <el-tab-pane :label="'交易(' + (btResult?.trades?.length || 0) + ')'" name="trades">
            <el-table :data="btResult?.trades || []" size="small" max-height="calc(100vh - 260px)" stripe>
              <el-table-column prop="date" label="日期" width="100" />
              <el-table-column prop="code" label="代码" width="70" />
              <el-table-column prop="direction" label="方向" width="55">
                <template #default="{ row }">
                  <span :style="{ color: row.direction === 'buy' ? '#f56c6c' : '#67c23a', fontWeight: 600 }">
                    {{ row.direction === 'buy' ? '买' : '卖' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="price" label="价格" width="80" align="right">
                <template #default="{ row }">{{ Number(row.price).toFixed(2) }}</template>
              </el-table-column>
              <el-table-column prop="amount" label="数量" width="80" align="right" />
              <el-table-column prop="value" label="金额" width="100" align="right">
                <template #default="{ row }">{{ Number(row.value).toFixed(0) }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="持仓" name="positions">
            <el-table :data="lastPositions" size="small" max-height="calc(100vh - 260px)" stripe>
              <el-table-column prop="code" label="代码" width="70" />
              <el-table-column prop="amount" label="持仓" width="80" align="right" />
              <el-table-column prop="avg_cost" label="成本" width="80" align="right">
                <template #default="{ row }">{{ Number(row.avg_cost).toFixed(2) }}</template>
              </el-table-column>
              <el-table-column prop="price" label="现价" width="80" align="right">
                <template #default="{ row }">{{ Number(row.price).toFixed(2) }}</template>
              </el-table-column>
              <el-table-column prop="profit_rate" label="盈亏" width="80" align="right">
                <template #default="{ row }">
                  <span :style="{ color: row.profit_rate >= 0 ? '#f56c6c' : '#67c23a' }">
                    {{ Number(row.profit_rate).toFixed(1) }}%
                  </span>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane :label="'日志(' + (btResult?.logs?.length || 0) + ')'" name="logs">
            <div class="log-box">
              <div v-for="(l, i) in (btResult?.logs || []).slice(-200)" :key="i" class="log-line">{{ l }}</div>
              <div v-if="!btResult?.logs?.length" class="log-empty">暂无日志</div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
      <div class="result-panel placeholder" v-else>
        <div class="placeholder-content">
          <el-icon :size="48" color="#c0c4cc"><DataLine /></el-icon>
          <p>点击「运行回测」查看结果</p>
          <p class="tips">Ctrl+S 保存</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, DocumentChecked, CaretRight, Monitor, DataLine } from '@element-plus/icons-vue'
import { getStrategyCodeDetail, saveStrategyCode, runPortfolioBacktest, createPaperTrading } from '@/api/stock'
import * as echarts from 'echarts'

const route = useRoute()
const router = useRouter()
const strategyId = computed(() => Number(route.params.id))

const strategy = ref<any>({ id: 0, name: '', code: '' })
const btDateRange = ref(['2024-01-01', '2025-01-01'])
const btCash = ref(1000000)
const btResult = ref<any>(null)
const showResults = ref(false)
const running = ref(false)
const saving = ref(false)
const dirty = ref(false)
const editingName = ref(false)
const activeTab = ref('overview')
const chartEl = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

const dateShortcuts = [
  { text: '近1年', value: () => { const e = new Date(); const s = new Date(); s.setFullYear(s.getFullYear()-1); return [s, e] }},
  { text: '近2年', value: () => { const e = new Date(); const s = new Date(); s.setFullYear(s.getFullYear()-2); return [s, e] }},
  { text: '2024全年', value: [new Date('2024-01-01'), new Date('2024-12-31')] },
]

const metricCards = computed(() => {
  const m = btResult.value?.metrics
  if (!m) return []
  return [
    { key: 'ret', label: '策略收益', val: (m.total_return >= 0 ? '+' : '') + m.total_return.toFixed(2) + '%',
      cls: m.total_return >= 0 ? 'val-red' : 'val-green' },
    { key: 'annual', label: '年化收益', val: (m.annual_return >= 0 ? '+' : '') + m.annual_return.toFixed(2) + '%',
      cls: m.annual_return >= 0 ? 'val-red' : 'val-green' },
    { key: 'sharpe', label: '夏普比率', val: m.sharpe_ratio.toFixed(3), cls: '' },
    { key: 'dd', label: '最大回撤', val: m.max_drawdown.toFixed(2) + '%', cls: 'val-green' },
    { key: 'alpha', label: 'Alpha', val: (m.alpha || 0).toFixed(2) + '%', cls: '' },
    { key: 'beta', label: 'Beta', val: (m.beta || 0).toFixed(3), cls: '' },
    { key: 'wr', label: '日胜率', val: (m.daily_win_rate || 0).toFixed(1) + '%', cls: '' },
    { key: 'tc', label: '交易次数', val: String(m.trade_count), cls: '' },
  ]
})

const lastPositions = computed(() => {
  const p = btResult.value?.positions
  return (p && p.length > 0) ? p[p.length - 1].positions || [] : []
})

// Helper: extract response data regardless of axios unwrap
function unwrap(res: any) {
  // After axios interceptor unwrap, res is {code:0, data:{...}}
  if (res?.code === 0) return { ok: true, data: res.data, msg: '' }
  if (res?.data?.code === 0) return { ok: true, data: res.data.data, msg: '' }
  return { ok: false, data: null, msg: res?.msg || res?.data?.msg || '操作失败' }
}

onMounted(async () => {
  if (strategyId.value) {
    try {
      const res = await getStrategyCodeDetail(strategyId.value) as any
      const { ok, data } = unwrap(res)
      if (ok && data) {
        strategy.value = data
        dirty.value = false  // 刚加载，标记为已保存
      }
    } catch (e) {
      ElMessage.error('加载策略失败')
    }
  }
})

async function doSave() {
  if (!strategy.value.code?.trim()) { ElMessage.warning('代码为空'); return }
  saving.value = true
  try {
    const res = await saveStrategyCode({
      id: strategy.value.id || undefined,
      name: strategy.value.name || '未命名策略',
      code: strategy.value.code,
      description: strategy.value.description || '',
      initial_cash: btCash.value,
    }) as any
    const { ok, data, msg } = unwrap(res)
    if (ok) {
      if (!strategy.value.id && data?.id) strategy.value.id = data.id
      dirty.value = false
      ElMessage.success('已保存')
    } else {
      ElMessage.error(msg)
    }
  } finally {
    saving.value = false
  }
}

async function doRun() {
  if (!strategy.value.code?.trim()) { ElMessage.warning('请输入策略代码'); return }
  if (!btDateRange.value?.[0]) { ElMessage.warning('请选择回测日期'); return }
  if (dirty.value) await doSave()

  running.value = true
  showResults.value = false
  btResult.value = null
  try {
    const res = await runPortfolioBacktest({
      code: strategy.value.code,
      strategy_id: strategy.value.id || undefined,
      start_date: btDateRange.value[0],
      end_date: btDateRange.value[1],
      initial_cash: btCash.value,
    }) as any
    const { ok, data } = unwrap(res)
    if (ok && data) {
      btResult.value = data
      showResults.value = true
      if (data.status === 'completed') {
        ElMessage.success('回测完成 (' + data.elapsed + 's)')
        await nextTick()
        renderChart()
      } else if (data.status === 'error') {
        ElMessage.error(data.message)
      }
    }
  } catch (e: any) {
    ElMessage.error(e.message || '回测异常')
  } finally {
    running.value = false
  }
}

async function doCreatePaper() {
  if (!strategy.value.id) { ElMessage.warning('请先保存策略'); return }
  try {
    const res = await createPaperTrading({
      strategy_id: strategy.value.id,
      name: '模拟-' + strategy.value.name,
      initial_cash: btCash.value,
    }) as any
    if (unwrap(res).ok) {
      ElMessage.success('模拟盘已创建')
      router.push('/algo/paper')
    }
  } catch (e) { ElMessage.error('创建失败') }
}

function renderChart() {
  if (!chartEl.value || !btResult.value?.nav?.length) return
  if (chart) chart.dispose()
  chart = echarts.init(chartEl.value)
  const nav = btResult.value.nav
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['策略收益', '基准收益'], top: 5 },
    grid: { left: 50, right: 15, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: nav.map((r: any) => r.date), axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%', fontSize: 10 } },
    series: [
      { name: '策略收益', type: 'line', data: nav.map((r: any) => ((r.nav - 1) * 100).toFixed(2)),
        symbol: 'none', lineStyle: { width: 2, color: '#e6a23c' },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(230,162,60,0.3)' }, { offset: 1, color: 'rgba(230,162,60,0.02)' }]) }},
      { name: '基准收益', type: 'line', data: nav.map((r: any) => ((r.benchmark_nav - 1) * 100).toFixed(2)),
        symbol: 'none', lineStyle: { width: 1.5, type: 'dashed', color: '#909399' }},
    ]
  })
}

watch(() => route.params.id, async (newId) => {
  if (newId) {
    const res = await getStrategyCodeDetail(Number(newId)) as any
    const { ok, data } = unwrap(res)
    if (ok && data) {
      strategy.value = data
      showResults.value = false
      btResult.value = null
      dirty.value = false
    }
  }
})

window.addEventListener('resize', () => chart?.resize())
</script>

<style scoped>
.algo-editor { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
.editor-toolbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 16px; border-bottom: 1px solid #ebeef5; background: #fff; flex-shrink: 0;
}
.toolbar-left, .toolbar-right { display: flex; align-items: center; gap: 8px; }
.strategy-name { font-size: 15px; font-weight: 600; cursor: pointer; }
.param-label { font-size: 12px; color: #909399; }
.editor-main { display: flex; flex: 1; overflow: hidden; }
.code-panel { flex: 1; display: flex; flex-direction: column; border-right: 1px solid #ebeef5; }
.panel-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 12px; background: #f5f7fa; border-bottom: 1px solid #ebeef5;
  font-size: 13px; font-weight: 500; flex-shrink: 0;
}
.save-hint { color: #e6a23c; font-size: 12px; }
.code-editor {
  flex: 1; width: 100%; border: none; outline: none; resize: none;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px; line-height: 1.6; padding: 12px;
  background: #1e1e1e; color: #d4d4d4; tab-size: 4;
}
.result-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.result-panel.placeholder { display: flex; align-items: center; justify-content: center; }
.placeholder-content { text-align: center; color: #c0c4cc; }
.placeholder-content p { margin: 8px 0; }
.placeholder-content .tips { font-size: 12px; }
.result-overview { padding: 12px; overflow-y: auto; }
.metrics-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 12px; }
.metric { text-align: center; padding: 10px 8px; background: #f5f7fa; border-radius: 6px; }
.metric-val { font-size: 16px; font-weight: 700; color: #303133; }
.metric-lbl { font-size: 11px; color: #909399; margin-top: 2px; }
.val-red { color: #f56c6c !important; }
.val-green { color: #67c23a !important; }
.nav-chart { width: 100%; height: 280px; }
.log-box {
  height: calc(100vh - 260px); overflow-y: auto; font-family: monospace; font-size: 12px;
  background: #1e1e1e; color: #d4d4d4; padding: 8px 12px;
}
.log-line { white-space: pre-wrap; line-height: 1.5; }
.log-empty { text-align: center; color: #606266; padding: 40px; }
</style>
