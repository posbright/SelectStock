<script setup lang="ts">
import { ref, computed, watch, onMounted, onActivated } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getStockData, toggleAttention, getTradeDate } from '@/api/stock'
import { getColumnTooltip, strategyDescriptions } from '@/utils/columnTooltips'
import { buildBacktestDashboardQuery } from '@/utils/backtestDashboardLinks'
import dayjs from 'dayjs'

// 列定义接口
interface ColumnDef {
  value: string       // 字段名
  caption: string     // 中文名
  width: number       // 列宽
  dataType?: string   // 数据类型: 'numeric' | 'bigint' | 'datetime' | 'string'
  headerStyle?: any
  conditionalFormats?: any[]
}

const route = useRoute()
const router = useRouter()

// 表格数据和列定义
const tableData = ref<any[]>([])
const columnDefs = ref<ColumnDef[]>([])
const loading = ref(false)
const selectedDate = ref(dayjs().format('YYYY-MM-DD'))
const totalCount = ref(0)

// 分页
const currentPage = ref(1)
const pageSize = ref(50)

// 表名
const tableName = computed(() => route.meta.tableName as string || 'cn_stock_spot')
const pageTitle = computed(() => route.meta.title as string || '股票数据')
const noDateFilter = computed(() => route.meta.noDateFilter as boolean ?? false)
const isBacktestSummary = computed(() => tableName.value === 'cn_stock_backtest')

// 策略说明（仅策略页面显示）
const strategyDesc = computed(() => {
  const tn = tableName.value
  return strategyDescriptions[tn] || ''
})

// 动态列（排除 date, code, name, cdatetime 这些固定列，并隐藏全为空值的列）
const dynamicColumns = computed(() => {
  const baseCols = columnDefs.value.filter(col => 
    !['date', 'code', 'name', 'cdatetime'].includes(col.value)
  )
  // 如果没有数据行，返回所有列
  if (tableData.value.length === 0) return baseCols
  // 过滤掉所有值都为空/0/null 的列
  return baseCols.filter(col => {
    return tableData.value.some(row => {
      const v = row[col.value]
      return v !== null && v !== undefined && v !== '' && v !== 0
    })
  })
})

// 判断是否有code字段（用于显示关注按钮）
const hasCodeField = computed(() => {
  return columnDefs.value.some(col => col.value === 'code')
})

// 搜索关键词
const searchKeyword = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null

// 搜索变更时重新请求（防抖 500ms）
const handleSearch = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    currentPage.value = 1
    loadData()
  }, 500)
}

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    const params: any = {
      name: tableName.value,
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (selectedDate.value) {
      params.date = selectedDate.value
    }
    if (searchKeyword.value) {
      params.keyword = searchKeyword.value
    }
    const res: any = await getStockData(params)
    // 新的响应格式包含 columns、data 和 total
    if (res && res.columns && res.data) {
      columnDefs.value = res.columns
      tableData.value = Array.isArray(res.data) ? res.data : []
      totalCount.value = res.total ?? tableData.value.length
    } else if (Array.isArray(res)) {
      // 兼容旧格式
      tableData.value = res
      totalCount.value = res.length
    } else {
      tableData.value = []
      totalCount.value = 0
    }
  } catch (error: any) {
    console.error('加载数据失败:', error)
    const errMsg = error?.response?.data?.error || '加载数据失败'
    ElMessage.error(errMsg)
    columnDefs.value = []
    tableData.value = []
    totalCount.value = 0
  } finally {
    loading.value = false
  }
}

// 查看指标详情
const viewIndicators = (row: any) => {
  router.push({
    path: '/indicator/detail',
    query: {
      code: row.code,
      date: row.date || selectedDate.value,
      name: row.name,
      strategy: tableName.value
    }
  })
}

const goBacktestDashboard = (row: any) => {
  router.push({
    path: '/backtest/dashboard',
    query: buildBacktestDashboardQuery(row)
  })
}

const goBacktestTimeline = (row: any) => {
  router.push({
    path: '/backtest/dashboard',
    query: buildBacktestDashboardQuery(row, 'timeline')
  })
}

const goBacktestDetail = (row: any) => {
  router.push({
    path: '/backtest/dashboard',
    query: buildBacktestDashboardQuery(row, 'detail')
  })
}

