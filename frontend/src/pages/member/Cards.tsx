import { useEffect, useState } from "react";
import { accounts, cards as cardsApi } from "@/lib/api";
import type { AccountResponse, CardResponse } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CreditCard, Wifi } from "lucide-react";
import { maskAccountNumber } from "@/lib/format";

export default function CardsPage() {
  const [accts, setAccts] = useState<AccountResponse[]>([]);
  const [cardMap, setCardMap] = useState<Record<string, CardResponse | null>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const a = await accounts.list();
        setAccts(a);
        const map: Record<string, CardResponse | null> = {};
        await Promise.all(
          a.map(async (acc) => {
            try {
              map[acc.id] = await cardsApi.get(acc.id);
            } catch {
              map[acc.id] = null;
            }
          })
        );
        setCardMap(map);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return <div className="space-y-4">{[1, 2].map(i => <div key={i} className="h-48 rounded-xl bg-muted animate-pulse" />)}</div>;
  }

  const activeCards = accts
    .map(acc => ({ acc, card: cardMap[acc.id] }))
    .filter((x): x is { acc: AccountResponse; card: CardResponse } => x.card !== null && x.card.is_active);

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Cards</h1>
        <p className="text-muted-foreground mt-1">Your active debit cards</p>
      </div>

      {activeCards.length === 0 ? (
        <Card className="shadow-card">
          <CardContent className="p-12 text-center text-muted-foreground">
            <CreditCard className="h-12 w-12 mx-auto mb-4 opacity-30" />
            <p>No active cards found</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          {activeCards.map(({ acc, card }) => (
            <div
              key={card.id}
              className="relative rounded-2xl p-6 gradient-navy text-primary-foreground overflow-hidden shadow-premium aspect-[1.6/1] flex flex-col justify-between"
            >
              {/* Background pattern */}
              <div className="absolute inset-0 opacity-10">
                <div className="absolute top-4 right-4 h-32 w-32 rounded-full border-2 border-primary-foreground/20" />
                <div className="absolute top-10 right-10 h-24 w-24 rounded-full border-2 border-primary-foreground/10" />
              </div>

              <div className="flex items-start justify-between relative z-10">
                <div>
                  <p className="text-xs text-primary-foreground/60 uppercase tracking-wider">SecureBank</p>
                  <p className="text-xs text-primary-foreground/50 mt-1 capitalize">{acc.account_type}</p>
                </div>
                <Wifi className="h-6 w-6 text-primary-foreground/40 rotate-90" />
              </div>

              <div className="relative z-10">
                <p className="text-lg font-mono tracking-[0.25em] mb-4">
                  •••• •••• •••• {card.card_number_last_four}
                </p>
                <div className="flex items-end justify-between">
                  <div>
                    <p className="text-[10px] text-primary-foreground/50 uppercase">Account</p>
                    <p className="text-sm font-medium">{maskAccountNumber(acc.account_number)}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-primary-foreground/50 uppercase">Expires</p>
                    <p className="text-sm font-medium">
                      {String(card.expiration_month).padStart(2, "0")}/{String(card.expiration_year).slice(-2)}
                    </p>
                  </div>
                  <CreditCard className="h-8 w-8 text-accent" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
