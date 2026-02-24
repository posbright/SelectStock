<script setup lang="ts">
import { ref, onMounted, onActivated } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getBacktestConfig, runBacktest, runBatchBacktest } from '@/api/stock'

const route = useRoute()

// 配置数据
const periods = ref<any[]>([])
const strategies = ref<any[]>([])

// 表单
const backtestForm = ref({
  mode: 'single',    // single: 单股回测, batch: 批量回测
  code: '',
  strategy: '',
  period: '1m',
  start_date: '',
})

// 结果
const loading = ref(false)
const singleResult = ref<any>(null)
const batchResult = ref<any>(null)

// 加载配置
onMounted(async () => {
  try {
    const config: any = await getBacktestConfig()
    if (config) {
      periods.value = config.periods || []
      strategies.value = config.strategies || []
    }
  } catch {
    ElMessage.error('加载回测配置失败')
  }
  // 从路由参数回填表单
  _applyQueryParams()
})

// keep-alive 重新激活时回填
onActivated(() => {
  _applyQueryParams()
})

// 从 route.query 回填表单字段
const _applyQueryParams = () => {
  const q = route.query
  if (q.code) {
    backtestForm.value.code = q.code as string
    backtestForm.value.mode = 'single'
  }
  if (q.strategy) {
    backtestForm.value.strategy = q.strategy as string
  }
}

// 执行回测
const handleRun = async () => {
  if (backtestForm.value.mode === 'single') {
    if (!backtestForm.value.code) {
      ElMessage.warning('请输入股票代码')
      return
    }
    await runSingleBacktest()
  } else {
    if (!backtestForm.value.strategy) {
      ElMessage.warning('请选择回测策略')
      return
    }
    await runBatchBacktestAction()
  }
}

const runSingleBacktest = async () => {
  loading.value = true
  singleResult.value = null
  try {
    const res: any = await runBacktest({
      code: backtestForm.value.code,
      strategy: backtestForm.value.strategy || undefined,
      period: backtestForm.value.period,
      start_date: backtestForm.value.start_date || undefined,
    })
    if (res.error) {
      ElMessage.error(res.error)
    } else {
      singleResult.value = res
    }
  } catch (e: any) {
    ElMessage.error(e.message || '回测执行失败')
  } finally {
    loading.value = false
  }
}

const runBatchBacktestAction = async () => {
  loading.value = true
  batchResult.value = null
  try {
    const res: any = await runBatchBacktest({
      strategy: backtestForm.value.strategy,
      period: backtestForm.value.period,
      limit: 30,
    })
    if (res.error) {
      ElMessage.error(res.error)
    } else {
      batchResult.value = res
    }
  } catch (e: any) {
    ElMessage.error(e.message || '批量回测执行失败')
  } finally {
    loading.value = false
  }
}

const formatRate = (val: any) => {
  if (val === null || val === undefined) return '-'
  const num = Number(val)
  return num >= 0 ? `+${num.toFixed(2)}%` : `${num.toFixed(2)}%`
}

const getRateClass = (val: any) => {
  if (val === null || val === undefined) return ''
  return Number(val) >= 0 ? 'text-up' : 'text-down'
}
</script>

