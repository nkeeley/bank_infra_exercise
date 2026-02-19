import type {
  UserSignupRequest, SignupResponse, UserLoginRequest, TokenResponse,
  AccountHolderResponse, AccountHolderUpdateRequest,
  AccountResponse, AccountCreateRequest, BalanceResponse, AccountLookupResponse,
  TransactionResponse, TransactionCreateRequest,
  TransferRequest, TransferResponse,
  CardResponse, StatementResponse,
} from "@/types/api";

// Change this to your API base URL
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function getToken(): string | null {
  return localStorage.getItem("bank_token");
}

export function setToken(token: string) {
  localStorage.setItem("bank_token", token);
}

export function clearToken() {
  localStorage.removeItem("bank_token");
  localStorage.removeItem("bank_user_type");
  localStorage.removeItem("bank_user_email");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const msg = body?.detail?.[0]?.msg || body?.detail || res.statusText;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }

  return res.json();
}

// ── Auth ──
export const auth = {
  signup: (data: UserSignupRequest) =>
    request<SignupResponse>("/auth/signup", { method: "POST", body: JSON.stringify(data) }),
  login: (data: UserLoginRequest) =>
    request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(data) }),
};

// ── Account Holders ──
export const accountHolders = {
  me: () => request<AccountHolderResponse>("/account-holders/me"),
  update: (data: AccountHolderUpdateRequest) =>
    request<AccountHolderResponse>("/account-holders/me", { method: "PATCH", body: JSON.stringify(data) }),
};

// ── Accounts ──
export const accounts = {
  list: () => request<AccountResponse[]>("/accounts"),
  get: (id: string) => request<AccountResponse>(`/accounts/${id}`),
  create: (data: AccountCreateRequest) =>
    request<AccountResponse>("/accounts", { method: "POST", body: JSON.stringify(data) }),
  balance: (id: string) => request<BalanceResponse>(`/accounts/${id}/balance`),
  lookup: (accountNumber: string) =>
    request<AccountLookupResponse>(`/accounts/lookup?account_number=${encodeURIComponent(accountNumber)}`),
};

// ── Transactions ──
export const transactions = {
  list: (accountId: string, params?: { status?: string; type?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.type) q.set("type", params.type);
    if (params?.limit) q.set("limit", String(params.limit));
    if (params?.offset) q.set("offset", String(params.offset));
    const qs = q.toString();
    return request<TransactionResponse[]>(`/accounts/${accountId}/transactions${qs ? `?${qs}` : ""}`);
  },
  get: (accountId: string, txnId: string) =>
    request<TransactionResponse>(`/accounts/${accountId}/transactions/${txnId}`),
  create: (accountId: string, data: TransactionCreateRequest) =>
    request<TransactionResponse>(`/accounts/${accountId}/transactions`, { method: "POST", body: JSON.stringify(data) }),
};

// ── Transfers ──
export const transfers = {
  create: (data: TransferRequest) =>
    request<TransferResponse>("/transfers", { method: "POST", body: JSON.stringify(data) }),
};

// ── Cards ──
export const cards = {
  get: (accountId: string) => request<CardResponse>(`/accounts/${accountId}/card`),
  issue: (accountId: string) =>
    request<CardResponse>(`/accounts/${accountId}/card`, { method: "POST" }),
};

// ── Statements ──
export const statements = {
  get: (accountId: string, year: number, month: number) =>
    request<StatementResponse>(`/accounts/${accountId}/statements?year=${year}&month=${month}`),
};

// ── Admin ──
export const admin = {
  accounts: {
    list: () => request<AccountResponse[]>("/admin/accounts"),
    get: (id: string) => request<AccountResponse>(`/admin/accounts/${id}`),
    balance: (id: string) => request<BalanceResponse>(`/admin/accounts/${id}/balance`),
    transactions: (accountId: string, params?: { limit?: number; offset?: number }) => {
      const q = new URLSearchParams();
      if (params?.limit) q.set("limit", String(params.limit));
      if (params?.offset) q.set("offset", String(params.offset));
      const qs = q.toString();
      return request<TransactionResponse[]>(`/admin/accounts/${accountId}/transactions${qs ? `?${qs}` : ""}`);
    },
  },
  transactions: {
    list: (params?: { status?: string; type?: string; limit?: number; offset?: number }) => {
      const q = new URLSearchParams();
      if (params?.status) q.set("status", params.status);
      if (params?.type) q.set("type", params.type);
      if (params?.limit) q.set("limit", String(params.limit));
      if (params?.offset) q.set("offset", String(params.offset));
      const qs = q.toString();
      return request<TransactionResponse[]>(`/admin/transactions${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => request<TransactionResponse>(`/admin/transactions/${id}`),
  },
};
