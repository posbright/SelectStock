<template>
  <div class="paper-trading">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <h3>模拟交易</h3>
          <div class="header-actions">
            <el-button type="primary" :disabled="selectedRows.length < 2" @click="goCompare">
              <el-icon><DataAnalysis /></el-icon>
              对比 ({{ selectedRows.length }})
            </el-button>
            <el-button type="primary" @click="showCreateDialog = true" :icon="Plus">创建模拟盘</el-button>
          </div>
        </div>
      </template>

      <!-- 模拟盘列表 -->
      <el-table :data="paperList" v-loading="loading" stripe @selection-change="onSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称" width="150" />
        <el-table-column prop="strategy_name" label="策略" width="120" />
        <el-table-column prop="initial_cash" label="初始资金" width="110" align="right">
          <template #default="{ row }">{{ formatMoney(row.initial_cash) }}</template>
        </el-table-column>
        <el-table-column prop="current_value" label="当前总资产" width="120" align="right">
          <template #default="{ row }">{{ formatMoney(row.current_value) }}</template>
        </el-table-column>
        <el-table-column prop="profit_rate" label="收益率" width="90" align="right">
          <template #default="{ row }">
            <span :class="row.profit_rate >= 0 ? 'text-red' : 'text-green'">
              {{ row.profit_rate >= 0 ? '+' : '' }}{{ row.profit_rate }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_run_date" label="最后运行" width="100" />
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewDetail(row.id)">详情</el-button>
            <el-button size="small" type="warning" v-if="row.status === 'running'"
                       @click="doAction(row.id, 'pause')">暂停</el-button>
            <el-button size="small" type="success" v-if="row.status === 'paused'"
                       @click="doAction(row.id, 'resume')">恢复</el-button>
            <el-button size="small" type="danger" v-if="row.status !== 'stopped'"
                       @click="doAction(row.id, 'stop')">停止</el-button>
            <el-button size="small" type="primary" v-if="row.status === 'running'"
                       @click="doRun(row.id)" :loading="runningId === row.id">执行</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="showDetail" :title="detailData?.info?.name || '模拟盘详情'" width="85%">
      <div v-if="detailData" v-loading="detailLoading">
        <!-- 汇总信息 -->
        <div class="detail-summary">
          <div class="summary-item">
            <span class="label">初始资金</span>
            <span class="value">{{ formatMoney(detailData.info.initial_cash) }}</span>
          </div>
          <div class="summary-item">
            <span class="label">当前总资产</span>
            <span class="value">{{ formatMoney(detailData.info.current_value) }}</span>
          </div>
          <div class="summary-item">
            <span class="label">可用现金</span>
            <span class="value">{{ formatMoney(detailData.info.current_cash) }}</span>
          </div>
          <div class="summary-item">
            <span class="label">总收益</span>
            <span class="value" :class="detailData.info.profit_rate >= 0 ? 'text-red' : 'text-green'">
              {{ detailData.info.profit_rate >= 0 ? '+' : '' }}{{ detailData.info.profit_rate }}%
            </span>
          </div>
        </div>

        <!-- 绩效指标 -->
        <div class="detail-metrics" v-if="detailData.info.running_days > 0">
          <div class="metric-item" v-for="m in metricCards" :key="m.key">
            <span class="label">{{ m.label }}</span>
            <span class="value" :class="m.cls(detailData.info[m.key])">{{ m.fmt(detailData.info[m.key]) }}</span>
          </div>
        </div>

        <!-- NAV 走势图 -->
        <div v-if="detailData.nav && detailData.nav.length > 1" style="margin: 16px 0;">
          <h4>资产走势</h4>
          <div ref="navChartRef" style="height: 280px; width: 100%;"></div>
        </div>

        <!-- 当前持仓 -->
        <h4>当前持仓</h4>
        <el-table :data="detailData.positions" size="small" stripe v-if="detailData.positions.length">
          <el-table-column prop="code" label="代码" width="70" />
          <el-table-column prop="name" label="名称" width="80" />
          <el-table-column prop="amount" label="持仓" width="70" align="right" />
          <el-table-column prop="avg_cost" label="成本" width="80" align="right">
            <template #default="{ row }">{{ row.avg_cost.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="price" label="现价" width="80" align="right">
            <template #default="{ row }">{{ row.price.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="value" label="市值" width="100" align="right">
            <template #default="{ row }">{{ formatMoney(row.value) }}</template>
          </el-table-column>
          <el-table-column prop="profit_rate" label="盈亏" width="80" align="right">
            <template #default="{ row }">
              <span :class="row.profit_rate >= 0 ? 'text-red' : 'text-green'">
                {{ row.profit_rate >= 0 ? '+' : '' }}{{ row.profit_rate }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="weight" label="权重" width="70" align="right">
            <template #default="{ row }">{{ row.weight.toFixed(1) }}%</template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无持仓" :image-size="60" />

        <!-- 交易记录 -->
        <h4 style="margin-top: 16px;">交易记录</h4>
        <el-table :data="detailData.trades" size="small" max-height="300" stripe v-if="detailData.trades.length">
          <el-table-column prop="date" label="日期" width="100" />
          <el-table-column prop="code" label="代码" width="70" />
          <el-table-column prop="direction" label="方向" width="60">
            <template #default="{ row }">
              <el-tag :type="row.direction === 'buy' ? 'danger' : 'success'" size="small">
                {{ row.direction === 'buy' ? '买入' : '卖出' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="price" label="价格" width="80" align="right">
            <template #default="{ row }">{{ row.price.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="amount" label="数量" width="80" align="right" />
          <el-table-column prop="value" label="金额" width="100" align="right">
            <template #default="{ row }">{{ formatMoney(row.value) }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无交易记录" :image-size="60" />
      </div>
    </el-dialog>

    <!-- 对比对话框 -->
    <el-dialog v-model="showCompare" title="模拟盘对比" width="90%">
      <div v-loading="compareLoading">
        <div v-if="compareData.length">
          <!-- 对比 NAV 走势 -->
          <h4>收益走势对比</h4>
          <div ref="compareChartRef" style="height: 320px; width: 100%;"></div>

          <!-- 指标对比表 -->
          <h4 style="margin-top: 16px;">绩效指标对比</h4>
          <el-table :data="compareMetricRows" size="small" stripe border>
            <el-table-column prop="label" label="指标" width="120" fixed />
            <el-table-column v-for="p in compareData" :key="p.id" :label="p.name || p.strategy_name" align="right">
              <template #default="{ row }">
                <span :class="row.cls ? row.cls(row.values[p.id]) : ''">{{ row.fmt(row.values[p.id]) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <el-empty v-else description="暂无对比数据" />
      </div>
    </el-dialog>

    <!-- 创建对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建模拟盘" width="500px">
      <el-form label-width="100px">
        <el-form-item label="策略">
          <el-select v-model="createForm.strategy_id" placeholder="选择已保存的策略" style="width: 100%;">
            <el-option v-for="s in strategies" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="createForm.name" placeholder="模拟盘名称" />
        </el-form-item>
        <el-form-item label="初始资金">
          <el-input-number v-model="createForm.initial_cash" :min="10000" :step="100000" style="width: 100%;" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="doCreate" :loading="creating">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, DataAnalysis } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import {
  getPaperTradingList, getPaperTradingDetail, createPaperTrading,
  paperTradingAction, runPaperTrading, getStrategyCodeList, getPaperCompare
} from '@/api/stock'
import request from '@/api/request'

const paperList = ref<any[]>([])
const strategies = ref<any[]>([])
const loading = ref(false)
const showDetail = ref(false)
const showCreateDialog = ref(false)
const showCompare = ref(false)
const detailData = ref<any>(null)
const detailLoading = ref(false)
const compareData = ref<any[]>([])
const compareLoading = ref(false)
const creating = ref(false)
const runningId = ref<number | null>(null)
const selectedRows = ref<any[]>([])
const createForm = ref({ strategy_id: null as number | null, name: '', initial_cash: 1000000 })
const navChartRef = ref<HTMLElement | null>(null)
const compareChartRef = ref<HTMLElement | null>(null)

function formatMoney(v: number) {
  return v >= 10000 ? `${(v / 10000).toFixed(2)}万` : v.toFixed(0)
}
function statusType(s: string) {
  return s === 'running' ? 'success' : s === 'paused' ? 'warning' : 'info'
}
function statusLabel(s: string) {
  return s === 'running' ? '运行中' : s === 'paused' ? '已暂停' : '已停止'
}

const metricCards = [
  { key: 'annual_return', label: '年化收益', fmt: (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`,
    cls: (v: number) => v >= 0 ? 'text-red' : 'text-green' },
  { key: 'max_drawdown', label: '最大回撤', fmt: (v: number) => `${v.toFixed(2)}%`, cls: () => 'text-green' },
  { key: 'sharpe_ratio', label: '夏普比率', fmt: (v: number) => v.toFixed(2), cls: (v: number) => v >= 1 ? 'text-red' : '' },
  { key: 'sortino_ratio', label: '索提诺', fmt: (v: number) => v.toFixed(2), cls: (v: number) => v >= 1 ? 'text-red' : '' },
  { key: 'win_rate', label: '胜率', fmt: (v: number) => `${v.toFixed(1)}%`, cls: (v: number) => v >= 50 ? 'text-red' : '' },
  { key: 'profit_loss_ratio', label: '盈亏比', fmt: (v: number) => v.toFixed(2), cls: (v: number) => v >= 1 ? 'text-red' : '' },
  { key: 'trade_count', label: '交易笔数', fmt: (v: number) => String(v || 0), cls: () => '' },
  { key: 'running_days', label: '运行天数', fmt: (v: number) => String(v || 0), cls: () => '' },
]

const compareMetricRows = computed(() => {
  if (!compareData.value.length) return []
  const rows = [
    { label: '总收益', key: 'total_return', fmt: (v: number) => `${(v||0) >= 0 ? '+' : ''}${(v||0).toFixed(2)}%`, cls: (v: number) => (v||0) >= 0 ? 'text-red' : 'text-green' },
    { label: '年化收益', key: 'annual_return', fmt: (v: number) => `${(v||0) >= 0 ? '+' : ''}${(v||0).toFixed(2)}%`, cls: (v: number) => (v||0) >= 0 ? 'text-red' : 'text-green' },
    { label: '最大回撤', key: 'max_drawdown', fmt: (v: number) => `${(v||0).toFixed(2)}%`, cls: () => 'text-green' },
    { label: '夏普比率', key: 'sharpe_ratio', fmt: (v: number) => (v||0).toFixed(2), cls: undefined },
    { label: '索提诺', key: 'sortino_ratio', fmt: (v: number) => (v||0).toFixed(2), cls: undefined },
    { label: '胜率', key: 'win_rate', fmt: (v: number) => `${(v||0).toFixed(1)}%`, cls: undefined },
    { label: '盈亏比', key: 'profit_loss_ratio', fmt: (v: number) => (v||0).toFixed(2), cls: undefined },
    { label: '交易笔数', key: 'trade_count', fmt: (v: number) => String(v||0), cls: undefined },
  ]
  return rows.map(r => ({
    ...r,
    values: Object.fromEntries(compareData.value.map(p => [p.id, p.metrics?.[r.key] ?? 0]))
  }))
})

function onSelectionChange(rows: any[]) {
  selectedRows.value = rows
}

function initNavChart() {
  if (!navChartRef.value || !detailData.value?.nav?.length) return
  const chart = echarts.init(navChartRef.value)
  const dates = detailData.value.nav.map((n: any) => n.date)
  const values = detailData.value.nav.map((n: any) => n.total_value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', scale: true },
    series: [{ name: '总资产', type: 'line', data: values, smooth: true, areaStyle: { opacity: 0.15 } }],
    grid: { left: 60, right: 20, top: 20, bottom: 30 },
  })
}

function initCompareChart() {
  if (!compareChartRef.value || !compareData.value.length) return
  const chart = echarts.init(compareChartRef.value)
  const colors = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4']
  const series = compareData.value.map((p: any, i: number) => {
    const nav = p.nav || []
    if (!nav.length) return null
    const initial = nav[0].total_value || 1
    return {
      name: p.name || p.strategy_name,
      type: 'line',
      smooth: true,
      data: nav.map((n: any) => [n.date, ((n.total_value / initial - 1) * 100).toFixed(2)]),
      itemStyle: { color: colors[i % colors.length] },
    }
  }).filter(Boolean)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    xAxis: { type: 'category' },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
    series,
    grid: { left: 60, right: 20, top: 40, bottom: 30 },
  })
}

async function loadList() {
  loading.value = true
  try {
    const res = await getPaperTradingList()
    if ((res as any)?.code === 0) paperList.value = (res as any).data
    else if (res.data?.code === 0) paperList.value = res.data.data
  } finally {
    loading.value = false
  }
}

async function loadStrategies() {
  try {
    // 先同步内置模板到数据库，确保模板策略可选
    try { await request({ url: '/api/strategy/sync_templates', method: 'post' }) } catch { /* ignore */ }
    // 加载策略列表
    const res = await getStrategyCodeList() as any
    const d = res?.data || res
    strategies.value = d?.strategies || (Array.isArray(d) ? d : [])
  } catch (e) { /* ignore */ }
}

async function viewDetail(id: number) {
  showDetail.value = true
  detailLoading.value = true
  try {
    const res = await getPaperTradingDetail(id)
    if ((res as any)?.code === 0) detailData.value = (res as any).data
    else if (res.data?.code === 0) detailData.value = res.data.data
    await nextTick()
    initNavChart()
  } finally {
    detailLoading.value = false
  }
}

async function goCompare() {
  if (selectedRows.value.length < 2) return
  showCompare.value = true
  compareLoading.value = true
  try {
    const ids = selectedRows.value.map((r: any) => r.id)
    const res = await getPaperCompare(ids)
    const body = (res as any)?.code !== undefined ? (res as any) : res.data
    if (body?.code === 0) {
      compareData.value = body.data
      await nextTick()
      initCompareChart()
    } else {
      ElMessage.error(body?.msg || '对比失败')
    }
  } finally {
    compareLoading.value = false
  }
}

async function doAction(id: number, action: 'pause' | 'resume' | 'stop') {
  if (action === 'stop') {
    await ElMessageBox.confirm('确定要停止此模拟盘？停止后无法恢复。', '确认')
  }
  try {
    const res = await paperTradingAction({ id, action })
    if ((res as any)?.code === 0 || res.data?.code === 0) {
      ElMessage.success('操作成功')
      loadList()
    }
  } catch (e) { /* cancelled */ }
}

async function doRun(id: number) {
  runningId.value = id
  try {
    const res = await runPaperTrading(id)
    const body = (res as any)?.code !== undefined ? (res as any) : res.data
    if (body?.code === 0) {
      const r = body.data
      ElMessage.success(r.message || '执行完成')
      loadList()
    } else {
      ElMessage.error(body?.msg || '执行失败')
    }
  } finally {
    runningId.value = null
  }
}

async function doCreate() {
  if (!createForm.value.strategy_id) {
    ElMessage.warning('请选择策略')
    return
  }
  creating.value = true
  try {
    const res = await createPaperTrading({
      strategy_id: createForm.value.strategy_id,
      name: createForm.value.name,
      initial_cash: createForm.value.initial_cash,
    })
    const body = (res as any)?.code !== undefined ? (res as any) : res.data
    if (body?.code === 0) {
      ElMessage.success('模拟盘创建成功')
      showCreateDialog.value = false
      loadList()
    } else {
      ElMessage.error(body?.msg || '创建失败')
    }
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  loadList()
  loadStrategies()
})
</script>

<style scoped>
.paper-trading { padding: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-header h3 { margin: 0; }
.header-actions { display: flex; gap: 8px; }
.text-red { color: #f56c6c; font-weight: 600; }
.text-green { color: #67c23a; font-weight: 600; }
.detail-summary {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px;
}
.detail-metrics {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 16px;
}
.summary-item, .metric-item {
  text-align: center; padding: 12px; background: #f5f7fa; border-radius: 6px;
}
.summary-item .label, .metric-item .label { display: block; font-size: 12px; color: #909399; margin-bottom: 4px; }
.summary-item .value { font-size: 18px; font-weight: bold; }
.metric-item .value { font-size: 16px; font-weight: 600; }
</style>
