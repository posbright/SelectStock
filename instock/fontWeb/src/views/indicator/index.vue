<script setup lang="ts">
import { ref, onMounted, onUnmounted, onActivated, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import { getKlineData } from '@/api/stock'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()

let chartInstance: echarts.ECharts | null = null

const code = computed(() => route.query.code as string)
const date = computed(() => route.query.date as string || dayjs().format('YYYY-MM-DD'))
const stockName = computed(() => route.query.name as string)
const strategy = computed(() => route.query.strategy as string || '')

const klineChartRef = ref<HTMLDivElement>()
const loading = ref(false)

// 当前周期
const currentPeriod = ref('daily')
const periods = [
  { label: '日K', value: 'daily' },
  { label: '周K', value: 'weekly' },
  { label: '月K', value: 'monthly' },
  { label: '季K', value: 'quarterly' },
  { label: '年K', value: 'yearly' },
]

// 当前副图指标
const currentIndicator = ref('MACD')
const indicatorOptions = ['MACD', 'RSI', 'BOLL']

// K线数据
const klineData = ref<any>(null)

// 加载K线数据
const loadKlineData = async () => {
  if (!code.value) return
  loading.value = true
  try {
    const res = await getKlineData({
      code: code.value,
      date: date.value,
      period: currentPeriod.value,
      name: stockName.value || '',
    }) as any
    if (res?.error) {
      ElMessage.warning(res.error)
      klineData.value = null
    } else {
      klineData.value = res
    }
  } catch (e: any) {
    ElMessage.error('K线数据加载失败')
    klineData.value = null
  } finally {
    loading.value = false
    await nextTick()
    renderChart()
  }
}

// 渲染ECharts图表
const renderChart = () => {
  if (!klineChartRef.value || !klineData.value) return
  const d = klineData.value

  if (chartInstance) {
    chartInstance.dispose()
  }
  chartInstance = echarts.init(klineChartRef.value)

  const dates: string[] = d.dates
  const ohlc: number[][] = d.ohlc
  const volumes: number[] = d.volumes
  const ma = d.ma || {}
  const boll = d.boll || {}
  const rsi: (number | null)[] = d.rsi || []
  const macd = d.macd || {}

  // 根据当前指标决定副图配置
  const showBollOnMain = currentIndicator.value === 'BOLL'
  const showMacdSub = currentIndicator.value === 'MACD'
  const showRsiSub = currentIndicator.value === 'RSI'

  // 成交量颜色
  const volData = volumes.map((v, i) => ({
    value: v,
    itemStyle: {
      color: ohlc[i] && ohlc[i][1] >= ohlc[i][0] ? '#ec0000' : '#00da3c'
    }
  }))

  // Grid 布局：主图 + 成交量 + 副图指标
  const grids: any[] = [
    { left: '8%', right: '4%', top: '8%', height: '42%' },   // 主图
    { left: '8%', right: '4%', top: '55%', height: '12%' },   // 成交量
  ]
  const xAxes: any[] = [
    { type: 'category', data: dates, boundaryGap: false, axisLine: { onZero: false }, splitLine: { show: false }, min: 'dataMin', max: 'dataMax' },
    { type: 'category', gridIndex: 1, data: dates, axisLabel: { show: false } },
  ]
  const yAxes: any[] = [
    { scale: true, splitArea: { show: true } },
    { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false } },
  ]

  if (showMacdSub || showRsiSub) {
    grids.push({ left: '8%', right: '4%', top: '72%', height: '14%' })
    xAxes.push({ type: 'category', gridIndex: 2, data: dates, axisLabel: { show: false } })
    yAxes.push({ scale: true, gridIndex: 2, splitNumber: 2, axisLabel: { show: true, fontSize: 10 }, axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false } })
  }

  const legendData = ['K线', 'MA5', 'MA10', 'MA20', 'MA60']
  if (showBollOnMain) legendData.push('BOLL上轨', 'BOLL中轨', 'BOLL下轨')

  const series: any[] = [
    {
      name: 'K线', type: 'candlestick', data: ohlc,
      itemStyle: { color: '#ec0000', color0: '#00da3c', borderColor: '#ec0000', borderColor0: '#00da3c' }
    },
    { name: 'MA5', type: 'line', data: ma.ma5, smooth: true, lineStyle: { width: 1 }, symbol: 'none' },
    { name: 'MA10', type: 'line', data: ma.ma10, smooth: true, lineStyle: { width: 1 }, symbol: 'none' },
    { name: 'MA20', type: 'line', data: ma.ma20, smooth: true, lineStyle: { width: 1 }, symbol: 'none' },
    { name: 'MA60', type: 'line', data: ma.ma60, smooth: true, lineStyle: { width: 1 }, symbol: 'none' },
    { name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: volData },
  ]

  // BOLL 叠加到主图
  if (showBollOnMain && boll.upper) {
    series.push(
      { name: 'BOLL上轨', type: 'line', data: boll.upper, lineStyle: { width: 1, type: 'dashed', color: '#e6a23c' }, symbol: 'none' },
      { name: 'BOLL中轨', type: 'line', data: boll.middle, lineStyle: { width: 1, color: '#909399' }, symbol: 'none' },
      { name: 'BOLL下轨', type: 'line', data: boll.lower, lineStyle: { width: 1, type: 'dashed', color: '#67c23a' }, symbol: 'none' },
    )
  }

  // MACD 副图
  if (showMacdSub && macd.dif) {
    legendData.push('DIF', 'DEA', 'MACD')
    const macdBarData = (macd.histogram || []).map((v: number | null) => ({
      value: v,
      itemStyle: { color: v !== null && v >= 0 ? '#ec0000' : '#00da3c' }
    }))
    series.push(
      { name: 'DIF', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: macd.dif, lineStyle: { width: 1 }, symbol: 'none' },
      { name: 'DEA', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: macd.dea, lineStyle: { width: 1 }, symbol: 'none' },
      { name: 'MACD', type: 'bar', xAxisIndex: 2, yAxisIndex: 2, data: macdBarData },
    )
  }

  // RSI 副图
  if (showRsiSub && rsi.length) {
    legendData.push('RSI(14)')
    series.push(
      { name: 'RSI(14)', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: rsi, lineStyle: { width: 1, color: '#e6a23c' }, symbol: 'none' },
    )
  }

  const zoomXIndices = [0, 1]
  if (showMacdSub || showRsiSub) zoomXIndices.push(2)

  const option = {
    animation: false,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: legendData, top: 0, textStyle: { fontSize: 11 } },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    dataZoom: [
      { type: 'inside', xAxisIndex: zoomXIndices, start: 40, end: 100 },
      { show: true, xAxisIndex: zoomXIndices, type: 'slider', top: '92%', start: 40, end: 100 },
    ],
    series,
  }

  chartInstance.setOption(option)
}

