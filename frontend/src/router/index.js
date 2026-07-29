import { createRouter, createWebHistory } from 'vue-router'
import api from '@/api'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue')
  },
  {
    path: '/',
    name: 'Layout',
    component: () => import('@/views/Layout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/home'
      },
      {
        path: '/home',
        name: 'Home',
        component: () => import('@/views/Home.vue')
      },
      {
        path: '/rules',
        name: 'Rules',
        component: () => import('@/views/Rules.vue')
      },
      {
        path: '/recordings',
        name: 'Recordings',
        component: () => import('@/views/Recordings.vue')
      },
      {
        path: '/recordings/:id',
        name: 'RecordingDetail',
        component: () => import('@/views/RecordingDetail.vue')
      },
      {
        path: '/export',
        name: 'Export',
        component: () => import('@/views/Export.vue')
      },
      {
        path: '/storage',
        name: 'Storage',
        component: () => import('@/views/StorageCleanup.vue'),
        meta: { requiresAdmin: true }
      },
      {
        path: '/user-stats',
        name: 'UserStats',
        component: () => import('@/views/UserStats.vue'),
        meta: { requiresAdmin: true }
      },
      {
        path: '/system-settings',
        name: 'SystemSettings',
        component: () => import('@/views/SystemSettings.vue'),
        meta: { requiresAdmin: true }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const userInfo = api.auth.getUserInfo()
  if (to.meta.requiresAuth && !userInfo) {
    next('/login')
  } else if (to.meta.requiresAdmin && userInfo?.loginid !== 'admin') {
    next('/home')
  } else if (to.path === '/login' && userInfo) {
    next('/home')
  } else {
    next()
  }
})

export default router