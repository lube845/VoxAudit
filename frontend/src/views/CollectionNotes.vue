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
            v-if="isAdmin"
            v-model="filters.agentId"
            placeholder="座席工号"
            clearable
            style="width: 140px"
            @keyup.enter="handleQuery"
          >
            <template #prefix><el-icon><User /></el-icon></template>
          </el-input>
          <el-input
            v-model="filters.agentName"
            placeholder="座席姓名"
            clearable
            style="width: 140px"
            @keyup.enter="handleQuery"
          >
            <template #prefix><el-icon><User /></el-icon></template>
          </el-input>
          <el-input
            v-model="filters.extension"
            placeholder="分机号"
            clearable
            style="width: 140px"
            @keyup.enter="handleQuery"
          >
            <template #prefix><el-icon><Hash /></el-icon></template>
          </el-input>
          <el-input
            v-model="filters.phone"
            placeholder="呼叫号码"
            clearable
            style="width: 140px"
            @keyup.enter="handleQuery"
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
          />
          <div class="filter-spacer" />
          <el-button type="primary" :loading="loading" @click="handleQuery">
            <el-icon><Search /></el-icon>查询
          </el-button>
          <el-tooltip
            :content="isAdmin ? '从上游刷新「客服管理」白名单里所有工号坐席的通话数据（与筛选框无关）' : '从上游刷新我的通话数据'"
            placement="top"
          >
            <el-button
              :loading="refreshing"
              :disabled="refreshCooldown > 0"
              @click="handleRefresh"
            >
              <el-icon><RefreshCw /></el-icon>
              {{ refreshCooldown > 0 ? `刷新 (${refreshCooldown}s)` : '刷新' }}
            </el-button>
          </el-tooltip>
          <span v-if="refreshStatusText" class="refresh-status">{{ refreshStatusText }}</span>
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
        <el-table-column prop="phone" label="呼叫号码" width="130" />
        <el-table-column prop="callingNumber" label="客户号码" width="140" />
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
        <!-- 录音转写原文 -->
        <div class="note-col">
          <div class="note-col-header">
            <span>录音转写原文</span>
            <StepStatus :status="noteDialog.note?.asr_status" :error="noteDialog.note?.asr_error" />
          </div>
          <div class="note-col-body transcript">
            <template v-if="noteDialog.note?.asr_status === 'done'">
              {{ noteDialog.transcript || '（转写为空）' }}
            </template>
            <template v-else-if="noteDialog.note?.asr_status === 'processing' || noteDialog.note?.asr_status === 'pending'">
              <div class="status-placeholder">
                <el-icon class="is-loading"><Loader /></el-icon>
                <span>{{ noteDialog.note?.asr_status === 'pending' ? '等待处理...' : '转写中（约需 10-30 秒）...' }}</span>
              </div>
              <div v-if="stuckSeconds('asr') >= STUCK_SECONDS" class="stuck-actions">
                <el-button size="small" type="warning" :loading="retrying.asr" @click="handleRetry('asr')">重新转写</el-button>
                <span class="stuck-hint">
                  已等待 {{ stuckSeconds('asr') }} 秒仍未完成，可能已中断，可点上方按钮重试
                </span>
              </div>
            </template>
            <template v-else-if="noteDialog.note?.asr_status === 'failed'">
              <div class="status-placeholder failed">
                <div class="err-msg">转写失败：{{ noteDialog.note?.asr_error || '未知错误' }}</div>
                <el-button size="small" type="primary" :loading="retrying.asr" @click="handleRetry('asr')">重新转写</el-button>
              </div>
            </template>
            <template v-else>
              <div class="status-placeholder">
                <el-button size="small" type="primary" :loading="saving" @click="handleProcessAll">生成催记</el-button>
              </div>
            </template>
          </div>
        </div>

        <!-- 原始催记 -->
        <div class="note-col">
          <div class="note-col-header">
            <span>{{ noteDialog.type === 'structured' ? '原始结构化催记' : '原始非结构化催记' }}</span>
            <StepStatus
              :status="noteDialog.note?.[noteDialog.type === 'structured' ? 'structured_status' : 'unstructured_status']"
              :error="noteDialog.note?.[noteDialog.type === 'structured' ? 'structured_error' : 'unstructured_error']"
            />
          </div>
          <div class="note-col-body readonly">
            <template v-if="noteDialog.note?.[noteDialog.type === 'structured' ? 'structured_status' : 'unstructured_status'] === 'done'">
              {{ noteDialog.originalNote || '（催记为空）' }}
            </template>
            <template v-else-if="['processing', 'pending'].includes(noteDialog.note?.[noteDialog.type === 'structured' ? 'structured_status' : 'unstructured_status'])">
              <div class="status-placeholder">
                <el-icon class="is-loading"><Loader /></el-icon>
                <span>{{ noteDialog.note?.[noteDialog.type === 'structured' ? 'structured_status' : 'unstructured_status'] === 'pending' ? '等待处理...' : '生成中（约需 5-10 秒）...' }}</span>
              </div>
              <div v-if="stuckSeconds(noteDialog.type) >= STUCK_SECONDS" class="stuck-actions">
                <el-button
                  size="small"
                  type="warning"
                  :loading="retrying[noteDialog.type]"
                  :disabled="!noteDialog.transcript"
                  @click="handleRetry(noteDialog.type)"
                >重新生成</el-button>
                <span class="stuck-hint">
                  <template v-if="noteDialog.transcript">
                    已等待 {{ stuckSeconds(noteDialog.type) }} 秒仍未完成，可能已中断，可点上方按钮重试
                  </template>
                  <template v-else>需要先完成转写</template>
                </span>
              </div>
            </template>
            <template v-else-if="noteDialog.note?.[noteDialog.type === 'structured' ? 'structured_status' : 'unstructured_status'] === 'failed'">
              <div class="status-placeholder failed">
                <div class="err-msg">生成失败：{{ noteDialog.note?.[noteDialog.type === 'structured' ? 'structured_error' : 'unstructured_error'] || '未知错误' }}</div>
                <el-button
                  size="small"
                  type="primary"
                  :loading="retrying[noteDialog.type]"
                  :disabled="!noteDialog.transcript"
                  @click="handleRetry(noteDialog.type)"
                >重新生成</el-button>
                <div v-if="!noteDialog.transcript" class="err-hint">需要先完成转写</div>
              </div>
            </template>
            <template v-else>
              <div class="status-placeholder muted">尚未开始处理</div>
            </template>
          </div>
        </div>

        <!-- 校对区 -->
        <div class="note-col">
          <div class="note-col-header">
            <span>{{ noteDialog.type === 'structured' ? '校对结构化催记' : '校对非结构化催记' }}</span>
            <el-tag v-if="isDirty()" size="small" type="warning" effect="plain">未保存</el-tag>
            <el-tag v-else-if="savedNote(noteDialog.type) !== null" size="small" type="success" effect="plain">已校对</el-tag>
          </div>
          <el-input
            v-model="noteDialog.editedNote"
            type="textarea"
            :rows="14"
            resize="none"
            class="note-col-body edit-area"
            :placeholder="noteDialog.originalNote ? '可在右侧对催记内容进行校对修改...' : '等待原始催记生成后即可校对'"
            :disabled="!noteDialog.originalNote"
            @blur="handleEditBlur"
          />
        </div>
      </div>

      <template #footer>
        <el-button
          v-if="noteDialog.note && noteDialog.note.asr_status === 'failed' && noteDialog.note.structured_status === 'failed' && noteDialog.note.unstructured_status === 'failed'"
          type="warning"
          :loading="saving"
          @click="handleProcessAll"
        >全部重新处理</el-button>
        <el-button @click="handleCancel">取消</el-button>
        <el-button type="primary" :loading="saving" :disabled="!noteDialog.originalNote" @click="saveNote">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, onUnmounted, h } from 'vue'
