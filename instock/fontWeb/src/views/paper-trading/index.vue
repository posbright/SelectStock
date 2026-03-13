<template>
  <div class="paper-trading">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <h3>模拟交易</h3>
          <el-button type="primary" @click="showCreateDialog = true" :icon="Plus">创建模拟盘</el-button>
        </div>
      </template>

      <!-- 模拟盘列表 -->
      <el-table :data="paperList" v-loading="loading" stripe>
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
    <el-dialog v-model="showDetail" :title="detailData?.info?.name || '模拟盘详情'" width="80%">
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
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getPaperTradingList, getPaperTradingDetail, createPaperTrading,
  paperTradingAction, runPaperTrading, getStrategyCodeList
} from '@/api/stock'

const paperList = ref<any[]>([])
const strategies = ref<any[]>([])
const loading = ref(false)
const showDetail = ref(false)
const showCreateDialog = ref(false)
const detailData = ref<any>(null)
const detailLoading = ref(false)
const creating = ref(false)
const runningId = ref<number | null>(null)
const createForm = ref({ strategy_id: null as number | null, name: '', initial_cash: 1000000 })

function formatMoney(v: number) {
  return v >= 10000 ? `${(v / 10000).toFixed(2)}万` : v.toFixed(0)
}
function statusType(s: string) {
  return s === 'running' ? 'success' : s === 'paused' ? 'warning' : 'info'
}
function statusLabel(s: string) {
  return s === 'running' ? '运行中' : s === 'paused' ? '已暂停' : '已停止'
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
    const res = await getStrategyCodeList()
    if ((res as any)?.code === 0) strategies.value = (res as any).data
    else if (res.data?.code === 0) strategies.value = res.data.data
  } catch (e) { /* ignore */ }
}

async function viewDetail(id: number) {
  showDetail.value = true
  detailLoading.value = true
  try {
    const res = await getPaperTradingDetail(id)
    if ((res as any)?.code === 0) detailData.value = (res as any).data
    else if (res.data?.code === 0) detailData.value = res.data.data
  } finally {
    detailLoading.value = false
  }
}

async function doAction(id: number, action: 'pause' | 'resume' | 'stop') {
  if (action === 'stop') {
    await ElMessageBox.confirm('确定要停止此模拟盘？停止后无法恢复。', '确认')
  }
  try {
    const res = await paperTradingAction({ id, action })
    if (res.data?.code === 0) {
      ElMessage.success('操作成功')
      loadList()
    }
  } catch (e) { /* cancelled */ }
}

async function doRun(id: number) {
  runningId.value = id
  try {
    const res = await runPaperTrading(id)
    if (res.data?.code === 0) {
      const r = res.data.data
      ElMessage.success(r.message || '执行完成')
      loadList()
    } else {
      ElMessage.error(res.data?.msg || '执行失败')
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
    if (res.data?.code === 0) {
      ElMessage.success('模拟盘创建成功')
      showCreateDialog.value = false
      loadList()
    } else {
      ElMessage.error(res.data?.msg || '创建失败')
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
.text-red { color: #f56c6c; }
.text-green { color: #67c23a; }
.detail-summary {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px;
}
.summary-item {
  text-align: center; padding: 12px; background: #f5f7fa; border-radius: 6px;
}
.summary-item .label { display: block; font-size: 12px; color: #909399; margin-bottom: 4px; }
.summary-item .value { font-size: 18px; font-weight: bold; }
</style>
