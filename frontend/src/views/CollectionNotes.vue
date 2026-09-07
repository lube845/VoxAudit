<template>
  <div class="collection-notes-page">
    <!-- 顶部统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-label">总通话数</div>
          <div class="stat-value">{{ stats.totalCalls.toLocaleString() }}</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-label">今日通话</div>
          <div class="stat-value">{{ stats.todayCalls.toLocaleString() }}</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-label">平均通话时长</div>
          <div class="stat-value">{{ formatDuration(stats.avgDuration) }}</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-label">AI催记生成数</div>
          <div class="stat-value">{{ stats.aiNotesCount.toLocaleString() }}</div>
        </div>
      </el-col>
    </el-row>

    <!-- 筛选区 -->
    <el-card class="filter-card" shadow="never">
      <el-form :inline="true" class="filter-form">
        <el-form-item label="座席工号">
          <el-input
            v-model="filters.agentId"
            placeholder="请输入工号"
            clearable
            style="width: 180px"
          />
        </el-form-item>
        <el-form-item label="座席名称">
          <el-input
            v-model="filters.agentName"
            placeholder="请输入姓名"
            clearable
            style="width: 180px"
          />
        </el-form-item>
        <el-form-item label="分机号">
          <el-input
            v-model="filters.extension"
            placeholder="请输入分机号"
            clearable
            style="width: 180px"
          />
        </el-form-item>
        <el-form-item label="呼叫号码">
          <el-input
            v-model="filters.phone"
            placeholder="请输入手机号"
            clearable
            style="width: 180px"
          />
        </el-form-item>
        <el-form-item label="开始时间">
          <el-date-picker
            v-model="filters.startTime"
            type="datetime"
            placeholder="年/月/日 --:--"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-date-picker
            v-model="filters.endTime"
            type="datetime"
            placeholder="年/月/日 --:--"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item class="filter-actions">
          <el-button :loading="refreshing" @click="handleRefresh">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
          <el-button @click="handleReset">重置</el-button>
          <el-button type="primary" @click="handleQuery">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 通话列表 -->
    <el-card class="table-card" shadow="never">
      <el-table
        :data="pagedList"
        v-loading="loading"
        stripe
        class="calls-table"
      >
        <el-table-column prop="callId" label="通话 ID" min-width="160" show-overflow-tooltip />
        <el-table-column prop="agentId" label="座席工号" width="110" />
        <el-table-column prop="agentName" label="座席名称" width="110" />
        <el-table-column prop="extension" label="分机号" width="100" />
        <el-table-column prop="phone" label="呼叫号码" width="140" />
        <el-table-column prop="startTime" label="通话开始时间" width="170" />
        <el-table-column prop="endTime" label="通话结束时间" width="170" />
        <el-table-column prop="durationText" label="通话时长" width="100" />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewStructuredNote(row)">
              查看结构化催记
            </el-button>
            <el-button link type="primary" @click="viewUnstructuredNote(row)">
              查看非结构化催记
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="filteredList.length"
          layout="total, sizes, prev, pager, next, jumper"
          background
        />
      </div>
    </el-card>

    <!-- 催记详情对话框 -->
    <el-dialog
      v-model="noteDialog.visible"
      :title="noteDialog.title"
      width="1180px"
      top="5vh"
      destroy-on-close
      :before-close="handleBeforeClose"
      class="note-dialog"
    >
      <!-- 顶部元数据 -->
      <div class="note-meta">
        <div class="note-meta-item">
          <span class="note-meta-label">通话 ID</span>
          <span class="note-meta-value">{{ noteDialog.data?.callId }}</span>
        </div>
        <div class="note-meta-item">
          <span class="note-meta-label">座席</span>
          <span class="note-meta-value">{{ noteDialog.data?.agentName }}（{{ noteDialog.data?.agentId }}）</span>
        </div>
        <div class="note-meta-item">
          <span class="note-meta-label">分机号</span>
          <span class="note-meta-value">{{ noteDialog.data?.extension }}</span>
        </div>
        <div class="note-meta-item">
          <span class="note-meta-label">呼叫号码</span>
          <span class="note-meta-value">{{ noteDialog.data?.phone }}</span>
        </div>
        <div class="note-meta-item">
          <span class="note-meta-label">通话时长</span>
          <span class="note-meta-value">{{ noteDialog.data?.durationText }}</span>
        </div>
        <div class="note-meta-item">
          <span class="note-meta-label">开始时间</span>
          <span class="note-meta-value">{{ noteDialog.data?.startTime }}</span>
        </div>
        <div class="note-meta-item">
          <span class="note-meta-label">结束时间</span>
          <span class="note-meta-value">{{ noteDialog.data?.endTime }}</span>
        </div>
      </div>

      <!-- 三列内容 -->
      <div class="note-columns">
        <div class="note-col">
          <div class="note-col-header">录音转写原文</div>
          <div class="note-col-body transcript">{{ noteDialog.transcript }}</div>
        </div>

        <div class="note-col">
          <div class="note-col-header">
            <span>原始催记内容</span>
            <el-tag size="small" type="info" effect="plain">不可编辑</el-tag>
          </div>
          <div class="note-col-body readonly">{{ noteDialog.originalNote }}</div>
        </div>

        <div class="note-col">
          <div class="note-col-header">
            <span>返现原始催记</span>
            <el-button link type="primary" size="small" @click="copyOriginal">
              <el-icon><CopyDocument /></el-icon>
              一键复制
            </el-button>
          </div>
          <el-input
            v-model="noteDialog.editedNote"
            type="textarea"
            :rows="14"
            resize="none"
            class="note-col-body edit-area"
            placeholder="可在右侧对催记内容进行校对修改..."
          />
        </div>
      </div>

      <template #footer>
        <el-button @click="handleCancel">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveNote">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Refresh, CopyDocument } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

