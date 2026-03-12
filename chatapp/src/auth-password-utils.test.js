import assert from 'node:assert/strict';
import {
  normalizePasswordInput,
  validateSetPasswordInput,
} from './auth-password-utils.js';

assert.equal(normalizePasswordInput('  abc123  '), 'abc123');
assert.equal(normalizePasswordInput(null), '');

assert.deepEqual(validateSetPasswordInput('', ''), {
  valid: false,
  code: 'required',
});

assert.deepEqual(validateSetPasswordInput('12345', '12345'), {
  valid: false,
  code: 'too_short',
});

assert.deepEqual(validateSetPasswordInput('123456', '654321'), {
  valid: false,
  code: 'mismatch',
});

assert.deepEqual(validateSetPasswordInput('123456', '123456'), {
  valid: true,
  code: '',
});
