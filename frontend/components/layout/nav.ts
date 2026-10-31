import {
  LayoutDashboard, MessageSquareText, Mic, Package, BookOpen, Globe, HelpCircle, FileText, Users, BarChart3, Settings,
} from "lucide-react";

export const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, role: "team_member" },
  { href: "/assistant", label: "AI Assistant", icon: MessageSquareText, role: "team_member" },
  { href: "/voice", label: "Voice Assistant", icon: Mic, role: "team_member" },
  { href: "/products", label: "Product Database", icon: Package, role: "team_member" },
  { href: "/knowledge", label: "Knowledge Base", icon: BookOpen, role: "team_member" },
  { href: "/research", label: "Online Research", icon: Globe, role: "admin" },
  { href: "/faqs", label: "FAQ Management", icon: HelpCircle, role: "team_member" },
  { href: "/documents", label: "Document Management", icon: FileText, role: "team_member" },
  { href: "/team", label: "Team Management", icon: Users, role: "admin" },
  { href: "/analytics", label: "Analytics", icon: BarChart3, role: "admin" },
  { href: "/settings", label: "Settings", icon: Settings, role: "team_member" },
] as const;