// ---------- 模拟数据 ----------
// 真实部署时这里应替换为后端接口，例如：
//   api.collectionNotes.list(filters) → { items: [...], stats: {...} }
const mockAgents = [
  { agentId: 'CS001', agentName: '张明', extension: '8001' },
  { agentId: 'CS002', agentName: '李婷', extension: '8002' },
  { agentId: 'CS003', agentName: '王芳', extension: '8003' },
  { agentId: 'CS004', agentName: '刘强', extension: '8004' }
]

function pad(n) {
  return n.toString().padStart(2, '0')
}

function makeMockList() {
  const list = []
  const phones = ['13888885678', '13912341234', '13788889876', '13612344321', '13522228765', '13388882233']
  let seq = 1
  const today = new Date()
  for (let dayOffset = 0; dayOffset < 7; dayOffset++) {
    const day = new Date(today)
    day.setDate(today.getDate() - dayOffset)
    const callsPerDay = dayOffset === 0 ? 6 : 14
    for (let i = 0; i < callsPerDay; i++) {
      const agent = mockAgents[i % mockAgents.length]
      const phone = phones[(dayOffset + i) % phones.length]
      const startHour = 9 + (i % 6)
      const startMinute = pad((i * 7) % 60)
      const startSecond = pad((i * 13) % 60)
      const startDate = new Date(day)
      startDate.setHours(startHour, parseInt(startMinute), parseInt(startSecond))
      const durationSec = 90 + ((i * 37 + dayOffset * 13) % 360)
      const endDate = new Date(startDate.getTime() + durationSec * 1000)
      const datePart =
        startDate.getFullYear().toString() +
        pad(startDate.getMonth() + 1) +
        pad(startDate.getDate())
      const callId = `CALL${datePart}${pad(seq++)}`
      list.push({
        callId,
        agentId: agent.agentId,
        agentName: agent.agentName,
        extension: agent.extension,
        phone,
        startTime: formatDate(startDate),
        endTime: formatDate(endDate),
        durationSec,
        durationText: formatDuration(durationSec)
      })
    }
  }
  return list
}

function formatDate(d) {
  return (
    d.getFullYear() +
    '-' +
    pad(d.getMonth() + 1) +
    '-' +
    pad(d.getDate()) +
    ' ' +
    pad(d.getHours()) +
    ':' +
    pad(d.getMinutes()) +
    ':' +
    pad(d.getSeconds())
  )
}

function formatDuration(sec) {
  if (!sec || sec < 0) return '--'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}分${pad(s)}秒`
}

const allList = ref([])
const loading = ref(false)
const refreshing = ref(false)

const stats = ref({
  totalCalls: 1286,
  todayCalls: 42,
  avgDuration: 208, // 3 分 28 秒
  aiNotesCount: 1154
})

const filters = ref({
  agentId: '',
  agentName: '',
  extension: '',
  phone: '',
  startTime: '',
  endTime: ''
})

const page = ref(1)
const pageSize = ref(10)

const filteredList = computed(() => {
  return allList.value.filter(item => {
    if (filters.value.agentId && !item.agentId.toLowerCase().includes(filters.value.agentId.toLowerCase())) return false
    if (filters.value.agentName && !item.agentName.includes(filters.value.agentName)) return false
    if (filters.value.extension && !item.extension.includes(filters.value.extension)) return false
    if (filters.value.phone && !item.phone.includes(filters.value.phone)) return false
    if (filters.value.startTime && item.startTime < filters.value.startTime) return false
    if (filters.value.endTime && item.endTime > filters.value.endTime) return false
    return true
  })
})

const pagedList = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredList.value.slice(start, start + pageSize.value)
})

const noteDialog = ref({
  visible: false,
  title: '',
  type: 'structured',
  data: null,
  transcript: '',
  originalNote: '',
  editedNote: ''
})

const saving = ref(false)

// ---------- 模拟催记内容 ----------
// 真实部署时 transcript / originalNote 应来自后端接口
function makeMockTranscript(row) {
  const phoneTail = (row.phone || '').slice(-4)
  const overdueDays = (parseInt((row.callId || '0').slice(-3), 10) % 28) + 5
  const amount = (3000 + (parseInt((row.callId || '0').slice(-3), 10) * 31) % 3000).toFixed(2)
  const dueDate = row.endTime ? row.endTime.slice(0, 10) : '--'
  return `座席：您好，请问是尾号${phoneTail}机主本人吗？
