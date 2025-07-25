// User-related TypeScript interfaces matching backend structure

export interface User {
  id: string
  first_name: string
  last_name: string
  display_name: string
  created: string
  last_active: string
}

export interface UserRegistrationRequest {
  first_name: string
  last_name: string
}

export interface UserRegistrationResponse {
  user_id: string
  display_name: string
}

export interface UserSession {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
}

export interface UserContextType extends UserSession {
  registerUser: (firstName: string, lastName: string) => Promise<void>
  clearUser: () => void
  refreshUser: () => Promise<void>
}

// Storage keys for localStorage
export const USER_STORAGE_KEYS = {
  CURRENT_USER: 'project_planner_current_user',
  USER_SESSION: 'project_planner_user_session'
} as const

// Error types for user operations
export type UserError = 
  | 'REGISTRATION_FAILED'
  | 'STORAGE_UNAVAILABLE' 
  | 'NETWORK_ERROR'
  | 'INVALID_INPUT'
  | 'USER_NOT_FOUND'

export interface UserOperationResult<T = void> {
  success: boolean
  data?: T
  error?: UserError
  message?: string
}