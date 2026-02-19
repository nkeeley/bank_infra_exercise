import { useEffect, useState, useCallback } from "react";
import { admin } from "@/lib/api";
import type { AccountResponse, TransactionResponse } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCents, formatDateTime, maskAccountNumber } from "@/lib/format";
import { ArrowDownLeft, ArrowUpRight, Users, Wallet, Activity, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function AdminDashboard() {
  const [accts, setAccts] = useState<AccountResponse[]>([]);
  const [txns, setTxns] = useState<TransactionResponse[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [a, t] = await Promise.all([
        admin.accounts.list(),
        admin.transactions.list({ limit: 50 }),
      ]);
      setAccts(a);
      setTxns(t);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Auto-refresh every 30s
  useEffect(() => {
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const totalBalance = accts.reduce((s, a) => s + a.cached_balance_cents, 0);
  const uniqueHolders = new Set(accts.map(a => a.account_holder_id)).size;

  if (loading) {
    return <div className="space-y-4">{[1, 2, 3].map(i => <div key={i} className="h-32 rounded-xl bg-muted animate-pulse" />)}</div>;
  }

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Admin Dashboard</h1>
          <p className="text-muted-foreground mt-1">Organization-wide overview</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData} className="gap-2">
          <RefreshCw className="h-4 w-4" /> Refresh
        </Button>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="shadow-card">
          <CardContent className="p-6 flex items-center gap-4">
            <div className="h-12 w-12 rounded-xl gradient-accent flex items-center justify-center">
              <Wallet className="h-6 w-6 text-accent-foreground" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Total Deposits</p>
              <p className="text-2xl font-bold">{formatCents(totalBalance)}</p>
            </div>
          </CardContent>
        </Card>
        <Card className="shadow-card">
          <CardContent className="p-6 flex items-center gap-4">
            <div className="h-12 w-12 rounded-xl gradient-navy flex items-center justify-center">
              <Users className="h-6 w-6 text-primary-foreground" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Account Holders</p>
              <p className="text-2xl font-bold">{uniqueHolders}</p>
            </div>
          </CardContent>
        </Card>
        <Card className="shadow-card">
          <CardContent className="p-6 flex items-center gap-4">
            <div className="h-12 w-12 rounded-xl gradient-gold flex items-center justify-center">
              <Activity className="h-6 w-6 text-gold-foreground" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Total Accounts</p>
              <p className="text-2xl font-bold">{accts.length}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* All accounts table */}
      <div>
        <h2 className="text-lg font-semibold mb-3">All Accounts</h2>
        <Card className="shadow-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">Account</th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">Type</th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">Holder ID</th>
                  <th className="px-6 py-3 text-right font-medium text-muted-foreground">Balance</th>
                  <th className="px-6 py-3 text-center font-medium text-muted-foreground">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {accts.map(a => (
                  <tr key={a.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-6 py-3 font-mono text-xs">{maskAccountNumber(a.account_number)}</td>
                    <td className="px-6 py-3 capitalize">{a.account_type}</td>
                    <td className="px-6 py-3 font-mono text-xs text-muted-foreground">{a.account_holder_id.slice(0, 8)}…</td>
                    <td className="px-6 py-3 text-right font-semibold">{formatCents(a.cached_balance_cents)}</td>
                    <td className="px-6 py-3 text-center">
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${a.is_active ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive"}`}>
                        {a.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* Recent transactions */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Recent Transactions</h2>
        <Card className="shadow-card">
          <CardContent className="p-0 divide-y divide-border">
            {txns.length === 0 ? (
              <p className="p-6 text-center text-muted-foreground">No transactions yet</p>
            ) : (
              txns.map(tx => (
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
                  <div className="text-right">
                    <p className={`text-sm font-semibold ${tx.type === "credit" ? "text-success" : ""}`}>
                      {tx.type === "credit" ? "+" : "−"}{formatCents(tx.amount_cents)}
                    </p>
                    <p className="text-xs text-muted-foreground capitalize">{tx.status}</p>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