客户：是的，您是哪里？
座席：您好，我是 xx 银行催收中心的${row.agentName || '坐席'}，工号${row.agentId || ''}。您尾号${phoneTail}的信用卡本期账单已逾期${overdueDays}天，欠款金额${amount}元，请问您这边什么时候可以处理呢？
客户：我最近手头有点紧，能不能再缓几天？
座席：理解您的情况，但账单已经逾期了，会产生滞纳金和利息，也会影响您的个人征信。您看今天能否先还一部分呢？
客户：今天真的没有，下周吧，下周三我工资到了。
座席：好的，我给您登记一下，下周三也就是${dueDate}之前处理金额欠款。请您务必按时处理，避免进一步影响您的信用记录。
客户：知道了。
座席：感谢您的配合，再见。`
}

function makeStructuredNote(row) {
  const phoneTail = (row.phone || '').slice(-4)
  const overdueDays = (parseInt((row.callId || '0').slice(-3), 10) % 28) + 5
  const amount = (3000 + (parseInt((row.callId || '0').slice(-3), 10) * 31) % 3000).toFixed(2)
  const dueDate = row.endTime ? row.endTime.slice(0, 10) : '--'
  return `【客户身份】确认本人
【欠款情况】尾号${phoneTail}信用卡，逾期${overdueDays}天，金额${amount}元
【客户反馈】资金紧张，要求缓期
【承诺情况】承诺下周三（${dueDate}）发工资后全额还款
【后续跟进】${dueDate}跟进还款情况`
}

function makeUnstructuredNote(row) {
  const phoneTail = (row.phone || '').slice(-4)
  const dueDate = row.endTime ? row.endTime.slice(0, 10) : '--'
  return `本次通话由座席${row.agentName || '坐席'}（工号${row.agentId || ''}）于 ${row.startTime || ''} 外呼尾号${phoneTail} 用户，确认本人身份后告知其信用卡已逾期、欠款情况。
