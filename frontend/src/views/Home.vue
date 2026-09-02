<template>
  <div class="home-page">
    <div class="page-header">
      <div class="header-filters">
        <el-radio-group v-model="timeRange" @change="handleTimeChange">
          <el-radio-button value="7">近七天</el-radio-button>
          <el-radio-button value="30">近一月</el-radio-button>
        </el-radio-group>
        <el-button text @click="loadAllData">
          <el-icon><RefreshCw /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 核心指标卡片 -->
    <el-row :gutter="20" class="stat-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-label">上传录音数</div>
              <div class="stat-value">{{ overview.total_recordings }}</div>
            </div>
            <Mic :size="22" class="stat-icon" />
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-label">已评分录音数</div>
              <div class="stat-value">{{ overview.scored_count }}</div>
            </div>
            <FileCheckCorner :size="22" class="stat-icon" />
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-label">大盘平均分</div>
              <div class="stat-value">{{ overview.avg_total_score }}<span class="stat-unit">分</span></div>
            </div>
            <Star :size="22" class="stat-icon" />
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card stat-card-accent">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-label">违规率</div>
              <div class="stat-value accent">{{ violationRate }}<span class="stat-unit">%</span></div>
            </div>
            <TriangleAlert :size="22" class="stat-icon accent" />
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
import { RefreshCw, Mic, FileCheckCorner, Star, TriangleAlert } from 'lucide-vue-next'
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
        itemStyle: { color: '#b0442c' },
        lineStyle: { width: 2 },
        areaStyle: { color: 'rgba(176, 68, 44, 0.08)' },
        symbol: 'circle',
        symbolSize: 6,
      },
      {
        name: '平均加分',
        type: 'line',
        data: avgBonuses,
        smooth: true,
        itemStyle: { color: '#3d7a4f' },
        lineStyle: { width: 2 },
        symbol: 'circle',
        symbolSize: 5,
      },
      {
        name: '平均扣分',
        type: 'line',
        data: avgDeductions,
        smooth: true,
        itemStyle: { color: '#b03424' },
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
          <span style="color:#b03424">●</span> 违规率：${vr ? vr.value : 0}%<br/>
          <span style="color:#b07d2a">●</span> 否决率：${rr ? rr.value : 0}%`
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
        itemStyle: { color: '#b03424' },
        lineStyle: { width: 2 },
        symbol: 'circle',
        symbolSize: 5,
      },
      {
        name: '否决率',
        type: 'line',
        data: rejectionRates,
        smooth: true,
        itemStyle: { color: '#b07d2a' },
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
          itemStyle: { color: '#b0442c' },
          label: { show: true, position: 'insideRight', formatter: (p) => p.value > 0 ? p.value : '' }
        },
        {
          name: '未评分',
          type: 'bar',
          stack: 'total',
          data: unscoredCounts,
          itemStyle: { color: '#b07d2a' },
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
      itemStyle: { color: '#b0442c' },
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
    color: ['#b0442c', '#211d18', '#b07d2a', '#3d7a4f', '#8a8175', '#d3a08f', '#57503f', '#d3ccbd', '#8f3520', '#a89e8f'],
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
  justify-content: flex-end;
  align-items: center;
  margin-bottom: 24px;
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
  transition: border-color var(--va-duration) var(--va-ease);
}

.stat-card:hover {
  border-color: var(--va-hairline-dark);
}

.stat-card-accent {
  border-top: 2px solid var(--va-accent);
}

.stat-content {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 4px 0;
}

.stat-icon {
  color: var(--va-muted);
  margin-top: 2px;
  flex-shrink: 0;
}

.stat-icon.accent {
  color: var(--va-accent);
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-family: var(--va-font-display);
  font-size: 34px;
  font-weight: 700;
  color: var(--va-ink);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
  margin-top: 6px;
}

.stat-value.accent {
  color: var(--va-accent);
}

.stat-unit {
  font-size: 15px;
  font-weight: 400;
  color: var(--va-muted);
  margin-left: 2px;
}

.stat-label {
  font-size: 12.5px;
  color: var(--va-muted);
  letter-spacing: 0.06em;
}

.detail-card {
  padding: 4px 0;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid var(--va-hairline);
}

.detail-item:last-child {
  border-bottom: none;
}

.detail-label {
  color: var(--va-muted);
  font-size: 13.5px;
}

.detail-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--va-ink);
  font-variant-numeric: tabular-nums;
}

.detail-value.bonus {
  color: var(--va-success);
}

.detail-value.deduction {
  color: var(--va-danger);
}

.detail-value.rejection {
  color: var(--va-warning);
}

.chart-row {
  margin-bottom: 20px;
}

.chart-card {
  min-height: 320px;
}

.card-title {
  font-family: var(--va-font-display);
  font-weight: 700;
  font-size: 15.5px;
  color: var(--va-ink);
  letter-spacing: 0.02em;
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