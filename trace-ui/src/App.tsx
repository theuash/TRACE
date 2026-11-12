import { Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/app-shell";
import { OverviewPage } from "./pages/overview";
import { NewAuditPage } from "./pages/new-audit";
import { ReviewQueuePage } from "./pages/review-queue";
import { FilingsPage } from "./pages/filings";
import { FilingDetailPage } from "./pages/filing-detail";
import { AccuracyPage } from "./pages/accuracy";
import { AuditLogPage } from "./pages/audit-log";
import { SettingsPage } from "./pages/settings";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<OverviewPage />} />
        <Route path="new" element={<NewAuditPage />} />
        <Route path="review" element={<ReviewQueuePage />} />
        <Route path="filings" element={<FilingsPage />} />
        <Route path="filings/:id" element={<FilingDetailPage />} />
        <Route path="accuracy" element={<AccuracyPage />} />
        <Route path="audit" element={<AuditLogPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="overview" element={<OverviewPage />} />
      </Route>
    </Routes>
  );
}
