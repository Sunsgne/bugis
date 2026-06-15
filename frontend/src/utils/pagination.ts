import { api } from "../api/client";
import type { Paginated } from "../api/types";
import { buildListQuery } from "./table";

/** Backend list endpoints cap page_size at 200. */
export const API_MAX_PAGE_SIZE = 200;

/** Fetch every page of a paginated list API. */
export async function fetchAllPages<T>(
  path: string,
  params: Record<string, string | number | boolean | undefined | null> = {},
): Promise<T[]> {
  const items: T[] = [];
  let page = 1;
  let total = Infinity;

  while (items.length < total) {
    const qs = buildListQuery({ ...params, page, page_size: API_MAX_PAGE_SIZE });
    const { data } = await api.get<Paginated<T>>(`${path}${qs}`);
    items.push(...data.items);
    total = data.total;
    page += 1;
    if (!data.items.length) break;
  }

  return items;
}
