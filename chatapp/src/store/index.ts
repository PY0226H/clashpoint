// @ts-nocheck
import { createStore } from 'vuex';
import axios from 'axios';
import { getUrlBase } from '../utils';
import { initSSE } from '../utils';
import {
  sendAppExitEvent,
  sendAppStartEvent,
  sendChatCreatedEvent,
  sendChatJoinedEvent,
  sendChatLeftEvent,
  sendJudgeRealtimeRefreshEvent,
  sendMessageSentEvent,
  sendNavigationEvent,
  sendUserLoginEvent,
  sendUserLogoutEvent,
  sendUserRegisterEvent,
} from '../analytics/event';
import {
  normalizeJudgeRefreshSummaryMetrics,
  normalizeJudgeRefreshSummaryQuery,
} from '../judge-refresh-summary-utils';
import { normalizeWalletLedgerLimit } from '../wallet-utils';
import { toDisplayMessage, upsertMessage } from '../message-store-utils';
import { pickActiveChannelId } from '../channel-utils';
import {
  actionBindPhoneV2,
  actionGetOpsRbacMe,
  actionListOpsRoleAssignments,
  actionRequestJudgeRejudgeOps,
  actionRevokeOpsRoleAssignment,
  actionSendSmsCodeV2,
  actionSetPasswordV2,
  actionSigninOtpV2,
  actionSigninPasswordV2,
  actionSignupEmailV2,
  actionSignupPhoneV2,
  actionUpsertOpsRoleAssignment,
  actionWechatBindPhoneV2,
  actionWechatChallengeV2,
  actionWechatSigninV2,
} from './actions-auth-ops.ts';
import {
  actionCreateDebateSessionOps,
  actionCreateDebateTopicOps,
  actionExecuteJudgeReplayOps,
  actionGetJudgeReplayPreviewOps,
  actionGetOpsObservabilityConfig,
  actionListJudgeReplayActionsOps,
  actionUpdateDebateSessionOps,
  actionUpdateDebateTopicOps,
  actionUpsertOpsObservabilityAnomalyState,
  actionUpsertOpsObservabilityThresholds,
} from './actions-debate-ops.ts';
import {
  actionFetchDrawVoteStatus,
  actionFetchJudgeReport,
  actionJoinDebateSession,
  actionListDebateSessions,
  actionListDebateTopics,
  actionListJudgeReviewsOps,
  actionListJudgeTraceReplayOps,
  actionRequestJudgeJob,
  actionSubmitDrawVote,
} from './actions-debate-lifecycle.ts';
import {
  actionFetchWalletBalance,
  actionGetIapOrderByTransaction,
  actionListIapProducts,
  actionListWalletLedger,
  actionPinDebateMessage,
  actionVerifyIapOrder,
} from './actions-payment-wallet.ts';
import {
  actionLoadUserState,
  actionRefreshAccessTickets,
  actionRefreshSession,
} from './actions-session-tickets.ts';
import {
  actionCreateDebateMessage,
  actionFetchJudgeRefreshSummary,
  actionFetchJudgeRefreshSummaryMetrics,
  actionListDebateMessages,
  actionListDebatePinnedMessages,
  actionSendMessage,
  actionUploadFiles,
} from './actions-realtime-analytics.ts';
import { v4 as uuidv4 } from 'uuid';
import packageJson from '../../package.json';

const AUTH_BYPASS_PATHS = new Set([
  '/signin',
  '/signup',
  '/auth/refresh',
]);

const withAuthHeader = (store, url, headers = {}) => {
  const merged = { ...headers };
  if (!merged.Authorization && store.state.token && !AUTH_BYPASS_PATHS.has(url)) {
    merged.Authorization = `Bearer ${store.state.token}`;
  }
  return merged;
};

