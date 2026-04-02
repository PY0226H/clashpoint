export function normalizePasswordInput(raw) {
  return String(raw || '').trim();
}

export function normalizeSmsCodeInput(raw) {
  return String(raw || '').trim();
}

export function validateSetPasswordInput(password, confirmPassword, smsCode) {
  const normalized = normalizePasswordInput(password);
  const normalizedConfirm = normalizePasswordInput(confirmPassword);
  const normalizedSmsCode = normalizeSmsCodeInput(smsCode);
  if (!normalized) {
    return { valid: false, code: 'required' };
  }
  if (normalized.length < 6) {
    return { valid: false, code: 'too_short' };
  }
  if (normalizedConfirm !== normalized) {
    return { valid: false, code: 'mismatch' };
  }
  if (!normalizedSmsCode) {
    return { valid: false, code: 'sms_required' };
  }
  return { valid: true, code: '' };
}
