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
      <div class="search-bar">
        <div class="filter-row">
          <el-input
            v-model="filters.agentId"
            placeholder="座席工号"
            clearable
            style="width: 140px"
            @input="handleAutoQuery"
          >
            <template #prefix><el-icon><User /></el-icon></template>
          </el-input>
          <el-input
            v-model="filters.agentName"
            placeholder="座席姓名"
            clearable
            style="width: 140px"
            @input="handleAutoQuery"
          >
            <template #prefix><el-icon><User /></el-icon></template>
          </el-input>
          <el-input
            v-model="filters.extension"
            placeholder="分机号"
            clearable
            style="width: 140px"
            @input="handleAutoQuery"
          >
            <template #prefix><el-icon><Hash /></el-icon></template>
          </el-input>
          <el-input
            v-model="filters.phone"
            placeholder="呼叫号码"
            clearable
            style="width: 140px"
            @input="handleAutoQuery"
          >
            <template #prefix><el-icon><Phone /></el-icon></template>
          </el-input>
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD HH:mm:ss"
            :shortcuts="dateRangeShortcuts"
            style="width: 280px"
            @change="handleAutoQuery"
          />
          <div class="filter-spacer" />
          <el-button @click="handleReset">
            <el-icon><RotateCcw /></el-icon>重置
          </el-button>
          <span class="total-count">共 {{ filteredList.length }} 条</span>
        </div>
      </div>
    </el-card>

    <!-- 通话列表 -->
    <el-card class="table-card" shadow="never">
      <el-table :data="pagedList" v-loading="loading" stripe class="calls-table">
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
            <el-button link type="primary" @click="viewStructuredNote(row)">查看结构化催记</el-button>
            <el-button link type="primary" @click="viewUnstructuredNote(row)">查看非结构化催记</el-button>
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
      <div class="note-meta">
        <div class="note-meta-item"><span class="note-meta-label">通话 ID</span><span class="note-meta-value">{{ noteDialog.data?.callId }}</span></div>
        <div class="note-meta-item"><span class="note-meta-label">座席</span><span class="note-meta-value">{{ noteDialog.data?.agentName }}（{{ noteDialog.data?.agentId }}）</span></div>
        <div class="note-meta-item"><span class="note-meta-label">分机号</span><span class="note-meta-value">{{ noteDialog.data?.extension }}</span></div>
        <div class="note-meta-item"><span class="note-meta-label">呼叫号码</span><span class="note-meta-value">{{ noteDialog.data?.phone }}</span></div>
        <div class="note-meta-item"><span class="note-meta-label">通话时长</span><span class="note-meta-value">{{ noteDialog.data?.durationText }}</span></div>
        <div class="note-meta-item"><span class="note-meta-label">开始时间</span><span class="note-meta-value">{{ noteDialog.data?.startTime }}</span></div>
        <div class="note-meta-item"><span class="note-meta-label">结束时间</span><span class="note-meta-value">{{ noteDialog.data?.endTime }}</span></div>
      </div>

      <div class="note-columns">
        <div class="note-col">
          <div class="note-col-header">录音转写原文</div>
          <div class="note-col-body transcript">{{ noteDialog.transcript }}</div>
        </div>

        <div class="note-col">
          <div class="note-col-header">
            <span>{{ noteDialog.type === 'structured' ? '原始结构化催记' : '原始非结构化催记' }}</span>
            <el-tag size="small" type="info" effect="plain">不可编辑</el-tag>
          </div>
          <div class="note-col-body readonly">{{ noteDialog.originalNote }}</div>
        </div>

        <div class="note-col">
          <div class="note-col-header">
            <span>{{ noteDialog.type === 'structured' ? '校对结构化催记' : '校对非结构化催记' }}</span>
          </div>
          <el-input
            v-model="noteDialog.editedNote"
            type="textarea"
            :rows="14"
            resize="none"
            class="note-col-body edit-area"
            placeholder="可在右侧对催记内容进行校对修改..."
            @blur="handleEditBlur"
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
import { User, Hash, Phone, RotateCcw } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import { now } from '@/utils/timezone'
import api from '@/api'

// ——— 数据 ———
const allList = ref([])
const loading = ref(false)
const refreshing = ref(false)

const stats = ref({
  totalCalls: 0,
  todayCalls: 0,
  avgDuration: 0,
  aiNotesCount: 0,
})

const filters = ref({
  agentId: '',
  agentName: '',
  extension: '',
  phone: '',
  dateRange: [],
})

// 时间范围快捷选项 (与导出报告页保持一致)
const dateRangeShortcuts = [
  {
    text: '近一周',
    value: () => {
      const end = now().toDate()
      const start = now().subtract(6, 'day').toDate()
      return [start, end]
    },
  },
  {
    text: '近一月',
    value: () => {
      const end = now().toDate()
      const start = now().subtract(29, 'day').toDate()
      return [start, end]
    },
  },
  {
    text: '近半年',
    value: () => {
      const end = now().toDate()
      const start = now().subtract(179, 'day').toDate()
      return [start, end]
    },
  },
  {
    text: '近一年',
    value: () => {
      const end = now().toDate()
      const start = now().subtract(364, 'day').toDate()
      return [start, end]
    },
  },
]

