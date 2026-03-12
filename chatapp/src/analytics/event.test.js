import test from 'node:test';
import assert from 'node:assert/strict';

import { fromBinary } from '@bufbuild/protobuf';
import { AnalyticsEventSchema } from '../gen/messages_pb.js';
import {
  sendUserLoginEvent,
  sendUserLogoutEvent,
  sendUserRegisterEvent,
} from './event.js';

function decodeFirstEvent(calls) {
  assert.equal(calls.length, 1);
  const body = calls[0]?.init?.body;
  const bytes = body instanceof Uint8Array ? body : new Uint8Array(body || []);
  return fromBinary(AnalyticsEventSchema, bytes);
}

async function withMockedFetch(run) {
  const calls = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return {
      ok: true,
      status: 201,
    };
  };
  try {
    await run(calls);
  } finally {
    globalThis.fetch = originalFetch;
  }
}

test('sendUserLoginEvent should emit account metadata and keep legacy email for email login', async () => {
  await withMockedFetch(async (calls) => {
    await sendUserLoginEvent({}, 'token', {
      accountType: 'email',
      accountIdentifier: 'Tester@Acme.Org',
      userId: 42,
    });
    const event = decodeFirstEvent(calls);
    assert.equal(event.eventType.case, 'userLogin');
    assert.equal(event.eventType.value.email, 'tester@acme.org');
    assert.equal(event.eventType.value.accountType, 'email');
    assert.equal(event.eventType.value.userId, '42');
    assert.ok(event.eventType.value.accountIdentifierHash.length > 0);
  });
});

test('sendUserRegisterEvent should not write legacy email for phone register', async () => {
  await withMockedFetch(async (calls) => {
    await sendUserRegisterEvent({}, '', {
      accountType: 'phone',
      accountIdentifier: '+8613800138000',
      userId: '1001',
    });
    const event = decodeFirstEvent(calls);
    assert.equal(event.eventType.case, 'userRegister');
    assert.equal(event.eventType.value.email, '');
    assert.equal(event.eventType.value.accountType, 'phone');
    assert.equal(event.eventType.value.userId, '1001');
    assert.ok(event.eventType.value.accountIdentifierHash.length > 0);
  });
});

test('sendUserLogoutEvent should degrade hash to empty when crypto subtle digest throws', async () => {
  const originalCrypto = globalThis.crypto;
  Object.defineProperty(globalThis, 'crypto', {
    configurable: true,
    value: {
      subtle: {
        digest: async () => {
          throw new Error('digest-unavailable');
        },
      },
    },
  });
  try {
    await withMockedFetch(async (calls) => {
      await sendUserLogoutEvent({}, '', {
        accountType: 'wechat',
        accountIdentifier: 'mock_wechat_user_01',
        userId: '9001',
      });
      const event = decodeFirstEvent(calls);
      assert.equal(event.eventType.case, 'userLogout');
      assert.equal(event.eventType.value.accountType, 'wechat');
      assert.equal(event.eventType.value.email, '');
      assert.equal(event.eventType.value.accountIdentifierHash, '');
    });
  } finally {
    Object.defineProperty(globalThis, 'crypto', {
      configurable: true,
      value: originalCrypto,
    });
  }
});
