const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

/** Build API URLs while preserving the relative-path Vite proxy by default. */
export function apiUrl(path: string): string {
  const route = path.startsWith("/") ? path : `/${path}`;
  if (!configuredBaseUrl) return route;

  const base = configuredBaseUrl.replace(/\/+$/, "");
  const baseHasApi = /\/api$/i.test(base);
  const routeHasApi = /^\/api(?:\/|$)/i.test(route);

  if (baseHasApi && routeHasApi) {
    return `${base}${route.slice(4)}`;
  }

  return `${base}${route}`;
}
