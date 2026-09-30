import { createBrowserRouter } from "react-router-dom";

import { AppShell } from "../../components/layout/AppShell";
import { navItems } from "../navigation";
import { DashboardPage } from "../../pages/DashboardPage";
import { DesignSystemPage } from "../../pages/DesignSystemPage";
import { LeadDetailPage } from "../../pages/LeadDetailPage";
import { LeadFormPage } from "../../pages/LeadFormPage";
import { LeadImportPage } from "../../pages/LeadImportPage";
import { LeadListPage } from "../../pages/LeadListPage";
import { PipelinePage } from "../../pages/PipelinePage";
import { SectionPage } from "../../pages/SectionPage";

const placeholderItems = navItems.filter(
  (item) => item.description && item.to !== "/leads" && item.to !== "/pipeline",
);

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "leads", element: <LeadListPage /> },
      { path: "leads/new", element: <LeadFormPage /> },
      { path: "leads/import", element: <LeadImportPage /> },
      { path: "leads/:leadId/edit", element: <LeadFormPage /> },
      { path: "leads/:leadId", element: <LeadDetailPage /> },
      { path: "pipeline", element: <PipelinePage /> },
      ...placeholderItems.map((item) => ({
        path: item.to.slice(1),
        element: <SectionPage title={item.label} description={item.description ?? ""} />,
      })),
      { path: "design-system", element: <DesignSystemPage /> },
    ],
  },
]);
