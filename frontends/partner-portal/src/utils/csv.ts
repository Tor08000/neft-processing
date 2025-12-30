export interface CsvParseError {
  row: number;
  message: string;
}

export interface CsvParseResult {
  headers: string[];
  rows: Record<string, string>[];
  errors: CsvParseError[];
}

const parseCsvLine = (line: string): string[] => {
  const result: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === "\"") {
      if (inQuotes && line[i + 1] === "\"") {
        current += "\"";
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (char === "," && !inQuotes) {
      result.push(current.trim());
      current = "";
      continue;
    }
    current += char;
  }

  result.push(current.trim());
  return result;
};

export const parseCsv = (text: string): CsvParseResult => {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  const errors: CsvParseError[] = [];
  if (lines.length === 0) {
    return { headers: [], rows: [], errors: [{ row: 0, message: "Файл пустой" }] };
  }

  const headers = parseCsvLine(lines[0]).map((header) => header.trim());
  const rows: Record<string, string>[] = [];

  for (let index = 1; index < lines.length; index += 1) {
    const values = parseCsvLine(lines[index]);
    if (values.length !== headers.length) {
      errors.push({
        row: index + 1,
        message: `Количество колонок не совпадает с заголовком (${values.length}/${headers.length})`,
      });
      continue;
    }
    const row: Record<string, string> = {};
    headers.forEach((header, columnIndex) => {
      row[header] = values[columnIndex] ?? "";
    });
    rows.push(row);
  }

  const required = ["product_code", "price", "currency", "valid_from"];
  const hasStation = headers.includes("station_code") || headers.includes("station_id");
  if (!hasStation) {
    errors.push({ row: 0, message: "Добавьте колонку station_code или station_id" });
  }
  required.forEach((field) => {
    if (!headers.includes(field)) {
      errors.push({ row: 0, message: `Добавьте колонку ${field}` });
    }
  });

  return { headers, rows, errors };
};
