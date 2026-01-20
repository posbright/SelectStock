<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import dayjs from 'dayjs'

const route = useRoute()

// 图表实例引用，用于销毁时清理
let chartInstance: echarts.ECharts | null = null

// 从路由获取参数
const code = computed(() => route.query.code as string)
const date = computed(() => route.query.date as string || dayjs().format('YYYY-MM-DD'))
const stockName = computed(() => route.query.name as string)

// 图表容器
const klineChartRef = ref<HTMLDivElement>()
const volumeChartRef = ref<HTMLDivElement>()
const indicatorChartRef = ref<HTMLDivElement>()

// 当前选中的指标
const currentIndicator = ref('MACD')
const indicators = ['MACD', 'KDJ', 'RSI', 'BOLL', 'CCI', 'WR', 'DMI', 'OBV']

// 模拟 K线数据
const generateMockData = () => {
  const data = []
  let basePrice = 10 + Math.random() * 20
  const startDate = dayjs(date.value).subtract(60, 'day')
  
  for (let i = 0; i < 60; i++) {
    const currentDate = startDate.add(i, 'day').format('YYYY-MM-DD')
    const change = (Math.random() - 0.5) * 2
    const open = basePrice
    const close = basePrice + change
    const high = Math.max(open, close) + Math.random() * 0.5
    const low = Math.min(open, close) - Math.random() * 0.5
    const volume = Math.floor(Math.random() * 1000000) + 500000
    
    data.push({
      date: currentDate,
      open: +open.toFixed(2),
      close: +close.toFixed(2),
      high: +high.toFixed(2),
      low: +low.toFixed(2),
      volume
    })
    
    basePrice = close
  }
  
  return data
}

// 初始化 K线图
const initKlineChart = () => {
  if (!klineChartRef.value) return
  
  const chart = echarts.init(klineChartRef.value)
  const data = generateMockData()
  
  const dates = data.map(item => item.date)
  const klineData = data.map(item => [item.open, item.close, item.low, item.high])
  const volumes = data.map((item, index) => ({
    value: item.volume,
    itemStyle: {
      color: item.close >= item.open ? '#ec0000' : '#00da3c'
    }
  }))
  
  // 计算 MA
  const calculateMA = (dayCount: number) => {
    const result = []
    for (let i = 0; i < data.length; i++) {
      if (i < dayCount - 1) {
        result.push('-')
        continue
      }
      let sum = 0
      for (let j = 0; j < dayCount; j++) {
        sum += data[i - j].close
      }
      result.push((sum / dayCount).toFixed(2))
    }
    return result
  }
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      }
    },
    legend: {
      data: ['K线', 'MA5', 'MA10', 'MA20', 'MA30']
    },
    grid: [
      {
        left: '10%',
        right: '10%',
        top: '10%',
        height: '50%'
      },
      {
        left: '10%',
        right: '10%',
        top: '68%',
        height: '15%'
      }
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        scale: true,
        boundaryGap: false,
        axisLine: { onZero: false },
        splitLine: { show: false },
        min: 'dataMin',
        max: 'dataMax'
      },
      {
        type: 'category',
        gridIndex: 1,
        data: dates,
        axisLabel: { show: false }
      }
    ],
    yAxis: [
      {
        scale: true,
        splitArea: {
          show: true
        }
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: { show: false },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false }
      }
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 50,
        end: 100
      },
      {
        show: true,
        xAxisIndex: [0, 1],
        type: 'slider',
        top: '90%',
        start: 50,
        end: 100
      }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: klineData,
        itemStyle: {
          color: '#ec0000',
          color0: '#00da3c',
          borderColor: '#ec0000',
          borderColor0: '#00da3c'
        }
      },
      {
        name: 'MA5',
        type: 'line',
        data: calculateMA(5),
        smooth: true,
        lineStyle: { opacity: 0.8, width: 1 }
      },
      {
        name: 'MA10',
        type: 'line',
        data: calculateMA(10),
        smooth: true,
        lineStyle: { opacity: 0.8, width: 1 }
      },
      {
        name: 'MA20',
        type: 'line',
        data: calculateMA(20),
        smooth: true,
        lineStyle: { opacity: 0.8, width: 1 }
      },
      {
        name: 'MA30',
        type: 'line',
        data: calculateMA(30),
        smooth: true,
        lineStyle: { opacity: 0.8, width: 1 }
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes
      }
    ]
  }
  
  chart.setOption(option)
  
  // 保存图表实例
  chartInstance = chart
}

