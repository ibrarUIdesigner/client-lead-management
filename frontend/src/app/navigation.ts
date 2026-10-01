import {
  BarChart3,
  Bot,
  CalendarClock,
  FileText,
  Images,
  LayoutDashboard,
  Mail,
  MapPinned,
  Settings,
  SquareKanban,
  Users,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
  description?: string;
};

export const navItems: NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  {
    to: "/leads",
    label: "Leads",
    icon: Users,
    description: "Businesses you want to contact will show up here.",
  },
  {
    to: "/discover",
    label: "Find leads",
    icon: MapPinned,
    description: "Daily searches for businesses you can pitch.",
  },
  {
    to: "/apify",
    label: "Apify",
    icon: Bot,
    description: "Actors you connect from Apify will show up here.",
  },
  {
    to: "/pipeline",
    label: "Pipeline",
    icon: SquareKanban,
    description: "Prospects will move through stages here.",
  },
  {
    to: "/design-md",
    label: "Design MD",
    icon: FileText,
    description: "Markdown design guides for homepage mockups.",
  },
  {
    to: "/mockups",
    label: "Mockups",
    icon: Images,
    description: "Homepage concepts for a prospect will show up here.",
  },
  {
    to: "/outreach",
    label: "Outreach",
    icon: Mail,
    description: "Drafts you can edit before sending will show up here.",
  },
  {
    to: "/follow-ups",
    label: "Follow-ups",
    icon: CalendarClock,
    description: "Today, overdue, and upcoming follow-ups will show up here.",
  },
  {
    to: "/analytics",
    label: "Analytics",
    icon: BarChart3,
    description: "Acquisition activity will show up here after you start working leads.",
  },
  {
    to: "/settings",
    label: "Settings",
    icon: Settings,
    description: "Workspace preferences will show up here.",
  },
];
