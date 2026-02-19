import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Landmark, LogOut, LayoutDashboard, CreditCard, FileText, ArrowLeftRight, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

const memberLinks = [
  { to: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { to: "/dashboard/cards", label: "Cards", icon: CreditCard },
  { to: "/dashboard/statements", label: "Statements", icon: FileText },
  { to: "/dashboard/transfers", label: "Transfers", icon: ArrowLeftRight },
];

export default function MemberLayout() {
  const { isAuthenticated, userType, profile, email, logout, loading } = useAuth();

  if (!loading && !isAuthenticated) return <Navigate to="/login" replace />;
  if (!loading && userType === "admin") return <Navigate to="/admin" replace />;

  return (
    <div className="min-h-screen flex bg-background">
      {/* Sidebar */}
      <aside className="hidden md:flex w-64 flex-col gradient-navy">
        <div className="p-6 flex items-center gap-3">
          <Landmark className="h-8 w-8 text-accent" />
          <span className="text-lg font-bold text-primary-foreground tracking-tight">SecureBank</span>
        </div>

        <nav className="flex-1 px-3 space-y-1">
          {memberLinks.map(link => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === "/dashboard"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent/50"
                )
              }
            >
              <link.icon className="h-4 w-4" />
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-sidebar-border">
          <div className="flex items-center gap-3 px-2 mb-3">
            <div className="h-8 w-8 rounded-full gradient-accent flex items-center justify-center">
              <User className="h-4 w-4 text-accent-foreground" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-primary-foreground truncate">
                {profile ? `${profile.first_name} ${profile.last_name}` : email}
              </p>
              <p className="text-xs text-sidebar-foreground/50 truncate">{email}</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={logout}
            className="w-full justify-start text-sidebar-foreground/70 hover:text-primary-foreground hover:bg-sidebar-accent/50"
          >
            <LogOut className="h-4 w-4 mr-2" /> Sign Out
          </Button>
        </div>
      </aside>

      {/* Mobile header */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-50 gradient-navy px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Landmark className="h-6 w-6 text-accent" />
          <span className="font-bold text-primary-foreground">SecureBank</span>
        </div>
        <Button variant="ghost" size="sm" onClick={logout} className="text-primary-foreground/70">
          <LogOut className="h-4 w-4" />
        </Button>
      </div>

      {/* Mobile bottom nav */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-card border-t border-border flex">
        {memberLinks.map(link => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.to === "/dashboard"}
            className={({ isActive }) =>
              cn(
                "flex-1 flex flex-col items-center py-2 text-xs transition-colors",
                isActive ? "text-accent" : "text-muted-foreground"
              )
            }
          >
            <link.icon className="h-5 w-5 mb-0.5" />
            {link.label}
          </NavLink>
        ))}
      </div>

      {/* Main content */}
      <main className="flex-1 md:p-8 p-4 pt-16 pb-20 md:pt-8 md:pb-8 overflow-auto">
        <div className="max-w-6xl mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
