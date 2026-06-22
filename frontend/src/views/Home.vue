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
              <div class="stat-label">上传录音数</div>
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
              <div class="stat-label">已评分录音数</div>
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
            <span class="card-title">整体平均分</span>
          </template>
          <div ref="trendChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="chart-card">
          <template #header>
            <span class="card-title">违规率/否决率</span>
          </template>
          <div ref="violationChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="chart-row">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">Top 10 坐席情况</span>
              <el-radio-group v-model="agentSortBy" size="small" @change="loadAgentStats">
                <el-radio-button value="count">录音数</el-radio-button>
                <el-radio-button value="avg_score">平均分</el-radio-button>
                <el-radio-button value="violation_rate">违规率</el-radio-button>
                <el-radio-button value="rejection_rate">否决率</el-radio-button>
                <el-radio-button value="total_score">总分</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div ref="agentChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">规则命中 Top 10</span>
              <el-radio-group v-model="ruleType" size="small" @change="loadRuleStats">
                <el-radio-button value="bonus">加分规则</el-radio-button>
                <el-radio-button value="deduction">扣分规则</el-radio-button>
              </el-radio-group>
            </div>
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
import { now, formatDate } from '@/utils/timezone'
import api from '@/api'

const timeRange = ref('7')
const agentSortBy = ref('count')
const ruleType = ref('bonus')
const trendChartRef = ref(null)
const violationChartRef = ref(null)
const agentChartRef = ref(null)
const ruleChartRef = ref(null)

let trendChart = null
let violationChart = null
let agentChart = null
let ruleChart = null
let ruleChart2 = null

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
  const end = now().endOf('day').format('YYYY-MM-DD HH:mm:ss')
  const start = now().subtract(parseInt(timeRange.value) - 1, 'day').startOf('day').format('YYYY-MM-DD HH:mm:ss')
  return { start_date: start, end_date: end }
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
    const data = await api.statistics.agentStats({ ...dates, sort_by: agentSortBy.value })
    await nextTick()
    renderAgentChart(data)
  } catch (e) {
    console.error('加载坐席数据失败', e)
  }
}

async function loadRuleStats() {
  try {
    const dates = getDateRange()
    const data = await api.statistics.ruleHitStats({ ...dates, item_type: ruleType.value })
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

  const dates = trendData.value.map(d => d.date)
  const avgScores = trendData.value.map(d => d.avg_score)
  const avgBonuses = trendData.value.map(d => d.avg_bonus)
  const avgDeductions = trendData.value.map(d => d.avg_deduction)

  // 自适应纵轴范围
  const allValues = [...avgScores, ...avgBonuses, ...avgDeductions].filter(v => v !== null && v !== undefined)
  const dataMin = Math.min(...allValues)
  const dataMax = Math.max(...allValues)
  const padding = Math.max(Math.abs(dataMin), Math.abs(dataMax)) * 0.15 || 10
  const yMin = Math.floor(dataMin - padding)
  const yMax = Math.ceil(dataMax + padding)

  trendChart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        let result = `<strong>${params[0].axisValue}</strong><br/>`
        params.forEach(p => {
          if (p.value !== null && p.value !== undefined) {
            result += `<span style="color:${p.color}">●</span> ${p.seriesName}：${p.value}分<br/>`
          }
        })
        return result
      }
    },
    legend: { data: ['平均分', '平均加分', '平均扣分'], top: 0, right: 0, textStyle: { fontSize: 11 } },
    grid: { left: 50, right: 20, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', min: yMin, max: yMax, axisLabel: { fontSize: 11 } },
    series: [
      {
        name: '平均分',
        type: 'line',
        data: avgScores,
        smooth: true,
        itemStyle: { color: '#409eff' },
        lineStyle: { width: 2 },
        areaStyle: { color: 'rgba(64, 158, 255, 0.1)' },
        symbol: 'circle',
        symbolSize: 6,
      },
      {
        name: '平均加分',
        type: 'line',
        data: avgBonuses,
        smooth: true,
        itemStyle: { color: '#67c23a' },
        lineStyle: { width: 2 },
        symbol: 'circle',
        symbolSize: 5,
      },
      {
        name: '平均扣分',
        type: 'line',
        data: avgDeductions,
        smooth: true,
        itemStyle: { color: '#f56c6c' },
        lineStyle: { width: 2 },
        symbol: 'circle',
        symbolSize: 5,
      }
    ]
  })
}

