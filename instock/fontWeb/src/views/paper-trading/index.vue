<template>
  <div class="paper-trading">
    <!-- ═══════════ 列表视图 ═══════════ -->
    <template v-if="!detailId">
      <div class="page-header">
        <div class="header-left">
          <h2>模拟交易</h2>
          <el-tag type="info" size="small" class="count-tag">{{ paperList.length }} 个策略</el-tag>
        </div>
        <div class="header-right">
          <el-button :disabled="selectedRows.length < 2" @click="goCompare">
            <el-icon><DataAnalysis /></el-icon>对比 ({{ selectedRows.length }})
          </el-button>
          <el-button type="primary" @click="showCreateDialog = true" :icon="Plus">创建模拟盘</el-button>
        </div>
      </div>

      <!-- 聚宽风格表格 -->
      <el-table :data="paperList" v-loading="loading" stripe
                @selection-change="onSelectionChange"
                class="jq-table" header-cell-class-name="jq-header-cell"
                table-layout="auto">
        <el-table-column type="selection" width="40" />
        <el-table-column prop="name" label="名称" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="jq-name-link" @click="viewDetail(row.id)">
              {{ row.name || `模拟盘-${row.id}` }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="strategy_name" label="频率" width="60" align="center">
          <template #default>每天</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="70" align="center">
          <template #default="{ row }">
            <span :class="'jq-status-' + row.status">{{ statusLabel(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="started_at" label="开始时间" width="100" align="center">
          <template #default="{ row }">{{ row.started_at || row.last_run_date || '--' }}</template>
        </el-table-column>
        <el-table-column label="累计收益" width="90" align="center">
          <template #default="{ row }">
            <span :class="retCls(row.profit_rate)">{{ fmtPct(row.profit_rate) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="年化收益" width="90" align="center">
          <template #default="{ row }">
            <span :class="retCls(row.annual_return)">{{ fmtPctDash(row.annual_return) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="今日收益" width="90" align="center">
          <template #default="{ row }">
            <span :class="retCls(row.today_return)">{{ fmtPctDash(row.today_return) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最大回撤" width="90" align="center">
          <template #default="{ row }">
            <span class="val-green">{{ row.max_drawdown ? '-' + row.max_drawdown.toFixed(2) + '%' : '——' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="230" align="center" fixed="right">
          <template #default="{ row }">
            <div class="jq-ops">
              <a class="jq-op" @click="viewDetail(row.id)">详情</a>
              <span class="jq-op-sep">|</span>
              <a class="jq-op" :class="{ 'jq-op-disabled': row.status === 'stopped' }"
                 @click="row.status !== 'stopped' && doAction(row.id, row.status === 'paused' ? 'resume' : 'pause')">
                {{ row.status === 'paused' ? '恢复' : '暂停' }}
              </a>
              <span class="jq-op-sep">|</span>
              <a class="jq-op jq-op-danger" :class="{ 'jq-op-disabled': row.status === 'stopped' }"
                 @click="row.status !== 'stopped' && doAction(row.id, 'stop')">停止</a>
              <span class="jq-op-sep">|</span>
              <a class="jq-op jq-op-primary" :class="{ 'jq-op-disabled': row.status !== 'running' }"
                 @click="row.status === 'running' && doRun(row.id)">
                {{ runningId === row.id ? '执行中...' : '执行' }}
              </a>
              <span class="jq-op-sep">|</span>
              <a class="jq-op jq-op-danger" @click="doDelete(row.id, row.name)">删除</a>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && paperList.length === 0"
                 description="还没有模拟盘，点击「创建模拟盘」开始">
        <el-button type="primary" @click="showCreateDialog = true">创建模拟盘</el-button>
      </el-empty>
    </template>

    <!-- ═══════════ 详情视图（聚宽实盘风格） ═══════════ -->
    <template v-else>
      <div class="detail-page" v-loading="detailLoading">
        <!-- ▸ 顶部标题条 -->
        <div class="jq-detail-header">
          <div class="jq-detail-title">
            <el-button text size="small" @click="goBackToList" class="back-btn">
              <el-icon><ArrowLeft /></el-icon>
            </el-button>
            <span class="jq-title-text">模拟交易</span>
            <span class="jq-title-name">{{ detailData?.info?.name || '' }}</span>
            <el-tag :type="statusType(detailData?.info?.status)" size="small"
                    v-if="detailData?.info?.status" style="margin-left: 8px;">
              {{ statusLabel(detailData?.info?.status) }}
            </el-tag>
          </div>
          <div class="jq-detail-actions" v-if="detailData?.info">
            <el-button size="small" type="primary" v-if="detailData.info.status === 'running'"
                       @click="doRun(detailId!)" :loading="runningId === detailId">
              <el-icon><CaretRight /></el-icon>手动执行
            </el-button>
            <el-dropdown trigger="click" @command="(cmd: string) => doAction(detailId!, cmd as any)">
              <el-button size="small">其他操作 <el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="pause" v-if="detailData.info.status === 'running'">暂停</el-dropdown-item>
                  <el-dropdown-item command="resume" v-if="detailData.info.status === 'paused'">恢复运行</el-dropdown-item>
                  <el-dropdown-item command="stop" v-if="detailData.info.status !== 'stopped'" divided>
                    <span style="color:#f56c6c;">停止</span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>

        <template v-if="detailData">
          <!-- ▸ 顶部指标条（聚宽风格横排） -->
          <div class="jq-metrics-bar">
            <div class="jq-metric-cell">
              <span class="jq-mc-value" :class="retCls(detailData.info.profit_rate)">
                {{ fmtPctDash(detailData.info.profit_rate) }}
              </span>
              <span class="jq-mc-label" :class="retCls(detailData.info.profit_rate)">累计收益</span>
            </div>
            <div class="jq-metric-sep"></div>
            <div class="jq-metric-cell">
              <span class="jq-mc-value" :class="retCls(detailData.info.annual_return)">
                {{ fmtPctDash(detailData.info.annual_return) }}
              </span>
              <span class="jq-mc-label" :class="retCls(detailData.info.annual_return)">年化收益</span>
            </div>
            <div class="jq-metric-sep"></div>
            <div class="jq-metric-cell">
              <span class="jq-mc-value">¥{{ formatMoneyFull(detailData.info.current_value) }}</span>
              <span class="jq-mc-label">总资产</span>
            </div>
            <div class="jq-metric-sep"></div>
            <div class="jq-metric-cell">
              <span class="jq-mc-value">¥{{ formatMoneyFull(detailData.info.current_cash) }}</span>
              <span class="jq-mc-label">可用资金</span>
            </div>
            <div class="jq-metric-sep"></div>
            <div class="jq-metric-cell">
              <span class="jq-mc-value">{{ positionRatio }}%</span>
              <span class="jq-mc-label">仓位占比</span>
            </div>
            <div class="jq-metric-sep"></div>
            <div class="jq-metric-cell">
              <span class="jq-mc-value">{{ detailData.info.trade_count ?? 0 }}</span>
              <span class="jq-mc-label">累计换手</span>
            </div>
            <div class="jq-metric-sep"></div>
            <div class="jq-metric-cell">
              <span class="jq-mc-value val-green">{{ detailData.info.max_drawdown ? '-' + detailData.info.max_drawdown.toFixed(2) + '%' : '——' }}</span>
              <span class="jq-mc-label">最大回撤</span>
            </div>
            <div class="jq-metric-sep"></div>
            <el-popover placement="bottom-end" :width="320" trigger="click">
              <template #reference>
                <div class="jq-metric-cell jq-metric-more">
                  <span class="jq-mc-value">其他指标 <el-icon><InfoFilled /></el-icon></span>
                </div>
              </template>
              <div class="jq-extra-metrics">
                <div class="jq-em-row">
                  <span>初始资金</span><span>¥{{ formatMoneyFull(detailData.info.initial_cash) }}</span>
                </div>
                <div class="jq-em-row">
                  <span>夏普比率</span><span>{{ fmtNum(detailData.info.sharpe_ratio) }}</span>
                </div>
                <div class="jq-em-row">
                  <span>索提诺比率</span><span>{{ fmtNum(detailData.info.sortino_ratio) }}</span>
                </div>
                <div class="jq-em-row">
                  <span>胜率</span><span>{{ detailData.info.win_rate != null ? detailData.info.win_rate.toFixed(1) + '%' : '--' }}</span>
                </div>
                <div class="jq-em-row">
                  <span>盈亏比</span><span>{{ fmtNum(detailData.info.profit_loss_ratio) }}</span>
                </div>
                <div class="jq-em-row">
                  <span>运行天数</span><span>{{ detailData.info.running_days ?? 0 }} 天</span>
                </div>
                <div class="jq-em-row">
                  <span>开始日期</span><span>{{ detailData.info.started_at || '--' }}</span>
                </div>
              </div>
            </el-popover>
          </div>

          <!-- ▸ 左侧Tab + 右侧内容（聚宽侧边栏风格） -->
          <div class="jq-detail-body">
            <el-tabs v-model="sideTab" tab-position="left" class="jq-side-tabs">
              <!-- ──── 概述 ──── -->
              <el-tab-pane name="overview">
                <template #label><el-icon><Document /></el-icon><span>概述</span></template>
                <!-- 历史收益 -->
                <div class="jq-section">
                  <el-tabs v-model="chartTab" class="jq-inner-tabs">
                    <el-tab-pane label="历史收益" name="returns">
                      <div v-if="detailData.nav && detailData.nav.length > 1">
                        <div ref="navChartRef" style="height: 320px; width: 100%;"></div>
                      </div>
                      <div v-else class="jq-empty-chart">未开始，暂无数据</div>
                    </el-tab-pane>
                  </el-tabs>
                </div>

                <!-- 持仓详情 -->
                <div class="jq-section">
                  <div class="jq-section-header">
                    <span class="jq-section-title">持仓详情({{ posHistDate || '--' }})</span>
                    <div class="jq-section-actions">
                      <span class="jq-export-link">导出全部</span>
                      <span class="jq-date-label">历史持仓:</span>
                      <el-date-picker v-model="posHistDate" type="date" size="small"
                                      value-format="YYYY-MM-DD" style="width: 130px;" />
                    </div>
                  </div>
                  <!-- 列可见性切换（聚宽风格） -->
                  <div class="jq-col-filter">
                    <el-checkbox v-for="col in posColumnDefs" :key="col.key" size="small"
                      :model-value="posVisibleCols.includes(col.key)"
                      @change="(v: any) => togglePosCol(col.key, !!v)">
                      {{ col.label }}
                    </el-checkbox>
                  </div>
                  <el-table :data="detailData.positions" size="small" stripe border
                            style="width: 100%;" empty-text="暂无持仓" table-layout="auto">
                    <el-table-column prop="code" label="标的" width="85" />
                    <el-table-column v-if="showPosCol('name')" prop="name" label="名称" width="80" show-overflow-tooltip />
                    <el-table-column v-if="showPosCol('direction')" label="多空" width="60" align="center">
                      <template #default><span style="color: #f56c6c;">做多</span></template>
                    </el-table-column>
                    <el-table-column v-if="showPosCol('amount')" label="数量" width="80" align="right">
                      <template #default="{ row }">{{ Number(row.amount ?? 0).toLocaleString() }}</template>
                    </el-table-column>
                    <el-table-column v-if="showPosCol('available')" label="可用数量" width="80" align="right">
                      <template #default="{ row }">{{ Number(row.amount ?? 0).toLocaleString() }}</template>
                    </el-table-column>
                    <el-table-column v-if="showPosCol('price')" label="现价" width="80" align="right">
                      <template #default="{ row }">{{ (row.price ?? 0).toFixed(2) }}</template>
                    </el-table-column>
                    <el-table-column v-if="showPosCol('value')" label="市值/价值" width="110" align="right">
                      <template #default="{ row }">{{ formatMoneyFull(row.value) }}</template>
                    </el-table-column>
                    <el-table-column v-if="showPosCol('profit')" label="盈亏" width="90" align="right">
                      <template #default="{ row }">
                        <span :class="retCls(row.profit)">{{ fmtMoney(row.profit) }}</span>
                      </template>
                    </el-table-column>
                    <el-table-column v-if="showPosCol('profit_rate')" label="逐笔浮盈" width="100" align="right">
                      <template #default="{ row }">
                        <span :class="retCls(row.profit_rate)">{{ fmtPct(row.profit_rate) }}</span>
                      </template>
                    </el-table-column>
                    <el-table-column v-if="showPosCol('avg_cost')" label="开仓均价" width="90" align="right">
                      <template #default="{ row }">{{ (row.avg_cost ?? 0).toFixed(2) }}</template>
                    </el-table-column>
                    <el-table-column v-if="showPosCol('weight')" label="仓位占比" width="80" align="right">
                      <template #default="{ row }">{{ (row.weight ?? 0).toFixed(1) }}%</template>
                    </el-table-column>
                    <el-table-column v-if="showPosCol('pnl_ratio')" label="盈亏占比" width="80" align="right">
                      <template #default="{ row }">
                        <span :class="retCls(row.profit_rate)">
                          {{ row.profit != null && detailData.info.current_value > 0
                            ? ((row.profit / detailData.info.current_value) * 100).toFixed(2) + '%'
                            : '--' }}
                        </span>
                      </template>
                    </el-table-column>
                  </el-table>
                </div>

                <!-- 下单详情 -->
                <div class="jq-section">
                  <div class="jq-section-header">
                    <span class="jq-section-title">下单详情({{ tradeHistDate || '--' }})</span>
                    <div class="jq-section-actions">
                      <span class="jq-export-link">导出全部</span>
                      <span class="jq-date-label">历史下单:</span>
                      <el-date-picker v-model="tradeHistDate" type="date" size="small"
                                      value-format="YYYY-MM-DD" style="width: 130px;" />
                    </div>
                  </div>
                  <!-- 列可见性切换 -->
                  <div class="jq-col-filter">
                    <el-checkbox v-for="col in tradeColumnDefs" :key="col.key" size="small"
                      :model-value="tradeVisibleCols.includes(col.key)"
                      @change="(v: any) => toggleTradeCol(col.key, !!v)">
                      {{ col.label }}
                    </el-checkbox>
                  </div>
                  <el-table :data="filteredTrades" size="small" stripe border max-height="400"
                            style="width: 100%;" empty-text="暂无交易记录" table-layout="auto">
                    <el-table-column prop="date" label="日期" width="95" />
                    <el-table-column prop="code" label="标的" width="85" />
                    <el-table-column v-if="showTradeCol('name')" prop="name" label="名称" width="80" show-overflow-tooltip />
                    <el-table-column v-if="showTradeCol('direction')" label="交易类型" width="80">
                      <template #default="{ row }">
                        <span :style="{ color: row.direction === 'buy' ? '#f56c6c' : '#67c23a', fontWeight: 600 }">
                          {{ row.direction === 'buy' ? '买入' : '卖出' }}
                        </span>
                      </template>
                    </el-table-column>
                    <el-table-column v-if="showTradeCol('order_type')" label="下单类型" width="80" align="center">
                      <template #default>市价单</template>
                    </el-table-column>
                    <el-table-column v-if="showTradeCol('amount')" label="成交数量" width="85" align="right">
                      <template #default="{ row }">{{ Number(row.amount ?? 0).toLocaleString() }}</template>
                    </el-table-column>
                    <el-table-column v-if="showTradeCol('price')" label="成交价" width="85" align="right">
                      <template #default="{ row }">{{ (row.price ?? 0).toFixed(2) }}</template>
                    </el-table-column>
                    <el-table-column v-if="showTradeCol('value')" label="成交额" width="105" align="right">
                      <template #default="{ row }">{{ formatMoneyFull(row.value) }}</template>
                    </el-table-column>
                    <el-table-column v-if="showTradeCol('commission')" label="手续费" width="80" align="right">
                      <template #default="{ row }">{{ ((row.commission ?? 0) + (row.tax ?? 0)).toFixed(2) }}</template>
                    </el-table-column>
                    <el-table-column v-if="showTradeCol('status')" label="状态" width="80" align="center">
                      <template #default><el-tag size="small" type="success">全部成交</el-tag></template>
                    </el-table-column>
                  </el-table>
                </div>
              </el-tab-pane>

              <!-- ──── 统计 ──── -->
              <el-tab-pane name="stats">
                <template #label><el-icon><TrendCharts /></el-icon><span>统计</span></template>
                <div class="jq-section">
                  <div class="jq-stats-grid">
                    <div class="jq-stat-card" v-for="m in statMetrics" :key="m.key">
                      <span class="jq-stat-label">{{ m.label }}</span>
                      <span class="jq-stat-value" :class="m.cls ? m.cls(detailData.info[m.key]) : ''">
                        {{ m.fmt(detailData.info[m.key]) }}
                      </span>
                    </div>
                  </div>
                </div>
              </el-tab-pane>

              <!-- ──── 日志 ──── -->
              <el-tab-pane name="log">
                <template #label><el-icon><Notebook /></el-icon><span>日志</span></template>
                <div class="jq-section">
                  <div class="jq-log-area">
                    <div class="jq-log-entry" v-for="(t, i) in (detailData.trades || []).slice(0, 50)" :key="i">
                      <span class="jq-log-date">{{ t.date }}</span>
                      <span :style="{ color: t.direction === 'buy' ? '#f56c6c' : '#67c23a' }">
                        {{ t.direction === 'buy' ? '买入' : '卖出' }}
                      </span>
                      <span>{{ t.code }} {{ t.name || '' }}</span>
                      <span>{{ Number(t.amount ?? 0).toLocaleString() }}股</span>
                      <span>@{{ (t.price ?? 0).toFixed(2) }}</span>
                    </div>
                    <div v-if="!detailData.trades?.length" class="jq-log-empty">暂无运行日志</div>
                  </div>
                </div>
              </el-tab-pane>

              <!-- ──── 代码 ──── -->
              <el-tab-pane name="code">
                <template #label><span class="code-tab-icon">&lt;/&gt;</span><span>代码</span></template>
                <div class="jq-section" style="text-align: center; padding: 60px 20px;">
                  <el-icon :size="48" color="#c0c4cc"><EditPen /></el-icon>
                  <p style="color: #909399; margin-top: 12px;">
                    请在 <router-link to="/algo/list" style="color: #409eff;">策略列表</router-link> 中查看和编辑策略代码
                  </p>
                </div>
              </el-tab-pane>

              <!-- ──── 设置 ──── -->
              <el-tab-pane name="settings">
                <template #label><el-icon><Setting /></el-icon><span>设置</span></template>
                <div class="jq-section">
                  <div class="jq-settings">
                    <div class="jq-set-row">
                      <span class="jq-set-label">模拟盘名称</span>
                      <span class="jq-set-value">{{ detailData.info.name }}</span>
                    </div>
                    <div class="jq-set-row">
                      <span class="jq-set-label">策略名称</span>
                      <span class="jq-set-value">{{ detailData.info.strategy_name }}</span>
                    </div>
                    <div class="jq-set-row">
                      <span class="jq-set-label">初始资金</span>
                      <span class="jq-set-value">¥{{ formatMoneyFull(detailData.info.initial_cash) }}</span>
                    </div>
                    <div class="jq-set-row">
                      <span class="jq-set-label">运行频率</span>
                      <span class="jq-set-value">每天</span>
                    </div>
                    <div class="jq-set-row">
                      <span class="jq-set-label">开始日期</span>
                      <span class="jq-set-value">{{ detailData.info.started_at || '--' }}</span>
                    </div>
                    <div class="jq-set-row">
                      <span class="jq-set-label">最后运行</span>
                      <span class="jq-set-value">{{ detailData.info.last_run_date || '--' }}</span>
                    </div>
                    <div class="jq-set-row">
                      <span class="jq-set-label">当前状态</span>
                      <span class="jq-set-value">
                        <el-tag :type="statusType(detailData.info.status)" size="small">
                          {{ statusLabel(detailData.info.status) }}
                        </el-tag>
                      </span>
                    </div>
                  </div>
                </div>
              </el-tab-pane>
            </el-tabs>
          </div>
        </template>
      </div>
    </template>

    <!-- ═══════════ 对比对话框 ═══════════ -->
    <el-dialog v-model="showCompare" title="模拟盘对比" width="90%">
      <div v-loading="compareLoading">
        <div v-if="compareData.length">
          <h4>收益走势对比</h4>
          <div ref="compareChartRef" style="height: 320px; width: 100%;"></div>
          <h4 style="margin-top: 16px;">绩效指标对比</h4>
          <el-table :data="compareMetricRows" size="small" stripe border>
            <el-table-column prop="label" label="指标" width="120" fixed />
            <el-table-column v-for="p in compareData" :key="p.id" :label="p.name || p.strategy_name" align="right">
              <template #default="{ row }">
                <span :class="row.cls ? row.cls(row.values[p.id]) : ''">{{ row.fmt(row.values[p.id]) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <el-empty v-else description="暂无对比数据" />
      </div>
    </el-dialog>

    <!-- ═══════════ 创建对话框 ═══════════ -->
    <el-dialog v-model="showCreateDialog" title="创建模拟盘" width="500px">
      <el-form label-width="100px">
        <el-form-item label="策略">
          <el-select v-model="createForm.strategy_id" placeholder="选择已保存的策略" style="width: 100%;"
                     filterable>
            <el-option v-for="s in strategies" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="createForm.name" placeholder="模拟盘名称（可选）" />
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
import { ref, onMounted, onUnmounted, nextTick, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus, DataAnalysis, ArrowLeft, CaretRight, ArrowDown,
  InfoFilled, Document, TrendCharts, Notebook, Setting, EditPen,
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import {
  getPaperTradingList, getPaperTradingDetail, createPaperTrading,
  paperTradingAction, runPaperTrading, getStrategyCodeList, getPaperCompare,
  deletePaperTrading,
} from '@/api/stock'
import request from '@/api/request'

const route = useRoute()
const router = useRouter()

// ── 详情ID：基于路由query，侧栏导航点击会清除query回到列表 ──
const detailId = computed(() => {
  const id = route.query.id
  return id ? Number(id) : null
})

const paperList = ref<any[]>([])
const strategies = ref<any[]>([])
const loading = ref(false)
const showCreateDialog = ref(false)
const showCompare = ref(false)
const detailData = ref<any>(null)
const detailLoading = ref(false)
const sideTab = ref('overview')
const chartTab = ref('returns')
const compareData = ref<any[]>([])
const compareLoading = ref(false)
const creating = ref(false)
const runningId = ref<number | null>(null)
const selectedRows = ref<any[]>([])
const createForm = ref({ strategy_id: null as number | null, name: '', initial_cash: 1000000 })
const navChartRef = ref<HTMLElement | null>(null)
const compareChartRef = ref<HTMLElement | null>(null)
let navChart: echarts.ECharts | null = null

// ── 列可见性（聚宽风格列筛选） ──
const posColumnDefs = [
  { key: 'name', label: '名称' },
  { key: 'direction', label: '多空' },
  { key: 'amount', label: '数量' },
  { key: 'available', label: '可用数量' },
  { key: 'price', label: '现价' },
  { key: 'value', label: '市值/价值' },
  { key: 'profit', label: '盈亏' },
  { key: 'profit_rate', label: '逐笔浮盈' },
  { key: 'avg_cost', label: '开仓均价' },
  { key: 'weight', label: '仓位占比' },
  { key: 'pnl_ratio', label: '盈亏占比' },
]
const posVisibleCols = ref(['name', 'amount', 'price', 'profit', 'profit_rate', 'avg_cost', 'value', 'weight', 'pnl_ratio'])

const tradeColumnDefs = [
  { key: 'name', label: '名称' },
  { key: 'direction', label: '交易类型' },
  { key: 'order_type', label: '下单类型' },
  { key: 'amount', label: '成交数量' },
  { key: 'price', label: '成交价' },
  { key: 'value', label: '成交额' },
  { key: 'commission', label: '手续费' },
  { key: 'status', label: '状态' },
]
const tradeVisibleCols = ref(['direction', 'amount', 'price', 'value', 'commission'])

function showPosCol(key: string) { return posVisibleCols.value.includes(key) }
function showTradeCol(key: string) { return tradeVisibleCols.value.includes(key) }
function togglePosCol(key: string, checked: boolean) {
  if (checked && !posVisibleCols.value.includes(key)) posVisibleCols.value = [...posVisibleCols.value, key]
  else if (!checked) posVisibleCols.value = posVisibleCols.value.filter(k => k !== key)
}
function toggleTradeCol(key: string, checked: boolean) {
  if (checked && !tradeVisibleCols.value.includes(key)) tradeVisibleCols.value = [...tradeVisibleCols.value, key]
  else if (!checked) tradeVisibleCols.value = tradeVisibleCols.value.filter(k => k !== key)
}

// ── 历史日期选择 ──
const posHistDate = ref('')
const tradeHistDate = ref('')

// ── 格式化工具 ──
function formatMoneyFull(v: number) {
  if (v == null) return '--'
  return Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
function fmtPct(v: number | undefined | null, d = 2) {
  if (v == null) return '--'
  return `${Number(v) >= 0 ? '+' : ''}${Number(v).toFixed(d)}%`
}
function fmtPctDash(v: number | undefined | null, d = 2) {
  if (v == null || v === 0) return '——'
  return `${Number(v) >= 0 ? '+' : ''}${Number(v).toFixed(d)}%`
}
function fmtNum(v: number | undefined | null, d = 2) {
  if (v == null) return '--'
  return Number(v).toFixed(d)
}
function fmtMoney(v: number | undefined | null) {
  if (v == null) return '--'
  const n = Number(v)
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}`
}
function retCls(v: number | undefined | null) {
  if (v == null || v === 0) return ''
  return Number(v) > 0 ? 'val-red' : 'val-green'
}
function statusType(s: string) {
  return s === 'running' ? 'success' : s === 'paused' ? 'warning' : 'info'
}
function statusLabel(s: string) {
  return s === 'running' ? '运行中' : s === 'paused' ? '已暂停' : '已停止'
}

// ── 持仓占比 ──
const positionRatio = computed(() => {
  if (!detailData.value?.info) return '0.00'
  const { current_value, current_cash } = detailData.value.info
  if (!current_value || current_value <= 0) return '0.00'
  const pos = current_value - (current_cash ?? 0)
  return ((pos / current_value) * 100).toFixed(2)
})

// ── 按日期过滤交易（客户端过滤） ──
const filteredTrades = computed(() => {
  const trades = detailData.value?.trades || []
  if (!tradeHistDate.value) return trades
  return trades.filter((t: any) => t.date === tradeHistDate.value)
})

// ── 统计指标 ──
const statMetrics = [
  { key: 'total_return', label: '累计收益', fmt: (v: any) => fmtPctDash(v), cls: (v: any) => retCls(v) },
  { key: 'annual_return', label: '年化收益', fmt: (v: any) => fmtPctDash(v), cls: (v: any) => retCls(v) },
  { key: 'max_drawdown', label: '最大回撤', fmt: (v: any) => v ? '-' + Number(v).toFixed(2) + '%' : '——', cls: () => 'val-green' },
  { key: 'sharpe_ratio', label: '夏普比率', fmt: (v: any) => fmtNum(v), cls: undefined },
  { key: 'sortino_ratio', label: '索提诺比率', fmt: (v: any) => fmtNum(v), cls: undefined },
  { key: 'win_rate', label: '胜率', fmt: (v: any) => v != null ? Number(v).toFixed(1) + '%' : '--', cls: undefined },
  { key: 'profit_loss_ratio', label: '盈亏比', fmt: (v: any) => fmtNum(v), cls: undefined },
  { key: 'trade_count', label: '交易笔数', fmt: (v: any) => String(v || 0), cls: undefined },
  { key: 'running_days', label: '运行天数', fmt: (v: any) => `${v || 0} 天`, cls: undefined },
  { key: 'today_return', label: '今日收益', fmt: (v: any) => fmtPctDash(v), cls: (v: any) => retCls(v) },
]

// ── 对比指标行 ──
const compareMetricRows = computed(() => {
  if (!compareData.value.length) return []
  const rows = [
    { label: '总收益', key: 'total_return', fmt: (v: number) => fmtPct(v), cls: (v: number) => retCls(v) },
    { label: '年化收益', key: 'annual_return', fmt: (v: number) => fmtPct(v), cls: (v: number) => retCls(v) },
    { label: '最大回撤', key: 'max_drawdown', fmt: (v: number) => fmtPct(v), cls: () => 'val-green' },
    { label: '夏普比率', key: 'sharpe_ratio', fmt: (v: number) => fmtNum(v), cls: undefined },
    { label: '索提诺', key: 'sortino_ratio', fmt: (v: number) => fmtNum(v), cls: undefined },
    { label: '胜率', key: 'win_rate', fmt: (v: number) => fmtPct(v, 1), cls: undefined },
    { label: '盈亏比', key: 'profit_loss_ratio', fmt: (v: number) => fmtNum(v), cls: undefined },
    { label: '交易笔数', key: 'trade_count', fmt: (v: number) => String(v || 0), cls: undefined },
  ]
  return rows.map(r => ({
    ...r,
    values: Object.fromEntries(compareData.value.map(p => [p.id, p.metrics?.[r.key] ?? 0]))
  }))
})

// ── 列表选择 ──
function onSelectionChange(rows: any[]) {
  selectedRows.value = rows
}

// ── 导航 ──
function viewDetail(id: number) {
  router.push({ path: '/algo/paper', query: { id: String(id) } })
}
function goBackToList() {
  router.push({ path: '/algo/paper' })
}

// ── 图表 ──
function initNavChart() {
  if (!navChartRef.value || !detailData.value?.nav?.length) return
  if (navChart) { navChart.dispose(); navChart = null }
  navChart = echarts.init(navChartRef.value)
  const nav = detailData.value.nav as any[]
  const dates = nav.map((n: any) => n.date)
  const initial = nav[0]?.total_value || 1
  const returns = nav.map((n: any) => +(((n.total_value ?? initial) / initial - 1) * 100).toFixed(2))
  const values = nav.map((n: any) => n.total_value ?? 0)

  navChart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter(p: any) {
        const d = p[0]?.axisValue
        let h = `<b>${d}</b>`
        p.forEach((s: any) => {
          const unit = s.seriesIndex === 0 ? '%' : ' 元'
          h += `<br/>${s.marker} ${s.seriesName}: ${s.seriesIndex === 0 ? (s.value >= 0 ? '+' : '') : ''}${s.value}${unit}`
        })
        return h
      },
    },
    legend: { data: ['收益率', '总资产'], top: 4, textStyle: { fontSize: 11 } },
    grid: { left: 55, right: 55, top: 40, bottom: 30 },
    dataZoom: [{ type: 'inside', start: 0, end: 100 }],
    xAxis: { type: 'category', data: dates, boundaryGap: false, axisLabel: { fontSize: 10 } },
    yAxis: [
      { type: 'value', axisLabel: { formatter: '{value}%', fontSize: 10 },
        splitLine: { lineStyle: { type: 'dashed', color: '#eee' } } },
      { type: 'value', axisLabel: { fontSize: 10 }, splitLine: { show: false } },
    ],
    series: [
      {
        name: '收益率', type: 'line', yAxisIndex: 0, data: returns, symbol: 'none',
        lineStyle: { width: 2, color: '#e6a23c' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(230,162,60,0.22)' },
            { offset: 1, color: 'rgba(230,162,60,0.01)' },
          ]),
        },
      },
      {
        name: '总资产', type: 'line', yAxisIndex: 1, data: values, symbol: 'none',
        lineStyle: { width: 1.5, color: '#409eff' },
      },
    ],
  })
}

function initCompareChart() {
  if (!compareChartRef.value || !compareData.value.length) return
  const chart = echarts.init(compareChartRef.value)
  const colors = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4']
  const series = compareData.value.map((p: any, i: number) => {
    const nav = p.nav || []
    if (!nav.length) return null
    const initial = nav[0].total_value || 1
    return {
      name: p.name || p.strategy_name, type: 'line', smooth: true,
      data: nav.map((n: any) => [n.date, ((n.total_value / initial - 1) * 100).toFixed(2)]),
      itemStyle: { color: colors[i % colors.length] },
    }
  }).filter(Boolean)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    xAxis: { type: 'category' },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
    series,
    grid: { left: 60, right: 20, top: 40, bottom: 30 },
  })
}

// ── 数据加载 ──
async function loadList() {
  loading.value = true
  try {
    const res = await getPaperTradingList()
    if ((res as any)?.code === 0) paperList.value = (res as any).data
    else if (res.data?.code === 0) paperList.value = res.data.data
  } finally { loading.value = false }
}

async function loadStrategies() {
  try {
    try { await request({ url: '/api/strategy/sync_templates', method: 'post' }) } catch { /* ignore */ }
    const res = await getStrategyCodeList() as any
    const d = res?.data || res
    strategies.value = d?.strategies || (Array.isArray(d) ? d : [])
  } catch { /* ignore */ }
}

async function loadDetailData(id: number) {
  detailLoading.value = true
  sideTab.value = 'overview'
  chartTab.value = 'returns'
  detailData.value = null
  try {
    const res = await getPaperTradingDetail(id)
    if ((res as any)?.code === 0) detailData.value = (res as any).data
    else if (res.data?.code === 0) detailData.value = res.data.data
    // 设置日期选择器为最后运行日期
    if (detailData.value?.info?.last_run_date) {
      posHistDate.value = detailData.value.info.last_run_date
      tradeHistDate.value = detailData.value.info.last_run_date
    } else {
      posHistDate.value = ''
      tradeHistDate.value = ''
    }
    await nextTick()
    initNavChart()
  } finally { detailLoading.value = false }
}

// ── 按日期重新加载持仓 ──
async function reloadPositionsByDate(date: string) {
  if (!detailId.value || !detailData.value) return
  try {
    const res = await getPaperTradingDetail(detailId.value, date)
    const body = (res as any)?.code !== undefined ? (res as any) : res.data
    if (body?.code === 0 && body.data?.positions) {
      detailData.value.positions = body.data.positions
    }
  } catch { /* ignore */ }
}

async function goCompare() {
  if (selectedRows.value.length < 2) return
  showCompare.value = true
  compareLoading.value = true
  try {
    const ids = selectedRows.value.map((r: any) => r.id)
    const res = await getPaperCompare(ids)
    const body = (res as any)?.code !== undefined ? (res as any) : res.data
    if (body?.code === 0) {
      compareData.value = body.data
      await nextTick()
      initCompareChart()
    } else { ElMessage.error(body?.msg || '对比失败') }
  } finally { compareLoading.value = false }
}

async function doAction(id: number, action: 'pause' | 'resume' | 'stop') {
  if (action === 'stop') {
    try { await ElMessageBox.confirm('确定要停止此模拟盘？停止后无法恢复。', '确认') }
    catch { return }
  }
  try {
    const res = await paperTradingAction({ id, action })
    if ((res as any)?.code === 0 || res.data?.code === 0) {
      ElMessage.success('操作成功')
      loadList()
      if (detailId.value === id) loadDetailData(id)
    }
  } catch { /* cancelled */ }
}

async function doRun(id: number) {
  runningId.value = id
  try {
    const res = await runPaperTrading(id)
    const body = (res as any)?.code !== undefined ? (res as any) : res.data
    if (body?.code === 0) {
      ElMessage.success(body.data?.message || '执行完成')
      loadList()
      if (detailId.value === id) loadDetailData(id)
    } else { ElMessage.error(body?.msg || '执行失败') }
  } finally { runningId.value = null }
}

async function doDelete(id: number, name: string) {
  try {
    await ElMessageBox.confirm(
      `确定要删除模拟盘「${name || '模拟盘-' + id}」？删除后数据无法恢复。`,
      '确认删除', { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' })
    const res = await deletePaperTrading(id)
    const body = (res as any)?.code !== undefined ? (res as any) : res.data
    if (body?.code === 0) {
      ElMessage.success('删除成功')
      loadList()
    } else { ElMessage.error(body?.msg || '删除失败') }
  } catch { /* cancelled */ }
}

async function doCreate() {
  if (!createForm.value.strategy_id) { ElMessage.warning('请选择策略'); return }
  creating.value = true
  try {
    const res = await createPaperTrading({
      strategy_id: createForm.value.strategy_id,
      name: createForm.value.name,
      initial_cash: createForm.value.initial_cash,
    })
    const body = (res as any)?.code !== undefined ? (res as any) : res.data
    if (body?.code === 0) {
      ElMessage.success('模拟盘创建成功')
      showCreateDialog.value = false
      createForm.value = { strategy_id: null as any, name: '', initial_cash: 1000000 }
      loadList()
    } else { ElMessage.error(body?.msg || '创建失败') }
  } finally { creating.value = false }
}

// ── 路由变化时加载详情 ──
watch(detailId, async (newId) => {
  if (newId) {
    await loadDetailData(newId)
  } else {
    detailData.value = null
  }
}, { immediate: true })

// ── Tab切换后重绘图表 ──
watch(sideTab, async (tab) => {
  if (tab === 'overview' && detailData.value?.nav?.length) {
    await nextTick()
    setTimeout(initNavChart, 80)
  }
})

// ── 持仓日期变化时重新加载持仓数据 ──
watch(posHistDate, (newDate) => {
  if (newDate && detailData.value) {
    reloadPositionsByDate(newDate)
  }
})

onMounted(() => { loadList(); loadStrategies() })
onUnmounted(() => {
  if (navChart) { navChart.dispose(); navChart = null }
})
</script>

<style scoped>
.paper-trading { padding: 16px 20px; }

/* ── 页面头部 ── */
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.header-left { display: flex; align-items: center; gap: 12px; }
.header-left h2 { margin: 0; font-size: 18px; }
.header-right { display: flex; gap: 8px; }
.count-tag { font-variant-numeric: tabular-nums; }

/* ══════ 详情页：聚宽实盘风格 ══════ */
.detail-page { min-height: 500px; }

/* 顶部标题条 */
.jq-detail-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; background: #2196f3; color: #fff; border-radius: 4px 4px 0 0;
}
.jq-detail-title { display: flex; align-items: center; gap: 6px; }
.back-btn { color: #fff !important; padding: 4px; }
.back-btn:hover { background: rgba(255,255,255,0.15); }
.jq-title-text { font-size: 15px; font-weight: 600; }
.jq-title-name { font-size: 13px; color: rgba(255,255,255,0.7); margin-left: 4px; }
.jq-detail-actions { display: flex; gap: 8px; }

/* 顶部指标条 */
.jq-metrics-bar {
  display: flex; align-items: center; gap: 0;
  padding: 12px 20px; background: #fff; border: 1px solid #e4e7ed; border-top: none;
  overflow-x: auto;
}
.jq-metric-cell {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  padding: 0 18px; flex-shrink: 0;
}
.jq-metric-sep { width: 1px; height: 30px; background: #e4e7ed; flex-shrink: 0; }
.jq-mc-value { font-size: 18px; font-weight: 700; color: #303133; font-variant-numeric: tabular-nums; white-space: nowrap; }
.jq-mc-label { font-size: 11px; color: #909399; white-space: nowrap; }
.jq-metric-more { cursor: pointer; }
.jq-metric-more .jq-mc-value { font-size: 13px; font-weight: 400; color: #606266; }
.jq-metric-more:hover .jq-mc-value { color: #409eff; }

/* 其他指标弹出 */
.jq-extra-metrics { display: flex; flex-direction: column; gap: 8px; }
.jq-em-row { display: flex; justify-content: space-between; font-size: 13px; color: #303133; }
.jq-em-row span:first-child { color: #909399; }

/* 左侧Tab + 内容区 */
.jq-detail-body {
  border: 1px solid #e4e7ed; border-top: none; border-radius: 0 0 4px 4px;
  background: #fff; min-height: 400px;
}
.jq-side-tabs { height: 100%; }
:deep(.jq-side-tabs > .el-tabs__header) {
  width: 64px; background: #f5f7fa; border-right: 1px solid #e4e7ed;
}
:deep(.jq-side-tabs > .el-tabs__header .el-tabs__item) {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  height: 60px; padding: 8px 0 !important; font-size: 11px; color: #606266;
  justify-content: center;
}
:deep(.jq-side-tabs > .el-tabs__header .el-tabs__item .el-icon) { font-size: 18px; }
:deep(.jq-side-tabs > .el-tabs__header .el-tabs__item.is-active) {
  color: #409eff; background: #fff; font-weight: 600;
}
:deep(.jq-side-tabs > .el-tabs__content) { padding: 0; flex: 1; }
:deep(.jq-side-tabs > .el-tabs__content .el-tab-pane) { padding: 0; }

/* 代码Tab图标 */
.code-tab-icon {
  font-size: 14px; font-weight: 700; font-family: monospace;
  line-height: 20px; display: block;
}

/* 内容区段 */
.jq-section { padding: 16px 20px; }
.jq-section + .jq-section { border-top: 1px solid #f0f0f0; }
.jq-section-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 12px;
}
.jq-section-title { font-size: 14px; font-weight: 600; color: #303133; }
.jq-section-actions { display: flex; align-items: center; gap: 12px; }
.jq-export-link { font-size: 12px; color: #409eff; cursor: pointer; }
.jq-export-link:hover { text-decoration: underline; }
.jq-date-label { font-size: 12px; color: #909399; white-space: nowrap; }

/* 列筛选复选框 */
.jq-col-filter {
  display: flex; flex-wrap: wrap; gap: 4px 12px;
  padding: 8px 0; margin-bottom: 8px; border-bottom: 1px solid #f0f0f0;
}
:deep(.jq-col-filter .el-checkbox) { margin-right: 0; height: auto; }
:deep(.jq-col-filter .el-checkbox__label) { font-size: 12px; padding-left: 4px; }

/* 图表空态 */
.jq-empty-chart {
  display: flex; align-items: center; justify-content: center;
  height: 280px; color: #909399; font-size: 14px;
}
.jq-inner-tabs { margin: 0; }
:deep(.jq-inner-tabs .el-tabs__header) { margin-bottom: 8px; }

/* 统计指标网格 */
.jq-stats-grid {
  display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px;
}
.jq-stat-card {
  display: flex; flex-direction: column; gap: 4px;
  padding: 14px; background: #f9fafb; border-radius: 6px; border: 1px solid #ebeef5;
}
.jq-stat-label { font-size: 12px; color: #909399; }
.jq-stat-value { font-size: 16px; font-weight: 600; color: #303133; font-variant-numeric: tabular-nums; }

/* 日志 */
.jq-log-area { max-height: 500px; overflow-y: auto; }
.jq-log-entry {
  display: flex; gap: 12px; padding: 6px 0; font-size: 13px; color: #303133;
  border-bottom: 1px solid #f5f5f5;
}
.jq-log-date { color: #909399; flex-shrink: 0; }
.jq-log-empty { padding: 40px; text-align: center; color: #909399; }

/* 设置 */
.jq-settings { max-width: 500px; }
.jq-set-row {
  display: flex; justify-content: space-between; padding: 10px 0;
  border-bottom: 1px solid #f5f5f5; font-size: 13px;
}
.jq-set-label { color: #909399; }
.jq-set-value { color: #303133; font-weight: 500; }

/* ── 颜色 ── */
.val-red { color: #f56c6c !important; }
.val-green { color: #67c23a !important; }

/* ── 列表表格 ── */
.jq-table { margin-top: 4px; }
.jq-name-link { color: #409eff; cursor: pointer; font-weight: 500; }
.jq-name-link:hover { text-decoration: underline; }
.jq-status-running { color: #67c23a; font-weight: 500; }
.jq-status-paused { color: #e6a23c; font-weight: 500; }
.jq-status-stopped { color: #909399; }

/* ── 操作列 ── */
.jq-ops { display: flex; align-items: center; justify-content: center; gap: 4px; white-space: nowrap; }
.jq-op { color: #409eff; cursor: pointer; font-size: 13px; text-decoration: none; }
.jq-op:hover { text-decoration: underline; }
.jq-op-sep { color: #dcdfe6; font-size: 12px; margin: 0 1px; user-select: none; }
.jq-op-danger { color: #f56c6c; }
.jq-op-danger:hover { color: #f78989; }
.jq-op-primary { color: #409eff; }
.jq-op-disabled { color: #c0c4cc !important; cursor: not-allowed; pointer-events: none; }
</style>
