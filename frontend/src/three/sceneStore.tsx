import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { STATE_TARGETS, type SceneRig, type SceneState } from "./hooks";

interface SceneContextValue {
  rig: SceneRig;
  transitionTo: (next: SceneState) => void;
  subscribe: (fn: (s: SceneState) => void) => () => void;
  getState: () => SceneState;
}

const SceneContext = createContext<SceneContextValue | null>(null);

/** Owns the scene state machine. The rig is a mutable object eased toward the
 * active state's targets every frame inside the Canvas — zero re-renders.
 * React components subscribe to state *transitions* only (rare). */
export function SceneProvider({ children }: { children: ReactNode }) {
  const rigRef = useRef<SceneRig>({
    ...STATE_TARGETS.BOOT,
    state: "BOOT",
    enteredAt: performance.now() / 1000,
  });
  const stateRef = useRef<SceneState>("BOOT");
  const listeners = useRef(new Set<(s: SceneState) => void>());

  const transitionTo = useCallback((next: SceneState) => {
    if (stateRef.current === next) return;
    stateRef.current = next;
    rigRef.current.state = next;
    rigRef.current.enteredAt = performance.now() / 1000;
    listeners.current.forEach((fn) => fn(next));
  }, []);

  const subscribe = useCallback((fn: (s: SceneState) => void) => {
    listeners.current.add(fn);
    return () => listeners.current.delete(fn);
  }, []);

  const getState = useCallback(() => stateRef.current, []);

  const value = useMemo<SceneContextValue>(
    () => ({ rig: rigRef.current, transitionTo, subscribe, getState }),
    [transitionTo, subscribe, getState],
  );
  return <SceneContext.Provider value={value}>{children}</SceneContext.Provider>;
}

export function useScene(): SceneContextValue {
  const ctx = useContext(SceneContext);
  if (!ctx) throw new Error("useScene must be used inside SceneProvider");
  return ctx;
}

/** React state for the *current* scene state (re-renders only on transitions). */
export function useSceneState(): SceneState {
  const { subscribe, getState } = useScene();
  return useSyncExternalStore(subscribe, getState, getState);
}
