<template>
  <div class="algo-list">
    <!-- 顶部工具栏 -->
    <div class="page-header">
      <h2>我的策略</h2>
      <div class="header-actions">
        <el-button type="primary" @click="createStrategy" :icon="Plus">新建策略</el-button>
        <el-dropdown @command="onTemplateSelect" trigger="click">
          <el-button :icon="DocumentCopy">从模板创建</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="t in templates" :key="t.id" :command="t">
                <div>
                  <div style="font-weight: 500;">{{ t.name }}</div>
                  <div style="font-size: 12px; color: #909399;">{{ t.description }}</div>
                </div>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <!-- 策略卡片列表 -->
    <div class="strategy-grid" v-loading="loading">
      <div v-for="s in strategies" :key="s.id" class="strategy-card"
           @click="openStrategy(s.id)">
        <div class="card-body">
          <div class="card-icon">
            <el-icon :size="32" color="#409eff"><Document /></el-icon>
          </div>
          <div class="card-info">
            <div class="card-title">{{ s.name }}</div>
            <div class="card-desc">{{ s.description || '暂无描述' }}</div>
            <div class="card-meta">
              <span>初始资金: {{ formatCash(s.initial_cash) }}</span>
              <span>基准: {{ s.benchmark || '000300' }}</span>
            </div>
            <div class="card-time">
              <span>创建: {{ s.created_at }}</span>
              <span>修改: {{ s.updated_at }}</span>
            </div>
          </div>
        </div>
        <!-- 最新回测结果摘要 -->
        <div class="card-backtest" v-if="s.last_backtest">
          <el-tag :type="s.last_backtest.total_return >= 0 ? 'danger' : 'success'" size="small">
            {{ s.last_backtest.total_return >= 0 ? '+' : '' }}{{ s.last_backtest.total_return.toFixed(2) }}%
          </el-tag>
          <span class="bt-label">夏普 {{ s.last_backtest.sharpe_ratio.toFixed(2) }}</span>
          <span class="bt-label">回撤 {{ s.last_backtest.max_drawdown.toFixed(1) }}%</span>
        </div>
        <!-- 操作按钮 -->
        <div class="card-actions" @click.stop>
          <el-button size="small" type="primary" text @click="openStrategy(s.id)">
            <el-icon><Edit /></el-icon> 编辑
          </el-button>
          <el-button size="small" text @click="cloneStrategy(s)">
            <el-icon><CopyDocument /></el-icon> 克隆
          </el-button>
          <el-button size="small" text @click="renameStrategy(s)">
            <el-icon><EditPen /></el-icon> 重命名
          </el-button>
          <el-popconfirm title="确定删除此策略？" @confirm="deleteStrategy(s.id)">
            <template #reference>
              <el-button size="small" type="danger" text>
                <el-icon><Delete /></el-icon> 删除
              </el-button>
            </template>
          </el-popconfirm>
        </div>
      </div>

      <!-- 空状态 -->
      <el-empty v-if="!loading && strategies.length === 0"
                description="还没有策略，点击「新建策略」开始量化之旅">
        <el-button type="primary" @click="createStrategy">新建策略</el-button>
      </el-empty>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Document, DocumentCopy, Edit, EditPen, CopyDocument, Delete } from '@element-plus/icons-vue'
import {
  getStrategyCodeList, getStrategyTemplates, saveStrategyCode, deleteStrategyCode
} from '@/api/stock'

const router = useRouter()
const strategies = ref<any[]>([])
const templates = ref<any[]>([])
const loading = ref(false)

function formatCash(v: number) {
  if (!v) return '100万'
  return v >= 10000 ? `${(v / 10000).toFixed(0)}万` : `${v}`
}

async function loadData() {
  loading.value = true
  try {
    const [sRes, tRes] = await Promise.all([getStrategyCodeList(), getStrategyTemplates()])
    if (sRes.data?.code === 0) strategies.value = sRes.data.data
    if (tRes.data?.code === 0) templates.value = tRes.data.data
  } finally {
    loading.value = false
  }
}