const page = ref(1)
const pageSize = ref(10)

// ——— 工具 ———
function formatDuration(sec) {
  if (!sec || sec < 0) return '--'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}分${String(s).padStart(2, '0')}秒`
}

const filteredList = computed(() => {
  return allList.value.filter((item) => {
    if (filters.value.agentId && !String(item.agentId || '').toLowerCase().includes(filters.value.agentId.toLowerCase())) return false
    if (filters.value.agentName && !String(item.agentName || '').toLowerCase().includes(filters.value.agentName.toLowerCase())) return false
    if (filters.value.extension && !String(item.extension || '').toLowerCase().includes(filters.value.extension.toLowerCase())) return false
    if (filters.value.phone && !String(item.phone || '').toLowerCase().includes(filters.value.phone.toLowerCase())) return false
    const [tStart, tEnd] = filters.value.dateRange || []
    if (tStart && item.startTime < tStart) return false
    if (tEnd && item.endTime > tEnd) return false
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
  editedNote: '',
})

const saving = ref(false)

// ——— 接口调用 ———
async function fetchList() {
  loading.value = true
  try {
    const res = await api.collectionNotes.listCalls({
      agent_id: filters.value.agentId || undefined,
      agent_name: filters.value.agentName || undefined,
      extension: filters.value.extension || undefined,
      phone: filters.value.phone || undefined,
      start_time: filters.value.dateRange?.[0] || undefined,
      end_time: filters.value.dateRange?.[1] || undefined,
    })
    const items = (res.items || []).map((c) => ({
      callId: c.call_id,
      agentId: c.agent_id,
      agentName: c.agent_name,
      extension: c.extension,
      phone: c.phone,
      startTime: c.start_time,
      endTime: c.end_time,
      durationSec: c.duration_sec,
      durationText: c.duration_text || formatDuration(c.duration_sec),
    }))
    allList.value = items
    stats.value.totalCalls = items.length
    stats.value.aiNotesCount = items.length  // 上游未接，统计先置 0
  } finally {
    loading.value = false
  }
}

function handleQuery() {
  page.value = 1
}

// 自动查询: 任意筛选条件变化时触发, 200ms 防抖避免频繁请求
let autoQueryTimer = null
function handleAutoQuery() {
  if (autoQueryTimer) clearTimeout(autoQueryTimer)
  autoQueryTimer = setTimeout(async () => {
    page.value = 1
    await fetchList()
  }, 200)
}

function handleReset() {
  filters.value = {
    agentId: '', agentName: '', extension: '',
    phone: '', dateRange: [],
  }
  page.value = 1
  // 重置后立即重新拉一次, 不依赖防抖
  fetchList()
}

async function handleRefresh() {
  refreshing.value = true
  try {
    await fetchList()
  } finally {
    refreshing.value = false
  }
}

async function fetchDetail(callId) {
  const res = await api.collectionNotes.getCall(callId)
  return res.item
}

async function viewStructuredNote(row) {
  // 1) 拿详情
  const detail = await fetchDetail(row.callId)
  // 2) 记审计
  await api.collectionNotes.viewStructured(row.callId).catch(() => {})
  // 3) 打开弹窗
  noteDialog.value = {
    visible: true,
    title: `结构化催记详情 - ${row.callId}`,
    type: 'structured',
    data: row,
    transcript: detail.transcript || '',
    originalNote: detail.structured_note || '',
    editedNote: detail.structured_note || '',
  }
}

async function viewUnstructuredNote(row) {
  const detail = await fetchDetail(row.callId)
  await api.collectionNotes.viewUnstructured(row.callId).catch(() => {})
  noteDialog.value = {
    visible: true,
    title: `非结构化催记详情 - ${row.callId}`,
    type: 'unstructured',
    data: row,
    transcript: detail.transcript || '',
    originalNote: detail.unstructured_note || '',
    editedNote: detail.unstructured_note || '',
  }
}

// textarea 失焦时上报"编辑过"（仅在内容被改动时）
let lastEditReported = ''
async function handleEditBlur() {
  const dlg = noteDialog.value
  if (!dlg.data) return
  if (dlg.editedNote === lastEditReported) return  // 同一值不再重复
  lastEditReported = dlg.editedNote

  const payload = { content: dlg.editedNote, is_final: false }
  try {
    if (dlg.type === 'structured') {
      await api.collectionNotes.editStructured(dlg.data.callId, payload)
    } else {
      await api.collectionNotes.editUnstructured(dlg.data.callId, payload)
    }
  } catch {
    /* 失败不影响 */
  }
}

function isDirty() {
  return noteDialog.value.editedNote !== noteDialog.value.originalNote
}

async function handleBeforeClose(done) {
  if (!isDirty()) { done(); return }
  try {
    await ElMessageBox.confirm(
      '当前催记内容已修改，尚未保存。确定要放弃修改并退出吗？',
      '未保存的修改',
      { confirmButtonText: '放弃修改并退出', cancelButtonText: '继续编辑', type: 'warning', distinguishCancelAndClose: true }
    )
    done()
  } catch { /* 继续编辑 */ }
}

function handleCancel() {
  handleBeforeClose(() => { noteDialog.value.visible = false })
}

async function saveNote() {
  const dlg = noteDialog.value
  if (!dlg.data) return
  saving.value = true
  try {
    const payload = { content: dlg.editedNote, is_final: true }
    const res = dlg.type === 'structured'
      ? await api.collectionNotes.saveStructured(dlg.data.callId, payload)
      : await api.collectionNotes.saveUnstructured(dlg.data.callId, payload)
    ElMessage.success(res.message || '保存成功')
    // 保存后把"原始内容"刷新为最新已保存版（影响 isDirty 判断）
    dlg.originalNote = dlg.editedNote
    noteDialog.value.visible = false
  } catch {
    /* 拦截器已提示 */
  } finally {
    saving.value = false
  }
}

onMounted(fetchList)
</script>

<style scoped>
.collection-notes-page { display: flex; flex-direction: column; gap: 16px; }
.stats-row { margin-bottom: 0; }
.stat-card {
  background: var(--el-fill-color-blank);
  border: 1px solid var(--va-hairline);
  border-radius: var(--va-radius-md);
  padding: 18px 22px 20px;
  display: flex; flex-direction: column; gap: 10px;
  transition: box-shadow var(--va-duration) var(--va-ease);
}
.stat-card:hover { box-shadow: 0 2px 8px rgba(33, 29, 24, 0.06); }
.stat-label { font-size: 13px; color: var(--va-muted); letter-spacing: 0.02em; }
.stat-value {
  font-family: var(--va-font-display); font-size: 30px; font-weight: 700;
  color: var(--va-ink); line-height: 1.1; font-variant-numeric: tabular-nums;
}
.filter-card, .table-card { border: 1px solid var(--va-hairline); border-radius: var(--va-radius-md); }
.filter-card :deep(.el-card__body), .table-card :deep(.el-card__body) { padding: 18px 22px; }
.search-bar {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.filter-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
.filter-row :deep(.el-input__wrapper), .filter-row :deep(.el-date-editor) {
  font-size: 14px;
}
.filter-spacer { flex: 1; min-width: 12px; }
.total-count {
  margin-left: 4px;
  color: var(--va-muted);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.calls-table { width: 100%; }
.calls-table :deep(th.el-table__cell) { background: var(--va-paper-deep); color: var(--va-ink-soft); font-weight: 600; font-size: 13px; }
.pagination { margin-top: 18px; display: flex; justify-content: flex-end; }

.note-dialog :deep(.el-dialog__body) { padding: 20px 24px 8px; }
.note-meta {
  display: flex; flex-wrap: wrap; gap: 14px 28px;
  padding-bottom: 16px; margin-bottom: 18px;
  border-bottom: 1px solid var(--va-hairline);
}
.note-meta-item { display: flex; align-items: baseline; gap: 10px; min-width: 180px; }
.note-meta-label { color: var(--va-muted); font-size: 12.5px; flex-shrink: 0; }
.note-meta-value { color: var(--va-ink); font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums; }
.note-columns { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; }
.note-col {
  display: flex; flex-direction: column;
  border: 1px solid var(--va-hairline); border-radius: var(--va-radius-md);
  overflow: hidden; background: var(--el-fill-color-blank);
}
.note-col-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; background: var(--va-paper-deep);
  font-size: 13px; font-weight: 600; color: var(--va-ink);
  border-bottom: 1px solid var(--va-hairline); letter-spacing: 0.02em;
}
.note-col-body { flex: 1; min-height: 340px; max-height: 420px; overflow-y: auto; padding: 14px; }
.note-col-body.transcript { white-space: pre-wrap; font-size: 13px; line-height: 1.9; color: var(--va-ink-soft); }
.note-col-body.readonly { white-space: pre-wrap; font-size: 13px; line-height: 1.9; color: var(--va-ink-soft); background: var(--va-paper-deep); }
.note-col-body.edit-area :deep(.el-textarea__inner) {
  height: 100%; min-height: 340px; resize: none; font-size: 13px; line-height: 1.75;
  border: none; box-shadow: none; padding: 14px; background: transparent; color: var(--va-ink);
}
.note-col-body.edit-area :deep(.el-textarea__inner:focus) { background: var(--el-fill-color-blank); }
</style>