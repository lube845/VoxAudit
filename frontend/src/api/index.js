import axios from 'axios'
import { ElMessage } from 'element-plus'

const SESSION_EXPIRE_HOURS = 8

const getUserInfo = () => {
  const info = localStorage.getItem('user_info')
  if (!info) return null
  const userInfo = JSON.parse(info)

  // 检查会话是否过期
  if (userInfo.login_time) {
    const expireMs = SESSION_EXPIRE_HOURS * 60 * 60 * 1000
    if (Date.now() - userInfo.login_time * 1000 > expireMs) {
      localStorage.removeItem('user_info')
      ElMessage.warning('登录已过期，请重新登录')
      window.location.href = '/login'
      return null
    }
  }
  return userInfo
}

const getEncodedUserInfo = () => {
  const info = getUserInfo()
  if (!info) return null
  // Use UTF-8 encoding to handle non-Latin1 characters (e.g., Chinese names)
  const str = JSON.stringify(info)
  return btoa(unescape(encodeURIComponent(str)))
}

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 30000
})

request.interceptors.request.use(
  config => {
    const encoded = getEncodedUserInfo()
    if (encoded) {
      config.headers['X-User-Info'] = encoded
    }
    return config
  },
  error => Promise.reject(error)
)

request.interceptors.response.use(
  response => response.data,
  error => {
    const { response } = error
    const message = response?.data?.detail || response?.data?.message || '请求失败'
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

export default {
  auth: {
    login: (data) => request.post('/auth/login', data),
    getUserInfo: () => {
      const info = localStorage.getItem('user_info')
      return info ? JSON.parse(info) : null
    },
    logout: () => {
      localStorage.removeItem('user_info')
    }
  },

  rule: {
    list: (params) => request.get('/rules', { params }),
    get: (id) => request.get(`/rules/${id}`),
    create: (data) => request.post('/rules', data),
    update: (id, data) => request.put(`/rules/${id}`, data),
    delete: (id) => request.delete(`/rules/${id}`),
    toggleEnabled: (id) => request.patch(`/rules/${id}/toggle-enabled`),
    generateCode: (ruleType) => request.get(`/rules/generate-code/${ruleType}`),
    export: () => request.get('/rules/ruleexport'),
    import: (data) => request.post('/rules/ruleimport', data),

    // 规则历史
    getHistory: (ruleId) => request.get(`/rules/${ruleId}/history`),
    getVersion: (versionId) => request.get(`/rules/history/${versionId}`),
    rollback: (ruleId, versionId) => request.post(`/rules/${ruleId}/rollback/${versionId}`),
    deleteVersion: (ruleId, versionId) => request.delete(`/rules/${ruleId}/history/${versionId}`),
    refineDescription: (data) => request.post('/rules/refine-description', data),
  },

  recording: {
    list: (params) => {
      // 过滤掉无效的分数筛选参数，避免422
      const filtered = { ...params }
      if (filtered.score_dimension && filtered.score_operator && filtered.score_value !== '') {
        filtered.score_value = Number(filtered.score_value)
      } else {
        delete filtered.score_dimension
        delete filtered.score_operator
        delete filtered.score_value
      }
      // is_rejected 为空字符串时删除，避免 FastAPI bool 类型解析错误
      if (filtered.is_rejected === '' || filtered.is_rejected === null) {
        delete filtered.is_rejected
      }
      return request.get('/recordings', { params: filtered }).then(res => {
        // 确保列表中的 id 为整数类型，避免因 JSON 解析导致 id 变成字符串
        if (res.items) {
          res.items = res.items.map(item => ({ ...item, id: Number(item.id) }))
        }
        return res
      })
    },
    get: (id) => request.get(`/recordings/${Number(id)}`),
    initUpload: (data) => request.post('/recordings/init-upload', data),
    upload: (id, formData) => request.post(`/recordings/${Number(id)}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }),
    delete: (id) => request.delete(`/recordings/${Number(id)}`),
    getScore: (id) => request.get(`/recordings/${Number(id)}/score`),
    triggerTranscribe: (id) => request.post(`/recordings/${Number(id)}/transcribe`),
    triggerScore: (id) => request.post(`/recordings/${Number(id)}/score`),
    getPlayUrl: (id) => request.get(`/recordings/${Number(id)}/play`),
    retryTranscribe: (id) => request.post(`/recordings/${Number(id)}/transcribe`),
    retryScore: (id) => request.post(`/recordings/${Number(id)}/score`),
    batchRetry: (ids) => request.post('/recordings/batch-retry', ids.map(id => Number(id))),
  },

  statistics: {
    overview: (params) => request.get('/statistics/overview', { params }),
    trend: (days) => request.get('/statistics/trend', { params: { days } }),
    agentStats: (params) => request.get('/statistics/agent-stats', { params }),
    ruleStats: (params) => request.get('/statistics/rule-stats', { params }),
    ruleHitStats: (params) => request.get('/statistics/rule-hit-stats', { params }),
  },

  export: {
    agents: () => request.get('/export/agents'),
    getReport: (params) => request.get('/export/report', { params, responseType: 'blob' }),
    exportSingleRecording: (recordingId) => request.get(`/export/recording/${Number(recordingId)}`, { responseType: 'blob' }),
  },

  agent: {
    list: () => request.get('/export/agents'),
  },

  storage: {
    getInfo: () => request.get('/storage/info'),
    listObjects: (params) => request.get('/storage/objects', { params }),
    delete: (data) => request.post('/storage/delete', data),
    getCacheInfo: () => request.get('/storage/cache'),
    clearCache: (cacheType) => request.post('/storage/cache/clear', { cache_type: cacheType }),
  },

  userStats: {
    getOverview: (params) => request.get('/statistics/users/overview', { params }),
    getUsersList: (params) => request.get('/statistics/users/list', { params }),
    getUserDetail: (loginid, params) => request.get(`/statistics/users/${loginid}/detail`, { params }),
  },

  systemSettings: {
    getConfig: () => request.get('/system-settings/config'),
    getLlmConfig: () => request.get('/system-settings/config/llm'),
    updateLlmConfig: (data) => request.put('/system-settings/config/llm', data),
    updateAsrConfig: (data) => request.put('/system-settings/config/asr', data),
    testLlmConfig: (data) => request.post('/system-settings/config/llm/test', data),
    testAsrConfig: (data) => request.post('/system-settings/config/asr/test', data),
    getPrompts: () => request.get('/system-settings/prompts'),
    updatePrompts: (data) => request.put('/system-settings/prompts', data),
    resetPrompts: () => request.post('/system-settings/prompts/reset'),
  }
}