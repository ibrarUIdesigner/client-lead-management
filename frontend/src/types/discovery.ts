export type CategoryOption = {
  value: string;
  label: string;
};

export type DiscoverySearch = {
  id: string;
  category: string;
  city: string;
  country: string;
  is_active: boolean;
  use_openstreetmap: boolean;
  use_google: boolean;
  use_yelp: boolean;
  use_yell: boolean;
  use_businesslist: boolean;
  use_epages: boolean;
  use_apollo: boolean;
  use_serpapi: boolean;
  use_scrapingbee: boolean;
  created_at: string;
  last_status: string | null;
  last_started_at: string | null;
  last_finished_at: string | null;
  last_found_count: number | null;
  last_created_count: number | null;
  last_updated_count: number | null;
  last_skipped_count: number | null;
  last_message: string | null;
};

export type DiscoveryStatus = {
  running: boolean;
  google_configured: boolean;
  yelp_configured: boolean;
  apollo_configured: boolean;
  serpapi_configured: boolean;
  scrapingbee_configured: boolean;
  schedule: string;
  next_run_at: string | null;
  categories: CategoryOption[];
  searches: DiscoverySearch[];
  latest_message: string | null;
};

export type DiscoverySearchWrite = {
  category: string;
  city: string;
  country: string;
  use_openstreetmap: boolean;
  use_google: boolean;
  use_yelp: boolean;
  use_yell: boolean;
  use_businesslist: boolean;
  use_epages: boolean;
  use_apollo: boolean;
  use_serpapi: boolean;
  use_scrapingbee: boolean;
};

export type DiscoveryBatchWrite = {
  categories: string[];
  city?: string;
  country?: string;
  countries?: string[];
  use_openstreetmap: boolean;
  use_google: boolean;
  use_yelp: boolean;
  use_yell: boolean;
  use_businesslist: boolean;
  use_epages: boolean;
  use_apollo: boolean;
  use_serpapi: boolean;
  use_scrapingbee: boolean;
  run_now?: boolean;
};

export type DiscoveryBatchResult = {
  created_count: number;
  searches: DiscoverySearch[];
  started_run: boolean;
};
