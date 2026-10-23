import {
  Bell,
  Bot,
  CalendarClock,
  Images,
  LayoutDashboard,
  Mail,
  MapPinned,
  Palette,
  Settings,
  SquareKanban,
  TrendingUp,
  Users,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
  description?: string;
  badge?: string;
};

export type NavGroup = {
  title: string;
  items: NavItem[];
};

export const navigationGroups: NavGroup[] = [
  {
    title: "MAIN",
    items: [
      {
        to: "/",
        label: "Dashboard",
        icon: LayoutDashboard,
        end: true,
        description: "Daily client acquisition command center.",
      },
      {
        to: "/leads",
        label: "Leads",
        icon: Users,
        description: "Businesses you want to qualify and contact.",
      },
      {
        to: "/discover",
        label: "Find Leads",
        icon: MapPinned,
        description: "Search markets and directories for businesses.",
      },
    ],
  },
  {
    title: "SALES",
    items: [
      {
        to: "/pipeline",
        label: "Pipeline",
        icon: SquareKanban,
        description: "Move prospects through acquisition stages.",
      },
      {
        to: "/outreach",
        label: "Outreach",
        icon: Mail,
        description: "Personalized pitch drafts and Gmail messaging.",
      },
      {
        to: "/follow-ups",
        label: "Follow-ups",
        icon: CalendarClock,
        description: "Today, overdue, and scheduled prospect check-ins.",
      },
      {
        to: "/analytics",
        label: "Analytics",
        icon: TrendingUp,
        description: "Conversion metrics and acquisition analytics.",
      },
    ],
  },
  {
    title: "CREATIVE",
    items: [
      {
        to: "/mockups",
        label: "Mockups",
        icon: Images,
        description: "Homepage concepts generated for prospects.",
      },
      {
        to: "/design-md",
        label: "Design Guides",
        icon: Palette,
        description: "Visual design systems and brand style specs.",
      },
    ],
  },
  {
    title: "AUTOMATION",
    items: [
      {
        to: "/apify",
        label: "Apify",
        icon: Bot,
        description: "Actor automations and scraper connectors.",
      },
      {
        to: "/notifications",
        label: "Notifications",
        icon: Bell,
        description: "Inbox alerts, reply events, and push notifications.",
      },
    ],
  },
];

export const utilityNavItems: NavItem[] = [
  {
    to: "/settings",
    label: "Settings",
    icon: Settings,
    description: "Workspace preferences and integrations.",
  },
];

// Flat export for backwards compatibility
export const navItems: NavItem[] = [
  ...navigationGroups.flatMap((group) => group.items),
  ...utilityNavItems,
];
