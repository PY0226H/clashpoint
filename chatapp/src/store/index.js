import { createStore } from 'vuex';
import axios from 'axios';
import { getUrlBase } from '../utils';
import { initSSE } from '../utils';
import {
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
    workspace: {},      // Current workspace
    channels: [],       // List of channels
    messages: {},       // Messages hashmap, keyed by channel ID
    users: {},          // Users hashmap under workspace, keyed by user ID
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
    setWorkspace(state, workspace) {
      state.workspace = workspace;
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
      state.activeChannel = channel;
    },
    loadUserState(state) {
      setContext(state);

      console.log("context:", state.context);

      const storedUser = localStorage.getItem('user');
      const storedWorkspace = localStorage.getItem('workspace');
      const storedChannels = localStorage.getItem('channels');
      // we do not store messages in local storage, so this is always empty
      const storedMessages = localStorage.getItem('messages');
      const storedUsers = localStorage.getItem('users');
      const storedActiveChannelId = localStorage.getItem('activeChannelId');

      if (storedUser) {
        state.user = JSON.parse(storedUser);
      }
      if (storedWorkspace) {
        state.workspace = JSON.parse(storedWorkspace);
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
        onDebateJudgeReportReady: (payload) => {
          commit('setLatestJudgeReportEvent', {
            ...payload,
            receivedAt: Date.now(),
          });
        },
        onDebateDrawVoteResolved: (payload) => {
          commit('setLatestDrawVoteResolvedEvent', {
            ...payload,
            receivedAt: Date.now(),
          });
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
    async signup({ commit }, { email, fullname, password, workspace }) {
      try {
        const response = await network(this, 'post', '/signup', {
          email,
          fullname,
          password,
          workspace
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
      localStorage.removeItem('workspace');
      localStorage.removeItem('channels');
      localStorage.removeItem('messages');
      localStorage.removeItem('activeChannelId');

      commit('setUser', null);
      commit('setToken', null);
      commit('setAccessTickets', null);
      commit('setWorkspace', '');
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
      if (!sessionId) {
        throw new Error('sessionId is required');
      }
      const query = new URLSearchParams();
      if (maxStageCount != null) {
        query.set('maxStageCount', String(maxStageCount));
      }
      if (stageOffset != null) {
        query.set('stageOffset', String(stageOffset));
      }
      const suffix = query.toString() ? `?${query.toString()}` : '';
      const response = await network(
        this,
        'get',
        `/debate/sessions/${sessionId}/judge-report${suffix}`,
        null,
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      return response.data;
    },
    async fetchDrawVoteStatus({ state }, { sessionId }) {
      if (!sessionId) {
        throw new Error('sessionId is required');
      }
      const response = await network(
        this,
        'get',
        `/debate/sessions/${sessionId}/draw-vote`,
        null,
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      return response.data;
    },
    async submitDrawVote({ state }, { sessionId, agreeDraw }) {
      if (!sessionId) {
        throw new Error('sessionId is required');
      }
      if (typeof agreeDraw !== 'boolean') {
        throw new Error('agreeDraw must be boolean');
      }
      const response = await network(
        this,
        'post',
        `/debate/sessions/${sessionId}/draw-vote/ballots`,
        { agreeDraw },
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      return response.data;
    },
    async requestJudgeJob({ state }, { sessionId, allowRejudge = false, styleMode = null } = {}) {
      if (!sessionId) {
        throw new Error('sessionId is required');
      }
      const payload = {
        allowRejudge: !!allowRejudge,
      };
      if (styleMode != null && String(styleMode).trim()) {
        payload.styleMode = String(styleMode).trim();
      }
      const response = await network(
        this,
        'post',
        `/debate/sessions/${sessionId}/judge/jobs`,
        payload,
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      return response.data;
    },
    async listDebateTopics({ state }, payload = {}) {
      const suffix = buildQueryString({
        category: payload.category,
        activeOnly: payload.activeOnly,
        limit: payload.limit,
      });
      const response = await network(this, 'get', `/debate/topics${suffix}`, null, {
        Authorization: `Bearer ${state.token}`,
      });
      return response.data || [];
    },
    async listDebateSessions({ state }, payload = {}) {
      const suffix = buildQueryString({
        status: payload.status,
        topicId: payload.topicId,
        from: payload.from,
        to: payload.to,
        limit: payload.limit,
      });
      const response = await network(this, 'get', `/debate/sessions${suffix}`, null, {
        Authorization: `Bearer ${state.token}`,
      });
      return response.data || [];
    },
    async listJudgeReviewsOps({ state }, payload = {}) {
      const suffix = buildQueryString({
        from: payload.from,
        to: payload.to,
        winner: payload.winner,
        rejudgeTriggered: payload.rejudgeTriggered,
        hasVerdictEvidence: payload.hasVerdictEvidence,
        anomalyOnly: payload.anomalyOnly,
        limit: payload.limit,
      });
      const response = await network(this, 'get', `/debate/ops/judge-reviews${suffix}`, null, {
        Authorization: `Bearer ${state.token}`,
      });
      return response.data || { scannedCount: 0, returnedCount: 0, items: [] };
    },
    async listOpsRoleAssignments({ state }) {
      const response = await network(this, 'get', '/debate/ops/rbac/roles', null, {
        Authorization: `Bearer ${state.token}`,
      });
      return response.data || { items: [] };
    },
    async getOpsRbacMe({ state, commit }) {
      const response = await network(this, 'get', '/debate/ops/rbac/me', null, {
        Authorization: `Bearer ${state.token}`,
      });
      const payload = response.data || null;
      commit('setOpsRbacMe', payload);
      return payload;
    },
    async getOpsObservabilityConfig({ state }) {
      const response = await network(this, 'get', '/debate/ops/observability/config', null, {
        Authorization: `Bearer ${state.token}`,
      });
      return response.data || null;
    },
    async upsertOpsObservabilityThresholds({ state }, payload = {}) {
      const response = await network(
        this,
        'put',
        '/debate/ops/observability/thresholds',
        payload,
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      return response.data || null;
    },
    async upsertOpsObservabilityAnomalyState({ state }, payload = {}) {
      const response = await network(
        this,
        'put',
        '/debate/ops/observability/anomaly-state',
        payload,
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      return response.data || null;
    },
    async upsertOpsRoleAssignment({ state }, { userId, role } = {}) {
      if (!userId) {
        throw new Error('userId is required');
      }
      if (!role || !String(role).trim()) {
        throw new Error('role is required');
      }
      const response = await network(
        this,
        'put',
        `/debate/ops/rbac/roles/${Number(userId)}`,
        { role: String(role).trim() },
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      return response.data;
    },
    async revokeOpsRoleAssignment({ state }, { userId } = {}) {
      if (!userId) {
        throw new Error('userId is required');
      }
      const response = await network(
        this,
        'delete',
        `/debate/ops/rbac/roles/${Number(userId)}`,
        null,
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      return response.data;
    },
    async requestJudgeRejudgeOps({ state }, { sessionId } = {}) {
      if (!sessionId) {
        throw new Error('sessionId is required');
      }
      const response = await network(
        this,
        'post',
        `/debate/ops/sessions/${Number(sessionId)}/judge/rejudge`,
        {},
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      return response.data;
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
      if (!title || !String(title).trim()) {
        throw new Error('title is required');
      }
      if (!description || !String(description).trim()) {
        throw new Error('description is required');
      }
      if (!category || !String(category).trim()) {
        throw new Error('category is required');
      }
      if (!stancePro || !String(stancePro).trim()) {
        throw new Error('stancePro is required');
      }
      if (!stanceCon || !String(stanceCon).trim()) {
        throw new Error('stanceCon is required');
      }

      const response = await network(
        this,
        'post',
        '/debate/ops/topics',
        {
          title: String(title).trim(),
          description: String(description).trim(),
          category: String(category).trim(),
          stancePro: String(stancePro).trim(),
          stanceCon: String(stanceCon).trim(),
          contextSeed: contextSeed == null ? null : String(contextSeed).trim() || null,
          isActive: !!isActive,
        },
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      return response.data;
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
      if (!topicId) {
        throw new Error('topicId is required');
      }
      if (!title || !String(title).trim()) {
        throw new Error('title is required');
      }
      if (!description || !String(description).trim()) {
        throw new Error('description is required');
      }
      if (!category || !String(category).trim()) {
        throw new Error('category is required');
      }
      if (!stancePro || !String(stancePro).trim()) {
        throw new Error('stancePro is required');
      }
      if (!stanceCon || !String(stanceCon).trim()) {
        throw new Error('stanceCon is required');
      }
      const response = await network(
        this,
        'put',
        `/debate/ops/topics/${Number(topicId)}`,
        {
          title: String(title).trim(),
          description: String(description).trim(),
          category: String(category).trim(),
          stancePro: String(stancePro).trim(),
          stanceCon: String(stanceCon).trim(),
          contextSeed: contextSeed == null ? null : String(contextSeed).trim() || null,
          isActive: !!isActive,
        },
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      return response.data;
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
      if (!topicId) {
        throw new Error('topicId is required');
      }
      if (!scheduledStartAt || !String(scheduledStartAt).trim()) {
        throw new Error('scheduledStartAt is required');
      }
      if (!endAt || !String(endAt).trim()) {
        throw new Error('endAt is required');
      }
      const response = await network(
        this,
        'post',
        '/debate/ops/sessions',
        {
          topicId: Number(topicId),
          status: String(status || 'scheduled').trim(),
          scheduledStartAt: String(scheduledStartAt).trim(),
          endAt: String(endAt).trim(),
          maxParticipantsPerSide: Number(maxParticipantsPerSide),
        },
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      return response.data;
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
      if (!sessionId) {
        throw new Error('sessionId is required');
      }
      const payload = {};
      if (status != null && String(status).trim()) {
        payload.status = String(status).trim();
      }
      if (scheduledStartAt != null && String(scheduledStartAt).trim()) {
        payload.scheduledStartAt = String(scheduledStartAt).trim();
      }
      if (endAt != null && String(endAt).trim()) {
        payload.endAt = String(endAt).trim();
      }
      if (maxParticipantsPerSide != null) {
        payload.maxParticipantsPerSide = Number(maxParticipantsPerSide);
      }
      const response = await network(
        this,
        'put',
        `/debate/ops/sessions/${Number(sessionId)}`,
        payload,
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      return response.data;
    },
    async joinDebateSession({ state }, { sessionId, side }) {
      if (!sessionId) {
        throw new Error('sessionId is required');
      }
      if (!side) {
        throw new Error('side is required');
      }
      const response = await network(
        this,
        'post',
        `/debate/sessions/${sessionId}/join`,
        { side },
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      return response.data;
    },
    async listDebateMessages({ state }, { sessionId, lastId = null, limit = 80 } = {}) {
      if (!sessionId) {
        throw new Error('sessionId is required');
      }
      const suffix = buildQueryString({
        lastId,
        limit,
      });
      const response = await network(
        this,
        'get',
        `/debate/sessions/${sessionId}/messages${suffix}`,
        null,
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      return response.data || [];
    },
    async listDebatePinnedMessages({ state }, { sessionId, activeOnly = true, limit = 20 } = {}) {
      if (!sessionId) {
        throw new Error('sessionId is required');
      }
      const suffix = buildQueryString({
        activeOnly,
        limit,
      });
      const response = await network(
        this,
        'get',
        `/debate/sessions/${sessionId}/pins${suffix}`,
        null,
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      return response.data || [];
    },
    async listIapProducts({ state }, { activeOnly = true } = {}) {
      const suffix = buildQueryString({ activeOnly });
      const response = await network(this, 'get', `/pay/iap/products${suffix}`, null, {
        Authorization: `Bearer ${state.token}`,
      });
      return response.data || [];
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
      if (!productId || !String(productId).trim()) {
        throw new Error('productId is required');
      }
      if (!transactionId || !String(transactionId).trim()) {
        throw new Error('transactionId is required');
      }
      if (!receiptData || !String(receiptData).trim()) {
        throw new Error('receiptData is required');
      }
      const response = await network(
        this,
        'post',
        '/pay/iap/verify',
        {
          productId: String(productId).trim(),
          transactionId: String(transactionId).trim(),
          originalTransactionId: originalTransactionId == null
            ? null
            : String(originalTransactionId).trim() || null,
          receiptData: String(receiptData).trim(),
        },
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      return response.data;
    },
    async getIapOrderByTransaction({ state }, { transactionId } = {}) {
      if (!transactionId || !String(transactionId).trim()) {
        throw new Error('transactionId is required');
      }
      const suffix = buildQueryString({
        transactionId: String(transactionId).trim(),
      });
      const response = await network(this, 'get', `/pay/iap/orders/by-transaction${suffix}`, null, {
        Authorization: `Bearer ${state.token}`,
      });
      return response.data;
    },
    async fetchWalletBalance({ state }) {
      const response = await network(this, 'get', '/pay/wallet', null, {
        Authorization: `Bearer ${state.token}`,
      });
      return response.data;
    },
    async listWalletLedger({ state }, { lastId = null, limit = 20 } = {}) {
      const suffix = buildQueryString({
        lastId,
        limit: normalizeWalletLedgerLimit(limit),
      });
      const response = await network(this, 'get', `/pay/wallet/ledger${suffix}`, null, {
        Authorization: `Bearer ${state.token}`,
      });
      return response.data || [];
    },
    async createDebateMessage({ state }, { sessionId, content }) {
      if (!sessionId) {
        throw new Error('sessionId is required');
      }
      if (!content || !content.trim()) {
        throw new Error('content is required');
      }
      const response = await network(
        this,
        'post',
        `/debate/sessions/${sessionId}/messages`,
        { content: content.trim() },
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      return response.data;
    },
    async pinDebateMessage({ state }, { messageId, pinSeconds, idempotencyKey }) {
      if (!messageId) {
        throw new Error('messageId is required');
      }
      if (!pinSeconds) {
        throw new Error('pinSeconds is required');
      }
      if (!idempotencyKey || !idempotencyKey.trim()) {
        throw new Error('idempotencyKey is required');
      }
      const response = await network(
        this,
        'post',
        `/debate/messages/${messageId}/pin`,
        {
          pinSeconds,
          idempotencyKey: idempotencyKey.trim(),
        },
        {
          Authorization: `Bearer ${state.token}`,
        },
      );
      return response.data;
    },
    async uploadFiles({ state, commit }, files) {
      try {
        await this.dispatch('refreshAccessTickets');
        const formData = new FormData();
        files.forEach(file => {
          formData.append(`files`, file);
        });

        const response = await network(this, 'post', '/upload', formData, {
          'Authorization': `Bearer ${state.token}`,
          'Content-Type': 'multipart/form-data'
        });

        const uploadedFiles = response.data.map(path => ({
          path,
          fullUrl: `${getUrlBase()}${path}?token=${state.accessTickets?.fileToken || ''}`
        }));

        return uploadedFiles;
      } catch (error) {
        console.error('Failed to upload files:', error);
        throw error;
      }
    },
    async sendMessage({ state, commit }, payload) {
      if (!payload.chatId) {
        throw new Error('active channel is required before sending message');
      }
      try {
        const response = await network(this, 'post', `/chats/${payload.chatId}`, payload, {
          Authorization: `Bearer ${state.token}`,
        });
        commit('addMessage', { channelId: payload.chatId, message: response.data });
        console.log('Message sent:', response.data);
        return response.data;
      } catch (error) {
        console.error('Failed to send message:', error);
        throw error;
      }
    },
    addMessage({ commit }, { channelId, message }) {
      commit('addMessage', { channelId, message });
    },
    async loadUserState({ commit, dispatch }) {
      commit('loadUserState');
      if (!this.state.user) {
        return;
      }
      try {
        await dispatch('refreshSession');
        await dispatch('initSSE');
      } catch (_error) {
        await dispatch('logout', { skipRemote: true });
      }
    },
    async appStart({ state }) {
      await sendAppStartEvent(state.context, state.token);
    },
    async appExit({ state }) {
      await sendAppExitEvent(state.context, state.token);
    },
    async userLogin({ state }, { email }) {
      await sendUserLoginEvent(state.context, state.token, email);
    },
    async userLogout({ state }) {
      await sendUserLogoutEvent(state.context, state.token, state.user.email);
    },
    async userRegister({ state }, { email, workspaceId }) {
      await sendUserRegisterEvent(state.context, state.token, email, workspaceId);
    },
    async chatCreated({ state }, { workspaceId }) {
      await sendChatCreatedEvent(state.context, state.token, workspaceId);
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
      const {
        hours,
        limit,
        debateSessionId,
      } = normalizeJudgeRefreshSummaryQuery(payload);
      const params = {
        hours,
        limit,
      };
      if (debateSessionId != null) {
        params.debateSessionId = debateSessionId;
      }
      const response = await network(
        this,
        'get',
        `/analytics/judge-refresh/summary${buildQueryString(params)}`,
        null,
        state.token ? { Authorization: `Bearer ${state.token}` } : {},
      );
      return response?.data;
    },
    async fetchJudgeRefreshSummaryMetrics({ state }) {
      const response = await network(
        this,
        'get',
        '/analytics/judge-refresh/summary/metrics',
        null,
        state.token ? { Authorization: `Bearer ${state.token}` } : {},
      );
      return normalizeJudgeRefreshSummaryMetrics(response?.data || {});
    },
    async refreshSession({ commit, dispatch }) {
      const response = await network(this, 'post', '/auth/refresh', null, {}, false);
      const accessToken = response?.data?.accessToken;
      if (!accessToken) {
        throw new Error('missing accessToken from refresh response');
      }
      commit('setToken', accessToken);
      await dispatch('refreshAccessTickets');
      return accessToken;
    },
    async refreshAccessTickets({ state, commit }) {
      if (!state.token) {
        commit('setAccessTickets', null);
        return null;
      }
      const now = Date.now();
      const expireAt = state.accessTickets?.expireAt || 0;
      if (expireAt > now + 30_000) {
        return state.accessTickets;
      }

      const response = await network(this, 'post', '/tickets', null, {
        Authorization: `Bearer ${state.token}`,
      });
      const data = response.data;
      const tickets = {
        fileToken: data.fileToken,
        notifyToken: data.notifyToken,
        expiresInSecs: data.expiresInSecs,
        expireAt: now + data.expiresInSecs * 1000,
      };
      commit('setAccessTickets', tickets);
      return tickets;
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
    getWorkspace(state) {
      return state.workspace;
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
  const user = response?.data?.user;
  if (!token || !user) {
    throw new Error('missing access token or user profile in auth response');
  }
  const workspace = { id: user.wsId, name: user.wsName };

  try {
    // fetch all workspace users
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
    localStorage.setItem('workspace', JSON.stringify(workspace));
    localStorage.setItem('users', JSON.stringify(usersMap));
    localStorage.setItem('channels', JSON.stringify(channels));
    if (activeChannelId != null) {
      localStorage.setItem('activeChannelId', JSON.stringify(activeChannelId));
    } else {
      localStorage.removeItem('activeChannelId');
    }

    // Commit the mutations to update the state
    commit('setUser', user);
    commit('setToken', token);
    commit('setAccessTickets', null);
    commit('setWorkspace', workspace);
    commit('setChannels', channels);
    commit('setUsers', usersMap);
    if (activeChannelId != null) {
      commit('setActiveChannel', activeChannelId);
    }

    // call initSSE action
    await self.dispatch('initSSE');

    return user;
  } catch (error) {
    console.error('Failed to load user state:', error);
    throw error;
  }
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
