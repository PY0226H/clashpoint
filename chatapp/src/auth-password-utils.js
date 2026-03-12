export function normalizePasswordInput(raw) {
  return String(raw || '').trim();
}

export function validateSetPasswordInput(password, confirmPassword) {
  const normalized = normalizePasswordInput(password);
  const normalizedConfirm = normalizePasswordInput(confirmPassword);
  if (!normalized) {
    return { valid: false, code: 'required' };
  }
  if (normalized.length < 6) {
    return { valid: false, code: 'too_short' };
  }
  if (normalizedConfirm !== normalized) {
    return { valid: false, code: 'mismatch' };
  }
  return { valid: true, code: '' };
}
