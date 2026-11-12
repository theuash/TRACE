import { useState } from "react";
import { ShieldAlert, Trash2 } from "lucide-react";
import { useDataMode, useHealth, useResetDemo, useSetFailureMode, useTamperWithLastRow } from "@/hooks/use-trace";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useTheme } from "@/components/theme-provider";
import { toast } from "sonner";

export function SettingsPage() {
  const { mode } = useDataMode();
  const { data: health, refetch: refetchHealth } = useHealth();
  const resetDemo = useResetDemo();
  const setFailureMode = useSetFailureMode();
  const tamper = useTamperWithLastRow();
  const { theme, toggleTheme } = useTheme();
  const [confirmReset, setConfirmReset] = useState(false);

  const connectionOk = health?.status === "ok" || health?.status === "healthy";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Settings</h2>
        <p className="text-sm text-muted-foreground">Data source, policy defaults, and demo controls.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Data source</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm">Current mode</span>
            <Badge variant={mode === "mock" ? "warning" : "success"}>{mode === "mock" ? "Demo data" : "Live"}</Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm">Connection status</span>
            <span className="text-sm font-medium text-success">{connectionOk ? "Healthy" : "Unreachable"}</span>
          </div>
          {mode === "http" ? (
            <div className="text-sm text-muted-foreground">Base URL: {import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000"}</div>
          ) : null}
          <Button variant="outline" size="sm" onClick={() => void refetchHealth()}>
            Test connection
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Policy defaults</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm">Default confidence threshold</span>
            <span className="rounded-full bg-accent px-2 py-0.5 text-sm font-semibold">85%</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm">Default YoY tolerance</span>
            <span className="rounded-full bg-accent px-2 py-0.5 text-sm font-semibold">30%</span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Demo controls</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">Simulate failure</div>
              <div className="text-xs text-muted-foreground">Force new audits into the FAILED state.</div>
            </div>
            <Switch
              checked={false}
              onCheckedChange={(v) => {
                void setFailureMode.mutateAsync(v).then(() => toast.success(v ? "Failure simulation enabled" : "Failure simulation disabled"));
              }}
              aria-label="Simulate failure"
            />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">Tamper with last audit row</div>
              <div className="text-xs text-muted-foreground">Development only - breaks the hash chain to demo the tamper state.</div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                void tamper.mutateAsync().then((r) => toast.error(r.verified ? "Chain unexpectedly intact" : `Chain broken at ${r.broken_row_id}`))
              }
            >
              <ShieldAlert className="h-4 w-4" aria-hidden="true" /> Tamper
            </Button>
          </div>
          {tamper.data ? (
            <div className={`rounded-xl border p-3 text-sm ${tamper.data.verified ? "border-success/40 bg-success/10 text-success" : "border-danger/40 bg-danger/10 text-danger"}`}>
              {tamper.data.verified ? "Chain intact" : `Chain broken at ${tamper.data.broken_row_id}`}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-between">
          <span className="text-sm">Theme</span>
          <Button variant="outline" size="sm" onClick={toggleTheme}>
            Switch to {theme === "dark" ? "light" : "dark"} theme
          </Button>
        </CardContent>
      </Card>

      <Card className="border-danger/40">
        <CardHeader>
          <CardTitle className="text-danger">Danger zone</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">Reset demo data</div>
              <div className="text-xs text-muted-foreground">Clears all mock threads and audit logs.</div>
            </div>
            <Button variant="destructive" size="sm" onClick={() => setConfirmReset(true)}>
              <Trash2 className="h-4 w-4" aria-hidden="true" /> Reset
            </Button>
          </div>
        </CardContent>
      </Card>

      <Dialog open={confirmReset} onOpenChange={setConfirmReset}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset demo data?</DialogTitle>
            <DialogDescription>This clears all local demo threads and audit log rows. This cannot be undone.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmReset(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                void resetDemo.mutateAsync().then(() => {
                  setConfirmReset(false);
                  toast.success("Demo data reset");
                });
              }}
            >
              Reset demo data
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
