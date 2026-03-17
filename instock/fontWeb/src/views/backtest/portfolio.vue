<template>
  <div class="portfolio-backtest">
    <!-- 顶部操作栏 -->
    <el-card class="top-bar" shadow="never">
      <div class="toolbar">
        <h3>组合回测</h3>
        <div class="actions">
          <el-select v-model="selectedTemplate" placeholder="加载模板策略" @change="loadTemplate" style="width: 200px; margin-right: 12px;">
            <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
          <el-button type="primary" @click="runBacktest" :loading="running" :icon="CaretRight">运行回测</el-button>
          <el-button @click="saveStrategy" :icon="DocumentAdd">保存策略</el-button>
        </div>
      </div>
    </el-card>

    <el-row :gutter="16" class="main-content">
      <!-- 左侧：策略编辑器 -->
      <el-col :span="12">
        <el-card shadow="never" class="editor-card">
          <template #header>
            <div class="card-header">
              <span>策略代码</span>
              <el-input v-model="strategyName" placeholder="策略名称" style="width: 200px;" size="small" />
            </div>
          </template>
          <div class="editor-wrapper">
            <textarea ref="codeEditor" v-model="strategyCode" class="code-textarea"
                      spellcheck="false" wrap="off" />
          </div>
          <!-- 参数配置 -->
          <div class="params-row">
            <el-date-picker v-model="dateRange" type="daterange" range-separator="至"
                            start-placeholder="开始日期" end-placeholder="结束日期"
                            value-format="YYYY-MM-DD" size="small" style="width: 260px;" />
            <el-input-number v-model="initialCash" :min="10000" :step="100000"
                             size="small" style="width: 150px;" />
            <span class="param-label">初始资金</span>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：回测结果 -->
      <el-col :span="12">
        <el-card shadow="never" class="result-card" v-loading="running">
          <template #header>
            <div class="card-header">
              <span>回测结果</span>
              <el-tag v-if="result?.status === 'completed'" type="success">完成</el-tag>
              <el-tag v-else-if="result?.status === 'error'" type="danger">错误</el-tag>
            </div>
          </template>

          <!-- 错误信息 -->
          <el-alert v-if="result?.status === 'error'" :title="result.message"
                    type="error" show-icon :closable="false" style="margin-bottom: 16px;" />

          <!-- 汇总指标 -->
          <div v-if="result?.metrics" class="metrics-grid">
            <div class="metric-item">
              <div class="metric-value" :class="result.metrics.total_return >= 0 ? 'positive' : 'negative'">
                {{ result.metrics.total_return.toFixed(2) }}%
              </div>
              <div class="metric-label">累计收益</div>
            </div>
            <div class="metric-item">
              <div class="metric-value" :class="result.metrics.annual_return >= 0 ? 'positive' : 'negative'">
                {{ result.metrics.annual_return.toFixed(2) }}%
              </div>
              <div class="metric-label">年化收益</div>
            </div>
            <div class="metric-item">
              <div class="metric-value negative">{{ result.metrics.max_drawdown.toFixed(2) }}%</div>
              <div class="metric-label">最大回撤</div>
            </div>
            <div class="metric-item">
              <div class="metric-value">{{ result.metrics.sharpe_ratio.toFixed(2) }}</div>
              <div class="metric-label">夏普比率</div>
            </div>
            <div class="metric-item">
              <div class="metric-value">{{ result.metrics.trade_count }}</div>
              <div class="metric-label">交易笔数</div>
            </div>
            <div class="metric-item">
              <div class="metric-value">{{ result.metrics.daily_win_rate.toFixed(1) }}%</div>
              <div class="metric-label">日胜率</div>
            </div>
          </div>

          <!-- 净值曲线 -->
          <div v-if="result?.nav?.length" ref="navChartRef" class="nav-chart"></div>

          <!-- 交易明细 -->
          <div v-if="result?.trades?.length" style="margin-top: 16px;">
            <h4>交易明细 ({{ result.trades.length }} 笔)</h4>
            <el-table :data="result.trades" size="small" max-height="300" stripe>
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
                <template #default="{ row }">{{ Number(row.price).toFixed(2) }}</template>
              </el-table-column>
              <el-table-column prop="amount" label="数量" width="80" align="right" />
              <el-table-column prop="value" label="金额" width="100" align="right">
                <template #default="{ row }">{{ Number(row.value).toFixed(0) }}</template>
              </el-table-column>
              <el-table-column prop="commission" label="佣金" width="70" align="right">
                <template #default="{ row }">{{ Number(row.commission).toFixed(2) }}</template>
              </el-table-column>
            </el-table>
          </div>

          <!-- 策略日志 -->
          <div v-if="result?.logs?.length" style="margin-top: 16px;">
            <el-collapse>
              <el-collapse-item title="策略日志" name="logs">
                <div class="log-area">
                  <div v-for="(log, i) in result.logs.slice(-50)" :key="i" class="log-line">{{ log }}</div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>

          <!-- 空状态 -->
          <el-empty v-if="!result && !running" description="编写策略后点击「运行回测」" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { CaretRight, DocumentAdd } from '@element-plus/icons-vue'
import { getStrategyTemplates, runPortfolioBacktest, saveStrategyCode } from '@/api/stock'
import * as echarts from 'echarts'