async function createStrategy() {
  const { value: name } = await ElMessageBox.prompt('请输入策略名称', '新建策略', {
    confirmButtonText: '创建',
    inputValue: '我的策略',
    inputPattern: /\S+/,
    inputErrorMessage: '名称不能为空',
  }).catch(() => ({ value: '' }))
  if (!name) return

  const defaultCode = `def initialize(context):
    # 设置要操作的股票
    context.security = '000001'
    # 设定沪深300作为基准
    # set_benchmark('000300')

def handle_data(context, data):
    security = context.security
    # 获取股票收盘价
    price = data[security].close
    # 获取过去5天的平均价格
    ma5 = history(security, 5, 'close')
    if len(ma5) < 5:
        return
    ma_val = ma5.mean()

    # 上一时间点价格高出5日均线1%则买入
    if price > ma_val * 1.01 and security not in context.portfolio.positions:
        order_value(security, context.portfolio.available_cash * 0.9)
        log.info('买入 ' + security)
    # 价格低于5日均线则卖出
    elif price < ma_val * 0.99 and security in context.portfolio.positions:
        order_target(security, 0)
        log.info('卖出 ' + security)
`
  try {
    const res = await saveStrategyCode({ name, code: defaultCode })
    if (res.data?.code === 0) {
      const id = res.data.data.id
      ElMessage.success('策略已创建')
      router.push(`/algo/edit/${id}`)
    }
  } catch (e) {
    ElMessage.error('创建失败')
  }
}

async function onTemplateSelect(template: any) {
  try {
    const res = await saveStrategyCode({
      name: template.name,
      code: template.code,
      description: template.description,
    })
    if (res.data?.code === 0) {
      ElMessage.success(`已从模板「${template.name}」创建策略`)
      router.push(`/algo/edit/${res.data.data.id}`)
    }
  } catch (e) {
    ElMessage.error('创建失败')
  }
}

function openStrategy(id: number) {
  router.push(`/algo/edit/${id}`)
}

async function cloneStrategy(s: any) {
  try {
    const res = await saveStrategyCode({
      name: s.name + ' (副本)',
      code: '', // will load code from detail
      description: s.description,
    })
    // Need to get code first
    const { getStrategyCodeDetail } = await import('@/api/stock')
    const detail = await getStrategyCodeDetail(s.id)
    if (detail.data?.code === 0) {
      const origCode = detail.data.data.code
      await saveStrategyCode({
        id: res.data?.data?.id,
        name: s.name + ' (副本)',
        code: origCode,
        description: s.description,
        initial_cash: s.initial_cash,
      })
    }
    ElMessage.success('策略已克隆')
    loadData()
  } catch (e) {
    ElMessage.error('克隆失败')
  }
}

async function renameStrategy(s: any) {
  const { value: name } = await ElMessageBox.prompt('新名称', '重命名策略', {
    confirmButtonText: '确定',
    inputValue: s.name,
    inputPattern: /\S+/,
  }).catch(() => ({ value: '' }))
  if (!name) return

  try {
    const { getStrategyCodeDetail } = await import('@/api/stock')
    const detail = await getStrategyCodeDetail(s.id)
    if (detail.data?.code === 0) {
      await saveStrategyCode({ id: s.id, name, code: detail.data.data.code })
      ElMessage.success('已重命名')
      loadData()
    }
  } catch (e) {
    ElMessage.error('重命名失败')
  }
}

async function deleteStrategy(id: number) {
  try {
    await deleteStrategyCode(id)
    ElMessage.success('策略已删除')
    loadData()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

onMounted(loadData)
</script>

<style scoped>
.algo-list { padding: 20px; }
.page-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px;
}
.page-header h2 { margin: 0; font-size: 20px; }
.header-actions { display: flex; gap: 12px; }
.strategy-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 16px;
}
.strategy-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex; flex-direction: column; gap: 12px;
}
.strategy-card:hover {
  border-color: #409eff;
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.15);
}
.card-body { display: flex; gap: 12px; }
.card-icon { flex-shrink: 0; padding-top: 4px; }
.card-info { flex: 1; min-width: 0; }
.card-title { font-size: 16px; font-weight: 600; color: #303133; margin-bottom: 4px; }
.card-desc { font-size: 13px; color: #909399; margin-bottom: 6px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card-meta { font-size: 12px; color: #606266; display: flex; gap: 16px; }
.card-time { font-size: 12px; color: #c0c4cc; display: flex; gap: 16px; margin-top: 4px; }
.card-backtest {
  display: flex; align-items: center; gap: 12px;
  padding: 8px 12px; background: #f5f7fa; border-radius: 4px; font-size: 12px;
}
.bt-label { color: #606266; }
.card-actions {
  display: flex; gap: 4px; border-top: 1px solid #ebeef5; padding-top: 8px;
}
</style>
