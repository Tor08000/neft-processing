export type OverviewVehicle = {
  id: string;
  plate: string;
  model: string;
  status: "active" | "service";
  mileage?: number;
  fuelUsage?: number;
};

export type OverviewOperation = {
  id: string;
  date: string;
  type: string;
  amount: number;
  status: "paid" | "pending" | "failed";
};

export type OverviewData = {
  balance: number;
  limit: number;
  fuelSpent: number;
  fleetStats?: {
    vehicles: number;
    activeCards: number;
    fuelLimit: number;
    overdue: number;
  };
  vehicles: OverviewVehicle[];
  operations: OverviewOperation[];
};

export const demoOverviewData: Record<"personal" | "fleet", OverviewData> = {
  personal: {
    balance: 2_450_000,
    limit: 3_000_000,
    fuelSpent: 820,
    vehicles: [
      {
        id: "car-1",
        plate: "А123ВС 77",
        model: "BMW X5 · 2023",
        status: "active",
        mileage: 18_450,
        fuelUsage: 8.7,
      },
    ],
    operations: [
      {
        id: "op-1",
        date: "12 сен, 09:10",
        type: "Заправка · Лукойл",
        amount: -4_250,
        status: "paid",
      },
      {
        id: "op-2",
        date: "10 сен, 17:40",
        type: "Оплата · Счёт №8421",
        amount: 150_000,
        status: "paid",
      },
      {
        id: "op-3",
        date: "07 сен, 12:05",
        type: "Списание · Телематика",
        amount: -8_400,
        status: "pending",
      },
    ],
  },
  fleet: {
    balance: 12_450_000,
    limit: 18_000_000,
    fuelSpent: 4_120,
    fleetStats: {
      vehicles: 54,
      activeCards: 48,
      fuelLimit: 6_200_000,
      overdue: 125_000,
    },
    vehicles: [
      {
        id: "fleet-1",
        plate: "М245НЕ 199",
        model: "Mercedes Sprinter",
        status: "active",
        mileage: 98_200,
        fuelUsage: 12.4,
      },
      {
        id: "fleet-2",
        plate: "С381АК 178",
        model: "Toyota Camry",
        status: "service",
        mileage: 74_210,
      },
      {
        id: "fleet-3",
        plate: "Т902ОР 77",
        model: "Volkswagen Crafter",
        status: "active",
        mileage: 65_120,
        fuelUsage: 11.8,
      },
    ],
    operations: [
      {
        id: "f-op-1",
        date: "Сегодня, 08:15",
        type: "Заправка · Роснефть",
        amount: -18_250,
        status: "paid",
      },
      {
        id: "f-op-2",
        date: "Вчера, 19:30",
        type: "Счёт · Автопарк",
        amount: -56_000,
        status: "pending",
      },
      {
        id: "f-op-3",
        date: "08 сен, 11:20",
        type: "Оплата · Счёт №8412",
        amount: 260_000,
        status: "paid",
      },
    ],
  },
};