const templates = ref<any[]>([])
const selectedTemplate = ref('')
const strategyName = ref('我的策略')
const strategyCode = ref(`def initialize(context):
    context.security = '000001'

def handle_data(context, data):
    code = context.security
    price = data[code].close
    if price <= 0:
        return
    ma5 = history(code, 5, 'close')
    if len(ma5) < 5:
        return
    ma_val = ma5.mean()

    if price > ma_val * 1.01 and code not in context.portfolio.positions:
        order_value(code, context.portfolio.available_cash * 0.9)
    elif price < ma_val * 0.99 and code in context.portfolio.positions:
        order_target(code, 0)
`)
const dateRange = ref(['2024-01-01', '2025-01-01'])
const initialCash = ref(1000000)
const running = ref(false)
const result = ref<any>(null)
const navChartRef = ref<HTMLElement>()
let navChart: echarts.ECharts | null = null

onMounted(async () => {
  try {
    const res: any = await getStrategyTemplates()
    if (res?.code === 0) {
      templates.value = res.data
    }
  } catch (e) {
    console.error('加载模板失败', e)
  }
})

function loadTemplate(templateId: string) {
  const t = templates.value.find((x: any) => x.id === templateId)
  if (t) {
    strategyCode.value = t.code
    strategyName.value = t.name
    ElMessage.success(`已加载模板: ${t.name}`)
  }
}

async function runBacktest() {
  if (!strategyCode.value.trim()) {
    ElMessage.warning('请输入策略代码')
    return
  }
  if (!dateRange.value?.[0] || !dateRange.value?.[1]) {
    ElMessage.warning('请选择回测日期范围')
    return
  }

  running.value = true
  result.value = null
  try {
    const res: any = await runPortfolioBacktest({
      code: strategyCode.value,
      start_date: dateRange.value[0],
      end_date: dateRange.value[1],
      initial_cash: initialCash.value,
    })
    if (res?.code === 0) {
      result.value = res.data
      if (result.value?.status === 'completed') {
        ElMessage.success(`回测完成，耗时 ${result.value.elapsed}s`)
        await nextTick()
        renderNavChart()
      } else if (result.value?.status === 'error') {
        ElMessage.error(result.value.message)
      }
    } else {
      ElMessage.error(res?.msg || '回测失败')
    }
  } catch (e: any) {
    ElMessage.error(`回测异常: ${e.message}`)
  } finally {
    running.value = false
  }
}

async function saveStrategy() {
  if (!strategyName.value.trim()) {
    ElMessage.warning('请输入策略名称')
    return
  }
  try {
    const res: any = await saveStrategyCode({
      name: strategyName.value,
      code: strategyCode.value,
      initial_cash: initialCash.value,
    })
    if (res?.code === 0) {
      ElMessage.success('策略已保存')
    } else {
      ElMessage.error(res?.msg || '保存失败')
    }
  } catch (e: any) {
    ElMessage.error(`保存异常: ${e.message}`)
  }
}

function renderNavChart() {
  if (!navChartRef.value || !result.value?.nav?.length) return

  if (navChart) {
    navChart.dispose()
  }
  navChart = echarts.init(navChartRef.value)

  const dates = result.value.nav.map((r: any) => r.date)
  const navs = result.value.nav.map((r: any) => ((r.nav - 1) * 100).toFixed(2))
  const benchmarks = result.value.nav.map((r: any) => ((r.benchmark_nav - 1) * 100).toFixed(2))

  navChart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const date = params[0].name
        let html = `<strong>${date}</strong><br/>`
        params.forEach((p: any) => {
          html += `${p.marker} ${p.seriesName}: ${p.value}%<br/>`
        })
        return html
      }
    },
    legend: { data: ['策略收益', '基准收益'], top: 5 },
    grid: { left: 60, right: 20, top: 35, bottom: 30 },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
    series: [
      {
        name: '策略收益', type: 'line', data: navs,
        lineStyle: { width: 2 }, symbol: 'none',
        itemStyle: { color: '#e6a23c' },
        areaStyle: { color: 'rgba(230, 162, 60, 0.1)' }
      },
      {
        name: '基准收益', type: 'line', data: benchmarks,
        lineStyle: { width: 1, type: 'dashed' }, symbol: 'none',
        itemStyle: { color: '#909399' },
      },
    ]
  })
}

// 监听窗口大小变化
window.addEventListener('resize', () => navChart?.resize())
</script>

<style scoped>
.portfolio-backtest {
  padding: 16px;
}
.top-bar {
  margin-bottom: 16px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.toolbar h3 { margin: 0; }
.main-content {
  min-height: calc(100vh - 200px);
}
.editor-card, .result-card {
  height: calc(100vh - 200px);
  overflow-y: auto;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.editor-wrapper {
  height: 400px;
}
.code-textarea {
  width: 100%;
  height: 100%;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
  padding: 12px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: #fafafa;
  resize: none;
  tab-size: 4;
  outline: none;
}
.code-textarea:focus {
  border-color: #409eff;
  background: #fff;
}
.params-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}
.param-label {
  font-size: 12px;
  color: #909399;
}
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.metric-item {
  text-align: center;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 6px;
}
.metric-value {
  font-size: 20px;
  font-weight: bold;
  color: #303133;
}
.metric-value.positive { color: #f56c6c; }
.metric-value.negative { color: #67c23a; }
.metric-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.nav-chart {
  width: 100%;
  height: 300px;
}
.log-area {
  max-height: 200px;
  overflow-y: auto;
  font-family: monospace;
  font-size: 12px;
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 8px;
  border-radius: 4px;
}
.log-line {
  white-space: pre-wrap;
  line-height: 1.4;
}
</style>
