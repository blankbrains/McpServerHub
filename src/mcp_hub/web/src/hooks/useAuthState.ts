import { useSyncExternalStore } from 'react'
import {
  AuthState,
  getAuthState,
  subscribeAuthState,
} from '../api/client'

const ANONYMOUS_AUTH_STATE: AuthState = { token: null, userId: null }

export function useAuthState(): AuthState {
  return useSyncExternalStore(
    subscribeAuthState,
    getAuthState,
    () => ANONYMOUS_AUTH_STATE,
  )
}
