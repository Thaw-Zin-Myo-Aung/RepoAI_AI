// src/libs/stores/useUser.js
// Zustand store for authenticated user, synced with localStorage via utility helpers.

import { create } from 'zustand';
import { storage } from '../utils/storage';

const STORAGE_KEY = 'repoai:user';
const initialUser = storage.getJSON(STORAGE_KEY, null);

export const useUser = create((set) => ({
  user: initialUser,
  setUser: (user) => {
    set({ user });
    storage.setJSON(STORAGE_KEY, user);
  },
  clearUser: () => {
    set({ user: null });
    storage.remove(STORAGE_KEY);
  },
}));
