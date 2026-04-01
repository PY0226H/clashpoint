<template>
  <div class="flex h-screen echo-shell">
    <Sidebar />
    <div class="echo-main">
      <div class="max-w-6xl mx-auto p-6 lg:p-8 space-y-4 echo-fade-in">
        <div class="echo-panel-strong p-5 flex items-start justify-between gap-3">
          <div>
            <div class="text-[11px] uppercase tracking-[0.24em] text-slate-500">Wallet & IAP</div>
            <h1 class="text-2xl font-semibold text-slate-900 mt-1">充值与验单工作台</h1>
            <p class="text-sm text-slate-600 mt-1">
              用于演示充值验单链路：商品列表、验单入账、余额与账本收敛。
            </p>
          </div>
          <button
            @click="refreshPage"
            :disabled="loading"
            class="echo-btn-primary disabled:opacity-60"
          >
            {{ loading ? '刷新中...' : '刷新' }}
          </button>
        </div>

        <div v-if="errorText" class="bg-red-50 text-red-700 border border-red-200 rounded-xl p-3 text-sm">
          {{ errorText }}
        </div>
        <div v-if="successText" class="bg-green-50 text-green-700 border border-green-200 rounded-xl p-3 text-sm">
          {{ successText }}
        </div>

        <div class="echo-panel p-4 flex items-center justify-between gap-3">
          <div>
            <div class="text-xs uppercase text-gray-500">Wallet Balance</div>
            <div class="text-2xl font-bold text-gray-900">{{ walletBalance }}</div>
          </div>
          <button
            @click="refreshWallet"
            :disabled="loading"
            class="echo-btn-secondary disabled:opacity-50"
          >
            刷新余额
          </button>
        </div>

        <div v-if="tauriReady" class="echo-panel p-4 space-y-2">
          <div class="flex items-center justify-between">
            <div class="text-sm font-semibold text-gray-900">Native Bridge 诊断</div>
            <button
              @click="refreshNativeBridgeDiagnostics"
              :disabled="nativeBridgeDiagnosticsLoading"
              class="echo-btn-secondary text-xs px-3 py-1.5 disabled:opacity-50"
            >
              {{ nativeBridgeDiagnosticsLoading ? '检查中...' : '刷新诊断' }}
            </button>
          </div>
          <div v-if="!nativeBridgeDiagnostics" class="text-sm text-gray-600">
            尚未获取诊断信息。
          </div>
          <div v-else class="text-xs text-gray-700 space-y-1">
            <div>
              mode: {{ nativeBridgeDiagnostics.purchaseMode }}
              · runtime: {{ nativeBridgeDiagnostics.runtimeEnv || '-' }}
              · production: {{ nativeBridgeDiagnostics.runtimeIsProduction }}
            </div>
            <div>
              allowlistConfigured: {{ nativeBridgeDiagnostics.allowedProductIdsConfigured }}
              · allowlistSize: {{ nativeAllowedProductIds.length }}
            </div>
            <div>
              bin: {{ nativeBridgeDiagnostics.nativeBridgeBin || '(empty)' }}
              · exists: {{ nativeBridgeDiagnostics.nativeBridgeBinExists }}
              · executable: {{ nativeBridgeDiagnostics.nativeBridgeBinExecutable }}
            </div>
            <div>
              simulateArg: {{ nativeBridgeDiagnostics.hasSimulateArg }}
              · jsonOverride: {{ nativeBridgeDiagnostics.jsonOverridePresent }}
              · policyOk: {{ nativeBridgeDiagnostics.productionPolicyOk }}
            </div>
            <div
              class="font-semibold"
              :class="nativeBridgeDiagnostics.readyForNativePurchase ? 'text-emerald-700' : 'text-amber-700'"
            >
              {{ nativeBridgeDiagnostics.readyForNativePurchase
                ? '当前环境可进行 Native 购买联调'
                : '当前环境未满足 Native 购买联调条件' }}
            </div>
            <div v-if="nativeBridgeDiagnostics.productionPolicyError" class="text-red-700">
              policyError: {{ nativeBridgeDiagnostics.productionPolicyError }}
            </div>
            <div v-if="nativeBridgeDiagnostics.invalidAllowedProductIds.length > 0" class="text-red-700">
              invalidAllowlist: {{ nativeBridgeDiagnostics.invalidAllowedProductIds.join(', ') }}
            </div>
            <div v-if="backendProductsNotAllowlisted.length > 0" class="text-amber-700">
              backendOnlyProducts: {{ backendProductsNotAllowlisted.join(', ') }}
            </div>
            <div v-if="allowlistedProductsMissingBackend.length > 0" class="text-amber-700">
              allowlistOnlyProducts: {{ allowlistedProductsMissingBackend.join(', ') }}
            </div>
          </div>
        </div>

        <div class="echo-panel p-4 space-y-3">
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

        <div class="echo-panel p-4 space-y-3">
          <div class="text-sm font-semibold text-gray-900">手动验单</div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <div class="text-xs uppercase text-gray-500 mb-1">productId</div>
              <select
                v-model="form.productId"
                class="echo-field"
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
                class="echo-field"
              />
            </div>
            <div>
              <div class="text-xs uppercase text-gray-500 mb-1">originalTransactionId(optional)</div>
              <input
                v-model.trim="form.originalTransactionId"
                type="text"
                class="echo-field"
              />
            </div>
            <div class="md:col-span-2">
              <div class="text-xs uppercase text-gray-500 mb-1">receiptData</div>
              <textarea
                v-model.trim="form.receiptData"
                rows="3"
                class="echo-field"
              />
            </div>
          </div>
          <div class="flex gap-2">
            <button
              @click="submitVerify"
              :disabled="verifying"
              class="echo-btn-primary disabled:opacity-50"
            >
              {{ verifying ? '验单中...' : '提交验单' }}
            </button>
            <button
              @click="clearForm"
              :disabled="verifying"
              class="echo-btn-secondary disabled:opacity-50"
            >
              清空
            </button>
          </div>
        </div>

        <div class="echo-panel p-4 space-y-3">
          <div class="flex items-center justify-between">
            <div class="text-sm font-semibold text-gray-900">
              待重试交易队列
              <span class="text-xs font-normal text-gray-500">
                (maxAttempts={{ pendingRetryPolicy.maxAttempts }})
              </span>
            </div>
            <div class="flex items-center gap-2">
              <button
                @click="dropAllExhaustedPending"
                :disabled="retryingAll || exhaustedPendingCount === 0"
                class="echo-btn-secondary text-xs px-3 py-1.5 disabled:opacity-50"
              >
                清理已达上限({{ exhaustedPendingCount }})
              </button>
              <button
                @click="recoverAllExhaustedPending"
                :disabled="retryingAll || exhaustedPendingCount === 0"
                class="echo-btn-secondary text-xs px-3 py-1.5 disabled:opacity-50"
              >
                恢复已达上限({{ exhaustedPendingCount }})
              </button>
              <button
                @click="retryAllPending"
                :disabled="retryingAll || pendingQueue.length === 0"
                class="echo-btn-secondary text-xs px-3 py-1.5 disabled:opacity-50"
              >
                {{ retryingAll ? '重试中...' : '重试全部' }}
              </button>
            </div>
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
                  <div><span class="font-semibold">nextRetryAt:</span> {{ formatDateTime(item.nextRetryAt) }}</div>
                  <div
                    class="font-semibold"
                    :class="isPendingRetryable(item) ? 'text-emerald-700' : 'text-amber-700'"
                  >
                    {{ pendingRetryStatusText(item) }}
                  </div>
                  <div v-if="item.lastError" class="text-red-700">
                    <span class="font-semibold">lastError:</span> {{ item.lastError }}
                  </div>
                </div>
                <div class="flex flex-col gap-1">
                  <button
                    @click="retryPendingItem(item)"
                    :disabled="isRetryingItem(item.transactionId) || !isPendingRetryable(item)"
                    class="px-2 py-1 text-xs rounded bg-blue-600 text-white disabled:opacity-50"
                  >
                    {{ isRetryingItem(item.transactionId) ? '重试中...' : '重试' }}
                  </button>
                  <button
                    v-if="isPendingExhausted(item)"
                    @click="recoverPendingItem(item)"
                    :disabled="isRetryingItem(item.transactionId)"
                    class="echo-btn-secondary text-xs px-2 py-1 disabled:opacity-50"
                  >
                    恢复重试
                  </button>
                  <button
                    @click="ignorePendingItem(item)"
                    :disabled="isRetryingItem(item.transactionId)"
                    class="echo-btn-secondary text-xs px-2 py-1 disabled:opacity-50"
                  >
                    忽略
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="echo-panel p-4 space-y-3">
          <div class="flex items-center justify-between">
            <div class="text-sm font-semibold text-gray-900">钱包账本</div>
            <button
              @click="refreshLedger"
              :disabled="loading"
              class="echo-btn-secondary text-xs px-3 py-1.5 disabled:opacity-50"
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
import {
  getIapNativeBridgeDiagnostics,
  isTauriRuntime,
  purchaseIapViaTauri,
} from '../iap-bridge';
import {
  DEFAULT_PENDING_IAP_RETRY_POLICY,
  filterRetryablePendingIap,
  isPendingIapMaxAttemptsReached,
  isPendingIapRetryable,
  removeExhaustedPendingIap,
  removePendingIapByTransaction,
  readPendingIapQueue,
  registerPendingIapFailure,
  resetPendingIapRetry,
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
      nativeBridgeDiagnostics: null,
      nativeBridgeDiagnosticsLoading: false,
      pendingQueue: [],
      pendingRetryPolicy: { ...DEFAULT_PENDING_IAP_RETRY_POLICY },
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
  computed: {
    exhaustedPendingCount() {
      return this.pendingQueue.filter((item) => this.isPendingExhausted(item)).length;
    },
    nativeAllowedProductIds() {
      const ids = this.nativeBridgeDiagnostics?.allowedProductIds;
      return Array.isArray(ids) ? ids : [];
    },
    backendProductsNotAllowlisted() {
      if (this.nativeAllowedProductIds.length === 0) {
        return [];
      }
      const allowedSet = new Set(this.nativeAllowedProductIds);
      return this.products
        .map((product) => String(product?.productId || '').trim())
        .filter((id) => id && !allowedSet.has(id));
    },
    allowlistedProductsMissingBackend() {
      if (this.nativeAllowedProductIds.length === 0) {
        return [];
      }
      const backendSet = new Set(
        this.products
          .map((product) => String(product?.productId || '').trim())
          .filter((id) => id),
      );
      return this.nativeAllowedProductIds.filter((id) => !backendSet.has(id));
    },
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
    async refreshNativeBridgeDiagnostics({ silent = false } = {}) {
      if (!this.tauriReady) {
        this.nativeBridgeDiagnostics = null;
        return;
      }
      this.nativeBridgeDiagnosticsLoading = true;
      try {
        this.nativeBridgeDiagnostics = await getIapNativeBridgeDiagnostics();
      } catch (error) {
        if (!silent) {
          this.errorText = error?.message || 'native bridge diagnostics failed';
        }
      } finally {
        this.nativeBridgeDiagnosticsLoading = false;
      }
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
    isPendingRetryable(item, nowMs = Date.now()) {
      return isPendingIapRetryable(item, nowMs, this.pendingRetryPolicy);
    },
    isPendingExhausted(item) {
      return isPendingIapMaxAttemptsReached(item, this.pendingRetryPolicy);
    },
    pendingRetryStatusText(item, nowMs = Date.now()) {
      if (this.isPendingExhausted(item)) {
        return `已达最大重试次数(${this.pendingRetryPolicy.maxAttempts})`;
      }
      const nextRetryAt = Number(item?.nextRetryAt);
      if (Number.isFinite(nextRetryAt) && nextRetryAt > nowMs) {
        return '冷却中';
      }
      return '可重试';
    },
    recoverPendingItem(item) {
      if (!item?.transactionId) {
        return;
      }
      this.syncPendingQueue(
        resetPendingIapRetry(
          this.pendingQueue,
          item.transactionId,
          Date.now(),
          this.pendingRetryPolicy,
        ),
      );
      this.successText = `已恢复重试：tx=${item.transactionId}`;
      this.errorText = '';
    },
    ignorePendingItem(item) {
      if (!item?.transactionId) {
        return;
      }
      this.syncPendingQueue(
        removePendingIapByTransaction(this.pendingQueue, item.transactionId, Date.now()),
      );
      this.successText = `已忽略交易：tx=${item.transactionId}`;
      this.errorText = '';
    },
    recoverAllExhaustedPending() {
      const recoverCount = this.exhaustedPendingCount;
      if (recoverCount === 0) {
        return;
      }
      let nextQueue = [...this.pendingQueue];
      for (const item of this.pendingQueue) {
        if (!this.isPendingExhausted(item)) {
          continue;
        }
        nextQueue = resetPendingIapRetry(
          nextQueue,
          item.transactionId,
          Date.now(),
          this.pendingRetryPolicy,
        );
      }
      this.syncPendingQueue(nextQueue);
      this.successText = `已恢复 ${recoverCount} 条达到上限的交易`;
      this.errorText = '';
    },
    dropAllExhaustedPending() {
      const dropCount = this.exhaustedPendingCount;
      if (dropCount === 0) {
        return;
      }
      this.syncPendingQueue(
        removeExhaustedPendingIap(this.pendingQueue, Date.now(), this.pendingRetryPolicy),
      );
      this.successText = `已清理 ${dropCount} 条达到上限的交易`;
      this.errorText = '';
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
          const nowMs = Date.now();
          this.syncPendingQueue(
            registerPendingIapFailure(
              this.pendingQueue,
              purchase,
              errorText,
              nowMs,
              this.pendingRetryPolicy,
            ),
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
    async reconcilePendingItem(item, { silent = false } = {}) {
      const payload = await this.$store.dispatch('getIapOrderByTransaction', {
        transactionId: item.transactionId,
      });
      const order = payload?.order || null;
      if (!payload?.found || !order) {
        return false;
      }
      this.syncPendingQueue(
        settlePendingIapSuccess(this.pendingQueue, item.transactionId),
      );
      if (order.status === 'verified') {
        await Promise.all([this.refreshWallet(), this.refreshLedger()]);
        if (!silent) {
          this.successText = `交易已在服务端验单成功并入账：tx=${item.transactionId}`;
          this.errorText = '';
        }
        return true;
      }
      if (!silent) {
        this.errorText = `交易已在服务端落单且状态为 ${order.status}，已移出待重试队列`;
      }
      return true;
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
        const code = String(error?.code || '').trim().toLowerCase();
        if (code === 'purchase_pending') {
          this.successText = '购买已提交且处于待处理状态，请稍后完成支付后再重试验单。';
          this.errorText = '';
        } else if (code === 'purchase_cancelled') {
          this.errorText = '购买已取消，未发生扣费。';
        } else if (code === 'product_not_found') {
          this.errorText = 'StoreKit 未找到该商品，请检查商品配置与沙盒账号权限。';
        } else {
          this.errorText = error?.response?.data?.error || error?.message || 'Tauri 购买验单失败';
        }
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
        const tasks = [this.refreshProducts(), this.refreshWallet(), this.refreshLedger()];
        if (this.tauriReady) {
          tasks.push(this.refreshNativeBridgeDiagnostics({ silent: true }));
        }
        await Promise.all(tasks);
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
      if (!this.isPendingRetryable(item)) {
        if (!silent) {
          this.errorText = `交易暂不可重试：tx=${item.transactionId}，${this.pendingRetryStatusText(item)}`;
        }
        return false;
      }
      this.markRetrying(item.transactionId, true);
      try {
        try {
          const settled = await this.reconcilePendingItem(item, { silent });
          if (settled) {
            return true;
          }
        } catch (error) {
          if (!silent) {
            const errorText = error?.response?.data?.error || error?.message || 'query iap order failed';
            this.errorText = `对账查询失败，回退到重试验单：${errorText}`;
          }
        }
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
      const nowMs = Date.now();
      const retryableItems = filterRetryablePendingIap(
        this.pendingQueue,
        nowMs,
        this.pendingRetryPolicy,
      );
      const skippedCount = Math.max(0, this.pendingQueue.length - retryableItems.length);
      for (const item of retryableItems) {
        const ok = await this.retryPendingItem(item, { silent: true });
        if (ok) {
          successCount += 1;
        } else {
          failedCount += 1;
        }
      }
      const suffix = skippedCount > 0 ? `，跳过 ${skippedCount}` : '';
      if (failedCount > 0) {
        this.errorText = `队列重试完成：成功 ${successCount}，失败 ${failedCount}${suffix}（失败交易仍保留在队列中）`;
      } else {
        this.successText = `队列重试完成：全部成功（${successCount}${suffix}）`;
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
