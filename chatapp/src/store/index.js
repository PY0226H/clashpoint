import { createStore } from 'vuex';
import axios from 'axios';
import { jwtDecode } from "jwt-decode";
import { getUrlBase } from '../utils';
import { initSSE } from '../utils';
import { formatMessageDate } from '../utils';
import { sendAppStartEvent, sendUserLoginEvent, sendUserLogoutEvent, sendUserRegisterEvent, sendChatCreatedEvent, sendMessageSentEvent, sendChatJoinedEvent, sendChatLeftEvent, sendNavigationEvent } from '../analytics/event';
import { v4 as uuidv4 } from 'uuid';
import packageJson from '../../package.json';

// Wrap axios calls in a function that handles 403 errors
const network = async (store, method, url, data = null, headers = {}) => {
  try {
    const config = {
      method,
      url: `${getUrlBase()}${url}`,
      headers,
      data
    };
    const response = await axios(config);
    return response;
  } catch (error) {
    if (error.response && error.response.status === 403) {
      console.error('Unauthorized access, logging out');
      await store.dispatch('logout');
      // TODO: client side redirect to login page (can we use router instead?)
      window.location.href = '/login';
      return;
    }
    throw error;
  }
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
      // Format the date for each message before setting them in the state
      const formattedMessages = messages.map(message => ({
        ...message,
        formattedCreatedAt: formatMessageDate(message.createdAt)
      }));
      state.messages[channelId] = formattedMessages.reverse();
    },
    addChannel(state, channel) {
      state.channels.push(channel);
      state.messages[channel.id] = [];  // Initialize message list for the new channel
    },
    addMessage(state, { channelId, message }) {
      if (state.messages[channelId]) {
        // Format the message date before adding it to the state
        message.formattedCreatedAt = formatMessageDate(message.createdAt);
        state.messages[channelId].push(message);
      } else {
        message.formattedCreatedAt = formatMessageDate(message.createdAt);
        state.messages[channelId] = [message];
      }
    },
    setActiveChannel(state, channelId) {
      const channel = state.channels.find((c) => c.id === channelId);
      state.activeChannel = channel;
    },
    loadUserState(state) {
      setContext(state);

      console.log("context:", state.context);

      const storedUser = localStorage.getItem('user');
      const storedToken = localStorage.getItem('token');
      const storedWorkspace = localStorage.getItem('workspace');
      const storedChannels = localStorage.getItem('channels');
      // we do not store messages in local storage, so this is always empty
      const storedMessages = localStorage.getItem('messages');
      const storedUsers = localStorage.getItem('users');
      const storedActiveChannelId = localStorage.getItem('activeChannelId');

      if (storedUser) {
        state.user = JSON.parse(storedUser);
      }
      if (storedToken) {
        state.token = storedToken;
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
    logout({ commit }) {
      // Clear local storage and state
      localStorage.removeItem('user');
      localStorage.removeItem('token');
      localStorage.removeItem('workspace');
      localStorage.removeItem('channels');
      localStorage.removeItem('messages');

      commit('setUser', null);
      commit('setToken', null);
      commit('setAccessTickets', null);
      commit('setWorkspace', '');
      commit('setChannels', []);

      // close SSE
      this.dispatch('closeSSE');
    },
    setActiveChannel({ commit }, channel) {
      commit('setActiveChannel', channel);
      console.log("setActiveChannel:", channel);
      localStorage.setItem('activeChannelId', channel);
    },
    addChannel({ commit }, channel) {
      commit('addChannel', channel);

      // Update the channels and messages in local storage
      localStorage.setItem('channels', JSON.stringify(this.state.channels));
      localStorage.setItem('messages', JSON.stringify(this.state.messages));
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
      try {
        const response = await network(this, 'post', `/chats/${payload.chatId}`, payload, {
          Authorization: `Bearer ${state.token}`,
        });
        console.log('Message sent:', response.data);
      } catch (error) {
        console.error('Failed to send message:', error);
        throw error;
      }
    },
    addMessage({ commit }, { channelId, message }) {
      commit('addMessage', { channelId, message });
    },
    loadUserState({ commit }) {
      commit('loadUserState');
      // if user is already logged in, then init SSE
      if (this.state.token) {
        this.dispatch('initSSE');
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
  },
});

async function loadState(response, self, commit) {
  const token = response.data.token;
  const user = jwtDecode(token);
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

    // Store user info, token, and workspace in localStorage
    localStorage.setItem('user', JSON.stringify(user));
    localStorage.setItem('token', token);
    localStorage.setItem('workspace', JSON.stringify(workspace));
    localStorage.setItem('users', JSON.stringify(usersMap));
    localStorage.setItem('channels', JSON.stringify(channels));

    // Commit the mutations to update the state
    commit('setUser', user);
    commit('setToken', token);
    commit('setWorkspace', workspace);
    commit('setChannels', channels);
    commit('setUsers', usersMap);

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
