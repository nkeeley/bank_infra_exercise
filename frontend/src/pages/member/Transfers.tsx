import { useEffect, useState } from "react";
import { accounts, transfers as transfersApi } from "@/lib/api";
import type { AccountResponse, AccountLookupResponse } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCents, maskAccountNumber } from "@/lib/format";
import { ArrowLeftRight, CheckCircle2, Search } from "lucide-react";

const EXTERNAL_VALUE = "__external__";

export default function TransfersPage() {
  const [accts, setAccts] = useState<AccountResponse[]>([]);
  const [fromId, setFromId] = useState("");
  const [toId, setToId] = useState("");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  // External account lookup state
  const [externalNumber, setExternalNumber] = useState("");
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupResult, setLookupResult] = useState<AccountLookupResponse | null>(null);
  const [lookupError, setLookupError] = useState("");

  useEffect(() => {
    accounts.list().then(setAccts);
  }, []);

  const isExternal = toId === EXTERNAL_VALUE;

  const handleLookup = async () => {
    setLookupError("");
    setLookupResult(null);
    if (!externalNumber.trim()) { setLookupError("Enter an account number"); return; }
    setLookupLoading(true);
    try {
      const result = await accounts.lookup(externalNumber.trim());
      // Don't allow transferring to own accounts via external lookup
      if (accts.some(a => a.id === result.id)) {
        setLookupError("This is your own account — select it from the dropdown instead");
        return;
      }
      setLookupResult(result);
    } catch (err: any) {
      setLookupError(err.message || "Account not found");
    } finally {
      setLookupLoading(false);
    }
  };

  const resolvedToId = isExternal ? lookupResult?.id ?? "" : toId;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess(false);
    const cents = Math.round(parseFloat(amount) * 100);
    if (!cents || cents <= 0) { setError("Enter a valid amount"); return; }
    if (fromId === resolvedToId) { setError("Cannot transfer to the same account"); return; }
    if (!resolvedToId) { setError("Select or look up a destination account"); return; }
    setLoading(true);
    try {
      await transfersApi.create({
        from_account_id: fromId,
        to_account_id: resolvedToId,
        amount_cents: cents,
        description: description || null,
      });
      setSuccess(true);
      setAmount("");
      setDescription("");
      setLookupResult(null);
      setExternalNumber("");
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
        <p className="text-muted-foreground mt-1">Move money between accounts</p>
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
              <Select value={toId} onValueChange={(v) => { setToId(v); setLookupResult(null); setLookupError(""); setExternalNumber(""); }}>
                <SelectTrigger>
                  <SelectValue placeholder="Select destination account" />
                </SelectTrigger>
                <SelectContent>
                  {accts.map(a => (
                    <SelectItem key={a.id} value={a.id}>
                      {a.account_type} — {maskAccountNumber(a.account_number)}
                    </SelectItem>
                  ))}
                  <SelectItem value={EXTERNAL_VALUE}>
                    External account (look up by number)
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            {isExternal && (
              <div className="space-y-2 rounded-lg border p-3 bg-muted/50">
                <Label>Account Number</Label>
                <div className="flex gap-2">
                  <Input
                    placeholder="Enter 10-digit account number"
                    value={externalNumber}
                    onChange={e => { setExternalNumber(e.target.value); setLookupResult(null); setLookupError(""); }}
                  />
                  <Button type="button" variant="outline" size="icon" onClick={handleLookup} disabled={lookupLoading}>
                    <Search className="h-4 w-4" />
                  </Button>
                </div>
                {lookupError && <p className="text-destructive text-xs">{lookupError}</p>}
                {lookupResult && (
                  <p className="text-success text-xs">
                    Found: {lookupResult.account_type} account ({maskAccountNumber(lookupResult.account_number)})
                  </p>
                )}
              </div>
            )}

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

            <Button
              type="submit"
              className="w-full gradient-accent text-accent-foreground"
              disabled={loading || !fromId || !resolvedToId}
            >
              {loading ? "Processing..." : "Transfer Funds"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
