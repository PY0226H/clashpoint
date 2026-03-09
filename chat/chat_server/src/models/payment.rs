use crate::{AppError, AppState};
use chat_core::User;

mod helpers;
mod order_flow;
mod order_ops;
mod query_ops;
mod receipt_verify;
mod types;

const MAX_RECEIPT_LEN: usize = 4096;

pub use types::{
    GetIapOrderByTransaction, GetIapOrderByTransactionOutput, IapOrderSnapshot, IapProduct,
    ListIapProducts, ListWalletLedger, VerifyIapOrderInput, VerifyIapOrderOutput,
    WalletBalanceOutput, WalletLedgerItem,
};

#[cfg(test)]
mod tests;
