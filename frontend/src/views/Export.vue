<template>
  <div class="export-page">
    <div class="page-header">
      <h2>导出报告</h2>
    </div>

    <el-card class="export-card">
      <div class="export-form">
        <!-- 导出类型 -->
        <div class="form-section">
          <div class="section-label">导出方式</div>
          <div class="export-type-group">
            <div
              class="type-card"
              :class="{ active: exportType === 'all' }"
              @click="exportType = 'all'"
            >
              <div class="type-icon">
                <el-icon><Document /></el-icon>
              </div>
              <div class="type-info">
                <div class="type-name">整体导出</div>
                <div class="type-desc">导出所有坐席的评分数据</div>
              </div>
              <div class="type-check" v-if="exportType === 'all'">
                <el-icon><Check /></el-icon>
              </div>
            </div>

            <div
              class="type-card"
              :class="{ active: exportType === 'agent' }"
              @click="exportType = 'agent'"
            >
              <div class="type-icon">
                <el-icon><User /></el-icon>
              </div>
              <div class="type-info">
                <div class="type-name">按坐席导出</div>
                <div class="type-desc">选择特定坐席进行导出</div>
              </div>
              <div class="type-check" v-if="exportType === 'agent'">
                <el-icon><Check /></el-icon>
              </div>
            </div>
          </div>
        </div>

        <!-- 坐席选择 -->
        <div v-if="exportType === 'agent'" class="form-section">
          <div class="section-label">选择坐席</div>
          <el-select
            v-model="selectedAgent"
            filterable
            placeholder="请选择坐席"
            style="width: 300px"
            :loading="agentLoading"
          >
            <el-option
              v-for="agent in agentList"
              :key="agent.agent_name"
              :label="agent.agent_name"
              :value="agent.agent_name"
            />
          </el-select>
        </div>

        <!-- 时间范围 -->
        <div class="form-section">
          <div class="section-label">时间范围</div>
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD HH:mm:ss"
            :shortcuts="shortcuts"
            style="width: 320px"
          />
        </div>

        <!-- 导出按钮 -->
        <div class="export-actions">
          <el-button
            type="primary"
            size="large"
            :loading="exporting"
            :disabled="(exportType === 'agent' && !selectedAgent) || !dateRange || dateRange.length !== 2"
            @click="handleExport"
          >
            <el-icon v-if="!exporting"><Download /></el-icon>
            导出 Word 报告
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card class="info-card">
      <template #header>
        <span class="card-title">导出说明</span>
      </template>
      <div class="export-info">
        <ul>
          <li>报告包含所选时间范围内的评分数据</li>
          <li>第一页为数据概览，包含核心指标、加分统计、扣分统计</li>
          <li>从第二页开始为录音详情，包含：坐席姓名、加分、扣分、总分、转写文本、扣分情况、加分情况</li>
          <li>按坐席导出时，只包含该坐席的所有录音记录</li>
        </ul>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Download, Document, User, Check } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { now } from '@/utils/timezone'
import api from '@/api'

const exportType = ref('all')
const selectedAgent = ref('')
const agentList = ref([])
const agentLoading = ref(false)
const exporting = ref(false)
const dateRange = ref([])

const shortcuts = [
  {
    text: '近一周',
    value: () => {
      const end = now().toDate()
      const start = now().subtract(6, 'day').toDate()
      return [start, end]
    }
  },
  {
    text: '近一月',
    value: () => {
      const end = now().toDate()
      const start = now().subtract(29, 'day').toDate()
      return [start, end]
    }
  },
  {
    text: '近半年',
    value: () => {
      const end = now().toDate()
      const start = now().subtract(179, 'day').toDate()
      return [start, end]
    }
  },
  {
    text: '近一年',
    value: () => {
      const end = now().toDate()
      const start = now().subtract(364, 'day').toDate()
      return [start, end]
    }
  }
]

async function loadAgents() {
  agentLoading.value = true
  try {
    const res = await api.export.agents()
    agentList.value = res
  } catch (e) {
    console.error(e)
  } finally {
    agentLoading.value = false
  }
}

async function handleExport() {
  // 前端校验
  if (exportType.value === 'agent' && !selectedAgent.value) {
    ElMessage.warning('请选择坐席')
    return
  }
  if (!dateRange.value || dateRange.value.length !== 2) {
    ElMessage.warning('请选择日期范围')
    return
  }

  exporting.value = true
  try {
    const params = { type: exportType.value }
    if (exportType.value === 'agent') {
      params.agent_name = selectedAgent.value
    }
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }

    const response = await api.export.getReport(params)
    const blob = new Blob([response])
    const url = window.URL.createObjectURL(blob)

    const startDate = dateRange.value[0].split(' ')[0].replace(/\//g, '-')
    const endDate = dateRange.value[1].split(' ')[0].replace(/\//g, '-')
    let filename = exportType.value === 'agent'
      ? `坐席报告_${selectedAgent.value}_${startDate}_至_${endDate}.docx`
      : `整体报告_${startDate}_至_${endDate}.docx`

    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

    ElMessage.success('导出成功')
  } catch (e) {
    ElMessage.error('导出失败: ' + e.message)
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  loadAgents()
})
</script>

<style scoped>
.export-page {
  padding: 0;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.export-card {
  background: linear-gradient(135deg, #f8f9ff 0%, #f0f4ff 100%);
  border: none;
}

.export-form {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-label {
  font-size: 14px;
  font-weight: 600;
  color: #606266;
}

.export-type-group {
  display: flex;
  gap: 16px;
}

.type-card {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  background: #fff;
  border: 2px solid #e4e7ed;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s;
  position: relative;
}

.type-card:hover {
  border-color: #409eff;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.1);
}

.type-card.active {
  border-color: #409eff;
  background: linear-gradient(135deg, #f0f7ff 0%, #e8f4ff 100%);
}

.type-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  background: #f0f2ff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: #409eff;
}

.type-card.active .type-icon {
  background: #409eff;
  color: #fff;
}

.type-info {
  flex: 1;
}

.type-name {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.type-desc {
  font-size: 13px;
  color: #909399;
}

.type-check {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #409eff;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 12px;
}

.export-actions {
  padding-top: 8px;
}

.export-actions :deep(.el-button) {
  padding: 12px 32px;
  font-size: 15px;
}

.info-card {
  margin-top: 20px;
}

.card-title {
  font-weight: bold;
  font-size: 15px;
  color: #303133;
}

.export-info ul {
  margin: 0;
  padding-left: 20px;
  color: #606266;
  line-height: 2;
}

.export-info li {
  margin-bottom: 4px;
}
</style>