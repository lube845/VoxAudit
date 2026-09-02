<template>
  <div class="recording-detail">
    <el-page-header @back="goBack" content="录音详情">
      <template #actions>
        <el-button type="success" @click="exportReport" :disabled="!scoringResult">
          <el-icon><Download /></el-icon>
          导出报告
        </el-button>
      </template>
    </el-page-header>

    <el-row :gutter="20" style="margin-top: 20px">
      <!-- 左侧：录音信息 -->
      <el-col :span="8">
        <!-- 播放卡片 -->
        <el-card>
          <template #header>
            <span>基本信息</span>
          </template>
          <el-descriptions :column="1" border v-if="recording">
            <el-descriptions-item label="文件名">{{ recording.file_name }}</el-descriptions-item>
            <el-descriptions-item label="坐席姓名">{{ recording.agent_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="录音时长">{{ recording.duration ? `${Math.floor(recording.duration)}秒` : '-' }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusType(recording.status)">{{ getStatusText(recording.status) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="是否被否决">
              <el-tag :type="recording.is_rejected ? 'danger' : 'success'">
                {{ recording.is_rejected ? '是' : '否' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="上传时间">{{ formatDate(recording.created_at) }}</el-descriptions-item>
            <el-descriptions-item v-if="recording.remark" label="备注">
              <span style="color: #b03424">{{ recording.remark }}</span>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- 评分结果 -->
        <el-card style="margin-top: 20px" v-if="scoringResult">
          <template #header>
            <span>评分结果</span>
          </template>
           <el-descriptions :column="2" border>
            <el-descriptions-item label="加分总分">
              <span style="color: #3d7a4f; font-weight: bold">{{ scoringResult.bonus_score || 0 }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="减分总分">
              <span style="color: #b03424; font-weight: bold">{{ scoringResult.deduction_score || 0 }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="总分" :span="2">
              <span :style="{ color: scoringResult.total_score >= 60 ? '#3d7a4f' : scoringResult.total_score < 0 ? '#b03424' : '' }" style="font-weight: bold">
                {{ scoringResult.total_score >= 0 ? '+' : '' }}{{ scoringResult.total_score }}
              </span>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <!-- 右侧：转写文本和评分明细 -->
      <el-col :span="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>转写文本</span>
              <el-button link type="primary" @click="copyText">复制</el-button>
            </div>
          </template>
          <div class="transcript-container" v-if="recording?.transcript">
            <div v-if="transcriptSegments.length > 0">
              <div
                v-for="(seg, index) in transcriptSegments"
                :key="index"
                class="transcript-segment"
                :class="{ 'agent': seg.speaker === 'agent', 'customer': seg.speaker !== 'agent' }"
              >
                <div class="segment-speaker">
                  {{ getSpeakerLabel(seg.speaker) }}
                  <span class="segment-time">{{ formatTime(seg.start_time) }}</span>
                </div>
                <div class="segment-text" :class="getSegmentClass(seg)">
                  {{ seg.text }}
                </div>
              </div>
            </div>
            <div v-else class="transcript-plain">
              <pre>{{ recording.transcript }}</pre>
            </div>
          </div>
          <el-empty v-else description="暂无转写文本" />
        </el-card>

        <!-- 评分明细 -->
        <el-card style="margin-top: 20px" v-if="scoringResult">
          <template #header>
            <span>评分明细</span>
          </template>

          <!-- 加分项目 -->
          <div v-if="bonusItems.length > 0" style="margin-bottom: 16px">
            <div style="font-weight: bold; margin-bottom: 8px">加分项目</div>
            <el-table :data="bonusItems" stripe size="small">
              <el-table-column prop="item_name" label="考核项" />
              <el-table-column prop="score" label="得分" width="80">
                <template #default="{ row }">
                  <span style="color: #3d7a4f">{{ row.score || 0 }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="is_veto" label="是否否决项" width="100">
                <template #default="{ row }">
                  <el-tag v-if="row.is_veto" type="danger" size="small">是</el-tag>
                  <span v-else style="color: var(--va-muted)">否</span>
                </template>
              </el-table-column>
              <el-table-column prop="matched_text" label="匹配文本" show-overflow-tooltip />
            </el-table>
          </div>

          <!-- 减分项目 -->
          <div v-if="deductionItems.length > 0">
            <div style="font-weight: bold; margin-bottom: 8px">减分项目</div>
            <el-table :data="deductionItems" stripe size="small">
              <el-table-column prop="item_name" label="考核项" />
              <el-table-column prop="score" label="扣分" width="80">
                <template #default="{ row }">
                  <span style="color: #b03424">{{ Math.abs(row.score) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="is_veto" label="是否否决项" width="100">
                <template #default="{ row }">
                  <el-tag v-if="row.is_veto" type="danger" size="small">是</el-tag>
                  <span v-else style="color: var(--va-muted)">否</span>
                </template>
              </el-table-column>
              <el-table-column prop="matched_text" label="匹配文本" show-overflow-tooltip />
            </el-table>
          </div>

          <el-empty v-if="bonusItems.length === 0 && deductionItems.length === 0" description="暂无命中的规则" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Download } from 'lucide-vue-next'
import { formatDate } from '@/utils/timezone'
import api from '@/api'

const route = useRoute()
const router = useRouter()

const recording = ref(null)
const scoringResult = ref(null)

const transcriptSegments = computed(() => {
  if (!recording.value?.transcript_segments) return []
  return recording.value.transcript_segments
})

const bonusItems = computed(() => {
  if (!scoringResult.value?.details) return []
  return scoringResult.value.details
    .filter(d => d.item_type === 'bonus' && d.status === 'matched')
    .sort((a, b) => b.score - a.score)
})

const deductionItems = computed(() => {
  if (!scoringResult.value?.details) return []
  return scoringResult.value.details
    .filter(d => d.item_type === 'deduction' && d.status === 'matched')
    .sort((a, b) => Math.abs(b.score) - Math.abs(a.score))
})

function goBack() {
  router.back()
}

function formatTime(seconds) {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function getSpeakerLabel(speaker) {
  if (speaker === 'agent') return '坐席'
  if (speaker && speaker.startsWith('customer_')) {
    const num = speaker.replace('customer_', '')
    return `客户${num}`
  }
  return '客户'
}

function getStatusType(status) {
  const types = {
    uploading: 'info',
    uploaded: 'success',
    transcribing: 'warning',
    transcribed: 'success',
    scoring: 'warning',
    scored: 'success',
    transcribe_failed: 'danger',
    score_failed: 'danger'
  }
  return types[status] || 'info'
}

function getStatusText(status) {
  const texts = {
    uploading: '上传中',
    uploaded: '已上传',
    transcribing: '转写中',
    transcribed: '已转写',
    scoring: '评分中',
    scored: '已评分',
    transcribe_failed: '转写失败',
    score_failed: '评分失败'
  }
  return texts[status] || status
}


function getSegmentClass(seg) {
  if (!seg.text || !scoringResult.value?.details) {
    return ''
  }
  const matched = scoringResult.value.details.find(d =>
    d.matched_text && d.matched_text.includes(seg.text)
  )
  if (matched) {
    return matched.item_type === 'deduction' ? 'highlight-red' : 'highlight-green'
  }
  return ''
}

async function copyText() {
  const text = transcriptSegments.value.map(s => {
    const speaker = getSpeakerLabel(s.speaker)
    return `${speaker}: ${s.text}`
  }).join('\n')
  const textToCopy = text || recording.value?.transcript || ''
  if (!textToCopy) {
    ElMessage.warning('没有可复制的文本')
    return
  }
  try {
    await navigator.clipboard.writeText(textToCopy)
    ElMessage.success('已复制到剪贴板')
  } catch (e) {
    // 降级方案：使用传统方式复制
    const textarea = document.createElement('textarea')
    textarea.value = textToCopy
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    try {
      document.execCommand('copy')
      ElMessage.success('已复制到剪贴板')
    } catch (e2) {
      ElMessage.error('复制失败，请手动复制')
    } finally {
      document.body.removeChild(textarea)
    }
  }
}

async function exportReport() {
  try {
    const response = await api.export.exportSingleRecording(recording.value.id)
    const url = window.URL.createObjectURL(new Blob([response]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `录音报告_${recording.value.file_name}.docx`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    ElMessage.success('报告导出成功')
  } catch (e) {
    console.error(e)
    ElMessage.error('导出报告失败')
  }
}

async function loadData() {
  const id = route.params.id
  if (!id) {
    console.warn('录音ID不存在，等待路由参数准备好')
    return
  }
  try {
    const recData = await api.recording.get(id)
    recording.value = recData
    // 从 scoring_results 中获取评分结果
    if (recData.scoring_results && recData.scoring_results.length > 0) {
      scoringResult.value = recData.scoring_results[0]
    }
    // 如果转写未完成，轮询等待转写完成
    if (recData.status === 'uploaded' || recData.status === 'transcribing') {
      pollTranscriptionResult()
    }
  } catch (e) {
    console.error(e)
  }
   // 兼容单独调用 score 接口的方式（如果 scoring_results 为空）
  if (!scoringResult.value) {
    const scoreId = route.params.id
    if (!scoreId) {
      console.warn('录音ID不存在，跳过score查询')
    } else {
      try {
        const scoreData = await api.recording.getScore(scoreId)
        scoringResult.value = scoreData
      } catch (e) {
        console.error(e)
      }
    }
  }
}

async function pollTranscriptionResult() {
  const maxAttempts = 60
  const interval = 3000
  for (let i = 0; i < maxAttempts; i++) {
    const pollId = route.params.id
    if (!pollId) {
      // ID 还没准备好，短暂等待后重试
      await new Promise(resolve => setTimeout(resolve, 1000))
      continue
    }
    await new Promise(resolve => setTimeout(resolve, interval))
    try {
      const recData = await api.recording.get(pollId)
      recording.value = recData
      // 转写完成或失败，停止轮询
      if (recData.status === 'transcribed' || recData.status === 'scoring' || recData.status === 'scored') {
        break
      }
      if (recData.status === 'transcribe_failed') {
        break
      }
    } catch (e) {
      console.error(e)
    }
  }
}

onMounted(() => {
  loadData()
})

// 监听路由变化，防止 ID 未准备好就调用 API
watch(() => route.params.id, (newId) => {
  if (newId) {
    loadData()
  }
}, { immediate: false })
</script>

<style scoped>
.recording-detail {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.score-section {
  text-align: center;
  padding: 10px;
}
.score-section-title {
  font-size: 14px;
  color: var(--va-muted);
  margin-bottom: 8px;
}
.score-section .bonus {
  color: #3d7a4f;
}
.score-section .deduction {
  color: #b03424;
}
.score-info {
  text-align: center;
  padding: 20px;
}

.score-value {
  font-size: 48px;
  font-weight: bold;
  color: #3d7a4f;
}

.score-value.rejected {
  color: #b03424;
}

.score-label {
  color: var(--va-muted);
  margin-top: 10px;
}

.result-status {
  display: flex;
  justify-content: center;
  gap: 10px;
}

.transcript-container {
  max-height: 500px;
  overflow-y: auto;
}

.transcript-segment {
  padding: 10px 12px;
  margin-bottom: 8px;
  border-radius: var(--va-radius-sm);
  border-left: 2px solid transparent;
  transition: background var(--va-duration) var(--va-ease);
}

.transcript-segment:hover {
  background: var(--va-paper-deep);
}

.transcript-segment.agent {
  background: var(--va-accent-soft);
  border-left-color: var(--va-accent);
}

.transcript-segment.customer {
  background: var(--va-paper-deep);
  border-left-color: var(--va-hairline-dark);
}

.segment-speaker {
  font-size: 12px;
  color: var(--va-muted);
  margin-bottom: 5px;
}

.segment-time {
  margin-left: 10px;
}

.segment-text {
  font-size: 14px;
  line-height: 1.6;
}

.highlight-red {
  background: #f7e4e1;
  color: #b03424;
  padding: 2px 5px;
  border-radius: 3px;
}

.highlight-green {
  background: #e3eee4;
  color: #3d7a4f;
  padding: 2px 5px;
  border-radius: 3px;
}

.transcript-plain {
  padding: 10px;
}

.transcript-plain pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-size: 14px;
  line-height: 1.6;
}

.type-bubble {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  font-weight: bold;
  font-size: 14px;
}
.type-bubble.bonus {
  background-color: #3d7a4f;
  color: white;
}
.type-bubble.deduction {
  background-color: #b03424;
  color: white;
}
</style>