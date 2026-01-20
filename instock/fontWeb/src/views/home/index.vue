<script setup lang="ts">
import { ref, onMounted } from 'vue'

const features = ref([
  {
    icon: 'Monitor',
    title: '综合选股',
    desc: '支持股票范围、基本面、技术面、消息面等200多个信息栏目进行自由组合选股'
  },
  {
    icon: 'Document',
    title: '股票每日数据',
    desc: '每日股票数据、资金流向、分红配送、龙虎榜、大宗交易等关键数据'
  },
  {
    icon: 'TrendCharts',
    title: '技术指标计算',
    desc: '基于talib、pandas计算32种技术指标，计算高效准确，与同花顺结果一致'
  },
  {
    icon: 'PriceTag',
    title: 'K线形态识别',
    desc: '精准识别61种K线形态，支持用户自选形态识别'
  },
  {
    icon: 'Aim',
    title: '策略选股',
    desc: '内置放量上涨、停机坪、回踩年线、突破平台等11种选股策略'
  },
  {
    icon: 'DataAnalysis',
    title: '选股验证',
    desc: '对指标、策略等选出的股票进行回测，验证策略的成功率'
  }
])

const stats = ref([
  { label: '技术指标', value: 32 },
  { label: 'K线形态', value: 61 },
  { label: '选股策略', value: 11 },
  { label: '信息栏目', value: 200 }
])
</script>

<template>
  <div class="home-container">
    <!-- 欢迎横幅 -->
    <el-card class="welcome-card" shadow="hover">
      <div class="welcome-content">
        <div class="welcome-text">
          <h1>InStock 股票系统</h1>
          <p>
            量化投资的好帮手 - 抓取每日股票、ETF关键数据，计算股票技术指标、筹码分布，
            识别K线各种形态，综合选股，内置多种选股策略，支持选股验证回测。
          </p>
          <div class="welcome-actions">
            <el-button type="primary" size="large" @click="$router.push('/stock/selection')">
              <el-icon><Search /></el-icon>
              开始选股
            </el-button>
            <el-button size="large" @click="$router.push('/basic/spot')">
              <el-icon><Document /></el-icon>
              查看数据
            </el-button>
          </div>
        </div>
        <div class="welcome-stats">
          <div v-for="stat in stats" :key="stat.label" class="stat-item">
            <div class="stat-value">{{ stat.value }}+</div>
            <div class="stat-label">{{ stat.label }}</div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 功能介绍 -->
    <div class="section-title">
      <el-icon><Grid /></el-icon>
      <span>功能介绍</span>
    </div>
    
    <el-row :gutter="20">
      <el-col v-for="feature in features" :key="feature.title" :xs="24" :sm="12" :md="8">
        <el-card class="feature-card" shadow="hover">
          <div class="feature-icon">
            <el-icon size="32">
              <component :is="feature.icon" />
            </el-icon>
          </div>
          <h3>{{ feature.title }}</h3>
          <p>{{ feature.desc }}</p>
        </el-card>
      </el-col>
    </el-row>

    <!-- 快速入口 -->
    <div class="section-title">
      <el-icon><Promotion /></el-icon>
      <span>快速入口</span>
    </div>
    
    <el-row :gutter="20">
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="quick-link" shadow="hover" @click="$router.push('/stock/selection')">
          <el-icon size="40" color="#409eff"><Monitor /></el-icon>
          <span>综合选股</span>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="quick-link" shadow="hover" @click="$router.push('/basic/spot')">
          <el-icon size="40" color="#67c23a"><Document /></el-icon>
          <span>每日股票数据</span>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="quick-link" shadow="hover" @click="$router.push('/indicator/list')">
          <el-icon size="40" color="#e6a23c"><TrendCharts /></el-icon>
          <span>股票指标</span>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="quick-link" shadow="hover" @click="$router.push('/strategy/enter')">
          <el-icon size="40" color="#f56c6c"><Aim /></el-icon>
          <span>策略选股</span>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style lang="scss" scoped>
.home-container {
  max-width: 1400px;
  margin: 0 auto;
}

.welcome-card {
  margin-bottom: 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  
  :deep(.el-card__body) {
    padding: 30px 40px;
  }
}

.welcome-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 30px;
}

.welcome-text {
  flex: 1;
  min-width: 300px;
  color: #fff;
  
  h1 {
    font-size: 32px;
    margin-bottom: 16px;
  }
  
  p {
    font-size: 16px;
    line-height: 1.8;
    opacity: 0.9;
    margin-bottom: 24px;
  }
}

.welcome-actions {
  display: flex;
  gap: 12px;
}

.welcome-stats {
  display: flex;
  gap: 40px;
  
  .stat-item {
    text-align: center;
    color: #fff;
    
    .stat-value {
      font-size: 36px;
      font-weight: 600;
    }
    
    .stat-label {
      font-size: 14px;
      opacity: 0.8;
      margin-top: 4px;
    }
  }
}

.section-title {
  display: flex;
  align-items: center;
  font-size: 18px;
  font-weight: 600;
  margin: 24px 0 16px;
  color: #303133;
  
  .el-icon {
    margin-right: 8px;
    color: #409eff;
  }
}

.feature-card {
  margin-bottom: 20px;
  text-align: center;
  cursor: pointer;
  transition: transform 0.3s;
  
  &:hover {
    transform: translateY(-5px);
  }
  
  .feature-icon {
    width: 64px;
    height: 64px;
    margin: 0 auto 16px;
    background: linear-gradient(135deg, #409eff 0%, #67c23a 100%);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
  }
  
  h3 {
    font-size: 16px;
    color: #303133;
    margin-bottom: 8px;
  }
  
  p {
    font-size: 14px;
    color: #909399;
    line-height: 1.6;
  }
}

.quick-link {
  margin-bottom: 20px;
  cursor: pointer;
  transition: transform 0.3s;
  
  &:hover {
    transform: translateY(-5px);
  }
  
  :deep(.el-card__body) {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 30px;
    
    span {
      margin-top: 12px;
      font-size: 15px;
      color: #606266;
    }
  }
}

@media (max-width: 768px) {
  .welcome-stats {
    width: 100%;
    justify-content: space-around;
  }
}
</style>
