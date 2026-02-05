import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/home/index.vue'

// 创建测试用路由
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: { template: '<div>Home</div>' } },
    { path: '/stock/selection', component: { template: '<div>Selection</div>' } },
    { path: '/basic/spot', component: { template: '<div>Spot</div>' } },
    { path: '/indicator/list', component: { template: '<div>Indicator</div>' } },
    { path: '/strategy/enter', component: { template: '<div>Strategy</div>' } }
  ]
})

describe('HomeView 首页组件', () => {
  it('应该正确渲染首页标题', async () => {
    const wrapper = mount(HomeView, {
      global: {
        plugins: [router]
      }
    })

    expect(wrapper.text()).toContain('InStock 股票系统')
  })

  it('应该显示功能介绍卡片', async () => {
    const wrapper = mount(HomeView, {
      global: {
        plugins: [router]
      }
    })

    expect(wrapper.text()).toContain('综合选股')
    expect(wrapper.text()).toContain('股票每日数据')
    expect(wrapper.text()).toContain('技术指标计算')
    expect(wrapper.text()).toContain('K线形态识别')
    expect(wrapper.text()).toContain('策略选股')
    expect(wrapper.text()).toContain('选股验证')
  })

  it('应该显示统计数据', async () => {
    const wrapper = mount(HomeView, {
      global: {
        plugins: [router]
      }
    })

    expect(wrapper.text()).toContain('32')  // 技术指标
    expect(wrapper.text()).toContain('61')  // K线形态
    expect(wrapper.text()).toContain('11')  // 选股策略
    expect(wrapper.text()).toContain('200') // 信息栏目
  })

  it('应该包含快速入口按钮', async () => {
    const wrapper = mount(HomeView, {
      global: {
        plugins: [router]
      }
    })

    const buttons = wrapper.findAll('.el-button')
    expect(buttons.length).toBeGreaterThan(0)
    
    expect(wrapper.text()).toContain('开始选股')
    expect(wrapper.text()).toContain('查看数据')
  })

  it('快速入口卡片应该存在', async () => {
    const wrapper = mount(HomeView, {
      global: {
        plugins: [router]
      }
    })

    expect(wrapper.text()).toContain('每日股票数据')
    expect(wrapper.text()).toContain('股票指标')
  })
})
