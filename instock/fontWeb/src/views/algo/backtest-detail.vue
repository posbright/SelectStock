<template>
  <div class="bt-detail" v-loading="loading">
    <div class="detail-header">
      <el-button text @click="$router.back()">
        <el-icon><ArrowLeft /></el-icon> 返回
      </el-button>
      <h3>回测详情 #{{ btId }}</h3>
      <span class="header-sub" v-if="info">{{ info.strategy_name }} | {{ info.start_date }} ~ {{ info.end_date }}</span>
    </div>

    <!-- 指标概览 -->
    <div class="metrics-bar" v-if="info?.metrics">
      <div class="metric" v-for="m in metricCards" :key="m.key">
        <div class="metric-val" :class="m.cls">{{ m.val }}</div>
        <div class="metric-lbl">{{ m.label }}</div>
      </div>
    </div>

    <!-- Tabs: 收益概览 / 每日持仓 / 每日交易 / 日志 -->
    <el-tabs v-model="activeTab">
      <el-tab-pane label="收益概览" name="overview">
        <div ref="chartEl" class="nav-chart"></div>
      </el-tab-pane>

      <el-tab-pane :label="'每日交易(' + (info?.trades?.length || 0) + ')'" name="trades">
        <el-table :data="info?.trades || []" size="small" max-height="600" stripe>
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

      <el-tab-pane label="每日持仓" name="positions">
        <el-table :data="lastPositions" size="small" max-height="600" stripe>
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

      <el-tab-pane :label="'日志(' + (info?.logs?.length || 0) + ')'" name="logs">
        <div class="log-box">
          <div v-for="(l, i) in (info?.logs || []).slice(-300)" :key="i" class="log-line">{{ l }}</div>
          <div v-if="!info?.logs?.length" class="log-empty">暂无日志</div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { getPortfolioBacktestDetail } from '@/api/stock'
import * as echarts from 'echarts'

const route = useRoute()
const btId = computed(() => Number(route.params.id))
const info = ref<any>(null)
const loading = ref(false)
const activeTab = ref('overview')
const chartEl = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

const metricCards = computed(() => {
  const m = info.value?.metrics
  if (!m) return []
  return [
    { key: 'ret', label: '策略收益', val: `${m.total_return >= 0 ? '+' : ''}${m.total_return.toFixed(2)}%`,
      cls: m.total_return >= 0 ? 'val-red' : 'val-green' },
    { key: 'annual', label: '年化收益', val: `${m.annual_return >= 0 ? '+' : ''}${m.annual_return.toFixed(2)}%`,
      cls: m.annual_return >= 0 ? 'val-red' : 'val-green' },
    { key: 'alpha', label: 'Alpha', val: `${(m.alpha || 0).toFixed(2)}%`, cls: '' },
    { key: 'beta', label: 'Beta', val: (m.beta || 0).toFixed(3), cls: '' },
    { key: 'sharpe', label: '夏普比率', val: m.sharpe_ratio.toFixed(3), cls: '' },
    { key: 'dd', label: '最大回撤', val: `${m.max_drawdown.toFixed(2)}%`, cls: 'val-green' },
    { key: 'wr', label: '日胜率', val: `${(m.daily_win_rate || 0).toFixed(1)}%`, cls: '' },
    { key: 'tc', label: '交易次数', val: m.trade_count, cls: '' },
  ]
})

const lastPositions = computed(() => {
  const pos = info.value?.positions
  if (!pos || pos.length === 0) return []
  return pos[pos.length - 1].positions || []
})

onMounted(async () => {
  loading.value = true
  try {
    const res = await getPortfolioBacktestDetail(btId.value) as any
    info.value = res?.code === 0 ? res.data : res?.data
    await nextTick()
    renderChart()
  } finally {
    loading.value = false
  }
})

function renderChart() {
  if (!chartEl.value || !info.value?.nav?.length) return
  if (chart) chart.dispose()
  chart = echarts.init(chartEl.value)
  const nav = info.value.nav
  chart.setOption({
    tooltip: { trigger: 'axis', formatter: (p: any) => {
      let h = `<b>${p[0].name}</b><br/>`
      p.forEach((s: any) => { h += `${s.marker} ${s.seriesName}: ${s.value}%<br/>` })
      return h
    }},
    legend: { data: ['策略收益', '基准收益'], top: 5 },
    grid: { left: 50, right: 15, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: nav.map((r: any) => r.date), axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%', fontSize: 10 } },
    series: [
      { name: '策略收益', type: 'line', data: nav.map((r: any) => ((r.nav - 1) * 100).toFixed(2)),
        symbol: 'none', lineStyle: { width: 2, color: '#e6a23c' },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(230,162,60,0.3)' }, { offset: 1, color: 'rgba(230,162,60,0.02)' }
        ])}},
      { name: '基准收益', type: 'line', data: nav.map((r: any) => ((r.benchmark_nav - 1) * 100).toFixed(2)),
        symbol: 'none', lineStyle: { width: 1.5, type: 'dashed', color: '#909399' }},
    ]
  })
}
window.addEventListener('resize', () => chart?.resize())
</script>

<style scoped>
.bt-detail { padding: 20px; }
.detail-header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.detail-header h3 { margin: 0; }
.header-sub { color: #909399; font-size: 13px; }
.metrics-bar {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 20px;
}
.metric { text-align: center; padding: 12px; background: #f5f7fa; border-radius: 6px; }
.metric-val { font-size: 18px; font-weight: 700; color: #303133; }
.metric-lbl { font-size: 12px; color: #909399; margin-top: 2px; }
.val-red { color: #f56c6c !important; }
.val-green { color: #67c23a !important; }
.nav-chart { width: 100%; height: 350px; }
.log-box {
  max-height: 500px; overflow-y: auto; font-family: monospace; font-size: 12px;
  background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 4px;
}
.log-line { white-space: pre-wrap; line-height: 1.5; }
.log-empty { text-align: center; color: #606266; padding: 40px; }
</style>
