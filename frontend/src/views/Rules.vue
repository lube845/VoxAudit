<template>
  <div class="rules-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h2>评分规则管理</h2>
        <p class="subtitle">管理加分规则和扣分规则</p>
      </div>
      <div class="header-actions">
        <el-button type="warning" size="small" @click="showImportDialog" class="import-btn">
          <el-icon><Upload /></el-icon>
          导入规则
        </el-button>
        <el-button type="success" size="small" @click="exportRules" class="export-btn">
          <el-icon><Download /></el-icon>
          导出规则
        </el-button>
      </div>
    </div>

    <!-- 导入对话框 -->
    <el-dialog v-model="importDialogVisible" title="导入规则" width="500px" destroy-on-close>
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        accept=".json"
        :on-change="handleFileChange"
        :file-list="fileList"
        :before-remove="beforeRemove"
        drag
      >
        <el-icon><Upload /></el-icon>
        <div>将JSON文件拖到此处，或<em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip">
            只能上传JSON文件，请注意规则去重，导入的规则将不会自动去重
            <el-link type="primary" @click.prevent="downloadTemplate">下载模板</el-link>
          </div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="importRules" :loading="importing" :disabled="!importFileData">确认导入</el-button>
      </template>
    </el-dialog>

    <!-- 加分项 -->
    <el-card class="rules-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <div class="card-title">
            <span class="icon">⭐</span>
            <span>加分规则</span>
            <el-tag type="success" size="small" effect="plain">{{ bonusTotal }} 条</el-tag>
          </div>
          <el-button type="primary" size="small" @click="openCreateDialog('bonus')" class="create-btn">
            <el-icon><Plus /></el-icon>
            创建规则
          </el-button>
        </div>
      </template>

      <el-table :data="bonusRules" v-loading="loading" stripe class="rules-table">
        <el-table-column prop="name" label="规则名称" min-width="180">
          <template #default="{ row }">
            <div class="rule-name">{{ row.name }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="规则代码" width="150">
          <template #default="{ row }">
            <code class="code-tag">{{ row.code }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="total_score" label="分值" width="100" align="center">
          <template #default="{ row }">
            <span class="score bonus">+{{ row.total_score || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="100" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.is_enabled"
              active-color="#67c23a"
              inactive-color="#909399"
              :disabled="!row.is_latest"
              @change="toggleEnabled(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewRule(row)">查看</el-button>
            <el-button link type="primary" size="small" @click="editRule(row)">编辑</el-button>
            <el-button link type="info" size="small" @click="viewHistory(row)">历史</el-button>
            <el-button link type="danger" size="small" @click="deleteRule(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="bonusTotal > 0"
        v-model:current-page="bonusPage"
        v-model:page-size="bonusPageSize"
        :page-sizes="[5, 10, 20]"
        :total="bonusTotal"
        layout="sizes, prev, pager, next"
        @current-change="handleBonusPageChange"
        @size-change="handleBonusSizeChange"
        class="pagination"
      />

      <el-empty v-if="bonusRules.length === 0 && !loading" description="暂无加分规则" :image-size="80" />
    </el-card>

    <!-- 扣分项 -->
    <el-card class="rules-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <div class="card-title">
            <span class="icon">📉</span>
            <span>扣分规则</span>
            <el-tag type="danger" size="small" effect="plain">{{ deductionTotal }} 条</el-tag>
          </div>
          <el-button type="danger" size="small" @click="openCreateDialog('deduction')" class="create-btn-deduction">
            <el-icon><Plus /></el-icon>
            创建规则
          </el-button>
        </div>
      </template>

      <el-table :data="deductionRules" v-loading="loading" stripe class="rules-table">
        <el-table-column prop="name" label="规则名称" min-width="180">
          <template #default="{ row }">
            <div class="rule-name">{{ row.name }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="规则代码" width="150">
          <template #default="{ row }">
            <code class="code-tag">{{ row.code }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="total_score" label="分值" width="100" align="center">
          <template #default="{ row }">
            <span class="score deduction">-{{ row.total_score || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="is_veto" label="否决项" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_veto" type="warning" effect="dark" size="small">是</el-tag>
            <span v-else class="no-veto">否</span>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="100" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.is_enabled"
              active-color="#67c23a"
              inactive-color="#909399"
              :disabled="!row.is_latest"
              @change="toggleEnabled(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewRule(row)">查看</el-button>
            <el-button link type="primary" size="small" @click="editRule(row)">编辑</el-button>
            <el-button link type="info" size="small" @click="viewHistory(row)">历史</el-button>
            <el-button link type="danger" size="small" @click="deleteRule(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="deductionTotal > 0"
        v-model:current-page="deductionPage"
        v-model:page-size="deductionPageSize"
        :page-sizes="[5, 10, 20]"
        :total="deductionTotal"
        layout="sizes, prev, pager, next"
        @current-change="handleDeductionPageChange"
        @size-change="handleDeductionSizeChange"
        class="pagination"
      />

      <el-empty v-if="deductionRules.length === 0 && !loading" description="暂无扣分规则" :image-size="80" />
    </el-card>

    <!-- 查看详情对话框 -->
    <el-dialog v-model="viewDialogVisible" title="规则详情" width="550px" destroy-on-close>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="规则名称">{{ form.name }}</el-descriptions-item>
        <el-descriptions-item label="规则代码">
          <code class="code-tag">{{ form.code }}</code>
        </el-descriptions-item>
        <el-descriptions-item label="版本">{{ form.version }}</el-descriptions-item>
        <el-descriptions-item label="规则类型">
          <el-tag :type="form.rule_type === 'bonus' ? 'success' : 'danger'">
            {{ form.rule_type === 'bonus' ? '加分' : '扣分' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="总分值">
          <span :class="form.rule_type === 'bonus' ? 'score bonus' : 'score deduction'">
            {{ form.rule_type === 'bonus' ? '+' : '-' }}{{ form.total_score || 0 }}
          </span>
        </el-descriptions-item>
        <el-descriptions-item v-if="form.rule_type === 'deduction'" label="否决项">
          <el-tag :type="form.is_veto ? 'warning' : 'info'">
            {{ form.is_veto ? '是' : '否' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="最新版本">
          <el-tag :type="form.is_latest ? 'success' : 'info'">
            {{ form.is_latest ? '是' : '否' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">{{ form.description || '无' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editId ? '编辑规则' : '创建规则'"
      width="500px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px" class="rule-form">
        <el-form-item label="规则名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入规则名称" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="分值" prop="total_score">
          <el-input-number v-model="form.total_score" :min="0" :max="100" :precision="1" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" rows="3" placeholder="规则描述必填，越清晰越好，大模型根据该字段来理解规则" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item v-if="form.rule_type === 'deduction'" label="否决项">
          <el-switch v-model="form.is_veto" active-color="#f56c6c" inactive-color="#909399" />
          <span class="veto-tip">（否决项规则可直接否决评分）</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">
          {{ editId ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 规则历史对话框 -->
    <el-dialog v-model="historyDialogVisible" title="规则历史" width="700px" destroy-on-close>
      <el-table :data="historyList" stripe v-loading="historyLoading">
        <el-table-column prop="version" label="版本" width="120">
          <template #default="{ row }">
            <el-tag :type="row.is_latest ? 'success' : 'info'" effect="plain" size="small">
              {{ row.version }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="规则名称" min-width="120" />
        <el-table-column prop="total_score" label="分值" width="80" align="center">
          <template #default="{ row }">
            <span :class="row.rule_type === 'bonus' ? 'score bonus' : 'score deduction'">
              {{ row.rule_type === 'bonus' ? '+' : '-' }}{{ row.total_score }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="published_at" label="发布时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.published_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewVersion(row)">查看</el-button>
            <el-button link type="warning" size="small" @click="rollbackToVersion(row)" :disabled="row.is_latest">回溯</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="historyDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Download, Upload } from '@element-plus/icons-vue'
import { formatDate, getTimezone } from '@/utils/timezone'
import api from '@/api'

const loading = ref(false)
const list = ref([])
const searchKeyword = ref('')

// 分页
const bonusPage = ref(1)
const deductionPage = ref(1)
const bonusPageSize = ref(5)
const deductionPageSize = ref(5)
const bonusTotal = ref(0)
const deductionTotal = ref(0)

// 对话框
const dialogVisible = ref(false)
const viewDialogVisible = ref(false)
const historyDialogVisible = ref(false)
const importDialogVisible = ref(false)
const editId = ref(null)
const submitting = ref(false)
const historyLoading = ref(false)
const historyList = ref([])
const currentRuleId = ref(null)
const formRef = ref(null)
const uploadRef = ref(null)
const importing = ref(false)
const importFileData = ref(null)
const fileList = ref([])

function beforeRemove(file) {
  fileList.value = []
  importFileData.value = null
}

const form = reactive({
  name: '',
  code: '',
  version: '',
  description: '',
  rule_type: 'bonus',
  total_score: 10,
  is_veto: false
})

const rules = {
  name: [{ required: true, message: '请输入规则名称', trigger: 'blur' }],
  description: [{ required: true, message: '请输入规则描述', trigger: 'blur' }],
  total_score: [{ required: true, message: '请输入分数', trigger: 'blur' }]
}

// 计算属性 - 带分页
const bonusRules = computed(() => {
  const filtered = list.value.filter(r => r.rule_type === 'bonus')
  const start = (bonusPage.value - 1) * bonusPageSize.value
  const end = start + bonusPageSize.value
  return filtered.slice(start, end)
})

const deductionRules = computed(() => {
  const filtered = list.value.filter(r => r.rule_type === 'deduction')
  const start = (deductionPage.value - 1) * deductionPageSize.value
  const end = start + deductionPageSize.value
  return filtered.slice(start, end)
})

// 方法
async function loadRules() {
  loading.value = true
  try {
    const params = {}
    if (searchKeyword.value) {
      params.search = searchKeyword.value
    }
    list.value = await api.rule.list(params)

    // 计算总数
    bonusTotal.value = list.value.filter(r => r.rule_type === 'bonus').length
    deductionTotal.value = list.value.filter(r => r.rule_type === 'deduction').length
  } catch (e) {
    console.error(e)
    ElMessage.error('加载规则失败')
  } finally {
    loading.value = false
  }
}

function handleBonusPageChange() {
  // 页码变化时无需额外操作，computed会自动重新计算
}

function handleBonusSizeChange() {
  bonusPage.value = 1
}

function handleDeductionPageChange() {
  // 页码变化时无需额外操作，computed会自动重新计算
}

function handleDeductionSizeChange() {
  deductionPage.value = 1
}

async function exportRules() {
  try {
    const data = await api.rule.export()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `评分规则_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success(`导出成功，共 ${data.total} 条规则`)
  } catch (e) {
    console.error(e)
    ElMessage.error('导出失败')
  }
}

function showImportDialog() {
  importFileData.value = null
  fileList.value = []
  importDialogVisible.value = true
}

function handleFileChange(file) {
  fileList.value = [file]
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const data = JSON.parse(e.target.result)
      // 支持两种格式：1. { "rules": [...] }  2. [...] (直接数组)
      if (Array.isArray(data)) {
        importFileData.value = data
      } else if (data.rules && Array.isArray(data.rules)) {
        importFileData.value = data.rules
      } else {
        ElMessage.error('文件格式不正确')
      }
    } catch (err) {
      ElMessage.error('JSON解析失败')
    }
  }
  reader.readAsText(file.raw)
}

function downloadTemplate() {
  const link = document.createElement('a')
  link.href = '/upload_rules_template.json'
  link.download = 'upload_rules_template.json'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

async function importRules() {
  if (!importFileData.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  importing.value = true
  try {
    const result = await api.rule.import(importFileData.value)
    if (result.errors && result.errors.length > 0) {
      ElMessage.warning(`导入完成，但有 ${result.errors.length} 条错误`)
    } else {
      ElMessage.success(`成功导入 ${result.imported} 条规则`)
    }
    importDialogVisible.value = false
    fileList.value = []
    loadRules()
  } catch (e) {
    console.error(e)
    ElMessage.error('导入失败')
  } finally {
    importing.value = false
  }
}

async function openCreateDialog(type) {
  editId.value = null
  form.rule_type = type
  form.name = ''
  form.code = ''
  form.version = ''
  form.description = ''
  form.total_score = 10

  // 获取下一个规则代码
  try {
    const code = await api.rule.generateCode(type)
    form.code = code
  } catch (e) {
    console.error(e)
  }

  dialogVisible.value = true
}

function viewRule(row) {
  Object.assign(form, {
    name: row.name,
    code: row.code,
    version: row.version,
    description: row.description || '',
    rule_type: row.rule_type,
    total_score: row.total_score || 0,
    is_veto: row.is_veto || false,
    is_latest: row.is_latest,
    is_enabled: row.is_enabled !== undefined ? row.is_enabled : true
  })
  viewDialogVisible.value = true
}

function editRule(row) {
  editId.value = row.id
  Object.assign(form, {
    name: row.name,
    code: row.code,
    version: row.version,
    description: row.description || '',
    rule_type: row.rule_type,
    total_score: row.total_score || 0,
    is_veto: row.is_veto || false
  })
  dialogVisible.value = true
}

async function submitForm() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (editId.value) {
      await api.rule.update(editId.value, {
        name: form.name,
        description: form.description,
        total_score: form.total_score,
        is_veto: form.rule_type === 'deduction' ? form.is_veto : false
      })
      ElMessage.success('更新成功')
    } else {
      await api.rule.create({
        name: form.name,
        code: form.code,
        description: form.description,
        rule_type: form.rule_type,
        total_score: form.total_score,
        is_veto: form.rule_type === 'deduction' ? form.is_veto : false
      })
      ElMessage.success('创建成功')
    }

    dialogVisible.value = false
    loadRules()
  } catch (e) {
    console.error(e)
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

async function deleteRule(row) {
  try {
    await ElMessageBox.confirm(`确定要删除规则「${row.name}」吗？此操作不可恢复！`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      confirmButtonClass: 'el-button--danger'
    })
    await api.rule.delete(row.id)
    ElMessage.success('删除成功')
    loadRules()
  } catch (e) {
    if (e !== 'cancel') {
      console.error(e)
    }
  }
}

async function toggleEnabled(row) {
  try {
    await api.rule.toggleEnabled(row.id)
    ElMessage.success(row.is_enabled ? '规则已启用' : '规则已禁用')
  } catch (e) {
    // 恢复原状态
    row.is_enabled = !row.is_enabled
    console.error(e)
    ElMessage.error('操作失败')
  }
}

// 查看历史
async function viewHistory(row) {
  currentRuleId.value = row.id
  historyDialogVisible.value = true
  historyLoading.value = true
  try {
    historyList.value = await api.rule.getHistory(row.id)
  } catch (e) {
    console.error(e)
    ElMessage.error('加载历史失败')
  } finally {
    historyLoading.value = false
  }
}

function viewVersion(row) {
  Object.assign(form, {
    name: row.name,
    code: row.code,
    version: row.version,
    description: row.description || '',
    rule_type: row.rule_type,
    total_score: row.total_score || 0,
    is_latest: row.is_latest,
    is_enabled: row.is_enabled !== undefined ? row.is_enabled : true
  })
  viewDialogVisible.value = true
}

async function rollbackToVersion(row) {
  try {
    await ElMessageBox.confirm(`确定要回溯到版本「${row.version}」吗？`, '回溯确认', {
      type: 'warning',
      confirmButtonText: '确定回溯',
      cancelButtonText: '取消'
    })
    await api.rule.rollback(currentRuleId.value, row.id)
    ElMessage.success('回溯成功')
    historyDialogVisible.value = false
    loadRules()
  } catch (e) {
    if (e !== 'cancel') {
      console.error(e)
    }
  }
}

onMounted(() => {
  loadRules()
})
</script>

<style scoped>
.rules-page {
  padding: 0;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left h2 {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.export-btn {
  background: linear-gradient(135deg, #67c23a 0%, #85ce61 100%);
  border: none;
  font-weight: 500;
}

.import-btn {
  background: linear-gradient(135deg, #e6a23c 0%, #f56c6c 100%);
  border: none;
  font-weight: 500;
}

.subtitle {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.rules-card {
  margin-bottom: 20px;
  border-radius: 8px;
  border: none;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.card-title .icon {
  font-size: 20px;
}

.create-btn {
  background: linear-gradient(135deg, #67c23a 0%, #85ce61 100%);
  border: none;
  font-weight: 500;
}

.create-btn-deduction {
  background: linear-gradient(135deg, #f56c6c 0%, #f78989 100%);
  border: none;
  font-weight: 500;
}

.rules-table {
  border-radius: 8px;
  overflow: hidden;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.rule-name {
  font-weight: 500;
  color: #303133;
}

.code-tag {
  background: #f5f7fa;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: #606266;
  font-family: Consolas, Monaco, monospace;
}

.score {
  font-weight: 700;
  font-size: 15px;
}

.score.bonus {
  color: #67c23a;
}

.score.deduction {
  color: #f56c6c;
}

.no-veto {
  color: #909399;
  font-size: 13px;
}

.veto-tip {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
}

.radio-label.bonus {
  color: #67c23a;
}

.radio-label.deduction {
  color: #f56c6c;
}

.rule-form {
  padding: 10px 0;
}

:deep(.el-card__header) {
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
  background: #fafafa;
}

:deep(.el-card__body) {
  padding: 16px 20px;
}

:deep(.el-table th) {
  background: #fafafa !important;
  color: #606266;
  font-weight: 600;
  font-size: 13px;
}

:deep(.el-table td) {
  padding: 12px 0;
}

:deep(.el-table--striped .el-table__body tr.el-table__row--striped td) {
  background: #fafafa;
}

:deep(.el-button-link) {
  padding: 4px 8px;
  font-size: 13px;
}

:deep(.el-dialog__header) {
  padding: 20px 20px 10px;
  border-bottom: 1px solid #f0f0f0;
}

:deep(.el-dialog__body) {
  padding: 20px;
}

:deep(.el-dialog__footer) {
  padding: 10px 20px 20px;
  border-top: 1px solid #f0f0f0;
}
</style>
