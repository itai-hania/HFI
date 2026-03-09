"use client";

import { useCallback } from "react";

const TOKEN_KEY = "hfi_token";

export function useAuth() {
  const getToken = useCallback(() => {
    if (typeof window === "undefined") {
      return null;
    }
    return localStorage.getItem(TOKEN_KEY);
  }, []);

  const isAuthenticated = useCallback(() => Boolean(getToken()), [getToken]);

  const setToken = useCallback((token: string) => {
    localStorage.setItem(TOKEN_KEY, token);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
  }, []);

  return { getToken, isAuthenticated, setToken, logout };
}
