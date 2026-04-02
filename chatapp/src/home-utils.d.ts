export type HomeSearchKind = 'chat' | 'topic' | 'session';

export interface HomeDebateSessionStats {
  total: number;
  joinable: number;
  live: number;
  upcoming: number;
  ended: number;
}

export interface HomeSearchItem {
  key: string;
  kind: HomeSearchKind;
  title: string;
  subtitle: string;
  path: string;
  query: Record<string, string> | null;
  keywords: string[];
}

export interface HomeSearchChannelLike {
  id?: number | string | null;
  type?: string | null;
  name?: string | null;
}

export interface HomeSearchTopicLike {
  id?: number | string | null;
  title?: string | null;
  category?: string | null;
}

export interface HomeSearchSessionLike {
  id?: number | string | null;
  topicId?: number | string | null;
  status?: string | null;
  joinable?: boolean;
}

export interface BuildHomeSearchIndexInput {
  channels?: HomeSearchChannelLike[];
  topics?: HomeSearchTopicLike[];
  sessions?: HomeSearchSessionLike[];
  topicTitleById?: (topicId: unknown) => string;
}

export interface FilterHomeSearchItemsOptions {
  limit?: number;
}

export function normalizeHomeSearchQuery(raw: unknown): string;
export function summarizeDebateSessionStats(sessions?: HomeSearchSessionLike[]): HomeDebateSessionStats;
export function buildHomeSearchIndex(input?: BuildHomeSearchIndexInput): HomeSearchItem[];
export function filterHomeSearchItems(
  items?: HomeSearchItem[],
  query?: string,
  options?: FilterHomeSearchItemsOptions,
): HomeSearchItem[];
