<template>
  <div class="algo-editor">
    <!-- 顶部工具栏 -->
    <div class="editor-toolbar">
      <div class="toolbar-left">
        <el-button text @click="$router.push('/algo/list')">
          <el-icon><ArrowLeft /></el-icon> 返回策略列表
        </el-button>
        <el-divider direction="vertical" />
        <span class="strategy-name" v-if="!editingName" @dblclick="editingName = true">
          {{ strategy.name || '未命名策略' }}
        </span>
        <el-input v-else v-model="strategy.name" size="small" style="width: 200px;"
                  @blur="editingName = false; saveCode()" @keyup.enter="editingName = false; saveCode()" />
      </div>
      <div class="toolbar-right">
        <el-button @click="saveCode" :icon="DocumentChecked" :loading="saving">保存</el-button>
        <el-divider direction="vertical" />
        <el-date-picker v-model="btDateRange" type="daterange" size="small"
                        range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期"
                        value-format="YYYY-MM-DD" style="width: 240px;"
                        :shortcuts="dateShortcuts" />
        <el-input-number v-model="btCash" :min="10000" :step="100000" size="small"
                         style="width: 130px;" :controls="false" />
        <span class="param-label">元</span>
        <el-button type="primary" @click="runBacktest" :loading="running" :icon="CaretRight">
          运行回测
        </el-button>
        <el-button @click="createPaper" :icon="Monitor" :disabled="!strategy.id">
          创建模拟
        </el-button>
      </div>
    </div>

    <div class="editor-main">
      <!-- 左侧: 代码编辑器 -->
      <div class="code-panel">
        <div class="panel-header">
          <span>策略代码</span>
          <span class="save-hint" v-if="dirty">● 未保存</span>
        </div>
        <textarea v-model="strategy.code" class="code-editor" spellcheck="false" wrap="off"
                  @input="dirty = true" @keydown.ctrl.s.prevent="saveCode" />
      </div>

      <!-- 右侧: 回测结果 -->
      <div class="result-panel" v-if="showResults">
        <el-tabs v-model="activeTab">
          <!-- 概览 -->
          <el-tab-pane label="概览" name="overview">
            <div v-if="btResult?.status === 'error'" class="error-msg">
              <el-alert :title="btResult.message" type="error" show-icon :closable="false" />
            </div>
            <div v-if="btResult?.metrics" class="result-overview">
              <div class="metrics-row">
                <div class="metric" v-for="m in overviewMetrics" :key="m.key">
                  <div class="metric-val" :class="m.class">{{ m.value }}</div>
                  <div class="metric-lbl">{{ m.label }}</div>
                </div>
              </div>
              <!-- 收益曲线 -->
              <div ref="navChartEl" class="nav-chart"></div>
            </div>
          </el-tab-pane>

          <!-- 交易记录 -->
          <el-tab-pane :label="`交易记录(${btResult?.trades?.length || 0})`" name="trades">
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
              <el-table-column prop="commission" label="手续费" width="80" align="right">
                <template #default="{ row }">{{ Number(row.commission || 0).toFixed(2) }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- 每日持仓 -->
          <el-tab-pane label="持仓变化" name="positions">
            <el-table :data="lastPositions" size="small" max-height="calc(100vh - 260px)" stripe>
              <el-table-column prop="code" label="代码" width="70" />
              <el-table-column prop="amount" label="持仓" width="80" align="right" />
              <el-table-column prop="avg_cost" label="成本价" width="80" align="right">
                <template #default="{ row }">{{ Number(row.avg_cost).toFixed(2) }}</template>
              </el-table-column>
              <el-table-column prop="price" label="现价" width="80" align="right">
                <template #default="{ row }">{{ Number(row.price).toFixed(2) }}</template>
              </el-table-column>
              <el-table-column prop="profit_rate" label="盈亏" width="80" align="right">
                <template #default="{ row }">
                  <span :style="{ color: row.profit_rate >= 0 ? '#f56c6c' : '#67c23a' }">
                    {{ row.profit_rate >= 0 ? '+' : '' }}{{ Number(row.profit_rate).toFixed(1) }}%
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="weight" label="权重" width="70" align="right">
                <template #default="{ row }">{{ Number(row.weight).toFixed(1) }}%</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- 日志 -->
          <el-tab-pane :label="`日志(${btResult?.logs?.length || 0})`" name="logs">
            <div class="log-container">
              <div v-for="(line, i) in (btResult?.logs || []).slice(-200)" :key="i" class="log-line">
                {{ line }}
              </div>
              <div v-if="!btResult?.logs?.length" class="log-empty">暂无日志</div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>

      <!-- 无结果时的提示 -->
      <div class="result-panel placeholder" v-else>
        <div class="placeholder-content">
          <el-icon :size="48" color="#c0c4cc"><DataLine /></el-icon>
          <p>配置好参数后点击「运行回测」</p>
          <p class="tips">快捷键: Ctrl+S 保存策略</p>
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
import {
  getStrategyCodeDetail, saveStrategyCode, runPortfolioBacktest, createPaperTrading
} from '@/api/stock'
import * as echarts from 'echarts'

