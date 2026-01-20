<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

interface Props {
  isCollapse: boolean
}

const props = defineProps<Props>()
const route = useRoute()
const router = useRouter()

// 获取路由菜单
const menuList = computed(() => {
  return router.options.routes.filter(item => item.path !== '/' || item.children?.length)
})

// 当前激活的菜单
const activeMenu = computed(() => {
  return route.path
})

// 判断是否有子菜单
const hasChildren = (item: RouteRecordRaw) => {
  return item.children && item.children.length > 0 && !item.children.every(child => child.meta?.hidden)
}

// 获取可见的子菜单
const getVisibleChildren = (item: RouteRecordRaw) => {
  return item.children?.filter(child => !child.meta?.hidden) || []
}
</script>

<template>
  <div class="sidebar-container">
    <!-- Logo -->
    <div class="sidebar-logo">
      <el-icon size="24" color="#409eff"><TrendCharts /></el-icon>
      <span v-show="!isCollapse" class="logo-title">InStock</span>
    </div>
    
    <!-- 菜单 -->
    <el-scrollbar>
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :collapse-transition="false"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        router
      >
        <template v-for="item in menuList" :key="item.path">
          <!-- 有子菜单 -->
          <el-sub-menu v-if="hasChildren(item)" :index="item.path">
            <template #title>
              <el-icon v-if="item.meta?.icon">
                <component :is="item.meta.icon" />
              </el-icon>
              <span>{{ item.meta?.title }}</span>
            </template>
            
            <el-menu-item
              v-for="child in getVisibleChildren(item)"
              :key="child.path"
              :index="`${item.path}/${child.path}`"
            >
              <el-icon v-if="child.meta?.icon">
                <component :is="child.meta.icon" />
              </el-icon>
              <template #title>{{ child.meta?.title }}</template>
            </el-menu-item>
          </el-sub-menu>
          
          <!-- 无子菜单 -->
          <el-menu-item v-else :index="item.redirect as string || item.path">
            <el-icon v-if="item.meta?.icon">
              <component :is="item.meta.icon" />
            </el-icon>
            <template #title>{{ item.meta?.title || item.children?.[0]?.meta?.title }}</template>
          </el-menu-item>
        </template>
      </el-menu>
    </el-scrollbar>
  </div>
</template>

<style lang="scss" scoped>
.sidebar-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.sidebar-logo {
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #263445;
  
  .logo-title {
    margin-left: 10px;
    color: #fff;
    font-size: 18px;
    font-weight: 600;
  }
}

.el-scrollbar {
  flex: 1;
}

.el-menu {
  border-right: none;
}

:deep(.el-sub-menu__title:hover),
:deep(.el-menu-item:hover) {
  background-color: #263445 !important;
}

:deep(.el-menu-item.is-active) {
  background-color: #263445 !important;
}
</style>
