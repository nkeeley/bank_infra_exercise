import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Landmark, LogOut, LayoutDashboard, User, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function AdminLayout() {
  const { isAuthenticated, userType, email, logout, loading } = useAuth();

  if (!loading && !isAuthenticated) return <Navigate to="/login" replace />;
  if (!loading && userType !== "admin") return <Navigate to="/dashboard" replace />;

  return (
    <div className="min-h-screen flex bg-background">
      <aside className="hidden md:flex w-64 flex-col gradient-navy">
        <div className="p-6 flex items-center gap-3">
          <Landmark className="h-8 w-8 text-accent" />
          <span className="text-lg font-bold text-primary-foreground tracking-tight">SecureBank</span>
        </div>

        <div className="px-4 mb-4">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-gold/20 text-gold">
            <Shield className="h-3 w-3" /> Admin
          </span>
        </div>

        <nav className="flex-1 px-3 space-y-1">
          <div className="flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium bg-sidebar-accent text-sidebar-accent-foreground">
            <LayoutDashboard className="h-4 w-4" />
            Dashboard
          </div>
        </nav>

        <div className="p-4 border-t border-sidebar-border">
          <div className="flex items-center gap-3 px-2 mb-3">
            <div className="h-8 w-8 rounded-full gradient-gold flex items-center justify-center">
              <User className="h-4 w-4 text-gold-foreground" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-primary-foreground truncate">Admin</p>
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

      <main className="flex-1 md:p-8 p-4 overflow-auto">
        <div className="max-w-7xl mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
