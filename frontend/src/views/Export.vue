<template>
  <div class="export-page">
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
                <el-icon><FileText /></el-icon>
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
import { Download, FileText, User, Check } from 'lucide-vue-next'
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

.export-card {
  background: #fff;
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
  font-size: 12.5px;
  font-weight: 600;
  color: var(--va-muted);
  letter-spacing: 0.08em;
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
  border: 1px solid var(--va-hairline-dark);
  border-radius: var(--va-radius-md);
  cursor: pointer;
  transition: border-color var(--va-duration) var(--va-ease), background var(--va-duration) var(--va-ease);
  position: relative;
}

.type-card:hover {
  border-color: var(--va-accent);
}

.type-card.active {
  border-color: var(--va-accent);
  border-width: 1px;
  box-shadow: inset 0 0 0 1px var(--va-accent);
  background: var(--va-accent-soft);
}

.type-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--va-radius-sm);
  background: var(--va-paper-deep);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--va-ink-soft);
  transition: all var(--va-duration) var(--va-ease);
}

.type-card.active .type-icon {
  background: var(--va-accent);
  color: #fff;
}

.type-info {
  flex: 1;
}

.type-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--va-ink);
  margin-bottom: 4px;
}

.type-desc {
  font-size: 12.5px;
  color: var(--va-muted);
}

.type-check {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--va-accent);
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
  font-family: var(--va-font-display);
  font-weight: 700;
  font-size: 15.5px;
  color: var(--va-ink);
  letter-spacing: 0.02em;
}

.export-info ul {
  margin: 0;
  padding-left: 20px;
  color: var(--va-ink-soft);
  line-height: 2;
}

.export-info li {
  margin-bottom: 4px;
}
</style>