// 切换周期
const switchPeriod = (p: string) => {
  currentPeriod.value = p
  loadKlineData()
}

// 切换副图指标
watch(currentIndicator, () => {
  renderChart()
})

// 跳转回测
const goBacktest = () => {
  router.push({
    path: '/backtest/custom',
    query: {
      code: code.value,
      name: stockName.value,
      strategy: strategy.value || undefined
    }
  })
}

const handleResize = () => { chartInstance?.resize() }

// 监听路由参数变化，当从别的股票点击进入时重新加载
let lastLoadedCode = ''
watch(
  () => route.query.code,
  (newCode, oldCode) => {
    if (newCode && newCode !== oldCode) {
      currentPeriod.value = 'daily'
      lastLoadedCode = newCode as string
      loadKlineData()
    }
  }
)

onMounted(() => {
  lastLoadedCode = code.value || ''
  loadKlineData()
  window.addEventListener('resize', handleResize)
})

// keep-alive 重新激活时，仅在股票代码变化时重新加载
onActivated(() => {
  window.addEventListener('resize', handleResize)
  nextTick(() => { chartInstance?.resize() })
  if (code.value && code.value !== lastLoadedCode) {
    lastLoadedCode = code.value
    currentPeriod.value = 'daily'
    loadKlineData()
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
  chartInstance = null
})
</script>

<template>
  <div class="indicator-container">
    <!-- 股票信息 -->
    <el-card class="info-card" shadow="never">
      <div class="stock-info">
        <div class="stock-basic">
          <span class="stock-code">{{ code }}</span>
          <span class="stock-name">{{ stockName }}</span>
          <el-tag size="small">{{ date }}</el-tag>
        </div>
        <div class="stock-actions">
          <el-button type="primary" size="small" @click="goBacktest">
            查看回测
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- K线图 -->
    <el-card class="chart-card" shadow="never" v-loading="loading">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <span>K线图</span>
            <el-radio-group v-model="currentIndicator" size="small" style="margin-left: 16px;">
              <el-radio-button v-for="ind in indicatorOptions" :key="ind" :value="ind">{{ ind }}</el-radio-button>
            </el-radio-group>
          </div>
          <el-button-group size="small">
            <el-button
              v-for="p in periods" :key="p.value"
              :type="currentPeriod === p.value ? 'primary' : ''"
              @click="switchPeriod(p.value)"
            >{{ p.label }}</el-button>
          </el-button-group>
        </div>
      </template>
      <div ref="klineChartRef" class="chart-container"></div>
    </el-card>

    <!-- 技术指标说明 -->
    <el-card class="desc-card" shadow="never">
      <template #header>
        <span>{{ currentIndicator }} 指标说明</span>
      </template>
      <div class="indicator-desc">
        <template v-if="currentIndicator === 'MACD'">
          <p><strong>MACD (指数平滑移动平均线)</strong></p>
          <p>MACD由快线EMA12减慢线EMA26得到DIF，再对DIF做9日EMA得到DEA。MACD柱 = 2×(DIF-DEA)。</p>
          <ul>
            <li>DIF 上穿 DEA → 金叉（买入参考）</li>
            <li>DIF 下穿 DEA → 死叉（卖出参考）</li>
            <li>红柱变长 → 上涨动力增强；绿柱变长 → 下跌动力增强</li>
          </ul>
        </template>
        <template v-else-if="currentIndicator === 'RSI'">
          <p><strong>RSI (相对强弱指标, 14日)</strong></p>
          <ul>
            <li>RSI &gt; 70 → 超买区，注意减仓</li>
            <li>RSI &lt; 30 → 超卖区，关注反弹机会</li>
            <li>RSI 在 40-60 区间 → 趋势温和，适合趋势回调买入</li>
          </ul>
        </template>
        <template v-else-if="currentIndicator === 'BOLL'">
          <p><strong>BOLL 布林带 (20日, 2倍标准差)</strong></p>
          <ul>
            <li>价格触及上轨并放量滞涨 → 注意减仓</li>
            <li>价格回调至中轨企稳，中轨上行 → 回调买入参考</li>
            <li>价格跌破下轨后收回 → 超跌反弹信号</li>
            <li>轨道收窄（缩口）→ 即将变盘</li>
          </ul>
        </template>
      </div>
    </el-card>
  </div>
</template>

<style lang="scss" scoped>
.indicator-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-card {
  :deep(.el-card__body) { padding: 12px 20px; }
}

.stock-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.stock-basic {
  display: flex;
  align-items: center;
  gap: 12px;
  .stock-code { font-size: 20px; font-weight: 600; color: #409eff; }
  .stock-name { font-size: 18px; color: #303133; }
}

.chart-card {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }
  .header-left {
    display: flex;
    align-items: center;
  }
}

.chart-container { height: 560px; }

.desc-card {
  .indicator-desc {
    line-height: 1.8;
    color: #606266;
    p { margin-bottom: 8px; }
    ul { padding-left: 20px; li { margin-bottom: 4px; } }
  }
}
</style>
