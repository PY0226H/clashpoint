import assert from 'node:assert/strict';
import {
  normalizePasswordInput,
  normalizeSmsCodeInput,
  validateSetPasswordInput,
} from './auth-password-utils';

assert.equal(normalizePasswordInput('  abc123  '), 'abc123');
assert.equal(normalizePasswordInput(null), '');
assert.equal(normalizeSmsCodeInput(' 123456 '), '123456');
assert.equal(normalizeSmsCodeInput(undefined), '');

assert.deepEqual(validateSetPasswordInput('', '', '123456'), {
  valid: false,
  code: 'required',
});

assert.deepEqual(validateSetPasswordInput('12345', '12345', '123456'), {
  valid: false,
  code: 'too_short',
});

assert.deepEqual(validateSetPasswordInput('123456', '654321', '123456'), {
  valid: false,
  code: 'mismatch',
});

assert.deepEqual(validateSetPasswordInput('123456', '123456', ''), {
  valid: false,
  code: 'sms_required',
});

assert.deepEqual(validateSetPasswordInput('123456', '123456', '123456'), {
  valid: true,
  code: '',
});
