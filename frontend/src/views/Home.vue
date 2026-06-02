<template>
  <div class="home-page">
    <div class="page-header">
      <h2>数据概览</h2>
      <div class="header-filters">
        <el-radio-group v-model="timeRange" @change="handleTimeChange">
          <el-radio-button value="7">近七天</el-radio-button>
          <el-radio-button value="30">近一月</el-radio-button>
        </el-radio-group>
        <el-button text @click="loadAllData">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 核心指标卡片 -->
    <el-row :gutter="20" class="stat-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #409eff">
              <el-icon :size="28"><Microphone /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ overview.total_recordings }}</div>
              <div class="stat-label">上传录音</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #67c23a">
              <el-icon :size="28"><DocumentChecked /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ overview.scored_count }}</div>
              <div class="stat-label">已评分</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #e6a23c">
              <el-icon :size="28"><Star /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ overview.avg_total_score }}分</div>
              <div class="stat-label">大盘平均分</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #f56c6c">
              <el-icon :size="28"><Warning /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ violationRate }}%</div>
              <div class="stat-label">违规率</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 详细指标 -->
    <el-row :gutter="20" class="stat-row">
      <el-col :span="6">
        <el-card class="detail-card">
          <div class="detail-item">
            <span class="detail-label">总加分</span>
            <span class="detail-value bonus">+{{ overview.total_bonus }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">有加分的录音</span>
            <span class="detail-value">{{ overview.recordings_with_bonus }}条</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">平均加分</span>
            <span class="detail-value bonus">+{{ overview.avg_bonus }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="detail-card">
          <div class="detail-item">
            <span class="detail-label">总扣分</span>
            <span class="detail-value deduction">-{{ overview.total_deduction }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">有扣分的录音</span>
            <span class="detail-value">{{ overview.recordings_with_deduction }}条</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">平均扣分</span>
            <span class="detail-value deduction">-{{ overview.avg_deduction }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="detail-card">
          <div class="detail-item">
            <span class="detail-label">最高加分</span>
            <span class="detail-value bonus">+{{ overview.max_bonus }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">最高扣分</span>
            <span class="detail-value deduction">-{{ overview.max_deduction }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">加分录音占比</span>
            <span class="detail-value">{{ bonusRate }}%</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="detail-card">
          <div class="detail-item">
            <span class="detail-label">否决录音</span>
            <span class="detail-value rejection">{{ overview.recordings_with_rejection || 0 }}条</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">否决率</span>
            <span class="detail-value rejection">{{ rejectionRate }}%</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="20" class="chart-row">
      <el-col :span="16">
        <el-card class="chart-card">
          <template #header>
            <span class="card-title">每日评分趋势</span>
          </template>
          <div ref="trendChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="chart-card">
          <template #header>
            <span class="card-title">违规率/否决率趋势</span>
          </template>
          <div ref="violationChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="chart-row">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <span class="card-title">Top 10 坐席评分</span>
          </template>
          <div ref="agentChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <span class="card-title">规则命中统计</span>
          </template>
          <div ref="ruleChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { Refresh, Microphone, DocumentChecked, Star, Warning } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import api from '@/api'

const timeRange = ref('7')
const trendChartRef = ref(null)
const violationChartRef = ref(null)
const agentChartRef = ref(null)
const ruleChartRef = ref(null)

let trendChart = null
let violationChart = null
let agentChart = null
let ruleChart = null

const overview = ref({
  total_recordings: 0,
  scored_count: 0,
  recordings_with_bonus: 0,
  recordings_with_deduction: 0,
  recordings_with_rejection: 0,
  total_bonus: 0,
  total_deduction: 0,
  avg_bonus: 0,
  avg_deduction: 0,
  max_bonus: 0,
  max_deduction: 0,
  avg_total_score: 0
})

const trendData = ref([])

const violationRate = computed(() => {
  if (!overview.value.scored_count) return 0
  return ((overview.value.recordings_with_deduction / overview.value.scored_count) * 100).toFixed(1)
})

const rejectionRate = computed(() => {
  if (!overview.value.scored_count) return 0
  return ((overview.value.recordings_with_rejection / overview.value.scored_count) * 100).toFixed(1)
})

const bonusRate = computed(() => {
  if (!overview.value.scored_count) return 0
  return ((overview.value.recordings_with_bonus / overview.value.scored_count) * 100).toFixed(1)
})

function getDateRange() {
  const now = new Date()
  const end = now.toISOString().slice(0, 19).replace('T', ' ')
  const start = new Date(now)
  start.setDate(start.getDate() - (parseInt(timeRange.value) - 1))
  const startStr = start.toISOString().slice(0, 19).replace('T', ' ')
  return { start: startStr, end }
}

async function loadOverview() {
  try {
    const dates = getDateRange()
    const data = await api.statistics.overview(dates)
    overview.value = data
  } catch (e) {
    console.error('加载概览数据失败', e)
  }
}

async function loadTrend() {
  try {
    const days = parseInt(timeRange.value)
    const data = await api.statistics.trend(days)
    trendData.value = data
    await nextTick()
    renderTrendChart()
    renderViolationChart()
  } catch (e) {
    console.error('加载趋势数据失败', e)
  }
}

async function loadAgentStats() {
  try {
    const dates = getDateRange()
    const data = await api.statistics.agentStats(dates)
    await nextTick()
    renderAgentChart(data)
  } catch (e) {
    console.error('加载坐席数据失败', e)
  }
}

async function loadRuleStats() {
  try {
    const dates = getDateRange()
    const data = await api.statistics.ruleStats(dates)
    await nextTick()
    renderRuleChart(data)
  } catch (e) {
    console.error('加载规则数据失败', e)
  }
}

function loadAllData() {
  loadOverview()
  loadTrend()
  loadAgentStats()
  loadRuleStats()
}

function handleTimeChange() {
  loadAllData()
}

function renderTrendChart() {
  if (!trendChart && trendChartRef.value) {
    trendChart = echarts.init(trendChartRef.value)
  }
  if (!trendData.value.length) return

  const dates = trendData.value.map(d => d.date.slice(5))
  const scores = trendData.value.map(d => d.avg_score)
  const bonus = trendData.value.map(d => d.avg_bonus)
  const deduction = trendData.value.map(d => d.avg_deduction)

  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['平均分', '平均加分', '平均扣分'], bottom: 0 },
    grid: { left: 50, right: 20, top: 20, bottom: 50 },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', name: '分数' },
    series: [
      { name: '平均分', type: 'line', data: scores, smooth: true, itemStyle: { color: '#409eff' } },
      { name: '平均加分', type: 'line', data: bonus, smooth: true, itemStyle: { color: '#67c23a' } },
      { name: '平均扣分', type: 'line', data: deduction, smooth: true, itemStyle: { color: '#f56c6c' } }
    ]
  })
}

function renderViolationChart() {
  if (!violationChart && violationChartRef.value) {
    violationChart = echarts.init(violationChartRef.value)
  }
  if (!trendData.value.length) return

  const dates = trendData.value.map(d => d.date.slice(5))
  const violationRates = trendData.value.map(d => d.violation_rate || 0)
  const rejectionRates = trendData.value.map(d => d.rejection_rate || 0)

  violationChart.setOption({
    tooltip: { trigger: 'axis', formatter: '{c}%' },
    legend: { data: ['违规率', '否决率'], bottom: 0 },
    grid: { left: 50, right: 20, top: 20, bottom: 50 },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', name: '比率', axisLabel: { formatter: '{value}%' }, max: 100 },
    series: [
      {
        name: '违规率',
        type: 'bar',
        data: violationRates,
        itemStyle: { color: '#f56c6c' }
      },
      {
        name: '否决率',
        type: 'bar',
        data: rejectionRates,
        itemStyle: { color: '#e6a23c' }
      }
    ]
  })
}

function renderAgentChart(data) {
  if (!agentChart && agentChartRef.value) {
    agentChart = echarts.init(agentChartRef.value)
  }
  if (!data.length) return

  const names = data.map(d => d.agent_name.slice(0, 6))
  const scores = data.map(d => d.avg_score)

  agentChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'value', name: '平均分' },
    yAxis: { type: 'category', data: names.reverse(), name: '坐席' },
    series: [{
      type: 'bar',
      data: scores.reverse(),
      itemStyle: { color: '#409eff' },
      label: { show: true, position: 'right', formatter: '{c}' }
    }]
  })
}