const route = useRoute()
const router = useRouter()
const strategyId = computed(() => Number(route.params.id))

const strategy = ref<any>({ id: 0, name: '', code: '', description: '' })
const btDateRange = ref(['2024-01-01', '2025-01-01'])
const btCash = ref(1000000)
const btResult = ref<any>(null)
const showResults = ref(false)
const running = ref(false)
const saving = ref(false)
const dirty = ref(false)
const editingName = ref(false)
const activeTab = ref('overview')
const navChartEl = ref<HTMLElement>()
let navChart: echarts.ECharts | null = null

const dateShortcuts = [
  { text: '近1年', value: () => { const e = new Date(); const s = new Date(); s.setFullYear(s.getFullYear()-1); return [s, e] }},
  { text: '近2年', value: () => { const e = new Date(); const s = new Date(); s.setFullYear(s.getFullYear()-2); return [s, e] }},
  { text: '近3年', value: () => { const e = new Date(); const s = new Date(); s.setFullYear(s.getFullYear()-3); return [s, e] }},
  { text: '2024全年', value: [new Date('2024-01-01'), new Date('2024-12-31')] },
  { text: '2025全年', value: [new Date('2025-01-01'), new Date('2025-12-31')] },
]

const overviewMetrics = computed(() => {
  const m = btResult.value?.metrics
  if (!m) return []
  return [
    { key: 'total', label: '策略收益', value: `${m.total_return >= 0 ? '+' : ''}${m.total_return.toFixed(2)}%`,
      class: m.total_return >= 0 ? 'val-red' : 'val-green' },
    { key: 'annual', label: '年化收益', value: `${m.annual_return >= 0 ? '+' : ''}${m.annual_return.toFixed(2)}%`,
      class: m.annual_return >= 0 ? 'val-red' : 'val-green' },
    { key: 'benchmark', label: '基准收益', value: `${m.benchmark_return >= 0 ? '+' : ''}${(m.benchmark_return || 0).toFixed(2)}%`,
      class: (m.benchmark_return || 0) >= 0 ? 'val-red' : 'val-green' },
    { key: 'alpha', label: 'Alpha', value: `${(m.alpha || 0).toFixed(2)}%`, class: '' },
    { key: 'beta', label: 'Beta', value: (m.beta || 0).toFixed(3), class: '' },
    { key: 'sharpe', label: '夏普比率', value: m.sharpe_ratio.toFixed(3), class: '' },
    { key: 'maxdd', label: '最大回撤', value: `${m.max_drawdown.toFixed(2)}%`, class: 'val-green' },
    { key: 'winrate', label: '日胜率', value: `${m.daily_win_rate.toFixed(1)}%`, class: '' },
    { key: 'trades', label: '交易次数', value: `${m.trade_count}`, class: '' },
  ]
})

const lastPositions = computed(() => {
  const positions = btResult.value?.positions
  if (!positions || positions.length === 0) return []
  return positions[positions.length - 1].positions || []
})

onMounted(async () => {
  if (strategyId.value) {
    try {
      const res = await getStrategyCodeDetail(strategyId.value) as any
      const d = res?.code === 0 ? res.data : res?.data?.data
      if (d) strategy.value = d
    } catch (e) {
      ElMessage.error('加载策略失败')
    }
  }
})

async function saveCode() {
  if (!strategy.value.code?.trim()) return
  saving.value = true
  try {
    const res = await saveStrategyCode({
      id: strategy.value.id || undefined,
      name: strategy.value.name || '未命名策略',
      code: strategy.value.code,
      description: strategy.value.description,
      initial_cash: btCash.value,
    }) as any
    const rCode = res?.code ?? res?.data?.code
    if (rCode === 0) {
      if (!strategy.value.id && (res?.data?.id || res?.data?.data?.id)) {
        strategy.value.id = res?.data?.id || res?.data?.data?.id
      }
      dirty.value = false
      ElMessage.success('已保存')
    } else {
      ElMessage.error(res?.msg || res?.data?.msg || '保存失败')
    }
  } finally {
    saving.value = false
  }
}

