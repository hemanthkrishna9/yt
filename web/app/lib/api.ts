import { authHeaders, getToken, logout } from "./auth";

const API = "http://localhost:8000/api";

export interface Config {
  languages: Record<string, string>;
  speakers: string[];
  themes: string[];
  moods: string[];
}

export interface JobResponse {
  job_id: string;
  status: string;
  progress: string[];
  output_path: string | null;
  error: string | null;
}

async function handleResponse(res: Response) {
  if (res.status === 401 || res.status === 403) {
    logout();
    window.location.href = "/login";
    throw new Error("Session expired");
  }
  return res;
}

export async function getConfig(): Promise<Config> {
  const res = await fetch(`${API}/config`);
  if (!res.ok) throw new Error("Failed to fetch config");
  return res.json();
}

export async function submitDub(params: {
  url?: string;
  file_path?: string;
  source_lang: string;
  target_lang: string;
  speaker?: string;
  workers?: number;
}): Promise<JobResponse> {
  const res = await handleResponse(
    await fetch(`${API}/dub`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(params),
    })
  );
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to submit dub job");
  }
  return res.json();
}

export async function submitStory(params: {
  text?: string;
  theme?: string;
  keyword?: string;
  target_lang: string;
  speaker?: string;
  mood?: string;
  no_upload?: boolean;
  workers?: number;
}): Promise<JobResponse> {
  const res = await handleResponse(
    await fetch(`${API}/story`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(params),
    })
  );
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to submit story job");
  }
  return res.json();
}

export async function getJob(jobId: string): Promise<JobResponse> {
  const res = await handleResponse(
    await fetch(`${API}/jobs/${jobId}`, {
      headers: authHeaders(),
    })
  );
  if (!res.ok) throw new Error("Failed to fetch job");
  return res.json();
}

export function getDownloadUrl(jobId: string): string {
  const token = getToken();
  return `${API}/jobs/${jobId}/download${token ? `?token=${token}` : ""}`;
}

export function getEventsUrl(jobId: string): string {
  const token = getToken();
  return `${API}/jobs/${jobId}/events${token ? `?token=${token}` : ""}`;
}
