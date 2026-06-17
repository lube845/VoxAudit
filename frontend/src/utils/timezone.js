/**
 * Dayjs timezone utility
 * Reads TZ from window.__TZ__ (injected at container startup via docker-entrypoint.sh)
 * Falls back to Asia/Shanghai if not set
 */
import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'

dayjs.extend(utc)
dayjs.extend(timezone)

// Get timezone from window.__TZ__ (injected by docker-entrypoint.sh) or fallback
export const getTimezone = () => {
  if (typeof window !== 'undefined' && window.__TZ__) {
    return window.__TZ__
  }
  return 'Asia/Shanghai' // fallback default
}

/**
 * Format a date with the container's timezone
 * @param {string|Date} date - The date to format
 * @param {string} formatStr - The format string (default: 'YYYY-MM-DD HH:mm:ss')
 * @returns {string} Formatted date string
 */
export function formatDate(date, formatStr = 'YYYY-MM-DD HH:mm:ss') {
  if (!date) return '-'
  return dayjs.tz(date, getTimezone()).format(formatStr)
}

/**
 * Format a date to date only (YYYY-MM-DD)
 * @param {string|Date} date
 * @returns {string}
 */
export function formatDateOnly(date) {
  if (!date) return '-'
  return dayjs.tz(date, getTimezone()).format('YYYY-MM-DD')
}

/**
 * Get current time in the container's timezone
 * @returns {dayjs.Dayjs}
 */
export function now() {
  return dayjs().tz(getTimezone())
}

/**
 * Get start of day in the container's timezone
 * @param {string|Date} date
 * @returns {dayjs.Dayjs}
 */
export function startOfDay(date) {
  return dayjs.tz(date, getTimezone()).startOf('day')
}

/**
 * Get end of day in the container's timezone
 * @param {string|Date} date
 * @returns {dayjs.Dayjs}
 */
export function endOfDay(date) {
  return dayjs.tz(date, getTimezone()).endOf('day')
}

export default {
  formatDate,
  formatDateOnly,
  now,
  startOfDay,
  endOfDay,
  dayjs,
  getTimezone
}