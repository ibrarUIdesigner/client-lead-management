import { createBrowserRouter } from "react-router-dom";

import { AppShell } from "../../components/layout/AppShell";
import { AnalyticsPage } from "../../pages/AnalyticsPage";
import { DashboardPage } from "../../pages/DashboardPage";
import { DiscoverPage } from "../../pages/DiscoverPage";
import { DesignSystemPage } from "../../pages/DesignSystemPage";
import { FollowUpsPage } from "../../pages/FollowUpsPage";
import { LeadDetailPage } from "../../pages/LeadDetailPage";
import { LeadFormPage } from "../../pages/LeadFormPage";
import { LeadImportPage } from "../../pages/LeadImportPage";
import { LeadListPage } from "../../pages/LeadListPage";
import { MockupsPage } from "../../pages/MockupsPage";
import { OutreachPage } from "../../pages/OutreachPage";
import { PipelinePage } from "../../pages/PipelinePage";
import { SettingsPage } from "../../pages/SettingsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "leads", element: <LeadListPage /> },
      { path: "discover", element: <DiscoverPage /> },
      { path: "leads/new", element: <LeadFormPage /> },
      { path: "leads/import", element: <LeadImportPage /> },
      { path: "leads/:leadId/edit", element: <LeadFormPage /> },
      { path: "leads/:leadId", element: <LeadDetailPage /> },
      { path: "pipeline", element: <PipelinePage /> },
      { path: "mockups", element: <MockupsPage /> },
      { path: "outreach", element: <OutreachPage /> },
      { path: "follow-ups", element: <FollowUpsPage /> },
      { path: "analytics", element: <AnalyticsPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "design-system", element: <DesignSystemPage /> },
    ],
  },
]);
