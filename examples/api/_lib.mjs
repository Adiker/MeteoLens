export const BASE_URL = (process.env.METEOLENS_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

export function optionValue(args, name, fallback = undefined) {
  const index = args.indexOf(name);
  if (index === -1 || index + 1 >= args.length) {
    return fallback;
  }
  return args[index + 1];
}

export function query(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const value = search.toString();
  return value ? `?${value}` : "";
}

export async function getJson(path) {
  const response = await fetch(`${BASE_URL}${path}`);
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail?.error?.message ?? body.error?.message ?? detail;
    } catch {
      // Keep the status fallback.
    }
    throw new Error(detail);
  }
  return response.json();
}
