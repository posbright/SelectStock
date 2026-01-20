<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

interface Props {
  isCollapse: boolean
}

const props = defineProps<Props>()
const emit = defineEmits(['toggle'])

const route = useRoute()
const router = useRouter()

// 面包屑导航（过滤掉首页，避免重复显示）
const breadcrumbs = computed(() => {
  const matched = route.matched.filter(item => item.meta?.title && item.meta?.title !== '首页')
  return matched.map(item => ({
    path: item.path,
    title: item.meta?.title as string
  }))
})

// 刷新页面
const handleRefresh = () => {
  router.go(0)
}
</script>

<template>
  <div class="navbar">
    <div class="navbar-left">
      <!-- 折叠按钮 -->
      <el-icon class="collapse-btn" @click="emit('toggle')">
        <Fold v-if="!isCollapse" />
        <Expand v-else />
      </el-icon>
      
      <!-- 面包屑 -->
      <el-breadcrumb separator="/">
        <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
        <el-breadcrumb-item v-for="item in breadcrumbs" :key="item.path">
          {{ item.title }}
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>
    
    <div class="navbar-right">
      <!-- 刷新按钮 -->
      <el-tooltip content="刷新" placement="bottom">
        <el-icon class="action-btn" @click="handleRefresh">
          <Refresh />
        </el-icon>
      </el-tooltip>
      
      <!-- GitHub 链接 -->
      <el-tooltip content="GitHub" placement="bottom">
        <a 
          href="https://github.com/myhhub/stock" 
          target="_blank" 
          class="action-btn"
        >
          <el-icon><Link /></el-icon>
        </a>
      </el-tooltip>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  padding: 0 20px;
}

.navbar-left {
  display: flex;
  align-items: center;
  
  .collapse-btn {
    font-size: 20px;
    cursor: pointer;
    margin-right: 15px;
    
    &:hover {
      color: #409eff;
    }
  }
}

.navbar-right {
  display: flex;
  align-items: center;
  
  .action-btn {
    font-size: 18px;
    cursor: pointer;
    margin-left: 15px;
    color: #606266;
    
    &:hover {
      color: #409eff;
    }
  }
}
</style>
