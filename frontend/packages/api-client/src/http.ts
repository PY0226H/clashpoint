import axios, { AxiosError } from "axios";
import { getRuntimeConfig } from "@echoisle/config";

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

const runtime = getRuntimeConfig();

export const http = axios.create({
  baseURL: runtime.server.chat,
  withCredentials: true,
  timeout: 20000
});

http.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

export type ApiErrorPayload = {
  error?: string;
  code?: string;
  message?: string;
};

export function toApiError(error: unknown): string {
  const known = error as AxiosError<ApiErrorPayload>;
  return (
    known.response?.data?.error ||
    known.response?.data?.message ||
    known.response?.data?.code ||
    known.message ||
    "request failed"
  );
}
