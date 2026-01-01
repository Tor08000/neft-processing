export const formatNumberParts = (value: number, fractionDigits = 2) => {
  const hasFraction = !Number.isInteger(value);
  const digits = hasFraction ? fractionDigits : 0;
  const fixed = value.toFixed(digits);
  const [intRaw, fraction] = fixed.split(".");
  const intPart = intRaw.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return {
    int: intPart,
    fraction: fraction && digits > 0 ? fraction : null,
  };
};