function renderViolationChart() {
  if (!violationChart && violationChartRef.value) {
    violationChart = echarts.init(violationChartRef.value)
  }
  if (!trendData.value.length) return

  const dates = trendData.value.map(d => d.date)
  const violationRates = trendData.value.map(d => d.violation_rate)
  const rejectionRates = trendData.value.map(d => d.rejection_rate)

  violationChart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const date = params[0].axisValue
        const vr = params.find(p => p.seriesName === '违规率')
        const rr = params.find(p => p.seriesName === '否决率')
        return `<strong>${date}</strong><br/>
          <span style="color:#f56c6c">●</span> 违规率：${vr ? vr.value : 0}%<br/>
          <span style="color:#e6a23c">●</span> 否决率：${rr ? rr.value : 0}%`
      }
    },
    legend: { data: ['违规率', '否决率'], top: 0, right: 0, textStyle: { fontSize: 11 } },
    grid: { left: 50, right: 20, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 11 } },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: { fontSize: 11, formatter: '{value}%' }
    },
    series: [
      {
        name: '违规率',
        type: 'line',
        data: violationRates,
        smooth: true,
        itemStyle: { color: '#f56c6c' },
        lineStyle: { width: 2 },
        symbol: 'circle',
        symbolSize: 5,
      },
      {
        name: '否决率',
        type: 'line',
        data: rejectionRates,
        smooth: true,
        itemStyle: { color: '#e6a23c' },
        lineStyle: { width: 2 },
        symbol: 'circle',
        symbolSize: 5,
      }
    ]
  })
}

function renderAgentChart(data) {
  if (!agentChart && agentChartRef.value) {
    agentChart = echarts.init(agentChartRef.value)
  }
  if (!data.length) {
    agentChart?.setOption({ series: [] })
    return
  }

  const names = data.map(d => d.agent_name.slice(0, 6))

  // 录音数视图：堆叠柱状图（已评分 + 未评分）
  if (agentSortBy.value === 'count') {
    const scoredCounts = data.map(d => d.count || 0).reverse()
    const unscoredCounts = data.map(d => d.unscored_count || 0).reverse()
    const totals = data.map(d => (d.count || 0) + (d.unscored_count || 0)).reverse()

    agentChart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: (params) => {
          const idx = params[0].dataIndex
          const total = totals[idx]
          const scored = scoredCounts[idx]
          const unscored = unscoredCounts[idx]
          return `<strong>${names[idx]}</strong><br/>已评分：${scored}条<br/>未评分：${unscored}条<br/>合计：${total}条`
        }
      },
      legend: { data: ['已评分', '未评分'], top: 0, right: 0, textStyle: { fontSize: 11 } },
      grid: { left: 60, right: 20, top: 30, bottom: 30 },
      xAxis: { type: 'value', name: '录音数' },
      yAxis: { type: 'category', data: names, name: '坐席' },
      series: [
        {
          name: '已评分',
          type: 'bar',
          stack: 'total',
          data: scoredCounts,
          itemStyle: { color: '#409eff' },
          label: { show: true, position: 'insideRight', formatter: (p) => p.value > 0 ? p.value : '' }
        },
        {
          name: '未评分',
          type: 'bar',
          stack: 'total',
          data: unscoredCounts,
          itemStyle: { color: '#e6a23c' },
          label: { show: true, position: 'insideRight', formatter: (p) => p.value > 0 ? p.value : '' }
        }
      ]
    })
    return
  }

  // 其他视图保持原有逻辑
  const dimFieldMap = {
    avg_score: 'avg_score',
    violation_rate: 'violation_rate',
    rejection_rate: 'rejection_rate',
    total_score: 'total_score_computed',
  }
  const dimLabelMap = {
    avg_score: '平均分',
    violation_rate: '违规率',
    rejection_rate: '否决率',
    total_score: '总分',
  }
  const dimUnitMap = {
    avg_score: '分',
    violation_rate: '%',
    rejection_rate: '%',
    total_score: '分',
  }
  const field = dimFieldMap[agentSortBy.value] || 'avg_score'
  const values = agentSortBy.value === 'total_score'
    ? data.map(d => Math.round((d.avg_score || 0) * d.count))
    : data.map(d => d[field])
  const unit = dimUnitMap[agentSortBy.value] || '分'

  agentChart.setOption({
    tooltip: { trigger: 'axis', formatter: (params) => {
      const p = params[0]
      return `${p.name}<br/>${p.value}${unit}`
    } },
    legend: { show: false },
    grid: { left: 60, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'value', name: dimLabelMap[agentSortBy.value] },
    yAxis: { type: 'category', data: names.reverse(), name: '坐席' },
    series: [{
      type: 'bar',
      data: values.reverse(),
      itemStyle: { color: '#409eff' },
      label: { show: true, position: 'right', formatter: `{c}${unit}` }
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

  const top10 = data.slice(0, 10)
  ruleChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c}次' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      data: top10.map(d => ({ name: d.item_name, value: d.hit_count }))
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

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.chart-container {
  height: 260px;
  width: 100%;
}
</style>