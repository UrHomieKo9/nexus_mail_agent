"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

const STORAGE_KEY = "nexus_mail_user_id";

function defaultUserId(): string {
  return process.env.NEXT_PUBLIC_DEFAULT_USER_ID || "demo-user";
}

type UserCtx = {
  userId: string;
  setUserId: (id: string) => void;
};

const UserContext = createContext<UserCtx | null>(null);

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [userId, setUserIdState] = useState(defaultUserId);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) setUserIdState(stored);
  }, []);

  const setUserId = useCallback((id: string) => {
    const trimmed = id.trim();
    localStorage.setItem(STORAGE_KEY, trimmed);
    setUserIdState(trimmed);
  }, []);

  return (
    <UserContext.Provider value={{ userId, setUserId }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUserId(): UserCtx {
  const ctx = useContext(UserContext);
  if (!ctx) {
    throw new Error("useUserId must be used within UserProvider");
  }
  return ctx;
}
