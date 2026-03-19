<template>
  <div class="bt-history">
    <div class="page-header">
      <div class="header-left">
        <h2>回测列表</h2>
        <el-tag type="info" size="small" class="count-tag">
          共 {{ list.length }} 条回测
        </el-tag>
      </div>
      <div class="header-right">
        <el-button type="primary" :disabled="selectedRows.length < 2" @click="goCompare">
          <el-icon><DataAnalysis /></el-icon>
          对比 ({{ selectedRows.length }})
        </el-button>
        <el-select v-model="filterStrategyId" placeholder="筛选策略" clearable style="width: 200px;"
                   @change="loadData">
          <el-option label="全部策略" :value="0" />
          <el-option v-for="s in strategies" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
      </div>
    </div>

    <el-table :data="list" v-loading="loading" stripe style="width: 100%;"
              :default-sort="{ prop: 'id', order: 'descending' }"
              @selection-change="onSelectionChange" ref="tableRef">
      <el-table-column type="selection" width="45" />
      <el-table-column prop="id" label="ID" width="60" sortable />
      <el-table-column prop="strategy_name" label="策略名称" width="150" show-overflow-tooltip>
        <template #default="{ row }">
          <el-link type="primary" @click="$router.push('/algo/edit/' + row.strategy_id)">
            {{ row.strategy_name }}
          </el-link>
        </template>
      </el-table-column>
      <el-table-column label="回测区间" width="200">
        <template #default="{ row }">{{ row.start_date }} ~ {{ row.end_date }}</template>
      </el-table-column>
      <el-table-column prop="initial_cash" label="初始资金" width="100" align="right">
        <template #default="{ row }">{{ formatCash(row.initial_cash) }}</template>
      </el-table-column>
      <el-table-column prop="total_return" label="策略收益" width="95" align="right" sortable>
        <template #default="{ row }">
          <span :class="retCls(row.total_return)">
            {{ fmtRet(row.total_return) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="annual_return" label="年化收益" width="95" align="right" sortable>
        <template #default="{ row }">
          <span :class="retCls(row.annual_return)">{{ fmtRet(row.annual_return) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="基准收益" width="95" align="right" sortable :sort-method="(a:any,b:any)=> (a.benchmark_return||0)-(b.benchmark_return||0)">
        <template #default="{ row }">
          <span :class="retCls(row.benchmark_return)">{{ fmtRet(row.benchmark_return) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="超额收益" width="95" align="right" sortable :sort-method="(a:any,b:any)=> (a.excess_return||0)-(b.excess_return||0)">
        <template #default="{ row }">
          <span :class="retCls(row.excess_return)">{{ fmtRet(row.excess_return) }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="max_drawdown" label="最大回撤" width="90" align="right" sortable>
        <template #default="{ row }">
          <span class="val-green">{{ N(row.max_drawdown).toFixed(2) }}%</span>
        </template>
      </el-table-column>
      <el-table-column label="超额最大回撤" width="110" align="right" sortable :sort-method="(a:any,b:any)=> (a.excess_max_drawdown||0)-(b.excess_max_drawdown||0)">
        <template #default="{ row }">
          <span class="val-green">{{ N(row.excess_max_drawdown || 0).toFixed(2) }}%</span>
        </template>
      </el-table-column>
      <el-table-column prop="sharpe_ratio" label="夏普" width="70" align="right" sortable>
        <template #default="{ row }">{{ N(row.sharpe_ratio).toFixed(2) }}</template>
      </el-table-column>
      <el-table-column label="超额夏普" width="85" align="right" sortable :sort-method="(a:any,b:any)=> (a.excess_sharpe_ratio||0)-(b.excess_sharpe_ratio||0)">
        <template #default="{ row }">{{ N(row.excess_sharpe_ratio || 0).toFixed(2) }}</template>
      </el-table-column>
      <el-table-column prop="trade_count" label="交易数" width="70" align="right" sortable />
      <el-table-column prop="elapsed" label="回测耗时" width="90" align="right" show-overflow-tooltip />
      <el-table-column prop="completed_at" label="完成时间" width="160" sortable />
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
import { DataAnalysis } from '@element-plus/icons-vue'
import { getPortfolioBacktestList, getStrategyCodeList } from '@/api/stock'

const router = useRouter()
const list = ref<any[]>([])
const strategies = ref<any[]>([])
const loading = ref(false)
const filterStrategyId = ref(0)
const selectedRows = ref<any[]>([])
const tableRef = ref()

const N = Number
function formatCash(v: number) {
  return v >= 10000 ? (v / 10000).toFixed(0) + '万' : v.toFixed(0)
}
function fmtRet(v: number | undefined) {
  if (v == null) return '--'
  return `${v >= 0 ? '+' : ''}${N(v).toFixed(2)}%`
}
function retCls(v: number | undefined) {
  if (v == null || v === 0) return ''
  return v > 0 ? 'val-red' : 'val-green'
}

function onSelectionChange(rows: any[]) {
  selectedRows.value = rows
}

function goCompare() {
  if (selectedRows.value.length < 2) return
  const ids = selectedRows.value.map((r: any) => r.id).join(',')
  router.push({ path: '/algo/backtest-compare', query: { ids } })
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
.header-left { display: flex; align-items: center; gap: 12px; }
.header-left h2 { margin: 0; }
.header-right { display: flex; align-items: center; gap: 12px; }
.count-tag { font-variant-numeric: tabular-nums; }
.val-red { color: #f56c6c; font-weight: 600; }
.val-green { color: #67c23a; font-weight: 600; }
</style>
