import axios from "axios";

import { env } from "../lib/env";

export const api = axios.create({
  baseURL: env.apiBaseUrl,
  headers: {
    Accept: "application/json",
  },
});
