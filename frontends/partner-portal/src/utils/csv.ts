export interface CsvParseError {
  row: number;
  message: string;
}

export interface CsvParseResult {
  headers: string[];
  rows: Record<string, string>[];
  errors: CsvParseError[];
}

export interface CsvParseOptions {
  requiredHeaders?: string[];
  requireAnyOf?: string[];
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

const validateHeaders = (headers: string[], options?: CsvParseOptions): CsvParseError[] => {
  const errors: CsvParseError[] = [];
  const requiredHeaders = options?.requiredHeaders ?? [];
  const requireAnyOf = options?.requireAnyOf ?? [];

  if (requireAnyOf.length && !requireAnyOf.some((header) => headers.includes(header))) {
    errors.push({ row: 0, message: `Добавьте колонку ${requireAnyOf.join(" или ")}` });
  }

  requiredHeaders.forEach((field) => {
    if (!headers.includes(field)) {
      errors.push({ row: 0, message: `Добавьте колонку ${field}` });
    }
  });

  return errors;
};

const parseCsvInternal = (text: string, options?: CsvParseOptions): CsvParseResult => {
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

  return { headers, rows, errors: [...errors, ...validateHeaders(headers, options)] };
};

export const parseCsv = (text: string): CsvParseResult =>
  parseCsvInternal(text, {
    requiredHeaders: ["product_code", "price", "currency", "valid_from"],
    requireAnyOf: ["station_code", "station_id"],
  });

export const parseCatalogCsv = (text: string): CsvParseResult =>
  parseCsvInternal(text, {
    requiredHeaders: ["title", "kind", "base_uom"],
  });
