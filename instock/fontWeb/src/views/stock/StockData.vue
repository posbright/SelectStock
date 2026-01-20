<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getStockData, toggleAttention } from '@/api/stock'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()

// 表格数据
const tableData = ref<any[]>([])
const loading = ref(false)
const selectedDate = ref(dayjs().format('YYYY-MM-DD'))

// 分页
const currentPage = ref(1)
const pageSize = ref(50)
const total = computed(() => tableData.value.length)

// 当前页数据（基于过滤后的数据）
const pagedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredData.value.slice(start, end)
})

// 表名
const tableName = computed(() => route.meta.tableName as string || 'cn_stock_spot')
const pageTitle = computed(() => route.meta.title as string || '股票数据')

// 搜索关键词
const searchKeyword = ref('')

// 过滤后的数据
const filteredData = computed(() => {
  if (!searchKeyword.value) return tableData.value
  const keyword = searchKeyword.value.toLowerCase()
  return tableData.value.filter((item: any) => {
    return (
      item.code?.toLowerCase().includes(keyword) ||
      item.name?.toLowerCase().includes(keyword)
    )
  })
})

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    const res = await getStockData({
      name: tableName.value,
      date: selectedDate.value
    })
    tableData.value = Array.isArray(res) ? res : []
  } catch (error) {
    console.error('加载数据失败:', error)
    ElMessage.error('加载数据失败')
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
      name: row.name
    }
  })
}

// 关注/取消关注
const handleAttention = async (row: any) => {
  const isCurrentlyAttention = !!row.cdatetime  // 当前是否已关注
  try {
    await toggleAttention({
      code: row.code,
      otype: isCurrentlyAttention ? '1' : '0'  // 1: 取消关注, 0: 添加关注
    })
    // 更新 cdatetime 字段来反映关注状态
    if (isCurrentlyAttention) {
      row.cdatetime = null  // 取消关注
      ElMessage.success('已取消关注')
    } else {
      row.cdatetime = new Date().toISOString()  // 添加关注，设置当前时间
      ElMessage.success('已添加关注')
    }
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

// 格式化涨跌幅
const formatPercent = (value: number) => {
  if (value === null || value === undefined) return '-'
  const formatted = (value * 100).toFixed(2)
  return value >= 0 ? `+${formatted}%` : `${formatted}%`
}

// 获取涨跌样式
const getChangeClass = (value: number) => {
  if (value > 0) return 'text-up'
  if (value < 0) return 'text-down'
  return ''
}

// 日期变更
const handleDateChange = () => {
  currentPage.value = 1
  loadData()
}

// 导出 Excel
const exportExcel = () => {
  ElMessage.info('导出功能开发中...')
}

// 监听路由变化
watch(
  () => route.path,
  () => {
    currentPage.value = 1
    loadData()
  }
)

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="stock-data-container">
    <!-- 顶部工具栏 -->
    <el-card class="toolbar-card" shadow="never">
      <div class="toolbar">
        <div class="toolbar-left">
          <span class="page-title">{{ pageTitle }}</span>
          <el-date-picker
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
        :data="pagedData"
        stripe
        border
        height="calc(100vh - 280px)"
        :row-class-name="({ row }) => row.cdatetime ? 'attention-row' : ''"
      >
        <el-table-column type="index" label="#" width="50" fixed="left" />
        
        <el-table-column prop="date" label="日期" width="110" fixed="left" />
        
        <el-table-column prop="code" label="代码" width="90" fixed="left">
          <template #default="{ row }">
            <el-link type="primary" @click="viewIndicators(row)">
              {{ row.code }}
            </el-link>
          </template>
        </el-table-column>
        
        <el-table-column prop="name" label="名称" width="100" fixed="left" />
        
        <el-table-column prop="new_price" label="最新价" width="90" align="right">
          <template #default="{ row }">
            <span :class="getChangeClass(row.change_rate)">
              {{ row.new_price?.toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        
        <el-table-column prop="change_rate" label="涨跌幅" width="100" align="right">
          <template #default="{ row }">
            <span :class="getChangeClass(row.change_rate)">
              {{ formatPercent(row.change_rate) }}
            </span>
          </template>
        </el-table-column>
        
        <el-table-column prop="change_amount" label="涨跌额" width="90" align="right">
          <template #default="{ row }">
            <span :class="getChangeClass(row.change_amount)">
              {{ row.change_amount?.toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        
        <el-table-column prop="volume" label="成交量" width="120" align="right">
          <template #default="{ row }">
            {{ row.volume ? (row.volume / 10000).toFixed(2) + '万' : '-' }}
          </template>
        </el-table-column>
        
        <el-table-column prop="deal_amount" label="成交额" width="120" align="right">
          <template #default="{ row }">
            {{ row.deal_amount ? (row.deal_amount / 100000000).toFixed(2) + '亿' : '-' }}
          </template>
        </el-table-column>
        
        <el-table-column prop="amplitude" label="振幅" width="90" align="right">
          <template #default="{ row }">
            {{ row.amplitude ? (row.amplitude * 100).toFixed(2) + '%' : '-' }}
          </template>
        </el-table-column>
        
        <el-table-column prop="high" label="最高价" width="90" align="right" />
        <el-table-column prop="low" label="最低价" width="90" align="right" />
        <el-table-column prop="open" label="开盘价" width="90" align="right" />
        <el-table-column prop="close" label="收盘价" width="90" align="right" />
        
        <el-table-column prop="turnover" label="换手率" width="90" align="right">
          <template #default="{ row }">
            {{ row.turnover ? (row.turnover * 100).toFixed(2) + '%' : '-' }}
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="100" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
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
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <span class="total-info">
          共 {{ filteredData.length }} 条记录
        </span>
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100, 200]"
          :total="filteredData.length"
          layout="sizes, prev, pager, next, jumper"
          background
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
</style>
