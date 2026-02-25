<template>
  <div class="flex h-screen">
    <Sidebar />
    <div class="flex-1 overflow-y-auto bg-gray-50">
      <div class="max-w-6xl mx-auto p-6 space-y-5">
        <div class="flex items-start justify-between gap-3">
          <div>
            <h1 class="text-2xl font-bold text-gray-900">Debate Ops Admin</h1>
            <p class="text-sm text-gray-600 mt-1">创建辩题、排期场次，提供最小运营上新能力。</p>
          </div>
          <button
            @click="refreshData"
            :disabled="loading"
            class="px-4 py-2 rounded bg-blue-600 text-white text-sm disabled:opacity-50"
          >
            {{ loading ? '刷新中...' : '刷新' }}
          </button>
        </div>

        <div v-if="errorText" class="bg-red-50 text-red-700 border border-red-200 rounded p-3 text-sm">
          {{ errorText }}
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div class="bg-white border rounded-lg p-4 space-y-3">
            <div class="text-sm font-semibold text-gray-900">创建辩题</div>
            <input v-model="topicForm.title" class="w-full border rounded px-3 py-2 text-sm" placeholder="标题" />
            <textarea
              v-model="topicForm.description"
              rows="3"
              class="w-full border rounded px-3 py-2 text-sm"
              placeholder="辩题描述"
            />
            <div class="grid grid-cols-2 gap-2">
              <input v-model="topicForm.category" class="border rounded px-3 py-2 text-sm" placeholder="分类（如 game）" />
              <label class="inline-flex items-center gap-2 text-sm text-gray-700">
                <input v-model="topicForm.isActive" type="checkbox" class="rounded border-gray-300" />
                active
              </label>
            </div>
            <div class="grid grid-cols-2 gap-2">
              <input v-model="topicForm.stancePro" class="border rounded px-3 py-2 text-sm" placeholder="正方立场" />
              <input v-model="topicForm.stanceCon" class="border rounded px-3 py-2 text-sm" placeholder="反方立场" />
            </div>
            <textarea
              v-model="topicForm.contextSeed"
              rows="2"
              class="w-full border rounded px-3 py-2 text-sm"
              placeholder="背景知识（可空）"
            />
            <button
              @click="createTopic"
              :disabled="createTopicLoading"
              class="px-3 py-2 rounded bg-emerald-600 text-white text-sm disabled:opacity-50"
            >
              {{ createTopicLoading ? '创建中...' : '创建辩题' }}
            </button>
          </div>

          <div class="bg-white border rounded-lg p-4 space-y-3">
            <div class="text-sm font-semibold text-gray-900">创建场次</div>
            <select v-model="sessionForm.topicId" class="w-full border rounded px-3 py-2 text-sm">
              <option value="">选择辩题</option>
              <option v-for="topic in topics" :key="topic.id" :value="String(topic.id)">
                {{ topic.title }} (#{{ topic.id }})
              </option>
            </select>
            <div class="grid grid-cols-2 gap-2">
              <select v-model="sessionForm.status" class="border rounded px-3 py-2 text-sm">
                <option value="scheduled">scheduled</option>
                <option value="open">open</option>
              </select>
              <input
                v-model.number="sessionForm.maxParticipantsPerSide"
                type="number"
                min="1"
                class="border rounded px-3 py-2 text-sm"
                placeholder="每侧人数上限"
              />
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
              <label class="text-xs text-gray-600">
                开始时间
                <input v-model="sessionForm.scheduledStartAtLocal" type="datetime-local" class="w-full border rounded px-3 py-2 text-sm mt-1" />
              </label>
              <label class="text-xs text-gray-600">
                结束时间
                <input v-model="sessionForm.endAtLocal" type="datetime-local" class="w-full border rounded px-3 py-2 text-sm mt-1" />
              </label>
            </div>
            <button
              @click="createSession"
              :disabled="createSessionLoading"
              class="px-3 py-2 rounded bg-indigo-600 text-white text-sm disabled:opacity-50"
            >
              {{ createSessionLoading ? '创建中...' : '创建场次' }}
            </button>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div class="bg-white border rounded-lg p-4 space-y-3">
            <div class="text-sm font-semibold text-gray-900">编辑辩题</div>
            <select v-model="topicEditForm.topicId" @change="syncTopicEditFormFromId(topicEditForm.topicId)" class="w-full border rounded px-3 py-2 text-sm">
              <option value="">选择辩题</option>
              <option v-for="topic in topics" :key="topic.id" :value="String(topic.id)">
                {{ topic.title }} (#{{ topic.id }})
              </option>
            </select>
            <input v-model="topicEditForm.title" class="w-full border rounded px-3 py-2 text-sm" placeholder="标题" />
            <textarea
              v-model="topicEditForm.description"
              rows="3"
              class="w-full border rounded px-3 py-2 text-sm"
              placeholder="辩题描述"
            />
            <div class="grid grid-cols-2 gap-2">
              <input v-model="topicEditForm.category" class="border rounded px-3 py-2 text-sm" placeholder="分类" />
              <label class="inline-flex items-center gap-2 text-sm text-gray-700">
                <input v-model="topicEditForm.isActive" type="checkbox" class="rounded border-gray-300" />
                active
              </label>
            </div>
            <div class="grid grid-cols-2 gap-2">
              <input v-model="topicEditForm.stancePro" class="border rounded px-3 py-2 text-sm" placeholder="正方立场" />
              <input v-model="topicEditForm.stanceCon" class="border rounded px-3 py-2 text-sm" placeholder="反方立场" />
            </div>
            <textarea
              v-model="topicEditForm.contextSeed"
              rows="2"
              class="w-full border rounded px-3 py-2 text-sm"
              placeholder="背景知识（可空）"
            />
            <button
              @click="updateTopic"
              :disabled="updateTopicLoading || !topicEditForm.topicId"
              class="px-3 py-2 rounded bg-amber-600 text-white text-sm disabled:opacity-50"
            >
              {{ updateTopicLoading ? '保存中...' : '保存辩题' }}
            </button>
          </div>

          <div class="bg-white border rounded-lg p-4 space-y-3">
            <div class="text-sm font-semibold text-gray-900">编辑场次</div>
            <select v-model="sessionEditForm.sessionId" @change="syncSessionEditFormFromId(sessionEditForm.sessionId)" class="w-full border rounded px-3 py-2 text-sm">
              <option value="">选择场次</option>
              <option v-for="session in sessions" :key="session.id" :value="String(session.id)">
                #{{ session.id }} · {{ topicTitle(session.topicId) }}
              </option>
            </select>
            <div class="grid grid-cols-2 gap-2">
              <select v-model="sessionEditForm.status" class="border rounded px-3 py-2 text-sm">
                <option value="scheduled">scheduled</option>
                <option value="open">open</option>
                <option value="running">running</option>
                <option value="judging">judging</option>
                <option value="closed">closed</option>
                <option value="canceled">canceled</option>
              </select>
              <input
                v-model.number="sessionEditForm.maxParticipantsPerSide"
                type="number"
                min="1"
                class="border rounded px-3 py-2 text-sm"
                placeholder="每侧人数上限"
              />
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
              <label class="text-xs text-gray-600">
                开始时间
                <input v-model="sessionEditForm.scheduledStartAtLocal" type="datetime-local" class="w-full border rounded px-3 py-2 text-sm mt-1" />
              </label>
              <label class="text-xs text-gray-600">
                结束时间
                <input v-model="sessionEditForm.endAtLocal" type="datetime-local" class="w-full border rounded px-3 py-2 text-sm mt-1" />
              </label>
            </div>
            <div class="flex flex-wrap gap-2">
              <button
                @click="updateSession"
                :disabled="updateSessionLoading || !sessionEditForm.sessionId"
                class="px-3 py-2 rounded bg-violet-600 text-white text-sm disabled:opacity-50"
              >
                {{ updateSessionLoading ? '保存中...' : '保存场次' }}
              </button>
              <button
                @click="openSessionJudgeReport(sessionEditForm.sessionId)"
                :disabled="!sessionEditForm.sessionId"
                class="px-3 py-2 rounded border border-gray-300 text-sm bg-white hover:bg-gray-100 disabled:opacity-50"
              >
                查看判决
              </button>
            </div>
          </div>
        </div>

        <div class="bg-white border rounded-lg p-4 space-y-3">
          <div class="flex items-center justify-between">
            <div class="text-sm font-semibold text-gray-900">场次看板</div>
            <div class="text-xs text-gray-500">topics: {{ topics.length }} · sessions: {{ sessions.length }}</div>
          </div>
          <div class="overflow-x-auto">
            <table class="min-w-full text-sm">
              <thead>
                <tr class="text-left text-gray-500 border-b">
                  <th class="py-2 pr-4">Session</th>
                  <th class="py-2 pr-4">Topic</th>
                  <th class="py-2 pr-4">Status</th>
                  <th class="py-2 pr-4">Scheduled</th>
                  <th class="py-2 pr-4">End</th>
                  <th class="py-2 pr-4">Joinable</th>
                  <th class="py-2 pr-4">Action</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in sessions.slice(0, 50)" :key="item.id" class="border-b last:border-b-0">
                  <td class="py-2 pr-4">#{{ item.id }}</td>
                  <td class="py-2 pr-4">{{ topicTitle(item.topicId) }}</td>
                  <td class="py-2 pr-4">{{ item.status }}</td>
                  <td class="py-2 pr-4">{{ formatDateTime(item.scheduledStartAt) }}</td>
                  <td class="py-2 pr-4">{{ formatDateTime(item.endAt) }}</td>
                  <td class="py-2 pr-4">{{ item.joinable ? 'yes' : 'no' }}</td>
                  <td class="py-2 pr-4">
                    <button
                      @click="openSessionJudgeReport(item.id)"
                      class="px-2 py-1 rounded border border-gray-300 text-xs bg-white hover:bg-gray-100"
                    >
                      判决
                    </button>
                  </td>
                </tr>
                <tr v-if="sessions.length === 0">
                  <td colspan="7" class="py-4 text-center text-gray-500">暂无场次</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Sidebar from '../components/Sidebar.vue';

function toLocalInputValue(date) {
  const d = new Date(date);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}T${hh}:${min}`;
}

function emptyTopicEditForm() {
  return {
    topicId: '',
    title: '',
    description: '',
    category: '',
    stancePro: '',
    stanceCon: '',
    contextSeed: '',
    isActive: true,
  };
}

function emptySessionEditForm(date = new Date()) {
  const plusOneHour = new Date(date.getTime() + 60 * 60 * 1000);
  return {
    sessionId: '',
    status: 'scheduled',
    scheduledStartAtLocal: toLocalInputValue(date),
    endAtLocal: toLocalInputValue(plusOneHour),
    maxParticipantsPerSide: 500,
  };
}

export default {
  components: {
    Sidebar,
  },
  data() {
    const now = new Date();
    const plusOneHour = new Date(now.getTime() + 60 * 60 * 1000);
    return {
      loading: false,
      createTopicLoading: false,
      createSessionLoading: false,
      updateTopicLoading: false,
      updateSessionLoading: false,
      errorText: '',
      topics: [],
      sessions: [],
      topicForm: {
        title: '',
        description: '',
        category: 'game',
        stancePro: '支持',
        stanceCon: '反对',
        contextSeed: '',
        isActive: true,
      },
      sessionForm: {
        topicId: '',
        status: 'scheduled',
        scheduledStartAtLocal: toLocalInputValue(now),
        endAtLocal: toLocalInputValue(plusOneHour),
        maxParticipantsPerSide: 500,
      },
      topicEditForm: emptyTopicEditForm(),
      sessionEditForm: emptySessionEditForm(now),
    };
  },
  methods: {
    formatDateTime(value) {
      if (!value) {
        return '-';
      }
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? '-' : date.toLocaleString();
    },
    topicTitle(topicId) {
      const topic = this.topics.find((item) => Number(item.id) === Number(topicId));
      return topic ? `${topic.title} (#${topic.id})` : `topic#${topicId}`;
    },
    toIso(localText) {
      if (!localText) {
        return '';
      }
      const date = new Date(localText);
      if (Number.isNaN(date.getTime())) {
        return '';
      }
      return date.toISOString();
    },
    syncTopicEditFormFromId(topicIdRaw) {
      const selectedTopicId = String(topicIdRaw || '');
      const topic = this.topics.find((item) => String(item.id) === selectedTopicId);
      if (!topic) {
        this.topicEditForm = {
          ...emptyTopicEditForm(),
          topicId: selectedTopicId,
        };
        return;
      }
      this.topicEditForm = {
        topicId: String(topic.id),
        title: topic.title || '',
        description: topic.description || '',
        category: topic.category || '',
        stancePro: topic.stancePro || '',
        stanceCon: topic.stanceCon || '',
        contextSeed: topic.contextSeed || '',
        isActive: !!topic.isActive,
      };
    },
    syncSessionEditFormFromId(sessionIdRaw) {
      const selectedSessionId = String(sessionIdRaw || '');
      const session = this.sessions.find((item) => String(item.id) === selectedSessionId);
      if (!session) {
        this.sessionEditForm = {
          ...emptySessionEditForm(new Date()),
          sessionId: selectedSessionId,
        };
        return;
      }
      this.sessionEditForm = {
        sessionId: String(session.id),
        status: session.status || 'scheduled',
        scheduledStartAtLocal: toLocalInputValue(session.scheduledStartAt || new Date()),
        endAtLocal: toLocalInputValue(session.endAt || new Date(Date.now() + 60 * 60 * 1000)),
        maxParticipantsPerSide: Number(session.maxParticipantsPerSide || 500),
      };
    },
    async refreshData() {
      this.loading = true;
      this.errorText = '';
      try {
        const [topics, sessions] = await Promise.all([
          this.$store.dispatch('listDebateTopics', { activeOnly: false, limit: 200 }),
          this.$store.dispatch('listDebateSessions', { limit: 200 }),
        ]);
        this.topics = topics || [];
        this.sessions = sessions || [];
        if (!this.topicEditForm.topicId && this.topics.length > 0) {
          this.topicEditForm.topicId = String(this.topics[0].id);
        }
        if (!this.sessionEditForm.sessionId && this.sessions.length > 0) {
          this.sessionEditForm.sessionId = String(this.sessions[0].id);
        }
        this.syncTopicEditFormFromId(this.topicEditForm.topicId);
        this.syncSessionEditFormFromId(this.sessionEditForm.sessionId);
      } catch (error) {
        this.errorText = error?.response?.data?.error || error?.message || '刷新失败';
      } finally {
        this.loading = false;
      }
    },
    async createTopic() {
      this.createTopicLoading = true;
      this.errorText = '';
      try {
        await this.$store.dispatch('createDebateTopicOps', {
          title: this.topicForm.title,
          description: this.topicForm.description,
          category: this.topicForm.category,
          stancePro: this.topicForm.stancePro,
          stanceCon: this.topicForm.stanceCon,
          contextSeed: this.topicForm.contextSeed,
          isActive: this.topicForm.isActive,
        });
        this.topicForm.title = '';
        this.topicForm.description = '';
        this.topicForm.contextSeed = '';
        await this.refreshData();
      } catch (error) {
        this.errorText = error?.response?.data?.error || error?.message || '创建辩题失败';
      } finally {
        this.createTopicLoading = false;
      }
    },
    async createSession() {
      this.createSessionLoading = true;
      this.errorText = '';
      try {
        const scheduledStartAt = this.toIso(this.sessionForm.scheduledStartAtLocal);
        const endAt = this.toIso(this.sessionForm.endAtLocal);
        if (!scheduledStartAt || !endAt) {
          throw new Error('请填写有效的开始/结束时间');
        }
        await this.$store.dispatch('createDebateSessionOps', {
          topicId: Number(this.sessionForm.topicId),
          status: this.sessionForm.status,
          scheduledStartAt,
          endAt,
          maxParticipantsPerSide: Number(this.sessionForm.maxParticipantsPerSide),
        });
        await this.refreshData();
      } catch (error) {
        this.errorText = error?.response?.data?.error || error?.message || '创建场次失败';
      } finally {
        this.createSessionLoading = false;
      }
    },
    async updateTopic() {
      if (!this.topicEditForm.topicId) {
        return;
      }
      this.updateTopicLoading = true;
      this.errorText = '';
      try {
        await this.$store.dispatch('updateDebateTopicOps', {
          topicId: Number(this.topicEditForm.topicId),
          title: this.topicEditForm.title,
          description: this.topicEditForm.description,
          category: this.topicEditForm.category,
          stancePro: this.topicEditForm.stancePro,
          stanceCon: this.topicEditForm.stanceCon,
          contextSeed: this.topicEditForm.contextSeed,
          isActive: this.topicEditForm.isActive,
        });
        await this.refreshData();
      } catch (error) {
        this.errorText = error?.response?.data?.error || error?.message || '更新辩题失败';
      } finally {
        this.updateTopicLoading = false;
      }
    },
    async updateSession() {
      if (!this.sessionEditForm.sessionId) {
        return;
      }
      this.updateSessionLoading = true;
      this.errorText = '';
      try {
        const scheduledStartAt = this.toIso(this.sessionEditForm.scheduledStartAtLocal);
        const endAt = this.toIso(this.sessionEditForm.endAtLocal);
        if (!scheduledStartAt || !endAt) {
          throw new Error('请填写有效的开始/结束时间');
        }
        await this.$store.dispatch('updateDebateSessionOps', {
          sessionId: Number(this.sessionEditForm.sessionId),
          status: this.sessionEditForm.status,
          scheduledStartAt,
          endAt,
          maxParticipantsPerSide: Number(this.sessionEditForm.maxParticipantsPerSide),
        });
        await this.refreshData();
      } catch (error) {
        this.errorText = error?.response?.data?.error || error?.message || '更新场次失败';
      } finally {
        this.updateSessionLoading = false;
      }
    },
    async openSessionJudgeReport(sessionIdRaw) {
      const sessionId = Number(sessionIdRaw);
      if (!sessionId) {
        return;
      }
      await this.$router.push({
        path: '/judge-report',
        query: { sessionId: String(sessionId) },
      });
    },
  },
  async mounted() {
    await this.refreshData();
  },
};
</script>