客户表示近期资金紧张、请求缓期；经沟通最终承诺下周三（${dueDate}）发工资后全额还款。
后续将于 ${dueDate} 跟进还款情况。`
}

function handleQuery() {
  page.value = 1
}

function handleReset() {
  filters.value = {
    agentId: '',
    agentName: '',
    extension: '',
    phone: '',
    startTime: '',
    endTime: ''
  }
  page.value = 1
}

function handleRefresh() {
  refreshing.value = true
  // 真实部署时这里应调用后端接口重新拉取列表，例如：
  //   api.collectionNotes.list(filters.value).then(res => { allList.value = res.items })
  setTimeout(() => {
    allList.value = makeMockList()
    refreshing.value = false
  }, 300)
}

function viewStructuredNote(row) {
  noteDialog.value = {
    visible: true,
    title: `结构化催记详情 - ${row.callId}`,
    type: 'structured',
    data: row,
    transcript: makeMockTranscript(row),
    originalNote: makeStructuredNote(row),
    editedNote: makeStructuredNote(row)
  }
}

function viewUnstructuredNote(row) {
  noteDialog.value = {
    visible: true,
    title: `非结构化催记详情 - ${row.callId}`,
    type: 'unstructured',
    data: row,
    transcript: makeMockTranscript(row),
    originalNote: makeUnstructuredNote(row),
    editedNote: makeUnstructuredNote(row)
  }
}

// 是否有未保存的修改（与原始催记内容比对）
function isDirty() {
  return noteDialog.value.editedNote !== noteDialog.value.originalNote
}

// 统一关闭处理：先判断是否有未保存修改，再决定是否弹确认
async function handleBeforeClose(done) {
  if (!isDirty()) {
    done()
    return
  }
  try {
    await ElMessageBox.confirm(
      '当前催记内容已修改，尚未保存。确定要放弃修改并退出吗？',
      '未保存的修改',
      {
        confirmButtonText: '放弃修改并退出',
        cancelButtonText: '继续编辑',
        type: 'warning',
        distinguishCancelAndClose: true
      }
    )
    done()
  } catch {
    // 用户点了「继续编辑」或关闭了确认框，留在当前弹窗
  }
}

function handleCancel() {
  // 复用 before-close 的判断逻辑
  handleBeforeClose(() => {
    noteDialog.value.visible = false
  })
}

async function copyOriginal() {
  const text = noteDialog.value.originalNote
  if (!text) return
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
    } else {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    ElMessage.success('已复制原始催记内容')
  } catch (err) {
    ElMessage.error('复制失败，请手动选择文本')
  }
}

function saveNote() {
  saving.value = true
  // 真实部署时这里应提交到后端，例如：
  //   api.collectionNotes.save({ callId: data.callId, type, content: editedNote })
  setTimeout(() => {
    saving.value = false
    ElMessage.success('保存成功')
    noteDialog.value.visible = false
  }, 400)
}

onMounted(() => {
  loading.value = true
  // 模拟异步拉取
  setTimeout(() => {
    allList.value = makeMockList()
    loading.value = false
  }, 200)
})
</script>

<style scoped>
.collection-notes-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stats-row {
  margin-bottom: 0;
}

.stat-card {
  background: var(--el-fill-color-blank);
  border: 1px solid var(--va-hairline);
  border-radius: var(--va-radius-md);
  padding: 18px 22px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: box-shadow var(--va-duration) var(--va-ease);
}

.stat-card:hover {
  box-shadow: 0 2px 8px rgba(33, 29, 24, 0.06);
}

.stat-label {
  font-size: 13px;
  color: var(--va-muted);
  letter-spacing: 0.02em;
}

.stat-value {
  font-family: var(--va-font-display);
  font-size: 30px;
  font-weight: 700;
  color: var(--va-ink);
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.filter-card,
.table-card {
  border: 1px solid var(--va-hairline);
  border-radius: var(--va-radius-md);
}

.filter-card :deep(.el-card__body),
.table-card :deep(.el-card__body) {
  padding: 18px 22px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  row-gap: 4px;
}

.filter-form :deep(.el-form-item) {
  margin-right: 18px;
  margin-bottom: 12px;
}

.filter-form :deep(.el-form-item__label) {
  color: var(--va-ink-soft);
  font-size: 13px;
}

.filter-actions {
  margin-left: auto;
  margin-right: 0;
}

.filter-actions :deep(.el-form-item__content) {
  display: flex;
  gap: 10px;
}

.calls-table {
  width: 100%;
}

.calls-table :deep(th.el-table__cell) {
  background: var(--va-paper-deep);
  color: var(--va-ink-soft);
  font-weight: 600;
  font-size: 13px;
}

.pagination {
  margin-top: 18px;
  display: flex;
  justify-content: flex-end;
}

/* ---- 催记详情弹窗 ---- */
.note-dialog :deep(.el-dialog__body) {
  padding: 20px 24px 8px;
}

.note-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 14px 28px;
  padding-bottom: 16px;
  margin-bottom: 18px;
  border-bottom: 1px solid var(--va-hairline);
}

.note-meta-item {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 180px;
}

.note-meta-label {
  color: var(--va-muted);
  font-size: 12.5px;
  flex-shrink: 0;
}

.note-meta-value {
  color: var(--va-ink);
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.note-columns {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 14px;
}

.note-col {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--va-hairline);
  border-radius: var(--va-radius-md);
  overflow: hidden;
  background: var(--el-fill-color-blank);
}

.note-col-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--va-paper-deep);
  font-size: 13px;
  font-weight: 600;
  color: var(--va-ink);
  border-bottom: 1px solid var(--va-hairline);
  letter-spacing: 0.02em;
}

.note-col-body {
  flex: 1;
  min-height: 340px;
  max-height: 420px;
  overflow-y: auto;
  padding: 14px;
}

.note-col-body.transcript {
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.9;
  color: var(--va-ink-soft);
}

.note-col-body.readonly {
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.9;
  color: var(--va-ink-soft);
  background: var(--va-paper-deep);
}

.note-col-body.edit-area :deep(.el-textarea__inner) {
  height: 100%;
  min-height: 340px;
  resize: none;
  font-size: 13px;
  line-height: 1.75;
  border: none;
  box-shadow: none;
  padding: 14px;
  background: transparent;
  color: var(--va-ink);
}

.note-col-body.edit-area :deep(.el-textarea__inner:focus) {
  background: var(--el-fill-color-blank);
}
</style>