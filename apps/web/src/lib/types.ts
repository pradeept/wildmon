import type { components } from './api-types';

export interface Profile {
  id: string;
  username: string;
  xp: number;
  public_leaderboard: boolean;
}

export interface Discovery {
  id: string;
  status: string;
  created_at: string;
  image_url?: string;
  common_name?: string;
  scientific_name?: string;
  category?: string;
  species_id?: string;
  uncertainty?: string;
  guidance?: string;
  xp_awarded: number;
  session_id?: string;
  ecosystem_attempt_id?: string;
  ecosystem_name?: string;
  ecosystem_slug?: string;
}

export interface Hunt {
  id: string;
  state: string;
  mode: string;
  started_at: string;
  deadline_at: string;
  ended_at?: string;
  duration_minutes: number;
}

export interface Challenge {
  id: string;
  inviter_id: string;
  invitee_id: string;
  requirements: Requirement[];
  duration_minutes: number;
  state: string;
  ready_ids: string[];
  done_ids: string[];
  started_at?: string;
  deadline_at?: string;
  result?: {
    winner_id: string | null;
    scores: number[];
    matches: Record<string, string>[];
  };
}

export type Requirement =
  | { id: string; kind: 'species'; species_id: string; count: 1 }
  | {
      id: string;
      kind: 'taxon_category';
      category: string;
      count: number;
      distinct_species: number;
    }
  | { id: string; kind: 'visual_trait'; trait_code: string; count: number };

export type Pack = Omit<components['schemas']['EcosystemPackView'], 'slots'> & {
  slots: Requirement[];
};
