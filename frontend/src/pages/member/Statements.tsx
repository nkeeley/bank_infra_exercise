import { useEffect, useState } from "react";
import { accounts, statements as statementsApi } from "@/lib/api";
import type { AccountResponse, StatementResponse } from "@/types/api";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCents, monthName, maskAccountNumber, formatDateTime } from "@/lib/format";
import { ArrowDownLeft, ArrowUpRight, FileText } from "lucide-react";

export default function StatementsPage() {
  const [accts, setAccts] = useState<AccountResponse[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<string>("");
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [statement, setStatement] = useState<StatementResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [stmtLoading, setStmtLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    accounts.list().then(a => {
      setAccts(a);
      if (a.length > 0) setSelectedAccount(a[0].id);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    if (!selectedAccount) return;
    setStmtLoading(true);
    setError("");
    statementsApi.get(selectedAccount, year, month)
      .then(setStatement)
      .catch(e => { setStatement(null); setError(e.message); })
      .finally(() => setStmtLoading(false));
  }, [selectedAccount, year, month]);

  if (loading) return <div className="h-64 rounded-xl bg-muted animate-pulse" />;

  const years = Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i);
  const months = Array.from({ length: 12 }, (_, i) => i + 1);

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Statements</h1>
        <p className="text-muted-foreground mt-1">Monthly account statements</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <Select value={selectedAccount} onValueChange={setSelectedAccount}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="Select account" />
          </SelectTrigger>
          <SelectContent>
            {accts.map(a => (
              <SelectItem key={a.id} value={a.id}>
                {a.account_type} — {maskAccountNumber(a.account_number)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={String(month)} onValueChange={v => setMonth(Number(v))}>
          <SelectTrigger className="w-[150px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {months.map(m => (
              <SelectItem key={m} value={String(m)}>{monthName(m)}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={String(year)} onValueChange={v => setYear(Number(v))}>
          <SelectTrigger className="w-[120px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {years.map(y => (
              <SelectItem key={y} value={String(y)}>{y}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {stmtLoading ? (
        <div className="h-48 rounded-xl bg-muted animate-pulse" />
      ) : error ? (
        <Card className="shadow-card">
          <CardContent className="p-12 text-center text-muted-foreground">
            <FileText className="h-12 w-12 mx-auto mb-4 opacity-30" />
            <p>No statement available for this period</p>
          </CardContent>
        </Card>
      ) : statement ? (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Opening Balance", value: formatCents(statement.opening_balance_cents) },
              { label: "Closing Balance", value: formatCents(statement.closing_balance_cents) },
              { label: "Total Credits", value: formatCents(statement.total_credits_cents), color: "text-success" },
              { label: "Total Debits", value: formatCents(statement.total_debits_cents), color: "text-destructive" },
            ].map(item => (
              <Card key={item.label} className="shadow-card">
                <CardContent className="p-4">
                  <p className="text-xs text-muted-foreground">{item.label}</p>
                  <p className={`text-lg font-bold mt-1 ${item.color || ""}`}>{item.value}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          <p className="text-sm text-muted-foreground">{statement.transaction_count} transactions</p>

          <Card className="shadow-card">
            <CardContent className="p-0 divide-y divide-border">
              {statement.transactions.map(tx => (
                <div key={tx.id} className="flex items-center justify-between px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className={`h-8 w-8 rounded-full flex items-center justify-center ${tx.type === "credit" ? "bg-success/10" : "bg-destructive/10"}`}>
                      {tx.type === "credit" ? <ArrowDownLeft className="h-4 w-4 text-success" /> : <ArrowUpRight className="h-4 w-4 text-destructive" />}
                    </div>
                    <div>
                      <p className="text-sm font-medium">{tx.description || tx.type}</p>
                      <p className="text-xs text-muted-foreground">{formatDateTime(tx.created_at)}</p>
                    </div>
                  </div>
                  <p className={`text-sm font-semibold ${tx.type === "credit" ? "text-success" : ""}`}>
                    {tx.type === "credit" ? "+" : "−"}{formatCents(tx.amount_cents)}
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}