// Wrap axios calls with refresh-once retry for 401 responses.
const network = async (store, method, url, data = null, headers = {}, allowRefreshRetry = true) => {
  const config = {
    method,
    url: `${getUrlBase()}${url}`,
    headers: withAuthHeader(store, url, headers),
    data,
    withCredentials: true,
  };
  try {
    return await axios(config);
  } catch (error) {
    const status = error?.response?.status;
    if (status === 401 && allowRefreshRetry && !AUTH_BYPASS_PATHS.has(url)) {
      try {
        await store.dispatch('refreshSession');
        return await axios({
          ...config,
          headers: withAuthHeader(store, url, headers),
        });
      } catch (_refreshError) {
        await store.dispatch('logout', { skipRemote: true });
        window.location.href = '/login';
        return;
      }
    }
    throw error;
  }
};

const buildQueryString = (params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') {
      return;
    }
    query.set(key, String(value));
  });
  const raw = query.toString();
  return raw ? `?${raw}` : '';
};

export default createStore({
  state: {
    context: {},        // Context for analytics events
    user: null,         // User information
    token: null,        // Authentication token
    channels: [],       // List of channels
    messages: {},       // Messages hashmap, keyed by channel ID
    users: {},          // Users hashmap keyed by user ID
    activeChannel: null,
    sse: null,
    accessTickets: null,
    sseReconnectAttempts: 0,
    sseReconnectTimer: null,
    latestJudgeReportEvent: null,
    latestDrawVoteResolvedEvent: null,
    opsRbacMe: null,
  },
  mutations: {
    setSSE(state, sse) {
      state.sse = sse;
    },
    setUser(state, user) {
      state.user = user;
    },
    setToken(state, token) {
      state.token = token;
    },
    setAccessTickets(state, tickets) {
      state.accessTickets = tickets;
    },
    setSSEReconnectAttempts(state, attempts) {
      state.sseReconnectAttempts = attempts;
    },
    setSSEReconnectTimer(state, timerId) {
      state.sseReconnectTimer = timerId;
    },
    setLatestJudgeReportEvent(state, event) {
      state.latestJudgeReportEvent = event;
    },
    setLatestDrawVoteResolvedEvent(state, event) {
      state.latestDrawVoteResolvedEvent = event;
    },
    setOpsRbacMe(state, payload) {
      state.opsRbacMe = payload;
    },
    setChannels(state, channels) {
      state.channels = channels;
    },
    setUsers(state, users) {
      state.users = users;
    },
    setMessages(state, { channelId, messages }) {
      const formattedMessages = messages.map((message) => toDisplayMessage(message));
      state.messages[channelId] = formattedMessages.reverse();
    },
    addChannel(state, channel) {
      state.channels.push(channel);
      state.messages[channel.id] = [];  // Initialize message list for the new channel
    },
    addMessage(state, { channelId, message }) {
      const existing = state.messages[channelId] || [];
      state.messages[channelId] = upsertMessage(existing, message);
    },
    setActiveChannel(state, channelId) {
      const channel = state.channels.find((c) => c.id === channelId);
      state.activeChannel = channel || null;
    },
    loadUserState(state) {
      setContext(state);

      console.log("context:", state.context);

      const storedUser = localStorage.getItem('user');
      const storedChannels = localStorage.getItem('channels');
      // we do not store messages in local storage, so this is always empty
      const storedMessages = localStorage.getItem('messages');
      const storedUsers = localStorage.getItem('users');
      const storedActiveChannelId = localStorage.getItem('activeChannelId');

      if (storedUser) {
        const parsedUser = JSON.parse(storedUser);
        state.user = normalizeUserForPhoneGate(parsedUser);
        localStorage.setItem('user', JSON.stringify(state.user));
      }
      if (storedChannels) {
        state.channels = JSON.parse(storedChannels);
      }
      if (storedMessages) {
        state.messages = JSON.parse(storedMessages);
      }
      if (storedUsers) {
        state.users = JSON.parse(storedUsers);
      }
      if (storedActiveChannelId) {
        const id = JSON.parse(storedActiveChannelId);
        const channel = state.channels.find((c) => c.id === id);
        state.activeChannel = channel;
      }
      if (!state.activeChannel && state.channels.length > 0) {
        const fallbackId = pickActiveChannelId(state.channels, null);
        const fallbackChannel = state.channels.find((c) => c.id === fallbackId);
        state.activeChannel = fallbackChannel || null;
        if (fallbackId != null) {
          localStorage.setItem('activeChannelId', JSON.stringify(fallbackId));
        }
      }
    },
  },
  actions: {
    async initSSE({ state, commit, dispatch }) {
      if (!state.token) {
        return;
      }
      if (state.sseReconnectTimer) {
        clearTimeout(state.sseReconnectTimer);
        commit('setSSEReconnectTimer', null);
      }
      await dispatch('refreshAccessTickets');
      if (state.sse) {
        state.sse.close();
      }
      const notifyToken = state.accessTickets?.notifyToken;
      if (!notifyToken) {
        console.warn('notify ticket is missing, skip SSE init');
        return;
      }
      const sse = initSSE(this, notifyToken, {
        onOpen: () => {
          commit('setSSEReconnectAttempts', 0);
        },
        onError: () => {
          dispatch('scheduleSSEReconnect');
        },
      });
      commit('setSSE', sse);
    },
    closeSSE({ state, commit }) {
      if (state.sse) {
        state.sse.close();
        commit('setSSE', null);
      }
      if (state.sseReconnectTimer) {
        clearTimeout(state.sseReconnectTimer);
        commit('setSSEReconnectTimer', null);
      }
      commit('setSSEReconnectAttempts', 0);
    },
    async signup({ commit }, { email, fullname, password }) {
      try {
        const response = await network(this, 'post', '/signup', {
          email,
          fullname,
          password,
        });

        const user = await loadState(response, this, commit);

        return user;
      } catch (error) {
        console.error('Signup failed:', error);
        throw error;
      }
    },
    async signin({ commit }, { email, password }) {
      try {
        const response = await network(this, 'post', '/signin', {
          email,
          password,
        });

        const user = await loadState(response, this, commit);
        return user;
      } catch (error) {
        console.error('Login failed:', error);
        throw error;
      }
    },
    async sendSmsCodeV2(_ctx, { phone, scene }) {
      return actionSendSmsCodeV2({
        network,
        store: this,
        phone,
        scene,
      });
    },
    async signupPhoneV2({ commit }, { phone, smsCode, password, fullname }) {
      return actionSignupPhoneV2({
        network,
        store: this,
        loadState,
        commit,
        phone,
        smsCode,
        password,
        fullname,
      });
    },
    async signupEmailV2({ commit }, { email, phone, smsCode, password, fullname }) {
      return actionSignupEmailV2({
        network,
        store: this,
        loadState,
        commit,
        email,
        phone,
        smsCode,
        password,
        fullname,
      });
    },
    async signinPasswordV2({ commit }, { account, accountType, password }) {
      return actionSigninPasswordV2({
        network,
        store: this,
        loadState,
        commit,
        account,
        accountType,
        password,
      });
    },
    async signinOtpV2({ commit }, { phone, smsCode }) {
      return actionSigninOtpV2({
        network,
        store: this,
        loadState,
        commit,
        phone,
        smsCode,
      });
    },
    async wechatChallengeV2() {
      return actionWechatChallengeV2({
        network,
        store: this,
      });
    },
    async wechatSigninV2({ commit }, { state, code }) {
      return actionWechatSigninV2({
        network,
        store: this,
        loadState,
        commit,
        state,
        code,
      });
    },
    async wechatBindPhoneV2(
      { commit },
      {
        wechatTicket,
        phone,
        smsCode,
        password,
        fullname,
      },
    ) {
      return actionWechatBindPhoneV2({
        network,
        store: this,
        loadState,
        commit,
        wechatTicket,
        phone,
        smsCode,
        password,
        fullname,
      });
    },
    async bindPhoneV2({ state, commit }, { phone, smsCode }) {
      return actionBindPhoneV2({
        network,
        store: this,
        commit,
        token: state.token,
        phone,
        smsCode,
      });
    },
    async setPasswordV2(_ctx, { password, smsCode }) {
      return actionSetPasswordV2({
        network,
        store: this,
        password,
        smsCode,
      });
    },
    async logout({ state, commit }, { skipRemote = false } = {}) {
      if (!skipRemote && state.token) {
        try {
          await network(this, 'post', '/auth/logout', null, {}, false);
        } catch (error) {
          console.warn('remote logout failed:', error);
        }
      }
      // Clear local storage and state
      localStorage.removeItem('user');
      localStorage.removeItem('channels');
      localStorage.removeItem('messages');
      localStorage.removeItem('activeChannelId');

      commit('setUser', null);
      commit('setToken', null);
      commit('setAccessTickets', null);
      commit('setChannels', []);
      commit('setLatestJudgeReportEvent', null);
      commit('setLatestDrawVoteResolvedEvent', null);
      commit('setOpsRbacMe', null);

      // close SSE
      await this.dispatch('closeSSE');
    },
    setActiveChannel({ commit }, channel) {
      commit('setActiveChannel', channel);
      console.log("setActiveChannel:", channel);
      localStorage.setItem('activeChannelId', JSON.stringify(channel));
    },
    addChannel({ commit }, channel) {
      commit('addChannel', channel);

      // Update the channels and messages in local storage
      localStorage.setItem('channels', JSON.stringify(this.state.channels));
      localStorage.setItem('messages', JSON.stringify(this.state.messages));
    },
    async createChannel({ state, commit }, { name, members, public: isPublic = false }) {
      const response = await network(
        this,
        'post',
        '/chats',
        {
          name,
          members,
          public: isPublic,
        },
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      const channel = response.data;
      commit('addChannel', channel);
      commit('setActiveChannel', channel.id);
      localStorage.setItem('channels', JSON.stringify(this.state.channels));
      localStorage.setItem('messages', JSON.stringify(this.state.messages));
      localStorage.setItem('activeChannelId', JSON.stringify(channel.id));
      return channel;
    },
    async fetchMessagesForChannel({ state, commit }, channelId) {
      if (!state.messages[channelId] || state.messages[channelId].length === 0) {
        try {
          await this.dispatch('refreshAccessTickets');
          const response = await network(this, 'get', `/chats/${channelId}/messages`, null, {
            Authorization: `Bearer ${state.token}`,
          });
          const messages = response.data;
          commit('setMessages', { channelId, messages });
        } catch (error) {
          console.error(`Failed to fetch messages for channel ${channelId}:`, error);
        }
      }
    },
    async fetchJudgeReport({ state }, { sessionId, maxStageCount = 3, stageOffset = 0 }) {
      return actionFetchJudgeReport({
        network,
        store: this,
        token: state.token,
        sessionId,
        maxStageCount,
        stageOffset,
      });
    },
    async fetchDrawVoteStatus({ state }, { sessionId }) {
      return actionFetchDrawVoteStatus({
        network,
        store: this,
        token: state.token,
        sessionId,
      });
    },
    async submitDrawVote({ state }, { sessionId, agreeDraw }) {
      return actionSubmitDrawVote({
        network,
        store: this,
        token: state.token,
        sessionId,
        agreeDraw,
      });
    },
    async requestJudgeJob({ state }, { sessionId, allowRejudge = false, styleMode = null } = {}) {
      return actionRequestJudgeJob({
        network,
        store: this,
        token: state.token,
        sessionId,
        allowRejudge,
        styleMode,
      });
    },
    async listDebateTopics({ state }, payload = {}) {
      return actionListDebateTopics({
        network,
        store: this,
        buildQueryString,
        token: state.token,
        payload,
      });
    },
    async listDebateSessions({ state }, payload = {}) {
      return actionListDebateSessions({
        network,
        store: this,
        buildQueryString,
        token: state.token,
        payload,
      });
    },
    async listJudgeReviewsOps({ state }, payload = {}) {
      return actionListJudgeReviewsOps({
        network,
        store: this,
        buildQueryString,
        token: state.token,
        payload,
      });
    },
    async listJudgeTraceReplayOps({ state }, payload = {}) {
      return actionListJudgeTraceReplayOps({
        network,
        store: this,
        buildQueryString,
        token: state.token,
        payload,
      });
    },
    async listJudgeReplayActionsOps({ state }, payload = {}) {
      return actionListJudgeReplayActionsOps({
        network,
        store: this,
        buildQueryString,
        token: state.token,
        payload,
      });
    },
    async getJudgeReplayPreviewOps({ state }, { scope, jobId } = {}) {
      return actionGetJudgeReplayPreviewOps({
        network,
        store: this,
        buildQueryString,
        token: state.token,
        scope,
        jobId,
      });
    },
    async executeJudgeReplayOps({ state }, { scope, jobId, reason = null } = {}) {
      return actionExecuteJudgeReplayOps({
        network,
        store: this,
        token: state.token,
        scope,
        jobId,
        reason,
      });
    },
    async listOpsRoleAssignments({ state }) {
      return actionListOpsRoleAssignments({
        network,
        store: this,
        token: state.token,
      });
    },
    async getOpsRbacMe({ state, commit }) {
      return actionGetOpsRbacMe({
        network,
        store: this,
        commit,
        token: state.token,
      });
    },
    async getOpsObservabilityConfig({ state }) {
      return actionGetOpsObservabilityConfig({
        network,
        store: this,
        token: state.token,
      });
    },
    async upsertOpsObservabilityThresholds({ state }, payload = {}) {
      return actionUpsertOpsObservabilityThresholds({
        network,
        store: this,
        token: state.token,
        payload,
      });
    },
    async upsertOpsObservabilityAnomalyState({ state }, payload = {}) {
      return actionUpsertOpsObservabilityAnomalyState({
        network,
        store: this,
        token: state.token,
        payload,
      });
    },
    async upsertOpsRoleAssignment({ state }, { userId, role } = {}) {
      return actionUpsertOpsRoleAssignment({
        network,
        store: this,
        token: state.token,
        userId,
        role,
      });
    },
    async revokeOpsRoleAssignment({ state }, { userId } = {}) {
      return actionRevokeOpsRoleAssignment({
        network,
        store: this,
        token: state.token,
        userId,
      });
    },
    async requestJudgeRejudgeOps({ state }, { sessionId } = {}) {
      return actionRequestJudgeRejudgeOps({
        network,
        store: this,
        token: state.token,
        sessionId,
      });
    },
    async createDebateTopicOps(
      { state },
      {
        title,
        description,
        category,
        stancePro,
        stanceCon,
        contextSeed = null,
        isActive = true,
      } = {},
    ) {
      return actionCreateDebateTopicOps({
        network,
        store: this,
        token: state.token,
        title,
        description,
        category,
        stancePro,
        stanceCon,
        contextSeed,
        isActive,
      });
    },
    async updateDebateTopicOps(
      { state },
      {
        topicId,
        title,
        description,
        category,
        stancePro,
        stanceCon,
        contextSeed = null,
        isActive = true,
      } = {},
    ) {
      return actionUpdateDebateTopicOps({
        network,
        store: this,
        token: state.token,
        topicId,
        title,
        description,
        category,
        stancePro,
        stanceCon,
        contextSeed,
        isActive,
      });
    },
    async createDebateSessionOps(
      { state },
      {
        topicId,
        status = 'scheduled',
        scheduledStartAt,
        endAt,
        maxParticipantsPerSide = 500,
      } = {},
    ) {
      return actionCreateDebateSessionOps({
        network,
        store: this,
        token: state.token,
        topicId,
        status,
        scheduledStartAt,
        endAt,
        maxParticipantsPerSide,
      });
    },
    async updateDebateSessionOps(
      { state },
      {
        sessionId,
        status = null,
        scheduledStartAt = null,
        endAt = null,
        maxParticipantsPerSide = null,
      } = {},
    ) {
      return actionUpdateDebateSessionOps({
        network,
        store: this,
        token: state.token,
        sessionId,
        status,
        scheduledStartAt,
        endAt,
        maxParticipantsPerSide,
      });
    },
    async joinDebateSession({ state }, { sessionId, side }) {
      return actionJoinDebateSession({
        network,
        store: this,
        token: state.token,
        sessionId,
        side,
      });
    },
    async listDebateMessages({ state }, { sessionId, lastId = null, limit = 80 } = {}) {
      return actionListDebateMessages({
        network,
        store: this,
        buildQueryString,
        token: state.token,
        sessionId,
        lastId,
        limit,
      });
    },
    async listDebatePinnedMessages({ state }, { sessionId, activeOnly = true, limit = 20 } = {}) {
      return actionListDebatePinnedMessages({
        network,
        store: this,
        buildQueryString,
        token: state.token,
        sessionId,
        activeOnly,
        limit,
      });
    },
    async listIapProducts({ state }, { activeOnly = true } = {}) {
      return actionListIapProducts({
        network,
        store: this,
        buildQueryString,
        token: state.token,
        activeOnly,
      });
    },
    async verifyIapOrder(
      { state },
      {
        productId,
        transactionId,
        originalTransactionId = null,
        receiptData,
      } = {},
    ) {
      return actionVerifyIapOrder({
        network,
        store: this,
        token: state.token,
        productId,
        transactionId,
        originalTransactionId,
        receiptData,
      });
    },
    async getIapOrderByTransaction({ state }, { transactionId } = {}) {
      return actionGetIapOrderByTransaction({
        network,
        store: this,
        buildQueryString,
        token: state.token,
        transactionId,
      });
    },
    async fetchWalletBalance({ state }) {
      return actionFetchWalletBalance({
        network,
        store: this,
        token: state.token,
      });
    },
    async listWalletLedger({ state }, { lastId = null, limit = 20 } = {}) {
      return actionListWalletLedger({
        network,
        store: this,
        buildQueryString,
        normalizeWalletLedgerLimit,
        token: state.token,
        lastId,
        limit,
      });
    },
    async createDebateMessage({ state }, { sessionId, content }) {
      return actionCreateDebateMessage({
        network,
        store: this,
        token: state.token,
        sessionId,
        content,
      });
    },
    async pinDebateMessage({ state }, { messageId, pinSeconds, idempotencyKey }) {
      return actionPinDebateMessage({
        network,
        store: this,
        token: state.token,
        messageId,
        pinSeconds,
        idempotencyKey,
      });
    },
    async uploadFiles({ state, commit }, files) {
      try {
        return await actionUploadFiles({
          network,
          store: this,
          dispatch: (action, payload) => this.dispatch(action, payload),
          token: state.token,
          files,
          getUrlBase,
          getAccessTicketToken: () => this.state.accessTickets?.fileToken,
        });
      } catch (error) {
        console.error('Failed to upload files:', error);
        throw error;
      }
    },
    async sendMessage({ state, commit }, payload) {
      try {
        const message = await actionSendMessage({
          network,
          store: this,
          commit,
          token: state.token,
          payload,
        });
        console.log('Message sent:', message);
        return message;
      } catch (error) {
        console.error('Failed to send message:', error);
        throw error;
      }
    },
    addMessage({ commit }, { channelId, message }) {
      commit('addMessage', { channelId, message });
    },
    async loadUserState({ commit, dispatch }) {
      return actionLoadUserState({
        commit,
        dispatch: (action, payload) => dispatch(action, payload),
        getUser: () => this.state.user,
      });
    },
    async appStart({ state }) {
      await sendAppStartEvent(state.context, state.token);
    },
    async appExit({ state }) {
      await sendAppExitEvent(state.context, state.token);
    },
    async userLogin({ state }, payload = {}) {
      await sendUserLoginEvent(state.context, state.token, payload);
    },
    async userLogout({ state }) {
      await sendUserLogoutEvent(
        state.context,
        state.token,
        buildAuthEventPayloadFromUser(state.user),
      );
    },
    async userRegister({ state }, payload = {}) {
      await sendUserRegisterEvent(state.context, state.token, payload);
    },
    async chatCreated({ state }) {
      await sendChatCreatedEvent(state.context, state.token);
    },
    async messageSent({ state }, { chatId, type, size, totalFiles }) {
      await sendMessageSentEvent(state.context, state.token, chatId, type, size, totalFiles);
    },
    async chatJoined({ state }, { chatId }) {
      await sendChatJoinedEvent(state.context, state.token, chatId);
    },
    async chatLeft({ state }, { chatId }) {
      await sendChatLeftEvent(state.context, state.token, chatId);
    },
    async navigation({ state }, { from, to }) {
      await sendNavigationEvent(state.context, state.token, from, to);
    },
    async judgeRealtimeRefresh({ state }, payload) {
      await sendJudgeRealtimeRefreshEvent(state.context, state.token, payload);
    },
    async fetchJudgeRefreshSummary({ state }, payload = {}) {
      return actionFetchJudgeRefreshSummary({
        network,
        store: this,
        buildQueryString,
        normalizeJudgeRefreshSummaryQuery,
        token: state.token,
        payload,
      });
    },
    async fetchJudgeRefreshSummaryMetrics({ state }) {
      return actionFetchJudgeRefreshSummaryMetrics({
        network,
        store: this,
        normalizeJudgeRefreshSummaryMetrics,
        token: state.token,
      });
    },
    async refreshSession({ commit, dispatch }) {
      return actionRefreshSession({
        network,
        store: this,
        commit,
        dispatch: (action, payload) => dispatch(action, payload),
      });
    },
    async refreshAccessTickets({ state, commit }) {
      return actionRefreshAccessTickets({
        network,
        store: this,
        commit,
        token: state.token,
        accessTickets: state.accessTickets,
      });
    },
    scheduleSSEReconnect({ state, commit, dispatch }) {
      if (!state.token) {
        return;
      }
      if (state.sseReconnectTimer) {
        return;
      }
      const attempts = state.sseReconnectAttempts + 1;
      commit('setSSEReconnectAttempts', attempts);
      const baseDelay = Math.min(30000, 1000 * Math.pow(2, Math.max(0, attempts - 1)));
      const jitter = Math.floor(Math.random() * 300);
      const delay = baseDelay + jitter;
      const timerId = setTimeout(async () => {
        commit('setSSEReconnectTimer', null);
        if (!state.token) {
          return;
        }
        try {
          await dispatch('initSSE');
        } catch (error) {
          console.error('SSE reconnect failed:', error);
          dispatch('scheduleSSEReconnect');
        }
      }, delay);
      commit('setSSEReconnectTimer', timerId);
    },
  },
  getters: {
    isAuthenticated(state) {
      return !!state.token;
    },
    getUser(state) {
      return state.user;
    },
    getUserById: (state) => (id) => {
      return state.users[id];
    },
    getChannels(state) {
      // filter out channels that type == 'single'
      return state.channels.filter((channel) => channel.type !== 'single');
    },
    getSingChannels(state) {
      const channels = state.channels.filter((channel) => channel.type === 'single');
      // return channel member that is not myself
      return channels.map((channel) => {
        let members = channel.members;
        const id = members.find((id) => id !== state.user.id);
        channel.recipient = state.users[id];
        return channel;
      });
    },
    getChannelMessages: (state) => (channelId) => {
      return state.messages[channelId] || [];
    },
    getMessagesForActiveChannel(state) {
      if (!state.activeChannel) {
        return [];
      }
      return state.messages[state.activeChannel.id] || [];
    },
    getLatestJudgeReportEvent(state) {
      return state.latestJudgeReportEvent;
    },
    getLatestDrawVoteResolvedEvent(state) {
      return state.latestDrawVoteResolvedEvent;
    },
    getOpsRbacMe(state) {
      return state.opsRbacMe;
    },
  },
});

async function loadState(response, self, commit) {
  const token = response?.data?.accessToken;
  const rawUser = response?.data?.user;
  if (!token || !rawUser) {
    throw new Error('missing access token or user profile in auth response');
  }
  const user = normalizeUserForPhoneGate(rawUser);

  // Persist auth context first. Unbound-phone users only keep the minimal state.
  localStorage.setItem('user', JSON.stringify(user));
  commit('setUser', user);
  commit('setToken', token);
  commit('setAccessTickets', null);

  if (user.phoneBindRequired) {
    applyPhoneBindPendingBootstrap(commit);
    return user;
  }

  try {
    // fetch all platform users
    const usersResp = await network(self, 'get', '/users', null, {
      Authorization: `Bearer ${token}`,
    });
    const users = usersResp.data;
    const usersMap = {};
    users.forEach((u) => {
      usersMap[u.id] = u;
    });

    // fetch all my channels
    const chatsResp = await network(self, 'get', '/chats', null, {
      Authorization: `Bearer ${token}`,
    });
    const channels = chatsResp.data;
    const activeChannelId = pickActiveChannelId(
      channels,
      (() => {
        const raw = localStorage.getItem('activeChannelId');
        if (!raw) {
          return null;
        }
        try {
          return JSON.parse(raw);
        } catch (_err) {
          return null;
        }
      })(),
    );

    // Store non-sensitive session bootstrap data only.
    localStorage.setItem('user', JSON.stringify(user));
    localStorage.setItem('users', JSON.stringify(usersMap));
    localStorage.setItem('channels', JSON.stringify(channels));
    if (activeChannelId != null) {
      localStorage.setItem('activeChannelId', JSON.stringify(activeChannelId));
    } else {
      localStorage.removeItem('activeChannelId');
    }

    // Commit the mutations to update the state
    commit('setChannels', channels);
    commit('setUsers', usersMap);
    if (activeChannelId != null) {
      commit('setActiveChannel', activeChannelId);
    } else {
      commit('setActiveChannel', null);
    }

    // call initSSE action
    await self.dispatch('initSSE');

    return user;
  } catch (error) {
    if (isPhoneBindGateError(error)) {
      const gatedUser = {
        ...user,
        phoneBindRequired: true,
      };
      localStorage.setItem('user', JSON.stringify(gatedUser));
      commit('setUser', gatedUser);
      applyPhoneBindPendingBootstrap(commit);
      return gatedUser;
    }
    console.error('Failed to load user state:', error);
    throw error;
  }
}

function resolvePhoneBindRequired(user) {
  const phone = String(user?.phoneE164 || '').trim();
  if (phone) {
    return false;
  }
  if (Object.prototype.hasOwnProperty.call(user || {}, 'phoneBindRequired')) {
    return !!user.phoneBindRequired;
  }
  return true;
}

function normalizeUserForPhoneGate(user) {
  return {
    ...user,
    phoneBindRequired: resolvePhoneBindRequired(user),
  };
}

function applyPhoneBindPendingBootstrap(commit) {
  localStorage.setItem('users', JSON.stringify({}));
  localStorage.setItem('channels', JSON.stringify([]));
  localStorage.removeItem('messages');
  localStorage.removeItem('activeChannelId');

  commit('setUsers', {});
  commit('setChannels', []);
  commit('setActiveChannel', null);
}

function isPhoneBindGateError(error) {
  return error?.response?.status === 403
    && error?.response?.data?.error === 'auth_phone_bind_required';
}

async function setContext(state) {
  // if clientId is not set, generate a new one and store it in local storage
  let clientId = localStorage.getItem('clientId');
  if (!clientId) {
    clientId = uuidv4();
    localStorage.setItem('clientId', clientId);
  }

  console.log("clientId:", clientId);

  const appVersion = packageJson.version;
  const userAgent = navigator.userAgent;
  // extract os and arch from userAgent
  const os = userAgent.match(/Macintosh|Windows|Linux/)[0];
  const arch = "arm64";
  // let info = await navigator.userAgentData.getHighEntropyValues(["architecture"]);
  const system = {
    os,
    arch,
    locale: navigator.language,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  };

  let userId = state.user?.id;
  // convert to string if not null
  userId = userId ? userId.toString() : null;

  const clientTs = (new Date()).getTime();

  state.context = {
    clientId,
    appVersion,
    system,
    userId,
    userAgent,
    clientTs,
  };
}

function buildAuthEventPayloadFromUser(user) {
  if (!user) {
    return {
      accountType: 'unknown',
      accountIdentifier: '',
      userId: '',
    };
  }
  const phone = String(user.phoneE164 || '').trim();
  const email = String(user.email || '').trim();
  return {
    accountType: phone ? 'phone' : (email ? 'email' : 'unknown'),
    accountIdentifier: phone || email || '',
    userId: user.id == null ? '' : String(user.id),
  };
}
