<template>
  <div class="recordings-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>录音列表</span>
          <div>
            <el-button
              type="danger"
              :disabled="selectedRecords.length === 0"
              @click="batchDeleteRecords"
            >
              批量删除{{ selectedRecords.length > 0 ? ` (${selectedRecords.length})` : '' }}
            </el-button>
            <el-button
              type="warning"
              :disabled="selectedRecords.length === 0"
              @click="batchRetryRecords"
            >
              批量重试{{ selectedRecords.length > 0 ? ` (${selectedRecords.length})` : '' }}
            </el-button>
            <el-button type="primary" @click="showUploadDialog = true">
              <el-icon><Upload /></el-icon>
              上传录音
            </el-button>
            <el-button @click="handleRefresh" :loading="refreshing">
              <el-icon><RefreshRight /></el-icon>
              刷新状态
            </el-button>
          </div>
        </div>
      </template>

      <!-- 搜索条件 -->
      <div class="search-bar">
        <el-input
          v-model="queryParams.keyword"
          placeholder="文件名"
          clearable
          style="width: 150px"
          @input="handleQuery"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select
          v-model="queryParams.agent_name"
          placeholder="坐席姓名"
          clearable
          filterable
          style="width: 150px"
          @change="handleQuery"
        >
          <el-option
            v-for="agent in agentOptions"
            :key="agent.agent_name"
            :label="agent.agent_name"
            :value="agent.agent_name"
          />
        </el-select>
        <el-select
          v-model="queryParams.status"
          placeholder="录音状态"
          clearable
          style="width: 150px"
          @change="handleQuery"
        >
          <el-option label="上传中" value="uploading" />
          <el-option label="已上传" value="uploaded" />
          <el-option label="转写中" value="transcribing" />
          <el-option label="已转写" value="transcribed" />
          <el-option label="评分中" value="scoring" />
          <el-option label="已评分" value="scored" />
          <el-option label="转写失败" value="transcribe_failed" />
          <el-option label="评分失败" value="score_failed" />
        </el-select>
        <el-select
          v-model="queryParams.is_rejected"
          placeholder="是否否决"
          clearable
          style="width: 120px"
          @change="handleQuery"
        >
          <el-option label="是" :value="true" />
          <el-option label="否" :value="false" />
        </el-select>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD HH:mm:ss"
          :shortcuts="shortcuts"
          style="width: 200px"
          @change="handleDateChange"
        />
        <div class="score-filter" :class="{ active: queryParams.score_dimension || queryParams.score_operator || queryParams.score_value }">
          <span class="score-filter-label">分数</span>
          <el-select
            v-model="queryParams.score_dimension"
            placeholder="维度"
            clearable
            style="width: 80px"
            @change="handleScoreFilterChange"
          >
            <el-option label="加分" value="bonus" />
            <el-option label="扣分" value="deduction" />
            <el-option label="总分" value="total" />
          </el-select>
          <el-select
            v-model="queryParams.score_operator"
            placeholder="条件"
            clearable
            style="width: 100px"
            @change="handleScoreFilterChange"
          >
            <el-option label="大于" value="gt" />
            <el-option label="大于等于" value="gte" />
            <el-option label="等于" value="eq" />
            <el-option label="小于等于" value="lte" />
            <el-option label="小于" value="lt" />
          </el-select>
          <el-input
            v-model="queryParams.score_value"
            placeholder="分值"
            clearable
            style="width: 80px"
            type="number"
            @input="handleScoreFilterChange"
          />
        </div>
        <span class="total-count">共 {{ total }} 条</span>
      </div>

      <!-- 表格 -->
      <el-table
        :data="list"
        v-loading="loading"
        stripe
        class="recordings-table"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="agent_name" label="坐席姓名" width="120" show-overflow-tooltip />
        <el-table-column prop="file_name" label="文件名" min-width="200" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_score" label="总分" width="80" align="center">
          <template #default="{ row }">
            <span v-if="row.total_score !== null" :style="{ color: row.total_score >= 60 ? '#67c23a' : '#f56c6c' }">
              {{ row.total_score >= 0 ? '+' : '' }}{{ row.total_score }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="bonus_score" label="加分" width="80">
          <template #default="{ row }">
            <span v-if="row.bonus_score != null" style="color: #67c23a">{{ row.bonus_score.toFixed(1) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="deduction_score" label="扣分" width="80">
          <template #default="{ row }">
            <span v-if="row.deduction_score != null" style="color: #f56c6c">{{ row.deduction_score.toFixed(1) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="is_rejected" label="是否否决" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_rejected === true" type="danger" size="small">是</el-tag>
            <el-tag v-else-if="row.is_rejected === false" type="info" size="small">否</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewDetail(row.id)">详情</el-button>
            <el-button link type="warning" v-if="row.status === 'transcribe_failed' || row.status === 'score_failed' || row.status === 'scored'" @click="handleRetry(row)">重试</el-button>
            <el-button link type="danger" @click="deleteRecord(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.page_size"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 上传对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传录音" width="600px" destroy-on-close>
      <el-form :model="uploadForm" ref="uploadFormRef" label-width="100px">
        <el-form-item label="坐席姓名 *">
          <el-input v-model="uploadForm.agent_name" placeholder="请输入坐席姓名" clearable />
        </el-form-item>
        <el-form-item label="录音文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :multiple="true"
            :drag="true"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            :file-list="fileList"
            accept=".mp3,.wav,.amr,.m4a,.zip"
          >
            <div class="upload-dragger">
              <el-icon class="el-icon--upload"><Upload /></el-icon>
              <div class="el-upload__text">
                将文件拖到此处，或<em>点击上传</em>
              </div>
            </div>
            <template #tip>
              <div class="upload-tip">支持 MP3/WAV/AMR/M4A 及 ZIP 压缩包（最大支持500MB，自动提取音频文件）</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item v-if="uploadQueue.length > 0" label="上传进度">
          <div class="upload-queue">
            <div v-for="(item, index) in uploadQueue" :key="index" class="upload-item">
              <span class="file-name">{{ item.name }}</span>
              <el-progress :percentage="item.percentage" :status="item.status" />
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeUploadDialog">取消</el-button>
        <el-button type="primary" @click="handleUpload" :loading="uploading" :disabled="fileList.length === 0">
          上传全部
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Upload, RefreshRight } from '@element-plus/icons-vue'
import { formatDate, now } from '@/utils/timezone'
import CryptoJS from 'crypto-js'
import api from '@/api'

const router = useRouter()

const loading = ref(false)
const refreshing = ref(false)
const uploading = ref(false)
const isProcessingZip = ref(false)
const list = ref([])
const total = ref(0)
const agentOptions = ref([])
const showUploadDialog = ref(false)
const fileList = ref([])
const uploadQueue = ref([])
const selectedRecords = ref([])

const queryParams = reactive({
  keyword: '',
  agent_name: '',
  status: '',
  is_rejected: '',
  start_date: '',
  end_date: '',
  score_dimension: '',
  score_operator: '',
  score_value: '',
  page: 1,
  page_size: 20
})

const dateRange = ref([])

const shortcuts = [
  { text: '近一周', value: () => [now().subtract(6, 'day').toDate(), now().toDate()] },
  { text: '近一月', value: () => [now().subtract(29, 'day').toDate(), now().toDate()] },
  { text: '近半年', value: () => [now().subtract(179, 'day').toDate(), now().toDate()] },
  { text: '近一年', value: () => [now().subtract(364, 'day').toDate(), now().toDate()] }
]

const uploadForm = reactive({ agent_id: '', agent_name: '' })
const uploadFormRef = ref(null)

// 状态映射
const statusMap = {
  uploading: { type: 'info', text: '上传中' },
  uploaded: { type: 'success', text: '已上传' },
  transcribing: { type: 'warning', text: '转写中' },
  transcribed: { type: 'success', text: '已转写' },
  scoring: { type: 'warning', text: '评分中' },
  scored: { type: 'success', text: '已评分' },
  transcribe_failed: { type: 'danger', text: '转写失败' },
  score_failed: { type: 'danger', text: '评分失败' }
}

function getStatusType(status) {
  return statusMap[status]?.type || 'info'
}

function getStatusText(status) {
  return statusMap[status]?.text || status
}


// 数据加载
async function loadData() {
  loading.value = true
  try {
    const res = await api.recording.list(queryParams)
    list.value = res.items || []
    total.value = res.total || 0
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function loadAgentOptions() {
  try {
    const res = await api.agent.list()
    agentOptions.value = res || []
  } catch (e) {
    console.error(e)
  }
}

async function handleRefresh() {
  refreshing.value = true
  try {
    await loadData()
    ElMessage.success('刷新成功')
  } catch (e) {
    console.error(e)
  } finally {
    refreshing.value = false
  }
}

// 搜索相关
function handleQuery() {
  queryParams.page = 1
  loadData()
}

function handleDateChange(val) {
  if (val && val.length === 2) {
    queryParams.start_date = val[0]
    queryParams.end_date = val[1]
  } else {
    queryParams.start_date = ''
    queryParams.end_date = ''
  }
  handleQuery()
}

function handleScoreFilterChange() {
  handleQuery()
}

function handleSizeChange(val) {
  queryParams.page_size = val
  loadData()
}

function handleCurrentChange(val) {
  queryParams.page = val
  loadData()
}

// 选择相关
function handleSelectionChange(selection) {
  selectedRecords.value = selection
}

// 操作
async function viewDetail(id) {
  router.push(`/recordings/${id}`)
}


async function retryTranscribe(row) {
  try {
    await api.recording.triggerTranscribe(row.id)
    ElMessage.success('已重新触发转写')
    loadData()
  } catch (e) {
    ElMessage.error('重试转写失败')
  }
}

async function handleRetry(row) {
  if (row.status === 'transcribe_failed') {
    retryTranscribe(row)
  } else if (row.status === 'score_failed') {
    retryScore(row)
  } else if (row.status === 'scored') {
    retryScored(row)
  }
}

async function retryScore(row) {
  try {
    await api.recording.triggerScore(row.id)
    ElMessage.success('已重新触发评分')
    loadData()
  } catch (e) {
    ElMessage.error('重试评分失败')
  }
}

async function retryScored(row) {
  try {
    await ElMessageBox.confirm('确定要重试该录音吗？将重新进行所有流程。', '提示')
    await api.recording.batchRetry([row.id])
    ElMessage.success('已提交重试任务')
    loadData()
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

async function batchRetryRecords() {
  if (selectedRecords.value.length === 0) return
  try {
    await ElMessageBox.confirm(`确定要重试选中的 ${selectedRecords.value.length} 条录音吗？将重新进行所有流程。`, '提示')
    const ids = selectedRecords.value.map(r => r.id)
    await api.recording.batchRetry(ids)
    ElMessage.success(`已提交 ${ids.length} 条重试任务`)
    selectedRecords.value = []
    loadData()
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

async function deleteRecord(row) {
  try {
    await ElMessageBox.confirm('确定要删除该录音吗？', '提示')
    await api.recording.delete(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

async function batchDeleteRecords() {
  if (selectedRecords.value.length === 0) return
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${selectedRecords.value.length} 条录音吗？`, '提示')
    const ids = selectedRecords.value.map(r => r.id)
    await Promise.all(ids.map(id => api.recording.delete(id)))
    ElMessage.success(`成功删除 ${ids.length} 条录音`)
    selectedRecords.value = []
    loadData()
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

// 上传相关
async function calculateFileMD5(file) {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      const wordArray = CryptoJS.lib.WordArray.create(e.target.result)
      resolve(CryptoJS.MD5(wordArray).toString())
    }
    reader.readAsArrayBuffer(file)
  })
}

function getMimeType(ext) {
  const map = { mp3: 'audio/mpeg', wav: 'audio/wav', amr: 'audio/amr', m4a: 'audio/mp4', flac: 'audio/flac', ogg: 'audio/ogg', webm: 'audio/webm' }
  return map[ext] || 'audio/mpeg'
}

async function handleFileChange(file, files) {
  const ext = file.name.split('.').pop().toLowerCase()
  const allowedExts = ['mp3', 'wav', 'amr', 'm4a', 'zip']

  if (!allowedExts.includes(ext)) {
    ElMessage.error('不支持的文件格式，仅支持 MP3/WAV/AMR/M4A/ZIP 格式')
    // 从 fileList 中移除无效文件，使用 files 参数过滤（排除无效扩展名）
    const allowedFiles = files.filter(f => allowedExts.includes(f.name.split('.').pop().toLowerCase()))
    fileList.value = allowedFiles
    return
  }

  if (ext === 'zip') {
    const MAX_ZIP_SIZE = 500 * 1024 * 1024 // 500MB
    if (file.size > MAX_ZIP_SIZE) {
      ElMessage.error('ZIP 压缩包最大支持 500MB')
      const allowedFiles = files.filter(f => {
        const e = f.name.split('.').pop().toLowerCase()
        return allowedExts.includes(e) && (e !== 'zip' || f.size <= MAX_ZIP_SIZE)
      })
      fileList.value = allowedFiles
      return
    }
    if (isProcessingZip.value) return
    isProcessingZip.value = true

    try {
      const JSZipModule = await import('jszip')
      const zip = new JSZipModule.default()
      const zipContent = await file.raw.arrayBuffer()
      await zip.loadAsync(zipContent)

      const audioFiles = []
      const audioExts = ['mp3', 'wav', 'amr', 'm4a', 'flac', 'ogg', 'webm']

      for (const [name, zipEntry] of Object.entries(zip.files)) {
        if (!zipEntry.dir) {
          const fileExt = name.split('.').pop().toLowerCase()
          if (audioExts.includes(fileExt)) {
            const blob = await zipEntry.async('blob')
            let baseName = name.split('/').pop().split('\\').pop()
            let finalName = baseName
            let counter = 1
            while (audioFiles.some(f => f.name === finalName)) {
              const parts = baseName.split('.')
              if (parts.length >= 2) {
                const ext = parts.pop()
                finalName = parts.join('.') + '_' + counter + '.' + ext
              } else {
                finalName = baseName + '_' + counter
              }
              counter++
            }
            const rawFile = new File([blob], finalName, { type: getMimeType(fileExt) })
            audioFiles.push({ name: finalName, raw: rawFile })
          }
        }
      }

      if (audioFiles.length === 0) {
        ElMessage.warning('ZIP中未找到音频文件')
        fileList.value = []
        return
      }

      ElMessage.info('从ZIP中提取了' + audioFiles.length + '个音频文件')
      fileList.value = audioFiles.map(af => ({ name: af.name, size: af.raw.size, raw: af.raw }))
    } catch (e) {
      ElMessage.error('解压ZIP失败: ' + e.message)
      fileList.value = files
    } finally {
      isProcessingZip.value = false
    }
  } else {
    fileList.value = files
  }
}

function handleFileRemove(file, files) {
  fileList.value = files
}

function closeUploadDialog() {
  showUploadDialog.value = false
  resetUploadForm()
}

function resetUploadForm() {
  fileList.value = []
  uploadQueue.value = []
  if (uploadFormRef.value) uploadFormRef.value.resetFields()
}

async function handleUpload() {
  if (fileList.value.length === 0) {
    ElMessage.warning('请选择文件')
    return
  }
  if (!uploadForm.agent_name?.trim()) {
    ElMessage.warning('请输入坐席姓名')
    return
  }

  uploading.value = true
  uploadQueue.value = fileList.value.map(f => ({ name: f.name, percentage: 0, status: '' }))

  try {
    for (let i = 0; i < fileList.value.length; i++) {
      const file = fileList.value[i]
      const queueItem = uploadQueue.value[i]

      queueItem.status = 'calculating'
      const file_md5 = await calculateFileMD5(file.raw)
      queueItem.status = ''

      queueItem.status = 'init'
      const initRes = await api.recording.initUpload({
        file_name: file.name,
        file_size: file.size,
        file_md5: file_md5,
        file_type: file.name.split('.').pop().toLowerCase(),
        agent_name: uploadForm.agent_name
      })

      if (initRes.exists) {
        queueItem.status = 'warning'
        queueItem.percentage = 100
        ElMessage.warning(`文件 ${file.name} 已存在，将跳过`)
        continue
      }

      queueItem.status = 'uploading'
      let progress = 0
      const progressInterval = setInterval(() => {
        progress = Math.min(progress + 10, 90)
        queueItem.percentage = progress
      }, 200)

      const formData = new FormData()
      formData.append('file', file.raw)
      await api.recording.upload(initRes.recording_id, formData)

      clearInterval(progressInterval)
      queueItem.percentage = 100
      queueItem.status = 'success'
    }

    ElMessage.success('上传完成')
    closeUploadDialog()
    loadData()
  } catch (e) {
    console.error(e)
    uploadQueue.value.forEach(item => {
      if (item.status !== 'success' && item.status !== 'warning') {
        item.status = 'exception'
      }
    })
  } finally {
    uploading.value = false
  }
}

onMounted(() => {
  loadData()
  loadAgentOptions()
})
</script>

<style scoped>
.recordings-page {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.score-filter {
  display: flex;
  align-items: center;
  gap: 0;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 0 8px;
  background: #fafafa;
}

.score-filter.active {
  border-color: #409eff;
  background: #fff;
}

.score-filter-label {
  color: #909399;
  font-size: 13px;
  margin-right: 4px;
  white-space: nowrap;
}

.score-filter :deep(.el-input__wrapper) {
  box-shadow: none !important;
  background: transparent;
}

.score-filter :deep(.el-input__inner) {
  font-size: 13px;
}

.score-filter :deep(.el-input) {
  --el-input-border-color: transparent;
}

.score-filter :deep(.el-input:hover .el-input__wrapper),
.score-filter :deep(.el-input.is-focus .el-input__wrapper) {
  box-shadow: none !important;
  background: transparent;
}

.score-filter :deep(input[type="number"]) {
  -moz-appearance: textfield;
}

.score-filter :deep(input[type="number"]::-webkit-outer-spin-button),
.score-filter :deep(input[type="number"]::-webkit-inner-spin-button) {
  -webkit-appearance: none;
  margin: 0;
}

.total-count {
  color: #909399;
  font-size: 13px;
}

.recordings-table {
  margin-top: 16px;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.upload-dragger {
  padding: 40px 20px;
  text-align: center;
}

.upload-dragger .el-icon--upload {
  font-size: 48px;
  color: #909399;
  margin-bottom: 16px;
}

.upload-dragger .el-upload__text {
  color: #606266;
}

.upload-dragger .el-upload__text em {
  color: #409eff;
  font-style: normal;
}

.upload-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

.upload-queue {
  max-height: 200px;
  overflow-y: auto;
}

.upload-item {
  margin-bottom: 8px;
}

.upload-item .file-name {
  display: block;
  font-size: 13px;
  color: #606266;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.el-card__header) {
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
  background: #fafafa;
}
</style>