// 关注/取消关注
const handleAttention = async (row: any) => {
  const isCurrentlyAttention = !!row.cdatetime
  try {
    await toggleAttention({
      code: row.code,
      otype: isCurrentlyAttention ? '1' : '0'
    })
    if (isCurrentlyAttention) {
      row.cdatetime = null
      ElMessage.success('已取消关注')
    } else {
      row.cdatetime = new Date().toISOString()
      ElMessage.success('已添加关注')
    }
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

// 根据列定义获取字段的数据类型
const getFieldDataType = (fieldName: string): string => {
  const col = columnDefs.value.find(c => c.value === fieldName)
  return col?.dataType || 'string'
}

// 格式化大数值为亿/万
const formatLargeNumber = (value: number): string => {
  if (Math.abs(value) >= 100000000) {
    return (value / 100000000).toFixed(2) + '亿'
  } else if (Math.abs(value) >= 10000) {
    return (value / 10000).toFixed(2) + '万'
  }
  return value.toFixed(2)
}

// 不应显示为百分比的字段（虽然名称中含有 rate/ratio）
const nonPercentFields = new Set([
  'volume_ratio',       // 量比，是一个倍数而非百分比
  'per_netcash_operate', // 每股经营现金流
  'equity_multiplier',  // 权益乘数
  'current_ratio',      // 流动比率
  'speed_ratio',        // 速动比率
  'equity_ratio',       // 产权比率
])

// 格式化单元格值
const formatCellValue = (value: any, fieldName: string) => {
  if (value === null || value === undefined) return '-'
  
  const dataType = getFieldDataType(fieldName)
  
  // bigint 类型：大数值字段（成交额、市值、净利润、营业收入、股本等），转换为亿/万
  if (dataType === 'bigint') {
    if (typeof value === 'number') {
      return formatLargeNumber(value)
    }
    return value
  }
  
  // 成交量转换为万
  if (fieldName === 'volume') {
    return typeof value === 'number' ? (value / 10000).toFixed(2) + '万' : value
  }
  
  // 百分比类字段：涨跌幅、换手率、振幅、各类比率/占比/增长率等
  // 但排除量比、流动比率等非百分比字段
  if (!nonPercentFields.has(fieldName)) {
    if (fieldName.includes('rate') || fieldName.includes('ratio') ||
        fieldName === 'amplitude' || fieldName === 'turnoverrate' ||
        fieldName.includes('yield') || fieldName.includes('growthrate') ||
        fieldName === 'sale_gpr' || fieldName === 'sale_npr' ||
        fieldName === 'roe_weight' || fieldName === 'jroa' || fieldName === 'roic' ||
        fieldName === 'zxgxl' || fieldName === 'dtsyl') {
      return typeof value === 'number' ? value.toFixed(2) + '%' : value
    }
  }
  
  // 浮点数保留2位小数
  if (typeof value === 'number' && !Number.isInteger(value)) {
    return value.toFixed(2)
  }
  
  return value
}

// 获取单元格样式类
const getCellClass = (value: any, fieldName: string) => {
  // 涨跌相关字段使用颜色
  if (fieldName === 'change_rate' || fieldName === 'ups_downs' ||
      fieldName.includes('change') || fieldName.includes('ranking_after')) {
    if (typeof value === 'number') {
      if (value > 0) return 'text-up'
      if (value < 0) return 'text-down'
    }
  }
  return ''
}

// 获取列最小宽度（用于自适应撑满表格）
const getColumnWidth = (col: ColumnDef) => {
  // 文本类型列（如详因、原因等 VARCHAR 大字段）给予更大的最小宽度
  if (col.dataType === 'string' && col.width && col.width >= 120) {
    return Math.max(col.width, 200)
  }
  if (col.width && col.width > 0) return col.width
  // 默认宽度
  return 100
}

// 日期变更
const handleDateChange = () => {
  currentPage.value = 1
  loadData()
}

// 分页变更
const handlePageChange = () => {
  loadData()
}

const handleSizeChange = () => {
  currentPage.value = 1
  loadData()
}

// 导出 Excel
const exportExcel = () => {
  ElMessage.info('导出功能开发中...')
}

// 获取行样式类名
const getRowClassName = ({ row }: { row: any }) => {
  return row.cdatetime ? 'attention-row' : ''
}

// 监听路由变化
watch(
  () => route.path,
  () => {
    currentPage.value = 1
    columnDefs.value = []
    lastLoadedPath = route.path
    loadData()
  }
)

// keep-alive 重新激活时，检查路由是否变化并重新加载
let lastLoadedPath = ''
onActivated(() => {
  if (route.path !== lastLoadedPath) {
    currentPage.value = 1
    columnDefs.value = []
    lastLoadedPath = route.path
    loadData()
  }
})

onMounted(async () => {
  // 立即记录当前路径，避免 onActivated 在 await 期间重复加载
  lastLoadedPath = route.path
  // noDateFilter 模式下不设置日期，加载所有日期的数据
  if (noDateFilter.value) {
    selectedDate.value = ''
    loadData()
    return
  }
  // 从服务端获取正确的交易日期，避免使用客户端本地日期导致日期不匹配
  try {
    const dateRes: any = await getTradeDate()
    if (dateRes && dateRes.run_date) {
      // 实时数据表用 run_date_nph（含当日未收盘），非实时表用 run_date（仅已收盘）
      const isRealtime = route.meta.isRealtime as boolean
      selectedDate.value = isRealtime ? dateRes.run_date_nph : dateRes.run_date
    }
  } catch {
    // 获取失败时保持客户端日期作为回退
  }
  loadData()
})
</script>

<template>
  <div class="stock-data-container">
    <!-- 顶部工具栏 -->
    <el-card class="toolbar-card" shadow="never">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-tooltip
            v-if="strategyDesc"
            :content="strategyDesc"
            placement="bottom"
            :show-after="200"
            effect="dark"
          >
            <span class="page-title page-title-with-tip">{{ pageTitle }} ⓘ</span>
          </el-tooltip>
          <span v-else class="page-title">{{ pageTitle }}</span>
          <el-date-picker
            v-if="!noDateFilter"
            v-model="selectedDate"
            type="date"
            placeholder="选择日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            :clearable="false"
            @change="handleDateChange"
          />
          <el-input
            v-model="searchKeyword"
            placeholder="搜索代码/名称"
            clearable
            style="width: 200px"
            @input="handleSearch"
            @clear="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
        <div class="toolbar-right">
          <el-button @click="loadData">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
          <el-button type="primary" @click="exportExcel">
            <el-icon><Download /></el-icon>
            导出
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 数据表格 -->
    <el-card class="table-card" shadow="never">
      <el-table
        v-loading="loading"
        :data="tableData"
        stripe
        border
        height="calc(100vh - 280px)"
        :row-class-name="getRowClassName"
      >
        <el-table-column type="index" label="#" width="50" fixed="left" />
        
        <!-- 固定列：日期 -->
        <el-table-column prop="date" label="日期" width="110" fixed="left" />
        
        <!-- 固定列：代码（如果有） -->
        <el-table-column v-if="hasCodeField" prop="code" label="代码" width="90" fixed="left">
          <template #default="{ row }">
            <el-link type="primary" @click="viewIndicators(row)">
              {{ row.code }}
            </el-link>
          </template>
        </el-table-column>
        
        <!-- 固定列：名称 -->
        <el-table-column prop="name" label="名称" width="100" fixed="left" />
        
        <!-- 动态列：根据后端返回的列定义动态生成，使用 min-width 自适应撑满表格 -->
        <el-table-column
          v-for="col in dynamicColumns"
          :key="col.value"
          :prop="col.value"
          :label="col.caption"
          :min-width="getColumnWidth(col)"
          :align="col.dataType === 'string' ? 'left' : 'right'"
          :show-overflow-tooltip="true"
        >          <template #header>
            <el-tooltip
              v-if="getColumnTooltip(col.value, tableName)"
              :content="getColumnTooltip(col.value, tableName)"
              placement="top"
              :show-after="300"
              :hide-after="0"
              effect="dark"
              :popper-options="{ modifiers: [{ name: 'computeStyles', options: { adaptive: false } }] }"
            >
              <span class="header-with-tooltip">{{ col.caption }} ⓘ</span>
            </el-tooltip>
            <span v-else>{{ col.caption }}</span>
          </template>          <template #default="{ row }">
            <span :class="getCellClass(row[col.value], col.value)">
              {{ formatCellValue(row[col.value], col.value) }}
            </span>
          </template>
        </el-table-column>
        
        <!-- 固定列：操作 -->
        <el-table-column v-if="hasCodeField || isBacktestSummary" label="操作" width="140" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              v-if="hasCodeField"
              :type="row.cdatetime ? 'warning' : 'primary'"
              size="small"
              text
              @click="handleAttention(row)"
            >
              <el-icon>
                <StarFilled v-if="row.cdatetime" />
                <Star v-else />
              </el-icon>
              {{ row.cdatetime ? '取消' : '关注' }}
            </el-button>

            <el-button
              v-if="isBacktestSummary"
              type="primary"
              size="small"
              text
              @click="goBacktestDashboard(row)"
            >
              看板
            </el-button>

            <el-button
              v-if="isBacktestSummary"
              type="primary"
              size="small"
              text
              @click="goBacktestTimeline(row)"
            >
              时间序列
            </el-button>

            <el-button
              v-if="isBacktestSummary"
              type="primary"
              size="small"
              text
              @click="goBacktestDetail(row)"
            >
              明细
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <span class="total-info">
          共 {{ totalCount }} 条记录
        </span>
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100, 200]"
          :total="totalCount"
          layout="sizes, prev, pager, next, jumper"
          background
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<style lang="scss" scoped>
.stock-data-container {
  height: 100%;
}

.toolbar-card {
  margin-bottom: 16px;
  
  :deep(.el-card__body) {
    padding: 12px 20px;
  }
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  
  .page-title {
    font-size: 16px;
    font-weight: 600;
    color: #303133;
    margin-right: 8px;
  }
  
  .page-title-with-tip {
    cursor: help;
    border-bottom: 1px dashed #909399;
  }
}

.table-card {
  :deep(.el-card__body) {
    padding: 0;
  }
}

.pagination-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-top: 1px solid #ebeef5;
  
  .total-info {
    font-size: 14px;
    color: #909399;
  }
}

.text-up {
  color: #f56c6c;
}

.text-down {
  color: #67c23a;
}

:deep(.attention-row) {
  background-color: #fef0f0 !important;
  
  td {
    font-weight: 500;
  }
}

.header-with-tooltip {
  cursor: help;
  border-bottom: 1px dashed #909399;
}
</style>
