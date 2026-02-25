import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authApi } from '../services/api';

// Auth Store
interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  tenant_id: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: true,

      login: async (email: string, password: string) => {
        const response = await authApi.login(email, password);
        const { access_token, user } = response.data;
        
        set({
          token: access_token,
          user,
          isAuthenticated: true,
          isLoading: false,
        });
      },

      logout: () => {
        set({
          user: null,
          token: null,
          isAuthenticated: false,
          isLoading: false,
        });
      },

      checkAuth: async () => {
        const { token } = get();
        if (!token) {
          set({ isLoading: false });
          return;
        }

        try {
          const response = await authApi.me();
          set({
            user: response.data,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch {
          set({
            user: null,
            token: null,
            isAuthenticated: false,
            isLoading: false,
          });
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ token: state.token }),
    }
  )
);

// Alias for backward compatibility
export const useStore = useAuthStore;

// Project Store
interface ProjectState {
  currentProjectId: string | null;
  setCurrentProject: (id: string | null) => void;
}

export const useProjectStore = create<ProjectState>((set) => ({
  currentProjectId: null,
  setCurrentProject: (id) => set({ currentProjectId: id }),
}));

// Run Store
interface Run {
  id: string;
  run_no: number;
  status: string;
  started_at?: string;
  finished_at?: string;
}

interface RunState {
  runs: Run[];
  currentRun: Run | null;
  setRuns: (runs: Run[]) => void;
  setCurrentRun: (run: Run | null) => void;
  updateRunStatus: (runId: string, status: string) => void;
}

export const useRunStore = create<RunState>()((set) => ({
  runs: [],
  currentRun: null,
  setRuns: (runs: Run[]) => set({ runs }),
  setCurrentRun: (run: Run | null) => set({ currentRun: run }),
  updateRunStatus: (runId: string, status: string) =>
    set((state) => ({
      runs: state.runs.map((r) => (r.id === runId ? { ...r, status } : r)),
    })),
}));
