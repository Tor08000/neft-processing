export const logisticsInspectionCopy = {
  firstUse: {
    title: "Inspection is not open yet",
    description:
      "Enter an order ID to open the canonical logistics inspection surface without a fake summary layer.",
    hint: "After an order is selected, the page shows grounded route, ETA, tracking, and explain artifacts.",
  },
  loadingLabel: "Loading inspection",
  unavailable: {
    title: "Inspection is unavailable",
    actionLabel: "Retry",
  },
  routesEmpty: {
    title: "No routes found yet",
    description: "The route owner has not returned any route versions for this order yet.",
  },
  etaEmpty: {
    title: "ETA snapshot is missing",
    description: "A local ETA snapshot has not been recorded yet.",
  },
  stopsEmpty: {
    title: "No route stops found",
    description: "The active route has not returned a stop list for this order yet.",
  },
  navigatorEmpty: {
    title: "Navigator snapshot is missing",
    description: "The navigator snapshot has not been stored yet. No synthetic fallback is shown here.",
  },
  trackingEmpty: {
    title: "Tracking events are missing",
    description: "The tracking tail is empty right now.",
  },
  explainEmpty: {
    title: "Explain artifacts are missing",
    description: "Navigator explain payloads have not been stored yet.",
  },
} as const;
