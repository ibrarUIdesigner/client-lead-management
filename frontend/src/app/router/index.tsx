import { createBrowserRouter } from "react-router-dom";

import { AppShell } from "../../components/layout/AppShell";
import { navItems } from "../navigation";
import { DashboardPage } from "../../pages/DashboardPage";
import { DesignSystemPage } from "../../pages/DesignSystemPage";
import { SectionPage } from "../../pages/SectionPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <DashboardPage /> },
      ...navItems
        .filter((item) => item.description)
        .map((item) => ({
          path: item.to.slice(1),
          element: <SectionPage title={item.label} description={item.description ?? ""} />,
        })),
      { path: "design-system", element: <DesignSystemPage /> },
    ],
  },
]);
