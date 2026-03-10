import { createRouter, createWebHistory } from 'vue-router';
import Login from '../views/Login.vue';
import Register from '../views/Register.vue';
import Home from '../views/Home.vue';
import Chat from '../views/Chat.vue';
import JudgeReport from '../views/JudgeReport.vue';
import DebateLobby from '../views/DebateLobby.vue';
import DebateRoom from '../views/DebateRoom.vue';
import Wallet from '../views/Wallet.vue';
import Me from '../views/Me.vue';
import Notifications from '../views/Notifications.vue';
import DebateOpsAdmin from '../views/DebateOpsAdmin.vue';
import store from '../store';
import {
  hasAnyOpsPermission,
  hasRequiredOpsPermissions,
  normalizeOpsRbacMe,
} from '../ops-permission-utils';

const routes = [
  { path: '/', redirect: '/home' },
  { path: '/home', name: 'Home', component: Home, meta: { requiresAuth: true } },
  { path: '/chat', name: 'Chat', component: Chat, meta: { requiresAuth: true } },
  { path: '/debate', name: 'DebateLobby', component: DebateLobby, meta: { requiresAuth: true } },
  { path: '/debate/sessions/:id', name: 'DebateRoom', component: DebateRoom, meta: { requiresAuth: true } },
  {
    path: '/debate/ops',
    name: 'DebateOpsAdmin',
    component: DebateOpsAdmin,
    meta: { requiresAuth: true, requiresOpsAccess: true },
  },
  { path: '/judge-report', name: 'JudgeReport', component: JudgeReport, meta: { requiresAuth: true } },
  { path: '/wallet', name: 'Wallet', component: Wallet, meta: { requiresAuth: true } },
  { path: '/me', name: 'Me', component: Me, meta: { requiresAuth: true } },
  { path: '/notifications', name: 'Notifications', component: Notifications, meta: { requiresAuth: true } },
  { path: '/login', name: 'Login', component: Login },
  { path: '/register', name: 'Register', component: Register },

];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

async function loadOpsSnapshotForGuard() {
  try {
    const response = await store.dispatch('getOpsRbacMe');
    return normalizeOpsRbacMe(response);
  } catch (error) {
    const cached = store.getters.getOpsRbacMe;
    if (cached) {
      return normalizeOpsRbacMe(cached);
    }
    throw error;
  }
}

// Navigation guard for authenticated routes and ops permissions
router.beforeEach(async (to, from, next) => {
  const isAuthenticated = !!store.getters.getUser;
  if (to.matched.some((record) => record.meta.requiresAuth) && !isAuthenticated) {
    return next({ name: 'Login' });
  }

  const requiresOpsAccess = to.matched.some((record) => record.meta.requiresOpsAccess);
  if (!requiresOpsAccess) {
    return next();
  }

  const requiredOpsPermissions = to.matched.flatMap(
    (record) => record.meta.requiredOpsPermissions || [],
  );

  try {
    const snapshot = await loadOpsSnapshotForGuard();
    const allowed = requiredOpsPermissions.length > 0
      ? hasRequiredOpsPermissions(snapshot, requiredOpsPermissions)
      : hasAnyOpsPermission(snapshot);
    if (!allowed) {
      return next({
        name: 'DebateLobby',
        query: {
          ...to.query,
          noOpsAccess: '1',
        },
      });
    }
  } catch (error) {
    console.error('Failed to verify ops route permission:', error);
    return next({
      name: 'DebateLobby',
      query: {
        ...to.query,
        noOpsAccess: '1',
      },
    });
  }

  return next();
});

export default router;
