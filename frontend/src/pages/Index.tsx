import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Landmark, ArrowRight, Shield, CreditCard, BarChart3 } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Index() {
  const { isAuthenticated, userType } = useAuth();
  const navigate = useNavigate();

  if (isAuthenticated) {
    navigate(userType === "admin" ? "/admin" : "/dashboard", { replace: true });
    return null;
  }

  return (
    <div className="min-h-screen gradient-navy flex flex-col">
      {/* Nav */}
      <header className="flex items-center justify-between px-6 md:px-12 py-4">
        <div className="flex items-center gap-2">
          <Landmark className="h-7 w-7 text-accent" />
          <span className="text-lg font-bold text-primary-foreground tracking-tight">SecureBank</span>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            className="text-primary-foreground/70 hover:text-primary-foreground hover:bg-sidebar-accent/50"
            onClick={() => navigate("/login")}
          >
            Sign In
          </Button>
          <Button className="gradient-accent text-accent-foreground" onClick={() => navigate("/signup")}>
            Get Started <ArrowRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </header>

      {/* Hero */}
      <main className="flex-1 flex items-center justify-center px-6 md:px-12 pb-12">
        <div className="max-w-3xl text-center animate-fade-in">
          <h1 className="text-4xl md:text-6xl font-bold text-primary-foreground tracking-tight leading-tight mb-6">
            Banking built for the
            <span className="block text-accent">modern era</span>
          </h1>
          <p className="text-lg md:text-xl text-primary-foreground/60 mb-10 max-w-xl mx-auto leading-relaxed">
            Manage your accounts, track every transaction, and transfer funds instantly — all in one secure platform.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button size="lg" className="gradient-accent text-accent-foreground text-base px-8" onClick={() => navigate("/signup")}>
              Open an Account <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
            <Button size="lg" variant="outline" className="border-primary-foreground/20 text-primary-foreground hover:bg-sidebar-accent/50 text-base px-8" onClick={() => navigate("/login")}>
              Sign In
            </Button>
          </div>

          {/* Features */}
          <div className="grid md:grid-cols-3 gap-6 mt-16">
            {[
              { icon: Shield, title: "Bank-grade Security", desc: "Enterprise encryption and secure authentication" },
              { icon: CreditCard, title: "Card Management", desc: "Virtual and physical debit cards at your fingertips" },
              { icon: BarChart3, title: "Real-time Analytics", desc: "Track spending and monitor balances instantly" },
            ].map(f => (
              <div key={f.title} className="p-6 rounded-xl bg-sidebar-accent/30 text-left">
                <f.icon className="h-8 w-8 text-accent mb-3" />
                <h3 className="text-sm font-semibold text-primary-foreground mb-1">{f.title}</h3>
                <p className="text-xs text-primary-foreground/50">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
