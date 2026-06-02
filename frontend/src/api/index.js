import axios from 'axios'
import { ElMessage } from 'element-plus'

const getUserInfo = () => {
  const info = localStorage.getItem('user_info')
  return info ? JSON.parse(info) : null
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
    generateCode: (ruleType) => request.get(`/rules/generate-code/${ruleType}`),
    export: () => request.get('/rules/ruleexport'),
    import: (data) => request.post('/rules/ruleimport', data),

    // 规则历史
    getHistory: (ruleId) => request.get(`/rules/${ruleId}/history`),
    getVersion: (versionId) => request.get(`/rules/history/${versionId}`),
    rollback: (ruleId, versionId) => request.post(`/rules/${ruleId}/rollback/${versionId}`),
    deleteVersion: (ruleId, versionId) => request.delete(`/rules/${ruleId}/history/${versionId}`),
  },

  recording: {
    list: (params) => request.get('/recordings', { params }),
    get: (id) => request.get(`/recordings/${id}`),
    initUpload: (data) => request.post('/recordings/init-upload', data),
    upload: (id, formData) => request.post(`/recordings/${id}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }),
    delete: (id) => request.delete(`/recordings/${id}`),
    getScore: (id) => request.get(`/recordings/${id}/score`),
    triggerTranscribe: (id) => request.post(`/recordings/${id}/transcribe`),
    triggerScore: (id) => request.post(`/recordings/${id}/score`),
    getPlayUrl: (id) => request.get(`/recordings/${id}/play`),
    retryTranscribe: (id) => request.post(`/recordings/${id}/transcribe`),
    retryScore: (id) => request.post(`/recordings/${id}/score`),
  },

  statistics: {
    overview: (params) => request.get('/statistics/overview', { params }),
    trend: (days) => request.get('/statistics/trend', { params: { days } }),
    agentStats: (params) => request.get('/statistics/agent-stats', { params }),
    ruleStats: (params) => request.get('/statistics/rule-stats', { params }),
  },

  export: {
    agents: () => request.get('/export/agents'),
    getReport: (params) => request.get('/export/report', { params, responseType: 'blob' }),
    exportSingleRecording: (recordingId) => request.get(`/export/recording/${recordingId}`, { responseType: 'blob' }),
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
    getLeaderboard: (params) => request.get('/statistics/users/leaderboard', { params }),
  }
}