<template>
  <div class="bt-history">
    <div class="page-header">
      <h2>回测列表</h2>
      <el-select v-model="filterStrategyId" placeholder="筛选策略" clearable style="width: 200px;"
                 @change="loadData">
        <el-option label="全部策略" :value="0" />
        <el-option v-for="s in strategies" :key="s.id" :label="s.name" :value="s.id" />
      </el-select>
    </div>

    <el-table :data="list" v-loading="loading" stripe style="width: 100%;">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="strategy_name" label="策略名称" width="150">
        <template #default="{ row }">
          <el-link type="primary" @click="$router.push('/algo/edit/' + row.strategy_id)">
            {{ row.strategy_name }}
          </el-link>
        </template>
      </el-table-column>
      <el-table-column label="回测区间" width="200">
        <template #default="{ row }">{{ row.start_date }} ~ {{ row.end_date }}</template>
      </el-table-column>
      <el-table-column prop="initial_cash" label="初始资金" width="110" align="right">
        <template #default="{ row }">{{ formatCash(row.initial_cash) }}</template>
      </el-table-column>
      <el-table-column prop="total_return" label="策略收益" width="100" align="right">
        <template #default="{ row }">
          <span :style="{ color: row.total_return >= 0 ? '#f56c6c' : '#67c23a', fontWeight: 600 }">
            {{ row.total_return >= 0 ? '+' : '' }}{{ row.total_return.toFixed(2) }}%
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="annual_return" label="年化收益" width="100" align="right">
        <template #default="{ row }">
          <span :style="{ color: row.annual_return >= 0 ? '#f56c6c' : '#67c23a' }">
            {{ row.annual_return >= 0 ? '+' : '' }}{{ row.annual_return.toFixed(2) }}%
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="max_drawdown" label="最大回撤" width="90" align="right">
        <template #default="{ row }">{{ row.max_drawdown.toFixed(2) }}%</template>
      </el-table-column>
      <el-table-column prop="sharpe_ratio" label="夏普" width="70" align="right">
        <template #default="{ row }">{{ row.sharpe_ratio.toFixed(2) }}</template>
      </el-table-column>
      <el-table-column prop="trade_count" label="交易数" width="70" align="right" />
      <el-table-column prop="completed_at" label="完成时间" width="160" />
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" text @click="viewDetail(row.id)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && list.length === 0" description="暂无回测记录" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getPortfolioBacktestList, getStrategyCodeList } from '@/api/stock'

const router = useRouter()
const list = ref<any[]>([])
const strategies = ref<any[]>([])
const loading = ref(false)
const filterStrategyId = ref(0)

function formatCash(v: number) {
  return v >= 10000 ? (v / 10000).toFixed(0) + '万' : v.toFixed(0)
}

function viewDetail(id: number) {
  router.push('/algo/backtest-detail/' + id)
}

async function loadData() {
  loading.value = true
  try {
    const params = filterStrategyId.value ? { strategy_id: filterStrategyId.value } : undefined
    const res = await getPortfolioBacktestList(params) as any
    list.value = res?.data || res?.code === 0 ? (res.data || []) : []
  } finally {
    loading.value = false
  }
}

async function loadStrategies() {
  try {
    const res = await getStrategyCodeList() as any
    const d = res?.data || res
    strategies.value = d?.strategies || (Array.isArray(d) ? d : [])
  } catch (e) { /* ignore */ }
}

onMounted(() => { loadData(); loadStrategies() })
</script>

<style scoped>
.bt-history { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; }
</style>
