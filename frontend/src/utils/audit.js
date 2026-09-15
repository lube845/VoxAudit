/**
 * 前端埋点工具
 *
 * 用法：
 *   import { audit } from '@/utils/audit'
 *   audit('home.filter', 'home', null, { date_range: '2026-09-01~2026-09-14' })
 *
 * 行为：
 *   - 5 分钟内同 actor + target + action 去重（防误点击刷屏）
 *   - 异步上报，不阻塞 UI
 *   - 上报失败不影响业务
 *   - 未登录直接 return
 */
import api from '@/api'

const DEDUP_WINDOW_MS = 5 * 60 * 1000
const recent = new Map()  // key → lastTimestamp(ms)

function buildKey(actor, action, targetType, targetId) {
  return `${actor}::${action}::${targetType || ''}::${targetId || ''}`
}

/**
 * 记录一条审计日志（前端埋点）
 *
 * @param {string} action         例如 'page.view' / 'rules.search'
 * @param {string|null} target_type  例如 'rule' / 'recording' / 'page'
 * @param {string|null} target_id    例如 rule_id / route_path
 * @param {object|null} detail       业务上下文（不含敏感字段原值）
 */
export function audit(action, target_type, target_id, detail) {
  try {
    const userInfo = api.auth.getUserInfo()
    if (!userInfo) return

    const actor = userInfo.loginid
    const key = buildKey(actor, action, target_type, target_id)
    const now = Date.now()
    const last = recent.get(key)
    if (last && now - last < DEDUP_WINDOW_MS) return
    recent.set(key, now)

    // 异步上报，不 await
    api.auditLog
      .record({ action, target_type, target_id, detail })
      .catch(() => { /* 失败不影响业务 */ })
  } catch {
    // 静默吞掉所有异常
  }
}

/**
 * 清空去重缓存（仅测试用）
 */
export function _clearAuditDedup() {
  recent.clear()
}