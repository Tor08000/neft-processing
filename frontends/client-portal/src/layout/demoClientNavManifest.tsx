import type { ClientNavItem } from "./ClientLayout";
import {
  ClipboardCheck,
  FileSpreadsheet,
  FileText,
  LayoutDashboard,
  LineChart,
  MessageCircle,
  Package,
  Settings,
  ShoppingCart,
  Workflow,
} from "../components/icons";

export const demoClientNavManifest: ClientNavItem[] = [
  { to: "/dashboard", label: "Обзор", shortLabel: "Обзор", icon: <LayoutDashboard size={18} />, audience: "all" },
  { to: "/documents", label: "Документы", shortLabel: "Док", icon: <FileText size={18} />, audience: "all" },
  { to: "/analytics", label: "Аналитика", shortLabel: "Аналитика", icon: <LineChart size={18} />, audience: "all" },
  { to: "/cards", label: "Карты", shortLabel: "Карты", icon: <ShoppingCart size={18} />, audience: "all" },
  {
    to: "/spend/transactions",
    label: "Расходы",
    shortLabel: "Расходы",
    icon: <FileSpreadsheet size={18} />,
    audience: "all",
  },
  { to: "/client/reports", label: "Отчёты", shortLabel: "Отчёты", icon: <FileSpreadsheet size={18} />, audience: "all" },
  { to: "/limits/templates", label: "Лимиты", shortLabel: "Лимиты", icon: <ClipboardCheck size={18} />, audience: "all" },
  { to: "/fleet/employees", label: "Пользователи", shortLabel: "Люди", icon: <Workflow size={18} />, audience: "all" },
  { to: "/fleet/groups", label: "Автопарк", shortLabel: "Автопарк", icon: <Package size={18} />, audience: "all" },
  { to: "/logistics/fleet", label: "Логистика · Автопарк", shortLabel: "Логистика", icon: <Package size={18} />, audience: "all" },
  { to: "/stations-map", label: "Карта станций", shortLabel: "Станции", icon: <Package size={18} />, audience: "all" },
  { to: "/settings", label: "Настройки", shortLabel: "Настройки", icon: <Settings size={18} />, audience: "all" },
  { to: "/client/support", label: "Поддержка", shortLabel: "Поддержка", icon: <MessageCircle size={18} />, audience: "all" },
];
