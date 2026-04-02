import {
  createRouter,
  createWebHistory,
  type NavigationGuardNext,
  type RouteLocationNormalized,
  type RouteRecordRaw,
} from 'vue-router';
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
import PhoneBind from '../views/PhoneBind.vue';
import store from '../store';
import {
  hasAnyOpsPermission,
  hasRequiredOpsPermissions,
  normalizeOpsRbacMe,
} from '../ops-permission-utils.ts';
import type { OpsPermissionInputKey, OpsRbacMe } from '../types/api';
import type { AuthUserProfile, RootGettersSnapshot } from '../store/types';

type StoreLike = {
  getters: RootGettersSnapshot;
  dispatch: (type: string, payload?: unknown) => Promise<unknown>;
};

interface AppRouteMeta {
  requiresAuth?: boolean;
  requiresOpsAccess?: boolean;
  requiredOpsPermissions?: OpsPermissionInputKey[];
}

type AppRouteRecord = RouteRecordRaw & {
  meta?: AppRouteMeta;
};

const appStore = store as unknown as StoreLike;

const routes: AppRouteRecord[] = [
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
  { path: '/bind-phone', name: 'PhoneBind', component: PhoneBind, meta: { requiresAuth: true } },
  { path: '/login', name: 'Login', component: Login },
  { path: '/register', name: 'Register', component: Register },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

function isPhoneBindRequired(user: AuthUserProfile | null | undefined): boolean {
  if (!user) {
    return false;
  }
  const hasBindFlag = Object.prototype.hasOwnProperty.call(user, 'phoneBindRequired');
  if (hasBindFlag) {
    return !!user.phoneBindRequired;
  }
  const phone = String(user.phoneE164 || '').trim();
  return !phone;
}

async function loadOpsSnapshotForGuard(): Promise<OpsRbacMe> {
  try {
    const response = await appStore.dispatch('getOpsRbacMe');
    return normalizeOpsRbacMe(response as Record<string, unknown>);
  } catch (error) {
    const cached = appStore.getters.getOpsRbacMe;
    if (cached) {
      return normalizeOpsRbacMe(cached);
    }
    throw error;
  }
}

// Navigation guard for authenticated routes and ops permissions.
router.beforeEach(async (
  to: RouteLocationNormalized,
  _from: RouteLocationNormalized,
  next: NavigationGuardNext,
) => {
  const isAuthenticated = !!appStore.getters.isAuthenticated;
  if (to.matched.some((record) => (record.meta as AppRouteMeta)?.requiresAuth) && !isAuthenticated) {
    return next({ name: 'Login' });
  }

  const user = appStore.getters.getUser;
  const phoneBindRequired = isPhoneBindRequired(user);
  if (isAuthenticated && phoneBindRequired && to.name !== 'PhoneBind') {
    return next({ name: 'PhoneBind' });
  }
  if (isAuthenticated && !phoneBindRequired && to.name === 'PhoneBind') {
    return next({ name: 'Home' });
  }

  const requiresOpsAccess = to.matched.some((record) => (record.meta as AppRouteMeta)?.requiresOpsAccess);
  if (!requiresOpsAccess) {
    return next();
  }

  const requiredOpsPermissions = to.matched.flatMap(
    (record) => ((record.meta as AppRouteMeta)?.requiredOpsPermissions || []),
  ) as OpsPermissionInputKey[];

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
