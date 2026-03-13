<template>
  <div class="algo-list">
    <!-- 顶部工具栏（仿聚宽） -->
    <div class="toolbar">
      <el-dropdown @command="onCreateStrategy" trigger="click">
        <el-button type="primary">+ 新建策略</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="stock">股票策略</el-dropdown-item>
            <el-dropdown-item command="multi_factor">多因子策略</el-dropdown-item>
            <el-dropdown-item command="portfolio">组合策略</el-dropdown-item>
            <el-dropdown-item command="blank">空白模版</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <el-button @click="onCreateFolder">
        <el-icon><FolderAdd /></el-icon> 新建文件夹
      </el-button>

      <el-button :disabled="selectedIds.length === 0" @click="onRenameSelected">
        重命名
      </el-button>

      <el-dropdown :disabled="selectedIds.length === 0" @command="onMoveToFolder" trigger="click">
        <el-button :disabled="selectedIds.length === 0">移动到</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item :command="0">根目录</el-dropdown-item>
            <el-dropdown-item v-for="f in folders" :key="f.id" :command="f.id">
              {{ f.name }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <el-popconfirm title="确定删除选中的策略？" @confirm="onBatchDelete"
                     :disabled="selectedIds.length === 0">
        <template #reference>
          <el-button :disabled="selectedIds.length === 0" type="danger" plain>
            <el-icon><Delete /></el-icon> 删除
          </el-button>
        </template>
      </el-popconfirm>
    </div>

    <!-- 策略表格（仿聚宽表格布局） -->
    <el-table :data="tableData" v-loading="loading" @selection-change="onSelectionChange"
              stripe row-key="rowKey" style="width: 100%;" size="default"
              :default-expand-all="true">
      <el-table-column type="selection" width="40" :selectable="isSelectable" />

      <!-- 图标 + 名称 -->
      <el-table-column label="" min-width="280">
        <template #default="{ row }">
          <div class="name-cell" @click="onRowClick(row)">
            <el-icon :size="18" class="row-icon" v-if="row.type === 'folder'" color="#e6a23c">
              <Folder />
            </el-icon>
            <el-icon :size="18" class="row-icon" v-else color="#409eff">
              <Document />
            </el-icon>
            <span class="name-text">{{ row.name }}</span>
          </div>
        </template>
      </el-table-column>

      <!-- 分类 -->
      <el-table-column label="分类" width="100" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.type === 'strategy'" size="small" type="info" effect="plain">
            {{ categoryLabel(row.category) }}
          </el-tag>
        </template>
      </el-table-column>

      <!-- 最后修改时间 -->
      <el-table-column label="最后修改时间" width="180" align="center">
        <template #default="{ row }">
          {{ row.updated_at || row.created_at || '' }}
        </template>
      </el-table-column>

      <!-- 历史编译运行 -->
      <el-table-column label="历史编译运行" width="120" align="center">
        <template #default="{ row }">
          <span v-if="row.type === 'strategy'">{{ row.compile_count || 0 }}</span>
        </template>
      </el-table-column>

      <!-- 历史回测 -->
      <el-table-column label="历史回测" width="100" align="center">
        <template #default="{ row }">
          <span v-if="row.type === 'strategy'">{{ row.backtest_count || 0 }}</span>
        </template>
      </el-table-column>
    </el-table>

    <!-- 空状态 -->
    <el-empty v-if="!loading && tableData.length === 0"
              description="还没有策略，点击「新建策略」或导入示例策略">
      <div style="display: flex; gap: 12px;">
        <el-button type="primary" @click="onCreateStrategy('stock')">新建股票策略</el-button>
        <el-button @click="seedTemplateStrategies">导入示例策略</el-button>
      </div>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Folder, FolderAdd, Document, Delete } from '@element-plus/icons-vue'
import {
  getStrategyCodeList, saveStrategyCode,
  createFolder, renameStrategy, renameFolder, moveStrategy,
  batchDeleteStrategy, getStrategyTemplates,
} from '@/api/stock'

const router = useRouter()
const strategies = ref<any[]>([])
const folders = ref<any[]>([])
const loading = ref(false)
const selectedRows = ref<any[]>([])

const CATEGORY_MAP: Record<string, string> = {
  stock: 'Code', multi_factor: 'Factor', portfolio: 'Portfolio', blank: 'Code'
}

const CATEGORY_TEMPLATES: Record<string, string> = {
  stock: `# 股票策略
def initialize(context):
    context.security = '000001'

def handle_data(context, data):
    security = context.security
    price = data[security].close
    ma5 = history(security, 5, 'close')
    if len(ma5) < 5:
        return
    ma_val = ma5.mean()
    if price > ma_val * 1.01 and security not in context.portfolio.positions:
        order_value(security, context.portfolio.available_cash * 0.9)
        log.info("买入 " + security)
    elif price < ma_val * 0.99 and security in context.portfolio.positions:
        order_target(security, 0)
        log.info("卖出 " + security)
`,
  multi_factor: `# 多因子策略
def initialize(context):
    context.stocks = ['600519', '000858', '601318', '600036', '300750']
    context.rebalance_days = 0

def handle_data(context, data):
    context.rebalance_days += 1
    if context.rebalance_days % 20 != 1:
        return
    target = context.portfolio.total_value / len(context.stocks)
    for code in context.stocks:
        order_target_value(code, target)
`,
  portfolio: `# 组合策略
def initialize(context):
    context.stocks = ['000001', '600519', '601318']

def handle_data(context, data):
    momentum = {}
    for code in context.stocks:
        h = history(code, 20, 'close')
        if len(h) >= 20 and h.iloc[0] > 0:
            momentum[code] = h.iloc[-1] / h.iloc[0] - 1
    if not momentum:
        return
    best = max(momentum, key=momentum.get)
    for code in list(context.portfolio.positions.keys()):
        if code != best:
            order_target(code, 0)
    if best not in context.portfolio.positions:
        order_value(best, context.portfolio.available_cash * 0.9)
`,
  blank: `def initialize(context):
    pass

def handle_data(context, data):
    pass
`,
}

