'use client'

import React, { createContext, useContext, ReactNode, useEffect } from 'react'
import { UserContextType } from '@/types/user'
import { useUserSession } from '@/hooks/useUserSession'
import { setUserIdGetter } from '@/lib/api'

// Create the context with undefined as default
const UserContext = createContext<UserContextType | undefined>(undefined)

// Custom hook to use the user context
export function useUser(): UserContextType {
  const context = useContext(UserContext)
  
  if (context === undefined) {
    throw new Error('useUser must be used within a UserProvider')
  }
  
  return context
}

// Props for the UserProvider component
interface UserProviderProps {
  children: ReactNode
}

// UserProvider component that provides user state to the app
export function UserProvider({ children }: UserProviderProps) {
  const userSession = useUserSession()

  const contextValue: UserContextType = {
    // State from useUserSession
    user: userSession.user,
    isAuthenticated: userSession.isAuthenticated,
    isLoading: userSession.isLoading,
    error: userSession.error,
    
    // Actions from useUserSession
    registerUser: userSession.registerUser,
    clearUser: userSession.clearUser,
    refreshUser: userSession.refreshUser
  }

  // Set up the API layer to use current user ID
  useEffect(() => {
    setUserIdGetter(() => userSession.getCurrentUserId())
  }, [userSession.getCurrentUserId])

  return (
    <UserContext.Provider value={contextValue}>
      {children}
    </UserContext.Provider>
  )
}

// Optional: Hook for checking if user needs registration
export function useUserRegistrationStatus() {
  const { user, isLoading, isAuthenticated } = useUser()
  
  return {
    needsRegistration: !isLoading && !user && !isAuthenticated,
    isReady: !isLoading,
    hasUser: !!user
  }
}

// Optional: Hook for getting current user ID for API calls
export function useCurrentUserId(): string {
  const { user } = useUser()
  return user?.id || 'anonymous'
}

// Optional: Hook for user display information
export function useUserDisplay() {
  const { user, isAuthenticated } = useUser()
  
  return {
    displayName: user?.display_name || 'Anonymous',
    firstName: user?.first_name || '',
    lastName: user?.last_name || '',
    initials: user ? `${user.first_name[0]}${user.last_name[0]}`.toUpperCase() : 'A',
    isAnonymous: !isAuthenticated
  }
}

// Type for components that need user context
export type WithUserContext<P = Record<string, unknown>> = P & {
  userContext: UserContextType
}

// HOC for components that need user context (alternative to hooks)
export function withUserContext<P extends Record<string, unknown>>(
  Component: React.ComponentType<WithUserContext<P>>
) {
  const WrappedComponent = (props: P) => {
    const userContext = useUser()
    return <Component {...props} userContext={userContext} />
  }
  
  WrappedComponent.displayName = `withUserContext(${Component.displayName || Component.name})`
  return WrappedComponent
}

// Export the context for advanced use cases
export { UserContext }