import { User, Hash, Phone, RotateCcw, RefreshCw, Search, Loader, CheckCircle2, XCircle, Clock } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import { now } from '@/utils/timezone'
import api from '@/api'

// 字段级状态徽标
const StepStatus = {
  props: ['status', 'error'],
  setup(props) {
    return () => {
      const s = props.status
      if (!s || s === 'pending') return h('span', { class: 'step-status pending' }, [h(Clock, { size: 12 }), ' 等待'])
      if (s === 'processing') return h('span', { class: 'step-status processing' }, [h(Loader, { size: 12, class: 'rotating' }), ' 处理中'])
      if (s === 'done') return h('span', { class: 'step-status done' }, [h(CheckCircle2, { size: 12 }), ' 已完成'])
      if (s === 'failed') return h('span', { class: 'step-status failed', title: props.error || '失败' }, [h(XCircle, { size: 12 }), ' 失败'])
      return null
    }
  },
}

// ——— 角色 ———
// k 客服：后端强制只返回本人工号的数据（见 backend/api/collection_note.py 的 _k_user_agent_id），
// 所以工号筛选框对 k 用户没有意义，前端直接隐藏。
const _loginid = api.auth.getUserInfo()?.loginid || ''
const isAdmin = _loginid === 'admin'

// ——— 数据 ———
const allList = ref([])
const loading = ref(false)
const refreshing = ref(false)
// 后台刷新任务进度文案（解密 + 落库在后台跑，前端轮询展示）
const refreshStatusText = ref('')
// 刷新频控：5 秒内只允许点击一次（与后端 COLLECTION_NOTE_REFRESH_COOLDOWN_SECONDS 对齐）
const refreshCooldown = ref(0)
let cooldownTimer = null

