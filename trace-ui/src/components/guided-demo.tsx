import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, ChevronRight, Circle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useStartAudit, useVerifyChain } from "@/hooks/use-trace";
const steps = [
  { id: "run", label: "Run an audit" },
  { id: "inspect", label: "Inspect a flagged item" },
  { id: "decide", label: "Make a decision" },
  { id: "accuracy", label: "View accuracy" },
  { id: "verify", label: "Verify audit chain" },
];

export function GuidedDemo() {
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState<Record<string, boolean>>({});
  const navigate = useNavigate();
  const startAudit = useStartAudit();
  const verifyChain = useVerifyChain();

  const runDemoAudit = async () => {
    const status = await startAudit.mutateAsync({ cik: "0000320193", confidence_threshold: 0.85, yoy_threshold_pct: 0.3, demo_only: true });
    setOpen(false);
    navigate(`/review?thread=${status.thread_id}`);
  };

  const handleVerify = async () => {
    const result = await verifyChain.refetch();
    if (result.data?.verified) setDone((prev) => ({ ...prev, verify: true }));
  };

  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        Guided demo
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Guided demo</DialogTitle>
            <DialogDescription>Walk through the full TRACE workflow in under two minutes.</DialogDescription>
          </DialogHeader>
          <ol className="space-y-2">
            {steps.map((s, index) => {
              const state = done[s.id] ? "done" : "todo";
              return (
                <li key={s.id} className="flex items-center gap-3 rounded-lg border p-3">
                  {state === "done" ? <Check className="h-4 w-4 text-success" aria-hidden="true" /> : <Circle className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}
                  <span className="flex-1 text-sm font-medium">{index + 1}. {s.label}</span>
                  {state === "todo" && <ChevronRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}
                </li>
              );
            })}
          </ol>
          <DialogFooter className="flex-col items-stretch gap-2 sm:flex-col">
            <Button onClick={runDemoAudit} disabled={startAudit.isPending}>
              {startAudit.isPending ? "Running…" : "Run demo audit"}
            </Button>
            <Button variant="outline" onClick={handleVerify} disabled={verifyChain.isPending}>
              {verifyChain.isPending ? "Verifying…" : "Verify audit chain"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
