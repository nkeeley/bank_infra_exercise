// ── Auth ──
export interface UserSignupRequest {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  phone?: string | null;
}

export interface UserLoginRequest {
  email: string;
  password: string;
}

export interface SignupResponse {
  user_id: string;
  email: string;
  user_type: string;
  token: string;
  token_type: string;
}

export interface TokenResponse {
  token: string;
  token_type: string;
}

// ── Account Holders ──
export interface AccountHolderResponse {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
  created_at: string;
}

export interface AccountHolderUpdateRequest {
  first_name?: string | null;
  last_name?: string | null;
  phone?: string | null;
}

// ── Accounts ──
export interface AccountCreateRequest {
  account_type?: "checking" | "savings";
}

export interface AccountResponse {
  id: string;
  account_holder_id: string;
  account_type: string;
  account_number: string;
  cached_balance_cents: number;
  currency: string;
  is_active: boolean;
  created_at: string;
}

export interface BalanceResponse {
  account_id: string;
  cached_balance_cents: number;
  computed_balance_cents: number;
  match: boolean;
  currency: string;
}

// ── Transactions ──
export interface TransactionCreateRequest {
  type: "credit" | "debit";
  amount_cents: number;
  description?: string | null;
  card_id?: string | null;
}

export interface TransactionResponse {
  id: string;
  type: string;
  amount_cents: number;
  from_account_id: string | null;
  to_account_id: string | null;
  status: string;
  description: string | null;
  transfer_pair_id: string | null;
  card_id: string | null;
  created_at: string;
}

// ── Transfers ──
export interface TransferRequest {
  from_account_id: string;
  to_account_id: string;
  amount_cents: number;
  description?: string | null;
}

export interface TransferResponse {
  transfer_pair_id: string;
  debit_transaction: TransactionResponse;
  credit_transaction: TransactionResponse;
  amount_cents: number;
  from_account_id: string;
  to_account_id: string;
}

// ── Cards ──
export interface CardResponse {
  id: string;
  account_id: string;
  card_number_last_four: string;
  expiration_month: number;
  expiration_year: number;
  is_active: boolean;
  created_at: string;
}

// ── Statements ──
export interface StatementResponse {
  account_id: string;
  year: number;
  month: number;
  opening_balance_cents: number;
  closing_balance_cents: number;
  total_credits_cents: number;
  total_debits_cents: number;
  transaction_count: number;
  transactions: TransactionResponse[];
}
