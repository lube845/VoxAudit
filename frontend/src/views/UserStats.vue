<template>
  <div class="user-stats-container">
    <!-- 概览统计 -->
    <el-row :gutter="20" class="overview-row" v-loading="loading">
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-value">{{ formatNumber(overview.total_users) }}</div>
          <div class="stat-label">用户总数</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-value">{{ formatNumber(overview.active_users) }}</div>
          <div class="stat-label">活跃用户(30天)</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-value">{{ formatNumber(overview.total_recordings) }}</div>
          <div class="stat-label">录音总数</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-value">{{ formatSize(overview.total_storage_bytes) }}</div>
          <div class="stat-label">总存储</div>
        </div>
      </el-col>
    </el-row>

    <el-card>
      <template #header>
        <div class="card-header">
          <span>用户使用情况</span>
        </div>
      </template>

      <el-table :data="usersList" stripe border v-loading="loading">
        <el-table-column type="index" label="排名" width="80" />
        <el-table-column prop="loginid" label="工号" width="120" />
        <el-table-column prop="name" label="姓名" width="120" />
        <el-table-column prop="department" label="部门" width="150" />
        <el-table-column prop="total_recordings" label="录音数" width="100" sortable />
        <el-table-column prop="scored_recordings" label="已评分" width="100" sortable />
        <el-table-column prop="avg_score" label="平均分" width="100" sortable>
          <template #default="{ row }">
            <span :class="getScoreClass(row.avg_score)">{{ row.avg_score || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="total_score" label="总分" width="120" sortable />
        <el-table-column label="总时长" width="120">
          <template #default="{ row }">
            {{ formatDuration(row.total_duration) }}
          </template>
        </el-table-column>
        <el-table-column label="存储" width="120">
          <template #default="{ row }">
            {{ formatSize(row.total_storage_bytes) }}
          </template>
        </el-table-column>
        <el-table-column label="通过率" width="100">
          <template #default="{ row }">
            {{ calcPassRate(row) }}%
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="showUserDetail(row)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 用户详情弹窗 -->
    <el-dialog v-model="detailVisible" title="用户详情" width="900px" destroy-on-close>
      <div v-if="currentUser" class="user-detail">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="工号">{{ currentUser.loginid }}</el-descriptions-item>
          <el-descriptions-item label="姓名">{{ currentUser.name }}</el-descriptions-item>
          <el-descriptions-item label="部门">{{ currentUser.department }}</el-descriptions-item>
          <el-descriptions-item label="规则总数">{{ currentUser.total_rules }}</el-descriptions-item>
          <el-descriptions-item label="启用规则">{{ currentUser.active_rules }}</el-descriptions-item>
          <el-descriptions-item label="最近评分时间">{{ currentUser.latest_scoring_time ? new Date(currentUser.latest_scoring_time).toLocaleString() : '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-divider />

        <el-row :gutter="20">
          <el-col :span="8">
            <div class="detail-stat">
              <div class="detail-stat-value">{{ currentUser.total_recordings }}</div>
              <div class="detail-stat-label">录音总数</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="detail-stat">
              <div class="detail-stat-value">{{ currentUser.scored_recordings }}</div>
              <div class="detail-stat-label">已评分</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="detail-stat">
              <div class="detail-stat-value">{{ formatDuration(currentUser.total_duration) }}</div>
              <div class="detail-stat-label">总时长</div>
            </div>
          </el-col>
        </el-row>

        <el-divider />

        <el-row :gutter="20">
          <el-col :span="8">
            <div class="detail-stat highlight">
              <div class="detail-stat-value">{{ currentUser.avg_total_score }}</div>
              <div class="detail-stat-label">平均分</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="detail-stat">
              <div class="detail-stat-value">{{ currentUser.avg_bonus_score }}</div>
              <div class="detail-stat-label">平均加分</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="detail-stat">
              <div class="detail-stat-value">{{ currentUser.avg_deduction_score }}</div>
              <div class="detail-stat-label">平均扣分</div>
            </div>
          </el-col>
        </el-row>

        <el-divider />

        <el-row :gutter="20">
          <el-col :span="12">
            <div class="pass-rate">
              <span class="rate-label">通过率(≥60分)</span>
              <el-progress :percentage="currentUser.pass_rate" :color="getPassRateColor(currentUser.pass_rate)" />
            </div>
          </el-col>
          <el-col :span="12">
            <div class="pass-rate">
              <span class="rate-label">否决率</span>
              <el-progress :percentage="currentUser.reject_rate" :color="getPassRateColor(100 - currentUser.reject_rate)" />
            </div>
          </el-col>
        </el-row>

        <el-divider />

        <div class="score-distribution">
          <div class="section-title">分数分布</div>
          <el-table :data="currentUser.score_distribution" stripe size="small">
            <el-table-column prop="label" label="分数段" width="140">
              <template #default="{ row }">
                {{ formatScoreLabel(row.label) }}
              </template>
            </el-table-column>
            <el-table-column prop="count" label="录音数" width="120" />
            <el-table-column prop="percentage" label="占比">
              <template #default="{ row }">
                <el-progress :percentage="row.percentage" :color="getScoreColor(row.label)" />
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div v-if="currentUser.recordings_timeline && currentUser.recordings_timeline.length" class="timeline-section">
          <div class="section-title">近30个使用日期</div>
          <div class="timeline-chart">
            <div v-for="item in currentUser.recordings_timeline.slice(0, 30)" :key="item.date" class="timeline-item">
              <div class="timeline-date">{{ item.date }}</div>
              <div class="timeline-count">{{ item.count }}</div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

const loading = ref(false)

const overview = ref({
  total_users: 0,
  active_users: 0,
  total_recordings: 0,
  total_storage_bytes: 0,
  avg_score_all: 0
})

const usersList = ref([])
const detailVisible = ref(false)
const currentUser = ref(null)

function formatNumber(num) {
  return num || 0
}

function formatSize(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024
    i++
  }
  return `${bytes.toFixed(2)} ${units[i]}`
}

function formatDuration(seconds) {
  if (!seconds) return '0s'
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${(seconds / 3600).toFixed(1)}h`
}

function getScoreClass(score) {
  if (!score && score !== 0) return ''
  if (score >= 80) return 'score-high'
  if (score >= 60) return 'score-mid'
  return 'score-low'
}

function formatScoreLabel(label) {
  const labelMap = {
    '<0': '(-∞, 0)',
    '0-60': '[0, 60)',
    '60-70': '[60, 70)',
    '70-80': '[70, 80)',
    '80-90': '[80, 90)',
    '90-100': '[90, 100)',
    '>100': '[100, +∞)'
  }
  return labelMap[label] || label
}

function getScoreColor(label) {
  const colors = {
    '<0': '#F56C6C',
    '0-60': '#F56C6C',
    '60-70': '#E6A23C',
    '70-80': '#409EFF',
    '80-90': '#67C23A',
    '90-100': '#909399',
    '>100': '#909399'
  }
  return colors[label] || '#409EFF'
}

function getPassRateColor(rate) {
  if (rate >= 80) return '#67C23A'
  if (rate >= 60) return '#E6A23C'
  return '#F56C6C'
}

function calcPassRate(user) {
  if (!user.score_distribution) return 0
  const dist = user.score_distribution
  const total = Object.values(dist).reduce((a, b) => a + b, 0)
  if (total === 0) return 0
  const passed = (dist['60-70'] || 0) + (dist['70-80'] || 0) + (dist['80-90'] || 0) + (dist['90-100'] || 0)
  return Math.round((passed / total) * 100)
}

async function loadOverview() {
  try {
    const res = await api.userStats.getOverview({})
    overview.value = res
  } catch (e) {
    console.error('获取概览失败', e)
  }
}

async function loadUsersList() {
  loading.value = true
  try {
    const res = await api.userStats.getUsersList({})
    usersList.value = res || []
  } catch (e) {
    console.error('获取用户列表失败', e)
  } finally {
    loading.value = false
  }
}

async function showUserDetail(user) {
  try {
    const res = await api.userStats.getUserDetail(user.loginid, {})
    currentUser.value = res
    detailVisible.value = true
  } catch (e) {
    ElMessage.error('获取用户详情失败')
  }
}

onMounted(() => {
  loadOverview()
  loadUsersList()
})
</script>

<style scoped>
.user-stats-container {
  max-width: 1400px;
}

.filter-card {
  margin-bottom: 20px;
}

.filter-card :deep(.el-card__body) {
  padding: 12px 20px;
}

.search-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.overview-row {
  margin-bottom: 20px;
}

.stat-card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 8px;
}

.stats-tabs {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.score-high {
  color: #67c23a;
  font-weight: 600;
}

.score-mid {
  color: #e6a23c;
  font-weight: 600;
}

.score-low {
  color: #f56c6c;
  font-weight: 600;
}

.user-detail {
  padding: 10px;
}

.detail-stat {
  text-align: center;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
}

.detail-stat.highlight {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.detail-stat.highlight .detail-stat-value,
.detail-stat.highlight .detail-stat-label {
  color: #fff;
}

.detail-stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.detail-stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.pass-rate {
  padding: 10px;
}

.rate-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
  display: block;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
}

.score-distribution {
  margin-top: 20px;
}

.timeline-section {
  margin-top: 20px;
}

.timeline-chart {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.timeline-item {
  background: #f5f7fa;
  padding: 8px 12px;
  border-radius: 4px;
  min-width: 80px;
  text-align: center;
}

.timeline-date {
  font-size: 12px;
  color: #909399;
}

.timeline-count {
  font-size: 16px;
  font-weight: 600;
  color: #409eff;
}
</style>