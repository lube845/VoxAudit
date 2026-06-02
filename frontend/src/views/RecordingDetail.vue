<template>
  <div class="recording-detail">
    <el-page-header @back="goBack" content="录音详情">
      <template #actions>
        <el-button type="primary" @click="playAudio" :disabled="!recording">
          <el-icon><VideoPlay /></el-icon>
          播放录音
        </el-button>
        <el-button type="success" @click="exportReport" :disabled="!scoringResult">
          <el-icon><Download /></el-icon>
          导出报告
        </el-button>
      </template>
    </el-page-header>

    <el-row :gutter="20" style="margin-top: 20px">
      <!-- 左侧：录音信息 -->
      <el-col :span="8">
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
              <el-button link type="warning" v-if="recording.status === 'transcribe_failed'" @click="retryTranscribe" style="margin-left: 8px">重试转写</el-button>
              <el-button link type="warning" v-if="recording.status === 'score_failed'" @click="retryScore" style="margin-left: 8px">重试评分</el-button>
            </el-descriptions-item>
            <el-descriptions-item label="是否被否决">
              <el-tag :type="recording.is_rejected ? 'danger' : 'success'">
                {{ recording.is_rejected ? '是' : '否' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="上传时间">{{ formatDate(recording.created_at) }}</el-descriptions-item>
            <el-descriptions-item v-if="recording.remark" label="备注">
              <span style="color: #f56c6c">{{ recording.remark }}</span>
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
              <span style="color: #67c23a; font-weight: bold">+{{ scoringResult.bonus_score || 0 }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="减分总分">
              <span style="color: #f56c6c; font-weight: bold">-{{ scoringResult.deduction_score || 0 }}</span>
            </el-descriptions-item>
          </el-descriptions>

          <!-- 加分项目 -->
          <div v-if="bonusItems.length > 0" style="margin-top: 16px">
            <div style="font-weight: bold; margin-bottom: 8px">加分项目</div>
            <el-table :data="bonusItems" stripe size="small">
              <el-table-column prop="item_name" label="考核项" />
              <el-table-column prop="score" label="得分" width="80">
                <template #default="{ row }">
                  <span style="color: #67c23a">+{{ row.score || 0 }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- 减分项目 -->
          <div v-if="deductionItems.length > 0" style="margin-top: 16px">
            <div style="font-weight: bold; margin-bottom: 8px">减分项目</div>
            <el-table :data="deductionItems" stripe size="small">
              <el-table-column prop="item_name" label="考核项" />
              <el-table-column prop="score" label="扣分" width="80">
                <template #default="{ row }">
                  <span style="color: #f56c6c">-{{ Math.abs(row.score) }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
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
                @click="seekTo(seg.start_time)"
              >
                <div class="segment-speaker">
                  {{ seg.speaker === 'agent' ? '坐席' : '客户' }}
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
          <el-table :data="scoringResult.details" stripe>
            <el-table-column prop="item_name" label="考核项" />
            <el-table-column prop="item_type" label="类型" width="60">
              <template #default="{ row }">
                <span class="type-bubble" :class="row.item_type === 'deduction' ? 'deduction' : 'bonus'">
                  {{ row.item_type === 'deduction' ? '-' : '+' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getDetailStatusType(row.status)">
                  {{ getDetailStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="score" label="得分" width="80">
              <template #default="{ row }">
                {{ row.score }}/{{ row.max_score }}
              </template>
            </el-table-column>
            <el-table-column prop="matched_text" label="匹配文本" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { VideoPlay, Download } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
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
  return scoringResult.value.details.filter(d => d.item_type === 'bonus')
})

const deductionItems = computed(() => {
  if (!scoringResult.value?.details) return []
  return scoringResult.value.details.filter(d => d.item_type === 'deduction')
})

function goBack() {
  router.back()
}

function formatDate(date) {
  return date ? dayjs(date).format('YYYY-MM-DD HH:mm:ss') : '-'
}

function formatTime(seconds) {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
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

function getDetailStatusType(status) {
  const types = { done: 'success', not_done: 'info', wrong: 'danger' }
  return types[status] || 'info'
}

function getDetailStatusText(status) {
  const texts = { done: '已做到', not_done: '未做到', wrong: '做错' }
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

function copyText() {
  const text = transcriptSegments.value.map(s => s.text).join('\n')
  if (!text && recording.value?.transcript) {
    navigator.clipboard.writeText(recording.value.transcript)
  } else {
    navigator.clipboard.writeText(text)
  }
  ElMessage.success('已复制到剪贴板')
}

function seekTo(time) {
  console.log('seek to', time)
}

async function retryTranscribe() {
  try {
    await api.recording.retryTranscribe(recording.value.id)
    ElMessage.success('已重新触发转写')
    recording.value.status = 'transcribing'
  } catch (e) {
    ElMessage.error('重试转写失败')
  }
}

async function handleRetry() {
  if (recording.value.status === 'transcribe_failed') {
    retryTranscribe()
  } else {
    retryScore()
  }
}

async function retryScore() {
  try {
    await api.recording.retryScore(recording.value.id)
    ElMessage.success('已重新触发评分')
    recording.value.status = 'scoring'
    // 轮询等待评分完成
    pollScoringResult()
  } catch (e) {
    ElMessage.error('重试评分失败')
  }
}

async function pollScoringResult() {
  const maxAttempts = 30
  const interval = 3000
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(resolve => setTimeout(resolve, interval))
    try {
      const id = route.params.id
      const recData = await api.recording.get(id)
      recording.value = recData
      if (recData.scoring_results && recData.scoring_results.length > 0) {
        scoringResult.value = recData.scoring_results[0]
      }
      if (recData.status === 'scored' || recData.status === 'score_failed') {
        break
      }
    } catch (e) {
      console.error(e)
    }
  }
}

async function playAudio() {
  try {
    const res = await api.recording.getPlayUrl(recording.value.id)
    window.open(res.play_url, '_blank')
  } catch (e) {
    console.error(e)
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
  try {
    const id = route.params.id
    const recData = await api.recording.get(id)
    recording.value = recData
    // 从 scoring_results 中获取评分结果
    if (recData.scoring_results && recData.scoring_results.length > 0) {
      scoringResult.value = recData.scoring_results[0]
    }
  } catch (e) {
    console.error(e)
  }
  // 兼容单独调用 score 接口的方式（如果 scoring_results 为空）
  if (!scoringResult.value) {
    try {
      const id = route.params.id
      const scoreData = await api.recording.getScore(id)
      scoringResult.value = scoreData
    } catch (e) {
      console.error(e)
    }
  }
}

onMounted(() => {
  loadData()
})
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
  color: #909399;
  margin-bottom: 8px;
}
.score-section .bonus {
  color: #67c23a;
}
.score-section .deduction {
  color: #f56c6c;
}
.score-info {
  text-align: center;
  padding: 20px;
}

.score-value {
  font-size: 48px;
  font-weight: bold;
  color: #67c23a;
}

.score-value.rejected {
  color: #f56c6c;
}

.score-label {
  color: #999;
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
  padding: 10px;
  margin-bottom: 10px;
  border-radius: 5px;
  cursor: pointer;
  transition: background 0.3s;
}

.transcript-segment:hover {
  background: #f5f7fa;
}

.transcript-segment.agent {
  background: #e6f7ff;
}

.transcript-segment.customer {
  background: #f6ffed;
}

.segment-speaker {
  font-size: 12px;
  color: #999;
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
  background: #ffebeb;
  color: #f56c6c;
  padding: 2px 5px;
  border-radius: 3px;
}

.highlight-green {
  background: #f0f9eb;
  color: #67c23a;
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
  background-color: #67c23a;
  color: white;
}
.type-bubble.deduction {
  background-color: #f56c6c;
  color: white;
}
</style>