async function runBacktest() {
  if (!strategy.value.code?.trim()) {
    ElMessage.warning('请输入策略代码')
    return
  }
  if (!btDateRange.value?.[0]) {
    ElMessage.warning('请选择回测日期')
    return
  }

  // 自动保存
  if (dirty.value) await saveCode()

  running.value = true
  showResults.value = false
  btResult.value = null
  try {
    const res = await runPortfolioBacktest({
      code: strategy.value.code,
      start_date: btDateRange.value[0],
      end_date: btDateRange.value[1],
      initial_cash: btCash.value,
    }) as any
    const rCode = res?.code ?? res?.data?.code
    if (rCode === 0) {
      btResult.value = res?.data?.status ? res.data : res
      showResults.value = true
      if (btResult.value?.status === 'completed') {
        ElMessage.success(`回测完成 (${btResult.value.elapsed}s)`)
        await nextTick()
        renderChart()
      } else if (btResult.value?.status === 'error') {
        ElMessage.error(btResult.value.message)
      }
    }
  } catch (e: any) {
    ElMessage.error(e.message || '回测异常')
  } finally {
    running.value = false
  }
}

async function createPaper() {
  if (!strategy.value.id) {
    ElMessage.warning('请先保存策略')
    return
  }
  try {
    const res = await createPaperTrading({
      strategy_id: strategy.value.id,
      name: '模拟-' + strategy.value.name,
      initial_cash: btCash.value,
    }) as any
    const rCode = res?.code ?? res?.data?.code
    if (rCode === 0) {
      ElMessage.success('模拟盘已创建')
      router.push('/algo/paper')
    }
  } catch (e) {
    ElMessage.error('创建失败')
  }
}

function renderChart() {
  if (!navChartEl.value || !btResult.value?.nav?.length) return
  if (navChart) navChart.dispose()
  navChart = echarts.init(navChartEl.value)

  const nav = btResult.value.nav
  const dates = nav.map((r: any) => r.date)
  const strategyReturns = nav.map((r: any) => ((r.nav - 1) * 100).toFixed(2))
  const benchmarkReturns = nav.map((r: any) => ((r.benchmark_nav - 1) * 100).toFixed(2))

  navChart.setOption({
    tooltip: { trigger: 'axis', formatter: (p: any) => {
      let h = `<b>${p[0].name}</b><br/>`
      p.forEach((s: any) => { h += `${s.marker} ${s.seriesName}: ${s.value}%<br/>` })
      return h
    }},
    legend: { data: ['策略收益', '基准收益'], top: 5, textStyle: { fontSize: 12 } },
    grid: { left: 50, right: 15, top: 40, bottom: 25 },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%', fontSize: 10 } },
    series: [
      { name: '策略收益', type: 'line', data: strategyReturns, symbol: 'none',
        lineStyle: { width: 2, color: '#e6a23c' },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(230,162,60,0.3)' }, { offset: 1, color: 'rgba(230,162,60,0.02)' }
        ])}},
      { name: '基准收益', type: 'line', data: benchmarkReturns, symbol: 'none',
        lineStyle: { width: 1.5, type: 'dashed', color: '#909399' }},
    ]
  })
}

watch(() => route.params.id, async (newId) => {
  if (newId) {
    const res = await getStrategyCodeDetail(Number(newId)) as any
    const d = res?.code === 0 ? res.data : res?.data?.data
    if (d) {
      strategy.value = res.data.data
      showResults.value = false
      btResult.value = null
      dirty.value = false
    }
  }
})

window.addEventListener('resize', () => navChart?.resize())
</script>

<style scoped>
.algo-editor { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
.editor-toolbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 16px; border-bottom: 1px solid #ebeef5; background: #fff;
  flex-shrink: 0;
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
.metrics-row {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 12px;
}
.metric { text-align: center; padding: 10px 8px; background: #f5f7fa; border-radius: 6px; }
.metric-val { font-size: 16px; font-weight: 700; color: #303133; }
.metric-lbl { font-size: 11px; color: #909399; margin-top: 2px; }
.val-red { color: #f56c6c !important; }
.val-green { color: #67c23a !important; }
.nav-chart { width: 100%; height: 280px; }
.error-msg { padding: 12px; }
.log-container {
  height: calc(100vh - 260px); overflow-y: auto;
  font-family: monospace; font-size: 12px; line-height: 1.5;
  background: #1e1e1e; color: #d4d4d4; padding: 8px 12px;
}
.log-line { white-space: pre-wrap; }
.log-empty { color: #606266; padding: 40px; text-align: center; }
</style>
