export const SERVICE_ICONS: Record<string, string> = {
  EC2: "🖥",
  EBS: "💾",
  EIP: "🌐",
  RDS: "🗄",
  S3: "🪣",
  Lambda: "⚙",
  "Load Balancer": "⚖",
  CloudWatch: "📊",
  "Cost Explorer": "💰",
  Networking: "🌐",
  apigateway: "🔗",
  AWS: "☁",
};

export function serviceIcon(service: string | null | undefined): string {
  if (!service) return "☁";
  return SERVICE_ICONS[service] ?? SERVICE_ICONS[service.split(" ")[0]] ?? "☁";
}

export function truncateResourceId(id: string, max = 12): string {
  if (id.length <= max) return id;
  return id.slice(0, max) + "…";
}
