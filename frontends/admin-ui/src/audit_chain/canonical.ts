const isDate = (value: unknown): value is Date => value instanceof Date;

const assertSerializable = (value: unknown, path: string) => {
  const type = typeof value;
  if (type === "function" || type === "symbol" || type === "bigint") {
    throw new Error(`Unsupported value at ${path}: ${type}`);
  }
};

const canonicalize = (value: unknown, stack: WeakSet<object>, path: string): string => {
  if (value === null) return "null";
  if (value === undefined) return "";
  if (isDate(value)) return JSON.stringify(value.toISOString());

  const type = typeof value;
  if (type === "string" || type === "number" || type === "boolean") {
    return JSON.stringify(value);
  }

  assertSerializable(value, path);

  if (Array.isArray(value)) {
    if (stack.has(value)) {
      throw new Error(`Circular reference detected at ${path}`);
    }
    stack.add(value);
    const items = value
      .filter((item) => item !== undefined)
      .map((item, index) => canonicalize(item, stack, `${path}[${index}]`));
    stack.delete(value);
    return `[${items.join(",")}]`;
  }

  if (typeof value === "object") {
    if (stack.has(value)) {
      throw new Error(`Circular reference detected at ${path}`);
    }
    stack.add(value as object);
    const entries = Object.keys(value as Record<string, unknown>)
      .sort()
      .flatMap((key) => {
        const entryValue = (value as Record<string, unknown>)[key];
        if (entryValue === undefined) return [];
        return [`${JSON.stringify(key)}:${canonicalize(entryValue, stack, `${path}.${key}`)}`];
      });
    stack.delete(value as object);
    return `{${entries.join(",")}}`;
  }

  return "null";
};

export const canonicalStringify = (value: unknown): string => {
  const stack = new WeakSet<object>();
  return canonicalize(value, stack, "$");
};
