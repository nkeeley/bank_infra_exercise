import { useEffect, useState } from "react";
import { accounts, transactions } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import type { AccountResponse, TransactionResponse } from "@/types/api";
import { formatCents, formatDateTime, maskAccountNumber } from "@/lib/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Wallet, TrendingUp, TrendingDown, ArrowUpRight, ArrowDownLeft } from "lucide-react";

export default function MemberOverview() {
  const { profile } = useAuth();
  const [accts, setAccts] = useState<AccountResponse[]>([]);
  const [txns, setTxns] = useState<Record<string, TransactionResponse[]>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const a = await accounts.list();
        setAccts(a);
        const txnMap: Record<string, TransactionResponse[]> = {};
        await Promise.all(
          a.map(async (acc) => {
            txnMap[acc.id] = await transactions.list(acc.id, { limit: 10 });
          })
        );
        setTxns(txnMap);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const totalBalance = accts.reduce((s, a) => s + a.cached_balance_cents, 0);

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-32 rounded-xl bg-muted animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Welcome header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Welcome back{profile ? `, ${profile.first_name}` : ""}
        </h1>
        <p className="text-muted-foreground mt-1">Here's your financial overview</p>
      </div>

      {/* Total balance card */}
      <Card className="border-0 shadow-premium gradient-navy text-primary-foreground">
        <CardContent className="p-6">
          <div className="flex items-center gap-3 mb-2">
            <Wallet className="h-5 w-5 text-accent" />
            <span className="text-sm font-medium text-primary-foreground/70">Total Balance</span>
          </div>
          <p className="text-4xl font-bold tracking-tight">{formatCents(totalBalance)}</p>
          <p className="text-sm text-primary-foreground/50 mt-1">
            Across {accts.length} account{accts.length !== 1 ? "s" : ""}
          </p>
        </CardContent>
      </Card>

      {/* Account cards */}
      <div className="grid gap-4 md:grid-cols-2">
        {accts.map(acc => (
          <Card key={acc.id} className="shadow-card hover:shadow-card-hover transition-shadow">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium capitalize text-muted-foreground">
                  {acc.account_type}
                </CardTitle>
                <span className="text-xs text-muted-foreground">{maskAccountNumber(acc.account_number)}</span>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{formatCents(acc.cached_balance_cents)}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Transactions per account */}
      {accts.map(acc => (
        <div key={acc.id}>
          <h2 className="text-lg font-semibold mb-3 capitalize">
            {acc.account_type} — {maskAccountNumber(acc.account_number)}
          </h2>
          <Card className="shadow-card">
            <CardContent className="p-0">
              {(!txns[acc.id] || txns[acc.id].length === 0) ? (
                <p className="p-6 text-center text-muted-foreground">No transactions yet</p>
              ) : (
                <div className="divide-y divide-border">
                  {txns[acc.id].map(tx => (
                    <div key={tx.id} className="flex items-center justify-between px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className={`h-9 w-9 rounded-full flex items-center justify-center ${tx.type === "credit" ? "bg-success/10" : "bg-destructive/10"}`}>
                          {tx.type === "credit" ? (
                            <ArrowDownLeft className="h-4 w-4 text-success" />
                          ) : (
                            <ArrowUpRight className="h-4 w-4 text-destructive" />
                          )}
                        </div>
                        <div>
                          <p className="text-sm font-medium">{tx.description || (tx.type === "credit" ? "Credit" : "Debit")}</p>
                          <p className="text-xs text-muted-foreground">{formatDateTime(tx.created_at)}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className={`text-sm font-semibold ${tx.type === "credit" ? "text-success" : "text-foreground"}`}>
                          {tx.type === "credit" ? "+" : "−"}{formatCents(tx.amount_cents)}
                        </p>
                        <p className="text-xs text-muted-foreground capitalize">{tx.status}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      ))}
    </div>
  );
}