function renderRuleChart(data) {
  if (!ruleChart && ruleChartRef.value) {
    ruleChart = echarts.init(ruleChartRef.value)
  }
  if (!data.length) {
    ruleChart?.setOption({ title: { text: '暂无数据' }, series: [] })
    return
  }

  const top5 = data.slice(0, 5)
  ruleChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c}次' },
    legend: { orient: 'vertical', left: 'left' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      data: top5.map(d => ({ name: d.rule_name, value: d.hit_count }))
    }]
  })
}

function handleResize() {
  trendChart?.resize()
  violationChart?.resize()
  agentChart?.resize()
  ruleChart?.resize()
}

onMounted(() => {
  loadAllData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  violationChart?.dispose()
  agentChart?.dispose()
  ruleChart?.dispose()
})
</script>

<style scoped>
.home-page {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.header-filters {
  display: flex;
  gap: 10px;
  align-items: center;
}

.stat-row {
  margin-bottom: 20px;
}

.stat-card {
  cursor: pointer;
  transition: transform 0.3s;
}

.stat-card:hover {
  transform: translateY(-3px);
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 0;
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 26px;
  font-weight: bold;
  color: #333;
}

.stat-label {
  font-size: 13px;
  color: #999;
  margin-top: 4px;
}

.detail-card {
  padding: 8px 0;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid #f0f0f0;
}

.detail-item:last-child {
  border-bottom: none;
}

.detail-label {
  color: #666;
  font-size: 14px;
}

.detail-value {
  font-size: 16px;
  font-weight: bold;
}

.detail-value.bonus {
  color: #67c23a;
}

.detail-value.deduction {
  color: #f56c6c;
}

.detail-value.rejection {
  color: #e6a23c;
}

.chart-row {
  margin-bottom: 20px;
}

.chart-card {
  min-height: 320px;
}

.card-title {
  font-weight: bold;
  font-size: 15px;
  color: #303133;
}

.chart-container {
  height: 260px;
  width: 100%;
}
</style>