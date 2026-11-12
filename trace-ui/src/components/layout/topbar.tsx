import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DemoPill } from "@/components/demo-pill";
import { GuidedDemo } from "@/components/guided-demo";

export function Topbar() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

  const onSearch = (event: FormEvent) => {
    event.preventDefault();
    const q = query.trim();
    if (q) navigate(`/filings?search=${encodeURIComponent(q)}`);
  };

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/90 px-6 backdrop-blur">
      <form onSubmit={onSearch} className="relative w-full max-w-sm" role="search">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" aria-hidden="true" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search company, ticker, CIK"
          className="pl-8"
          aria-label="Search companies, tickers, or CIKs"
        />
      </form>
      <div className="ml-auto flex items-center gap-2">
        <GuidedDemo />
        <Button size="sm" onClick={() => navigate("/new")}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          New audit
        </Button>
        <DemoPill />
      </div>
    </header>
  );
}