const selectedIds = computed(() =>
  selectedRows.value.filter(r => r.type === 'strategy').map(r => r.id)
)

const tableData = computed(() => {
  const result: any[] = []
  // 先显示文件夹
  for (const f of folders.value) {
    result.push({ ...f, rowKey: `folder-${f.id}` })
  }
  // 再显示策略
  for (const s of strategies.value) {
    result.push({ ...s, rowKey: `strategy-${s.id}` })
  }
  return result
})

function categoryLabel(cat: string) {
  return CATEGORY_MAP[cat] || 'Code'
}

function isSelectable(row: any) {
  return row.type === 'strategy'
}

function onSelectionChange(rows: any[]) {
  selectedRows.value = rows
}

function onRowClick(row: any) {
  if (row.type === 'folder') {
    // 可以展开/折叠文件夹，暂时跳过
    return
  }
  router.push(`/algo/edit/${row.id}`)
}

async function loadData() {
  loading.value = true
  try {
    const res = await getStrategyCodeList() as any
    // 响应拦截器已 unwrap: res = {code:0, data:{strategies:[], folders:[]}}
    const d = res?.data || res
    if (d?.strategies) {
      strategies.value = d.strategies
      folders.value = d.folders || []
    } else if (Array.isArray(d)) {
      strategies.value = d
      folders.value = []
    }
  } finally {
    loading.value = false
  }
}

async function onCreateStrategy(category: string) {
  const existingCount = strategies.value.length
  const defaultName = `一个简单的策略-${existingCount + 1}`

  try {
    const res = await saveStrategyCode({
      name: defaultName,
      code: CATEGORY_TEMPLATES[category] || CATEGORY_TEMPLATES.blank,
      category,
    }) as any
    const rCode = res?.code ?? res?.data?.code
    if (rCode === 0) {
      ElMessage.success('策略已创建')
      await loadData()
    } else {
      ElMessage.error(res?.msg || '创建失败')
    }
  } catch (e) {
    ElMessage.error('创建失败')
  }
}
async function seedTemplateStrategies() {
  // 从后端获取内置模板，批量创建到策略列表中
  try {
    const res = await getStrategyTemplates() as any
    const templates = res?.data || res
    if (!Array.isArray(templates) || templates.length === 0) {
      // 兼容两种返回格式: {code:0, data:[...]} 或直接 [...]
      if (res?.code === 0 && Array.isArray(res.data)) {
        // 已在上面处理
      } else {
        ElMessage.warning('无可用模板')
        return
      }
    }
    const list = Array.isArray(templates) ? templates : (res?.data || [])
    let created = 0
    for (const t of list) {
      const r = await saveStrategyCode({
        name: t.name,
        code: t.code,
        description: t.description || '',
        category: t.category || 'stock',
      }) as any
      const rCode = r?.code ?? r?.data?.code
      if (rCode === 0) created++
    }
    ElMessage.success('已导入 ' + created + ' 个示例策略')
    await loadData()
  } catch (e) {
    console.error('导入模板异常:', e)
    ElMessage.error('导入失败')
  }
}
async function onCreateFolder() {
  const { value: name } = await ElMessageBox.prompt(
    '请输入文件夹名称', '新建文件夹', {
      confirmButtonText: '创建', inputValue: '新文件夹',
      inputPattern: /\S+/, inputErrorMessage: '名称不能为空',
    }).catch(() => ({ value: '' }))
  if (!name) return
  try {
    await createFolder(name)
    ElMessage.success('文件夹已创建')
    loadData()
  } catch (e) {
    ElMessage.error('创建失败')
  }
}

async function onRenameSelected() {
  // 如果选了一个策略，重命名策略；如果是文件夹行为另处理
  if (selectedRows.value.length !== 1) {
    ElMessage.warning('请选择一个策略进行重命名')
    return
  }
  const item = selectedRows.value[0]
  const { value: name } = await ElMessageBox.prompt(
    '新名称', '重命名', {
      confirmButtonText: '确定', inputValue: item.name,
      inputPattern: /\S+/,
    }).catch(() => ({ value: '' }))
  if (!name) return
  try {
    if (item.type === 'folder') {
      await renameFolder(item.id, name)
    } else {
      await renameStrategy(item.id, name)
    }
    ElMessage.success('已重命名')
    loadData()
  } catch (e) {
    ElMessage.error('重命名失败')
  }
}

async function onMoveToFolder(folderId: number) {
  if (selectedIds.value.length === 0) return
  try {
    await moveStrategy(selectedIds.value, folderId)
    ElMessage.success('已移动')
    loadData()
  } catch (e) {
    ElMessage.error('移动失败')
  }
}

async function onBatchDelete() {
  if (selectedIds.value.length === 0) return
  try {
    await batchDeleteStrategy(selectedIds.value)
    ElMessage.success('已删除')
    loadData()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

onMounted(loadData)
</script>

<style scoped>
.algo-list { padding: 20px; }
.toolbar {
  display: flex; gap: 8px; margin-bottom: 16px;
  padding: 12px 0; border-bottom: 1px solid #ebeef5;
}
.name-cell {
  display: flex; align-items: center; gap: 8px; cursor: pointer;
}
.name-cell:hover .name-text { color: #409eff; }
.row-icon { flex-shrink: 0; }
.name-text {
  color: #303133; font-size: 14px;
  transition: color 0.15s;
}
</style>
