<template>
  <div class="flex h-screen">
    <Sidebar />
    <div class="flex-1 overflow-y-auto bg-gray-50">
      <div class="max-w-6xl mx-auto p-6 space-y-4">
        <div class="flex items-start justify-between gap-3">
          <div>
            <h1 class="text-2xl font-bold text-gray-900">Wallet & IAP</h1>
            <p class="text-sm text-gray-600 mt-1">
              用于演示充值验单链路：商品列表、验单入账、余额与账本收敛。
            </p>
          </div>
          <button
            @click="refreshPage"
            :disabled="loading"
            class="px-4 py-2 rounded bg-blue-600 text-white text-sm disabled:opacity-50"
          >
            {{ loading ? '刷新中...' : '刷新' }}
          </button>
        </div>

        <div v-if="errorText" class="bg-red-50 text-red-700 border border-red-200 rounded p-3 text-sm">
          {{ errorText }}
        </div>
        <div v-if="successText" class="bg-green-50 text-green-700 border border-green-200 rounded p-3 text-sm">
          {{ successText }}
        </div>

        <div class="bg-white border rounded-lg p-4 flex items-center justify-between gap-3">
          <div>
            <div class="text-xs uppercase text-gray-500">Wallet Balance</div>
            <div class="text-2xl font-bold text-gray-900">{{ walletBalance }}</div>
          </div>
          <button
            @click="refreshWallet"
            :disabled="loading"
            class="px-3 py-2 rounded border bg-white hover:bg-gray-100 text-sm disabled:opacity-50"
          >
            刷新余额
          </button>
        </div>

        <div class="bg-white border rounded-lg p-4 space-y-3">
          <div class="flex items-center justify-between">
            <div class="text-sm font-semibold text-gray-900">IAP 商品</div>
            <div class="text-xs text-gray-500">products: {{ products.length }}</div>
          </div>
          <div v-if="products.length === 0" class="text-sm text-gray-600">暂无可用商品。</div>
          <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div
              v-for="product in products"
              :key="product.productId"
              class="border rounded p-3 bg-gray-50 space-y-2"
            >
              <div class="font-medium text-gray-900">{{ product.productId }}</div>
              <div class="text-xs text-gray-600">coins: {{ product.coins }} · active: {{ product.isActive }}</div>
              <div class="flex gap-2">
                <button
                  @click="prepareMockPayload(product)"
                  class="px-2 py-1 text-xs rounded border bg-white hover:bg-gray-100"
                >
                  填充 mock 参数
                </button>
                <button
                  @click="quickMockVerify(product)"
                  :disabled="verifying"
                  class="px-2 py-1 text-xs rounded bg-indigo-600 text-white disabled:opacity-50"
                >
                  {{ verifying ? '处理中...' : '一键 mock 验单' }}
                </button>
                <button
                  v-if="tauriReady"
                  @click="purchaseAndVerifyViaTauri(product)"
                  :disabled="verifying"
                  class="px-2 py-1 text-xs rounded bg-emerald-600 text-white disabled:opacity-50"
                >
                  {{ verifying ? '处理中...' : 'Tauri 购买并验单' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="bg-white border rounded-lg p-4 space-y-3">
          <div class="text-sm font-semibold text-gray-900">手动验单</div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <div class="text-xs uppercase text-gray-500 mb-1">productId</div>
              <select
                v-model="form.productId"
                class="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">请选择商品</option>
                <option v-for="product in products" :key="product.productId" :value="product.productId">
                  {{ product.productId }} ({{ product.coins }} coins)
                </option>
              </select>
            </div>
            <div>
              <div class="text-xs uppercase text-gray-500 mb-1">transactionId</div>
              <input
                v-model.trim="form.transactionId"
                type="text"
                class="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <div class="text-xs uppercase text-gray-500 mb-1">originalTransactionId(optional)</div>
              <input
                v-model.trim="form.originalTransactionId"
                type="text"
                class="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div class="md:col-span-2">
              <div class="text-xs uppercase text-gray-500 mb-1">receiptData</div>
              <textarea
                v-model.trim="form.receiptData"
                rows="3"
                class="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          <div class="flex gap-2">
            <button
              @click="submitVerify"
              :disabled="verifying"
              class="px-4 py-2 rounded bg-blue-600 text-white text-sm disabled:opacity-50"
            >
              {{ verifying ? '验单中...' : '提交验单' }}
            </button>
            <button
              @click="clearForm"
              :disabled="verifying"
              class="px-4 py-2 rounded border bg-white hover:bg-gray-100 text-sm disabled:opacity-50"
            >
              清空
            </button>
          </div>
        </div>

        <div class="bg-white border rounded-lg p-4 space-y-3">
          <div class="flex items-center justify-between">
            <div class="text-sm font-semibold text-gray-900">待重试交易队列</div>
            <button
              @click="retryAllPending"
              :disabled="retryingAll || pendingQueue.length === 0"
              class="px-3 py-1.5 text-xs rounded border bg-white hover:bg-gray-100 disabled:opacity-50"
            >
              {{ retryingAll ? '重试中...' : '重试全部' }}
            </button>
          </div>
          <div v-if="pendingQueue.length === 0" class="text-sm text-gray-600">
            当前没有待重试交易。
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="item in pendingQueue"
              :key="item.transactionId"
              class="border rounded p-3 bg-gray-50"
            >
              <div class="flex items-start justify-between gap-2">
                <div class="text-xs text-gray-700 space-y-1">
                  <div><span class="font-semibold">tx:</span> {{ item.transactionId }}</div>
                  <div><span class="font-semibold">product:</span> {{ item.productId }}</div>
                  <div><span class="font-semibold">attempts:</span> {{ item.attempts }}</div>
                  <div><span class="font-semibold">updated:</span> {{ formatDateTime(item.updatedAt) }}</div>
                  <div v-if="item.lastError" class="text-red-700">
                    <span class="font-semibold">lastError:</span> {{ item.lastError }}
                  </div>
                </div>
                <button
                  @click="retryPendingItem(item)"
                  :disabled="isRetryingItem(item.transactionId)"
                  class="px-2 py-1 text-xs rounded bg-blue-600 text-white disabled:opacity-50"
                >
                  {{ isRetryingItem(item.transactionId) ? '重试中...' : '重试' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="bg-white border rounded-lg p-4 space-y-3">
          <div class="flex items-center justify-between">
            <div class="text-sm font-semibold text-gray-900">钱包账本</div>
            <button
              @click="refreshLedger"
              :disabled="loading"
              class="px-3 py-1.5 text-xs rounded border bg-white hover:bg-gray-100 disabled:opacity-50"
            >
              刷新账本
            </button>
          </div>
          <div v-if="ledger.length === 0" class="text-sm text-gray-600">暂无账本记录。</div>
          <div v-else class="overflow-x-auto">
            <table class="min-w-full text-sm">
              <thead>
                <tr class="text-left text-xs uppercase text-gray-500">
                  <th class="py-2 pr-3">ID</th>
                  <th class="py-2 pr-3">Type</th>
                  <th class="py-2 pr-3">Delta</th>
                  <th class="py-2 pr-3">Balance</th>
                  <th class="py-2 pr-3">Created At</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in ledger" :key="row.id" class="border-t">
                  <td class="py-2 pr-3 text-gray-700">{{ row.id }}</td>
                  <td class="py-2 pr-3">{{ row.entryType }}</td>
                  <td class="py-2 pr-3">{{ row.amountDelta }}</td>
                  <td class="py-2 pr-3">{{ row.balanceAfter }}</td>
                  <td class="py-2 pr-3 text-gray-600">{{ formatDateTime(row.createdAt) }}</td>
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
import { isTauriRuntime, purchaseIapViaTauri } from '../iap-bridge';
import {
  readPendingIapQueue,
  registerPendingIapFailure,
  settlePendingIapSuccess,
  writePendingIapQueue,
} from '../iap-pending-utils';
import { buildMockReceiptData, buildMockTransactionId } from '../wallet-utils';

export default {
  components: {
    Sidebar,
  },
  data() {
    return {
      loading: false,
      verifying: false,
      errorText: '',
      successText: '',
      tauriReady: false,
      pendingQueue: [],
      retryingMap: {},
      retryingAll: false,
      walletBalance: 0,
      products: [],
      ledger: [],
      form: {
        productId: '',
        transactionId: '',
        originalTransactionId: '',
        receiptData: '',
      },
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
    clearForm() {
      this.form = {
        productId: '',
        transactionId: '',
        originalTransactionId: '',
        receiptData: '',
      };
    },
    prepareMockPayload(product) {
      const productId = product?.productId || this.form.productId;
      if (!productId) {
        return;
      }
      this.form.productId = productId;
      this.form.transactionId = buildMockTransactionId(productId);
      this.form.receiptData = buildMockReceiptData(productId);
      this.successText = '已填充 mock 验单参数，可直接提交。';
      this.errorText = '';
    },
    syncPendingQueue(queue) {
      this.pendingQueue = Array.isArray(queue) ? queue : [];
      writePendingIapQueue(this.pendingQueue);
    },
    loadPendingQueue() {
      this.pendingQueue = readPendingIapQueue();
    },
    markRetrying(transactionId, retrying) {
      if (!transactionId) {
        return;
      }
      const next = { ...this.retryingMap };
      if (retrying) {
        next[transactionId] = true;
      } else {
        delete next[transactionId];
      }
      this.retryingMap = next;
    },
    isRetryingItem(transactionId) {
      return !!this.retryingMap[transactionId];
    },
    async verifyAndSettlePurchase(purchase, { queueOnFailure = true, silent = false } = {}) {
      try {
        const result = await this.$store.dispatch('verifyIapOrder', {
          productId: purchase.productId,
          transactionId: purchase.transactionId,
          originalTransactionId: purchase.originalTransactionId,
          receiptData: purchase.receiptData,
        });
        this.syncPendingQueue(
          settlePendingIapSuccess(this.pendingQueue, purchase.transactionId),
        );
        await Promise.all([this.refreshWallet(), this.refreshLedger()]);
        if (!silent) {
          this.successText = `验单完成：status=${result.status}, verifyMode=${result.verifyMode}, credited=${result.credited}`;
        }
        return true;
      } catch (error) {
        const errorText = error?.response?.data?.error || error?.message || 'verify failed';
        if (queueOnFailure) {
          this.syncPendingQueue(
            registerPendingIapFailure(this.pendingQueue, purchase, errorText),
          );
        }
        if (!silent) {
          this.errorText = queueOnFailure
            ? `验单失败，已加入待重试队列：${errorText}`
            : errorText;
        }
        return false;
      }
    },
    async quickMockVerify(product) {
      this.prepareMockPayload(product);
      await this.submitVerify();
    },
    async purchaseAndVerifyViaTauri(product) {
      const productId = product?.productId || this.form.productId;
      if (!productId) {
        this.errorText = 'productId 不能为空';
        return;
      }
      this.verifying = true;
      this.errorText = '';
      this.successText = '';
      try {
        const purchase = await purchaseIapViaTauri(productId);
        this.form.productId = purchase.productId;
        this.form.transactionId = purchase.transactionId;
        this.form.originalTransactionId = purchase.originalTransactionId || '';
        this.form.receiptData = purchase.receiptData;
        const ok = await this.verifyAndSettlePurchase(purchase, {
          queueOnFailure: true,
          silent: true,
        });
        if (ok) {
          this.successText = `Tauri 购买上报完成：source=${purchase.source}, tx=${purchase.transactionId}`;
        } else {
          this.errorText = `Tauri 购买验单失败，交易已入待重试队列：tx=${purchase.transactionId}`;
        }
      } catch (error) {
        this.errorText = error?.response?.data?.error || error?.message || 'Tauri 购买验单失败';
      } finally {
        this.verifying = false;
      }
    },
    async refreshProducts() {
      this.products = await this.$store.dispatch('listIapProducts', { activeOnly: true });
      if (!this.form.productId && this.products[0]?.productId) {
        this.form.productId = this.products[0].productId;
      }
    },
    async refreshWallet() {
      const payload = await this.$store.dispatch('fetchWalletBalance');
      this.walletBalance = Number(payload?.balance || 0);
    },
    async refreshLedger() {
      this.ledger = await this.$store.dispatch('listWalletLedger', { limit: 50 });
    },
    async refreshPage() {
      this.loading = true;
      this.errorText = '';
      this.successText = '';
      try {
        await Promise.all([this.refreshProducts(), this.refreshWallet(), this.refreshLedger()]);
      } catch (error) {
        this.errorText = error?.response?.data?.error || error?.message || '刷新失败';
      } finally {
        this.loading = false;
      }
    },
    async submitVerify() {
      if (!this.form.productId || !this.form.transactionId || !this.form.receiptData) {
        this.errorText = 'productId / transactionId / receiptData 不能为空';
        return;
      }
      this.verifying = true;
      this.errorText = '';
      this.successText = '';
      try {
        const purchase = {
          productId: this.form.productId,
          transactionId: this.form.transactionId,
          originalTransactionId: this.form.originalTransactionId || null,
          receiptData: this.form.receiptData,
          source: 'manual',
        };
        await this.verifyAndSettlePurchase(purchase, {
          queueOnFailure: true,
          silent: false,
        });
      } finally {
        this.verifying = false;
      }
    },
    async retryPendingItem(item, { silent = false } = {}) {
      if (!item?.transactionId || this.isRetryingItem(item.transactionId)) {
        return false;
      }
      this.markRetrying(item.transactionId, true);
      try {
        return await this.verifyAndSettlePurchase(item, {
          queueOnFailure: true,
          silent,
        });
      } finally {
        this.markRetrying(item.transactionId, false);
      }
    },
    async retryAllPending() {
      if (this.retryingAll || this.pendingQueue.length === 0) {
        return;
      }
      this.retryingAll = true;
      this.errorText = '';
      this.successText = '';
      let successCount = 0;
      let failedCount = 0;
      const snapshot = [...this.pendingQueue];
      for (const item of snapshot) {
        const ok = await this.retryPendingItem(item, { silent: true });
        if (ok) {
          successCount += 1;
        } else {
          failedCount += 1;
        }
      }
      if (failedCount > 0) {
        this.errorText = `队列重试完成：成功 ${successCount}，失败 ${failedCount}（失败交易仍保留在队列中）`;
      } else {
        this.successText = `队列重试完成：全部成功（${successCount}）`;
      }
      this.retryingAll = false;
    },
  },
  async mounted() {
    this.tauriReady = isTauriRuntime();
    this.loadPendingQueue();
    await this.refreshPage();
    if (this.pendingQueue.length > 0) {
      await this.retryAllPending();
    }
  },
};
</script>