function _startCooldown(seconds = 5) {
  refreshCooldown.value = seconds
  if (cooldownTimer) clearInterval(cooldownTimer)
  cooldownTimer = setInterval(() => {
    refreshCooldown.value -= 1
    if (refreshCooldown.value <= 0) {
      clearInterval(cooldownTimer)
      cooldownTimer = null
    }
  }, 1000)
}

const stats = ref({
  totalCalls: 0,
  todayCalls: 0,
  avgDuration: 0,
  aiNotesCount: 0,
})

// 输入中的筛选条件（未点击搜索前不生效）
const filters = ref({
  agentId: '',
  agentName: '',
  extension: '',
  phone: '',
  dateRange: [],
})

// 已生效的筛选条件（点击搜索后才更新，请求与前端过滤都以它为准）
const appliedFilters = ref({
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

// 后端返回的是 snake_case（列表接口和详情接口一致），统一转成驼峰。
// 兼容已经转过一次的驼峰对象，避免重复转换时字段丢失。
function mapCallItem(c = {}) {
  return {
    callId: c.callId ?? c.call_id,
    agentId: c.agentId ?? c.agent_id,
    agentName: c.agentName ?? c.agent_name,
    extension: c.extension,
    phone: c.phone,
    callingNumber: c.callingNumber ?? c.calling_number,
    startTime: c.startTime ?? c.start_time,
    endTime: c.endTime ?? c.end_time,
    durationSec: c.durationSec ?? c.duration_sec,
    durationText: c.durationText || c.duration_text || formatDuration(c.durationSec ?? c.duration_sec),
  }
}

const filteredList = computed(() => {
  return allList.value.filter((item) => {
    if (appliedFilters.value.agentId && !String(item.agentId || '').toLowerCase().includes(appliedFilters.value.agentId.toLowerCase())) return false
    if (appliedFilters.value.agentName && !String(item.agentName || '').toLowerCase().includes(appliedFilters.value.agentName.toLowerCase())) return false
    if (appliedFilters.value.extension && !String(item.extension || '').toLowerCase().includes(appliedFilters.value.extension.toLowerCase())) return false
    // 呼叫号码：主叫/分机 与 客户号码 任一命中即可
    if (appliedFilters.value.phone) {
      const kw = appliedFilters.value.phone.toLowerCase()
      const hay = `${item.phone || ''} ${item.callingNumber || ''}`.toLowerCase()
      if (!hay.includes(kw)) return false
    }
    const [tStart, tEnd] = appliedFilters.value.dateRange || []
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
  type: 'structured',  // 'structured' | 'unstructured'
  data: null,           // 行数据（list 中的 item）
  note: null,           // 后端返回的 call_note（含三步状态、转写、催记）
  transcript: '',       // 转写文本（来自 note.transcript）
  originalNote: '',     // 原始 AI 催记
  editedNote: '',       // 校对区（用户可编辑）
  savedText: '',        // 已保存（生效）的内容 —— 脏状态的比较基准
})

const saving = ref(false)
const retrying = ref({ asr: false, structured: false, unstructured: false })

// ——— 卡死检测 ———
// 后端进程重启/崩溃会把某些步骤永久留在 processing（后台循环只认领"三步全 pending"的行，
// processing 的行再也没人接手），前端就一直转圈、又没有重试入口（重试按钮只在 failed 时出现）。
// 这里在客户端盯住每一步进入 processing 的时刻，超过阈值就给出重试按钮。
const STUCK_SECONDS = 30
const tick = ref(Date.now())
const stepSince = reactive({ asr: null, structured: null, unstructured: null })
const lastStepStatus = reactive({ asr: null, structured: null, unstructured: null })
let tickTimer = null

const STEP_STATUS_FIELD = {
  asr: 'asr_status',
  structured: 'structured_status',
  unstructured: 'unstructured_status',
}

// 记录每一步进入 processing 的时刻（状态变化时重置）
function _syncStepSince(note) {
  for (const step of Object.keys(STEP_STATUS_FIELD)) {
    const st = note?.[STEP_STATUS_FIELD[step]] || null
    if (st === lastStepStatus[step]) continue
    lastStepStatus[step] = st
    stepSince[step] = st === 'processing' ? Date.now() : null
  }
}

// 切换到另一条通话时清空计时，避免上一条的等待时长串过来
function _resetStepSince() {
  for (const step of Object.keys(STEP_STATUS_FIELD)) {
    lastStepStatus[step] = null
    stepSince[step] = null
  }
}

// 某一步已经 processing 了多少秒（不在 processing 返回 0）
function stuckSeconds(step) {
  void tick.value // 依赖 tick 每秒触发重渲染
  const since = stepSince[step]
  if (!since) return 0
  return Math.floor((Date.now() - since) / 1000)
}

onMounted(() => {
  tickTimer = setInterval(() => { tick.value = Date.now() }, 1000)
})

// ——— 接口调用 ———
async function fetchList() {
  loading.value = true
  try {
    const res = await api.collectionNotes.listCalls({
      agent_id: appliedFilters.value.agentId || undefined,
      agent_name: appliedFilters.value.agentName || undefined,
      extension: appliedFilters.value.extension || undefined,
      phone: appliedFilters.value.phone || undefined,
      start_time: appliedFilters.value.dateRange?.[0] || undefined,
      end_time: appliedFilters.value.dateRange?.[1] || undefined,
    })
    const items = (res.items || []).map((c) => mapCallItem(c))
    allList.value = items
    stats.value.totalCalls = items.length
    // 后端统计：今日通话 / 平均通话时长 / AI 催记生成数
    stats.value.todayCalls = res.today_count ?? 0
    stats.value.avgDuration = res.avg_duration_sec ?? 0
    stats.value.aiNotesCount = res.ai_done_count ?? 0
  } finally {
    loading.value = false
  }
}

// 点击搜索: 先把输入条件同步为生效条件, 再拉取列表
async function handleQuery() {
  page.value = 1
  appliedFilters.value = {
    agentId: isAdmin ? filters.value.agentId : '',
    agentName: filters.value.agentName,
    extension: filters.value.extension,
    phone: filters.value.phone,
    dateRange: filters.value.dateRange ? [...filters.value.dateRange] : [],
  }
  await fetchList()
}

function handleReset() {
  filters.value = {
    agentId: '', agentName: '', extension: '',
    phone: '', dateRange: [],
  }
  appliedFilters.value = {
    agentId: '', agentName: '', extension: '',
    phone: '', dateRange: [],
  }
  page.value = 1
  // 重置后立即重新拉一次
  fetchList()
}

async function handleRefresh() {
  // 频控：冷却中直接返回（防止按钮被快速连点）
  if (refreshCooldown.value > 0) {
    ElMessage.warning(`请等待 ${refreshCooldown.value} 秒后再试`)
    return
  }
  refreshing.value = true
  // 点击立即启动倒计时（即使后端返回 429 也能阻止重复点击）
  _startCooldown(5)
  try {
    // 时间窗口由后端按 RECORDING_REQUEST_DURATION_DAYS 自动计算，前端不参与
    // 筛选框只跟"查询"有关，刷新不带任何筛选条件：
    //   admin → 后端刷客服白名单里所有工号坐席
    //   k 账号 → 后端刷自己的工号
    const res = await api.collectionNotes.refreshCalls({})

    // 后端把「上游查询 + 解密 + 落库」放到后台任务了：接口立刻返回 status=running + job_id，
    // 这里轮询进度直到跑完（k 账号单座席时上游查询是同步的，失败会直接进 catch）
    if (res?.status === 'running' && res?.job_id) {
      refreshStatusText.value = res.message || '正在后台解密…'
      const job = await _pollRefreshJob(res.job_id)
      if (!job) {
        ElMessage.warning('后台刷新仍在进行，稍后刷新列表查看结果')
      } else if (job.status === 'failed') {
        ElMessage.error(job.error || job.message || '刷新失败')
      } else {
        ElMessage.success(job.message || '刷新成功')
      }
    } else {
      ElMessage.success(res.message || `刷新成功，共 ${res.total} 条`)
    }

    // 刷新成功后重新从 DB 拉一次列表（前端筛选条件照旧叠加显示）
    await fetchList()
  } catch (err) {
    // 拦截器已弹过错误；这里给个 fallback 提示，避免无反馈
    const msg = err?.response?.data?.detail || err?.message || '刷新失败'
    ElMessage.error(msg)
    // 后端返回 429 时，按 Retry-After 头重新对齐倒计时（更准确）
    const retryAfter = parseInt(err?.response?.headers?.['retry-after'] || '0', 10)
    if (err?.response?.status === 429 && retryAfter > 0) {
      _startCooldown(Math.max(retryAfter, refreshCooldown.value))
    }
  } finally {
    refreshStatusText.value = ''
    refreshing.value = false
  }
}

/**
 * 轮询后台刷新任务，直到 done / failed
 * @returns {Promise<object|null>} 任务最终状态；任务丢失/超时返回 null
 */
async function _pollRefreshJob(jobId) {
  const maxTicks = 300          // 2s × 300 ≈ 10 分钟
  for (let i = 0; i < maxTicks; i++) {
    await new Promise((r) => setTimeout(r, 2000))
    let st
    try {
      st = await api.collectionNotes.refreshStatus(jobId)
    } catch (e) {
      // 404 = 任务不存在了（后端重启 / 状态已过期）→ 别再空转
      if (e?.response?.status === 404) return null
      continue                  // 单次网络抖动不中断，继续试
    }
    const job = st?.job
    if (!job) continue
    refreshStatusText.value = _refreshProgressText(job)
    if (job.status === 'done' || job.status === 'failed') {
      return job
    }
  }
  return null
}

// 刷新进度文案：多座席（admin 刷白名单）显示「已刷 n/N 个座席」
function _refreshProgressText(job) {
  const agents = job.agents || []
  if (agents.length > 1) {
    const done = agents.filter((a) => a.status === 'done' || a.status === 'failed').length
    const failed = agents.filter((a) => a.status === 'failed').length
    const tail = failed ? `（${failed} 个失败）` : ''
    return `正在刷新白名单座席 ${done}/${agents.length}，已入库 ${job.inserted || 0} 条${tail}…`
  }
  return `正在后台解密入库 ${job.decrypted || 0}/${job.total || 0}…`
}

async function fetchDetail(callId) {
  const res = await api.collectionNotes.getCall(callId)
  return { item: res.item, note: res.note }
}

// ——— 弹窗显示用：根据 type 选 note 中的字段，失败时取 edited_*_note 兜底 ———
function _pickOriginalNote(note, type) {
  if (!note) return ''
  return type === 'structured' ? (note.structured_note || '') : (note.unstructured_note || '')
}
// 校对区当前"生效"的内容：用户保存过的用保存值（明确存成空串也算保存过），
// 从没保存过才回落到 AI 原始催记
function _pickEditedNote(note, type) {
  if (!note) return ''
  const edited = type === 'structured' ? note.edited_structured_note : note.edited_unstructured_note
  if (edited !== null && edited !== undefined) return edited
  return type === 'structured' ? (note.structured_note || '') : (note.unstructured_note || '')
}

// 该类型已保存的校对内容（null = 从未保存过）
function savedNote(type) {
  const note = noteDialog.value.note
  if (!note) return null
  const v = type === 'structured' ? note.edited_structured_note : note.edited_unstructured_note
  return v === undefined ? null : v
}

function _applyNoteToDialog(detail) {
  const { item, note } = detail
  const t = noteDialog.value.type
  // 详情接口返回的是 snake_case，必须转成驼峰，否则 dlg.data.callId 为 undefined
  noteDialog.value.data = mapCallItem(item || {})
  noteDialog.value.note = note
  _syncStepSince(note)
  noteDialog.value.transcript = note?.transcript || ''
  noteDialog.value.originalNote = _pickOriginalNote(note, t)
  const saved = _pickEditedNote(note, t)
  // 用户还有未保存的改动时，别被轮询刷新覆盖掉
  if (noteDialog.value.editedNote === noteDialog.value.savedText) {
    noteDialog.value.editedNote = saved
  }
  noteDialog.value.savedText = saved
  // 失焦上报的去重 key：每次切到新对话时重置
  lastEditReported = noteDialog.value.editedNote
}

async function viewStructuredNote(row) {
  stopPolling()
  _resetStepSince()
  // 先用占位数据打开弹窗，避免空白闪烁
  noteDialog.value = {
    visible: true,
    title: `结构化催记详情 - ${row.callId}`,
    type: 'structured',
    data: row,
    note: null,
    transcript: '',
    originalNote: '',
    editedNote: '',
    savedText: '',
  }
  await api.collectionNotes.viewStructured(row.callId).catch(() => {})
  const detail = await fetchDetail(row.callId)
  _applyNoteToDialog(detail)
  startPolling(row.callId)
}

async function viewUnstructuredNote(row) {
  stopPolling()
  _resetStepSince()
  noteDialog.value = {
    visible: true,
    title: `非结构化催记详情 - ${row.callId}`,
    type: 'unstructured',
    data: row,
    note: null,
    transcript: '',
    originalNote: '',
    editedNote: '',
    savedText: '',
  }
  await api.collectionNotes.viewUnstructured(row.callId).catch(() => {})
  const detail = await fetchDetail(row.callId)
  _applyNoteToDialog(detail)
  startPolling(row.callId)
}

// ——— 轮询：3s 一次，仅弹窗打开时；三步任一 processing 则继续，否则停 ———
let pollTimer = null
function startPolling(callId) {
  stopPolling()
  pollTimer = setInterval(async () => {
    if (!noteDialog.value.visible || noteDialog.value.data?.callId !== callId) {
      stopPolling()
      return
    }
    try {
      const detail = await fetchDetail(callId)
      _applyNoteToDialog(detail)
      const n = detail.note
      const anyProcessing = n && (
        n.asr_status === 'processing' ||
        n.structured_status === 'processing' ||
        n.unstructured_status === 'processing'
      )
      if (!anyProcessing) stopPolling()
    } catch {
      /* 轮询失败忽略，下一次继续 */
    }
  }, 3000)
}
function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}
onUnmounted(() => {
  stopPolling()
  if (tickTimer) { clearInterval(tickTimer); tickTimer = null }
  if (cooldownTimer) { clearInterval(cooldownTimer); cooldownTimer = null }
})

// ——— 重试 ———
async function handleRetry(step) {
  const dlg = noteDialog.value
  if (!dlg.data) return
  retrying.value[step] = true
  try {
    let res
    if (step === 'asr') res = await api.collectionNotes.retryTranscribe(dlg.data.callId)
    else if (step === 'structured') res = await api.collectionNotes.retryStructured(dlg.data.callId)
    else res = await api.collectionNotes.retryUnstructured(dlg.data.callId)
    if (res.note) {
      _applyNoteToDialog({ item: dlg.data, note: res.note })
    }
    if (res.skipped) {
      ElMessage.info(res.message || '已有结果，未重跑')
    } else {
      ElMessage.success(res.message || '处理完成')
    }
    // 重跑后可能回到 processing，启动轮询等待
    const n = res.note
    if (n && (
      n.asr_status === 'processing' ||
      n.structured_status === 'processing' ||
      n.unstructured_status === 'processing'
    )) {
      startPolling(dlg.data.callId)
    }
  } catch (err) {
    const msg = err?.response?.data?.detail || err?.message || '重试失败'
    ElMessage.error(msg)
  } finally {
    retrying.value[step] = false
  }
}

async function handleProcessAll() {
  const dlg = noteDialog.value
  if (!dlg.data) return
  saving.value = true
  try {
    const res = await api.collectionNotes.processCall(dlg.data.callId)
    if (res.note) _applyNoteToDialog({ item: dlg.data, note: res.note })
    ElMessage.success(res.message || '处理完成')
    startPolling(dlg.data.callId)
  } catch (err) {
    const msg = err?.response?.data?.detail || err?.message || '处理失败'
    ElMessage.error(msg)
  } finally {
    saving.value = false
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
  // 跟"当前生效的内容"（已保存的值，没保存过就是 AI 原始催记）比，
  // 不能跟 AI 原始催记比 —— 只要用户改过并保存过，两者就永远不相等，
  // 结果是保存完再打开还是显示"未保存"、关弹窗还会被拦一下
  return noteDialog.value.editedNote !== noteDialog.value.savedText
}

async function handleBeforeClose(done) {
  stopPolling()
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
    // 用后端返回的最新 note 刷新弹窗
    if (res.note) _applyNoteToDialog({ item: dlg.data, note: res.note })
    else { dlg.originalNote = dlg.editedNote; dlg.savedText = dlg.editedNote }  // 兜底
    noteDialog.value.visible = false
    stopPolling()
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
.refresh-status {
  margin-left: 8px;
  color: var(--va-muted);
  font-size: 13px;
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

/* 字段级状态徽标 */
.step-status {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 12px; padding: 2px 8px; border-radius: 10px; line-height: 1.4;
  font-weight: 500; flex-shrink: 0;
}
.step-status.pending { color: #909399; background: rgba(144, 147, 153, 0.1); }
.step-status.processing { color: #b88244; background: rgba(184, 130, 68, 0.1); }
.step-status.done { color: #67c23a; background: rgba(103, 194, 58, 0.1); }
.step-status.failed { color: #f56c6c; background: rgba(245, 108, 108, 0.1); }
.step-status .rotating { animation: rotate 1s linear infinite; }
@keyframes rotate { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* 状态占位（处理中/失败/未开始） */
.status-placeholder {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 12px; min-height: 280px; color: var(--va-muted); font-size: 13px;
}
.status-placeholder.failed { color: #f56c6c; }
.status-placeholder.muted { color: #c0c4cc; }
.status-placeholder .err-msg {
  color: #f56c6c; font-size: 12.5px; line-height: 1.6;
  text-align: center; max-width: 90%;
  word-break: break-all;
}
.status-placeholder .err-hint { color: #c0c4cc; font-size: 12px; }
.status-placeholder :deep(.el-icon.is-loading) { animation: rotate 1.2s linear infinite; font-size: 22px; }

/* 卡死（长时间停在 processing）时的重试入口 */
.stuck-actions {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  margin-top: -8px; text-align: center;
}
.stuck-hint { color: #c0c4cc; font-size: 12px; line-height: 1.6; max-width: 90%; }
.note-col-body.edit-area :deep(.el-textarea__inner) {
  height: 100%; min-height: 340px; resize: none; font-size: 13px; line-height: 1.75;
  border: none; box-shadow: none; padding: 14px; background: transparent; color: var(--va-ink);
}
.note-col-body.edit-area :deep(.el-textarea__inner:focus) { background: var(--el-fill-color-blank); }
</style>