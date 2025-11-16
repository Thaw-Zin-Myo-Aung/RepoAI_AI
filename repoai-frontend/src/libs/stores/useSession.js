// src/libs/stores/useSession.js
// Simple Zustand store for persisting the current selected repo and branch.

import { create } from 'zustand';
import { storage } from '../utils/storage';

const STORAGE_KEY = 'repoai:session';
const initial = storage.getJSON(STORAGE_KEY, { currentRepo: null, currentBranch: null, currentConversation: null, authToken: null });

export const useSession = create((set, get) => ({
  currentRepo: initial.currentRepo,
  currentBranch: initial.currentBranch,
  currentConversation: initial.currentConversation,
  authToken: initial.authToken,
  setCurrentRepo: (repo) => {
    set({ currentRepo: repo });
    const { currentBranch, currentConversation, authToken } = get();
    storage.setJSON(STORAGE_KEY, { currentRepo: repo, currentBranch, currentConversation, authToken });
  },
  setCurrentBranch: (branch) => {
    set({ currentBranch: branch });
    const { currentRepo, currentConversation, authToken } = get();
    storage.setJSON(STORAGE_KEY, { currentRepo, currentBranch: branch, currentConversation, authToken });
  },
  setCurrentConversation: (conversation) => {
    set({ currentConversation: conversation });
    const { currentRepo, currentBranch, authToken } = get();
    storage.setJSON(STORAGE_KEY, { currentRepo, currentBranch, currentConversation: conversation, authToken });
  },
  setAuthToken: (token) => {
    set({ authToken: token });
    const { currentRepo, currentBranch, currentConversation } = get();
    storage.setJSON(STORAGE_KEY, { currentRepo, currentBranch, currentConversation, authToken: token });
  },
  clearSession: () => {
    set({ currentRepo: null, currentBranch: null, currentConversation: null, authToken: null });
    storage.remove(STORAGE_KEY);
  },
}));