// 窗口 resize 处理函数
const handleResize = () => {
  chartInstance?.resize()
}

// 切换指标
const switchIndicator = (indicator: string) => {
  currentIndicator.value = indicator
  // TODO: 重新绘制指标图表
}

onMounted(() => {
  initKlineChart()
  window.addEventListener('resize', handleResize)
})

// 组件销毁时清理资源
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
        <div class="indicator-tabs">
          <el-radio-group v-model="currentIndicator" size="small">
            <el-radio-button 
              v-for="ind in indicators" 
              :key="ind" 
              :value="ind"
            >
              {{ ind }}
            </el-radio-button>
          </el-radio-group>
        </div>
      </div>
    </el-card>

    <!-- K线图 -->
    <el-card class="chart-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>K线图 & 成交量</span>
          <el-button-group size="small">
            <el-button>日K</el-button>
            <el-button>周K</el-button>
            <el-button>月K</el-button>
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
          <p>MACD是由快的指数移动平均线（EMA12）减去慢的指数移动平均线（EMA26）得到快线DIF，再用2×(快线DIF-DIF的9日加权移动均线DEA)得到MACD柱。</p>
          <ul>
            <li>DIF线从下向上突破DEA线，为买入信号</li>
            <li>DIF线从上向下跌破DEA线，为卖出信号</li>
            <li>红色柱状线由短变长，表示上涨动力增强</li>
            <li>绿色柱状线由短变长，表示下跌动力增强</li>
          </ul>
        </template>
        <template v-else-if="currentIndicator === 'KDJ'">
          <p><strong>KDJ (随机指标)</strong></p>
          <p>KDJ指标是通过一个特定周期内出现过的最高价、最低价及最后一个收盘价这三者之间的比例关系来计算最后一个计算周期的未成熟随机值。</p>
          <ul>
            <li>K值在80以上，D值在70以上为超买区</li>
            <li>K值在20以下，D值在30以下为超卖区</li>
            <li>K线向上突破D线为买入信号</li>
            <li>K线向下跌破D线为卖出信号</li>
          </ul>
        </template>
        <template v-else-if="currentIndicator === 'RSI'">
          <p><strong>RSI (相对强弱指标)</strong></p>
          <p>RSI是根据一定时期内上涨和下跌幅度之和的比率制作出的一种技术曲线，能够反映出市场在一定时期内的景气程度。</p>
          <ul>
            <li>RSI > 80 为超买状态</li>
            <li>RSI &lt; 20 为超卖状态</li>
            <li>RSI在50附近波动为盘整状态</li>
          </ul>
        </template>
        <template v-else>
          <p>{{ currentIndicator }} 指标详情请参考相关技术分析文档。</p>
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
  :deep(.el-card__body) {
    padding: 12px 20px;
  }
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
  
  .stock-code {
    font-size: 20px;
    font-weight: 600;
    color: #409eff;
  }
  
  .stock-name {
    font-size: 18px;
    color: #303133;
  }
}

.chart-card {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}

.chart-container {
  height: 500px;
}

.desc-card {
  .indicator-desc {
    line-height: 1.8;
    color: #606266;
    
    p {
      margin-bottom: 8px;
    }
    
    ul {
      padding-left: 20px;
      
      li {
        margin-bottom: 4px;
      }
    }
  }
}
</style>