<template>
  <div class="backtest-container">
    <!-- 配置面板 -->
    <el-card shadow="never" class="config-card">
      <template #header>
        <span class="card-title">自定义回测</span>
      </template>
      
      <el-form :model="backtestForm" label-width="100px" inline>
        <el-form-item label="回测模式">
          <el-radio-group v-model="backtestForm.mode" @change="singleResult = null; batchResult = null">
            <el-radio value="single">单股回测</el-radio>
            <el-radio value="batch">策略验证</el-radio>
          </el-radio-group>
        </el-form-item>
        
        <el-form-item v-if="backtestForm.mode === 'single'" label="股票代码">
          <el-input v-model="backtestForm.code" placeholder="如 000001" style="width: 150px" />
        </el-form-item>
        
        <el-form-item label="选择策略">
          <el-select v-model="backtestForm.strategy" placeholder="选择策略（可选）" clearable style="width: 220px">
            <el-option v-for="s in strategies" :key="s.name" :label="s.cn" :value="s.name" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="回测周期">
          <el-select v-model="backtestForm.period" style="width: 130px">
            <el-option v-for="p in periods" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
        
        <el-form-item v-if="backtestForm.mode === 'single'" label="买入日期">
          <el-date-picker v-model="backtestForm.start_date" type="date" placeholder="默认最新" 
            format="YYYY-MM-DD" value-format="YYYY-MM-DD" clearable style="width: 160px" />
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handleRun">
            {{ loading ? '回测中...' : '执行回测' }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 单股回测结果 -->
    <el-card v-if="singleResult" shadow="never" class="result-card">
      <template #header>
        <span class="card-title">回测结果：{{ singleResult.name }}（{{ singleResult.code }}）</span>
      </template>
      
      <!-- 概要信息 -->
      <el-descriptions :column="4" border size="small">
        <el-descriptions-item label="买入日期">{{ singleResult.buy_date }}</el-descriptions-item>
        <el-descriptions-item label="买入价格">{{ singleResult.buy_price }}</el-descriptions-item>
        <el-descriptions-item label="回测周期">{{ singleResult.period }}</el-descriptions-item>
        <el-descriptions-item label="数据天数">{{ singleResult.data_points }} 个交易日</el-descriptions-item>
        <el-descriptions-item label="区间最大涨幅">
          <span :class="getRateClass(singleResult.max_return)">{{ formatRate(singleResult.max_return) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="区间最大回撤">
          <span :class="getRateClass(singleResult.max_drawdown)">{{ formatRate(singleResult.max_drawdown) }}</span>
        </el-descriptions-item>
        <el-descriptions-item v-if="singleResult.strategy_result !== null" label="策略命中">
          <el-tag :type="singleResult.strategy_result ? 'success' : 'info'" size="small">
            {{ singleResult.strategy_result ? '是' : '否' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <!-- 收益率表 -->
      <h4 style="margin: 16px 0 8px">各周期收益率</h4>
      <el-table :data="singleResult.returns" border size="small" stripe>
        <el-table-column prop="days" label="持有天数" width="100" align="center" />
        <el-table-column prop="date" label="卖出日期" width="120" align="center" />
        <el-table-column prop="price" label="卖出价格" width="100" align="right" />
        <el-table-column label="收益率" width="120" align="right">
          <template #default="{ row }">
            <span :class="getRateClass(row.rate)">{{ formatRate(row.rate) }}</span>
          </template>
        </el-table-column>
      </el-table>

      <!-- 关键指标 -->
      <h4 v-if="singleResult.indicators && Object.keys(singleResult.indicators).length > 0" style="margin: 16px 0 8px">买入日关键指标</h4>
      <el-descriptions v-if="singleResult.indicators" :column="5" border size="small">
        <el-descriptions-item v-for="(val, key) in singleResult.indicators" :key="key" :label="String(key).toUpperCase()">
          {{ val !== null ? val : '-' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 批量回测结果 -->
    <el-card v-if="batchResult" shadow="never" class="result-card">
      <template #header>
        <span class="card-title">策略验证：{{ batchResult.strategy }}</span>
      </template>
      
      <!-- 汇总统计 -->
      <el-descriptions :column="4" border size="small">
        <el-descriptions-item label="回测天数">{{ batchResult.total_days }} 天</el-descriptions-item>
        <el-descriptions-item label="总选股数">{{ batchResult.total_stocks }} 只</el-descriptions-item>
        <el-descriptions-item label="成功数">{{ batchResult.success_count }} 只</el-descriptions-item>
        <el-descriptions-item label="总成功率">
          <span :class="batchResult.success_rate >= 50 ? 'text-up' : 'text-down'">
            {{ batchResult.success_rate }}%
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="平均1日收益">
          <span :class="getRateClass(batchResult.avg_returns?.['1d'])">{{ formatRate(batchResult.avg_returns?.['1d']) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="平均5日收益">
          <span :class="getRateClass(batchResult.avg_returns?.['5d'])">{{ formatRate(batchResult.avg_returns?.['5d']) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="平均10日收益">
          <span :class="getRateClass(batchResult.avg_returns?.['10d'])">{{ formatRate(batchResult.avg_returns?.['10d']) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="平均20日收益">
          <span :class="getRateClass(batchResult.avg_returns?.['20d'])">{{ formatRate(batchResult.avg_returns?.['20d']) }}</span>
        </el-descriptions-item>
      </el-descriptions>

      <!-- 每日明细 -->
      <h4 style="margin: 16px 0 8px">每日明细</h4>
      <el-table :data="batchResult.details" border size="small" stripe max-height="400">
        <el-table-column prop="date" label="日期" width="120" align="center" />
        <el-table-column prop="stock_count" label="选股数" width="80" align="center" />
        <el-table-column prop="success_count" label="成功数" width="80" align="center" />
        <el-table-column label="成功率" width="100" align="right">
          <template #default="{ row }">
            <span :class="row.success_rate >= 50 ? 'text-up' : 'text-down'">{{ row.success_rate }}%</span>
          </template>
        </el-table-column>
        <el-table-column label="1日收益" width="100" align="right">
          <template #default="{ row }">
            <span :class="getRateClass(row.avg_1d)">{{ formatRate(row.avg_1d) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="5日收益" width="100" align="right">
          <template #default="{ row }">
            <span :class="getRateClass(row.avg_5d)">{{ formatRate(row.avg_5d) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="10日收益" width="100" align="right">
          <template #default="{ row }">
            <span :class="getRateClass(row.avg_10d)">{{ formatRate(row.avg_10d) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="20日收益" width="100" align="right">
          <template #default="{ row }">
            <span :class="getRateClass(row.avg_20d)">{{ formatRate(row.avg_20d) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style lang="scss" scoped>
.backtest-container {
  padding: 0;
}

.config-card {
  margin-bottom: 16px;
}

.result-card {
  margin-bottom: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.text-up {
  color: #f56c6c;
  font-weight: 500;
}

.text-down {
  color: #67c23a;
  font-weight: 500;
}

:deep(.el-descriptions__label) {
  width: 120px;
}
</style>
