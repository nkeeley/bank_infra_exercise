import { useEffect, useState } from "react";
import { accounts, transfers as transfersApi } from "@/lib/api";
import type { AccountResponse } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCents, maskAccountNumber } from "@/lib/format";
import { ArrowLeftRight, CheckCircle2 } from "lucide-react";

export default function TransfersPage() {
  const [accts, setAccts] = useState<AccountResponse[]>([]);
  const [fromId, setFromId] = useState("");
  const [toId, setToId] = useState("");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    accounts.list().then(setAccts);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess(false);
    const cents = Math.round(parseFloat(amount) * 100);
    if (!cents || cents <= 0) { setError("Enter a valid amount"); return; }
    if (fromId === toId) { setError("Cannot transfer to the same account"); return; }
    setLoading(true);
    try {
      await transfersApi.create({
        from_account_id: fromId,
        to_account_id: toId,
        amount_cents: cents,
        description: description || null,
      });
      setSuccess(true);
      setAmount("");
      setDescription("");
      // Refresh balances
      const refreshed = await accounts.list();
      setAccts(refreshed);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Transfers</h1>
        <p className="text-muted-foreground mt-1">Move money between your accounts</p>
      </div>

      <Card className="shadow-premium max-w-lg">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <ArrowLeftRight className="h-5 w-5 text-accent" />
            New Transfer
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && <div className="bg-destructive/10 text-destructive text-sm rounded-lg p-3">{error}</div>}
            {success && (
              <div className="bg-success/10 text-success text-sm rounded-lg p-3 flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4" /> Transfer completed successfully!
              </div>
            )}

            <div className="space-y-2">
              <Label>From Account</Label>
              <Select value={fromId} onValueChange={setFromId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select source account" />
                </SelectTrigger>
                <SelectContent>
                  {accts.map(a => (
                    <SelectItem key={a.id} value={a.id}>
                      {a.account_type} — {maskAccountNumber(a.account_number)} ({formatCents(a.cached_balance_cents)})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>To Account</Label>
              <Select value={toId} onValueChange={setToId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select destination account" />
                </SelectTrigger>
                <SelectContent>
                  {accts.map(a => (
                    <SelectItem key={a.id} value={a.id}>
                      {a.account_type} — {maskAccountNumber(a.account_number)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Amount ($)</Label>
              <Input
                type="number"
                step="0.01"
                min="0.01"
                placeholder="0.00"
                value={amount}
                onChange={e => setAmount(e.target.value)}
                required
              />
            </div>

            <div className="space-y-2">
              <Label>Description (optional)</Label>
              <Input
                placeholder="e.g. Savings deposit"
                value={description}
                onChange={e => setDescription(e.target.value)}
              />
            </div>

            <Button type="submit" className="w-full gradient-accent text-accent-foreground" disabled={loading || !fromId || !toId}>
              {loading ? "Processing..." : "Transfer Funds"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
