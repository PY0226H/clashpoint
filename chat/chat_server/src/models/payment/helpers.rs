use crate::AppError;
use sha1::{Digest, Sha1};

const DEFAULT_LIMIT: u64 = 20;
const MAX_LIMIT: u64 = 100;

pub(super) fn normalize_limit(limit: Option<u64>) -> i64 {
    let limit = limit.unwrap_or(DEFAULT_LIMIT).clamp(1, MAX_LIMIT);
    limit as i64
}

pub(super) fn validate_identifier(
    input: &str,
    field: &str,
    max_len: usize,
) -> Result<(), AppError> {
    if input.trim().is_empty() {
        return Err(AppError::PaymentError(format!("{field} cannot be empty")));
    }
    if input.len() > max_len {
        return Err(AppError::PaymentError(format!(
            "{field} is too long, max {max_len}"
        )));
    }
    Ok(())
}

pub(super) fn hash_receipt(receipt: &str) -> String {
    let mut hasher = Sha1::new();
    hasher.update(receipt.as_bytes());
    hex::encode(hasher.finalize())
}
