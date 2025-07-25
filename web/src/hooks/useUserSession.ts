'use client'

import { useState, useEffect, useCallback } from 'react'
import { User, UserSession, UserRegistrationRequest, UserRegistrationResponse, UserError } from '@/types/user'
import { UserStorage, userStorageUtils } from '@/utils/userStorage'
import { apiRequest } from '@/lib/api'

export function useUserSession() {
  const [session, setSession] = useState<UserSession>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
    error: null
  })

  // Initialize user session from storage
  const initializeSession = useCallback(async () => {
    try {
      setSession(prev => ({ ...prev, isLoading: true, error: null }))

      // Initialize storage system
      const storageResult = userStorageUtils.initialize()
      if (!storageResult.success) {
        console.warn('Storage initialization failed, using memory fallback')
      }

      // Try to load existing user data
      const userResult = userStorageUtils.validateStoredUser()
      
      if (userResult.success && userResult.data) {
        setSession({
          user: userResult.data,
          isAuthenticated: true,
          isLoading: false,
          error: null
        })
      } else {
        setSession({
          user: null,
          isAuthenticated: false,
          isLoading: false,
          error: userResult.message || null
        })
      }
    } catch (error) {
      console.error('Session initialization failed:', error)
      setSession({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: 'Failed to initialize user session'
      })
    }
  }, [])

  // Register a new user
  const registerUser = useCallback(async (firstName: string, lastName: string): Promise<void> => {
    try {
      setSession(prev => ({ ...prev, isLoading: true, error: null }))

      // Input validation
      if (!firstName.trim() || !lastName.trim()) {
        throw new Error('First name and last name are required')
      }

      if (firstName.length > 50 || lastName.length > 50) {
        throw new Error('Names must be 50 characters or less')
      }

      // Call backend API to register user
      const registrationRequest: UserRegistrationRequest = {
        first_name: firstName.trim(),
        last_name: lastName.trim()
      }

      const response = await apiRequest<UserRegistrationResponse>('/api/users', {
        method: 'POST',
        body: JSON.stringify(registrationRequest)
      })

      // Fetch the full user details
      const user: User = {
        id: response.user_id,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        display_name: response.display_name,
        created: new Date().toISOString(),
        last_active: new Date().toISOString()
      }

      // Store user data
      const storageResult = UserStorage.setUser(user)
      if (!storageResult.success) {
        console.warn('Failed to store user data:', storageResult.message)
        // Continue anyway - user is registered on backend
      }

      // Store session metadata
      UserStorage.setUserSession({
        user,
        isAuthenticated: true,
        isLoading: false,
        error: null
      })

      // Update state
      setSession({
        user,
        isAuthenticated: true,
        isLoading: false,
        error: null
      })

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Registration failed'
      console.error('User registration failed:', error)
      
      setSession(prev => ({
        ...prev,
        isLoading: false,
        error: errorMessage
      }))
      
      throw error // Re-throw so components can handle it
    }
  }, [])

  // Clear user session (logout)
  const clearUser = useCallback(() => {
    try {
      UserStorage.clearUser()
      setSession({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null
      })
    } catch (error) {
      console.error('Failed to clear user session:', error)
      // Force clear state even if storage fails
      setSession({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: 'Failed to clear session completely'
      })
    }
  }, [])

  // Refresh user data (e.g., after network reconnection)
  const refreshUser = useCallback(async (): Promise<void> => {
    if (!session.user?.id) {
      await initializeSession()
      return
    }

    try {
      setSession(prev => ({ ...prev, isLoading: true, error: null }))

      // Update last_active timestamp
      const updatedUser: User = {
        ...session.user,
        last_active: new Date().toISOString()
      }

      // Store updated user data
      const storageResult = UserStorage.setUser(updatedUser)
      if (storageResult.success) {
        setSession(prev => ({
          ...prev,
          user: updatedUser,
          isLoading: false
        }))
      } else {
        setSession(prev => ({
          ...prev,
          isLoading: false,
          error: 'Failed to update user data'
        }))
      }
    } catch (error) {
      console.error('Failed to refresh user data:', error)
      setSession(prev => ({
        ...prev,
        isLoading: false,
        error: 'Failed to refresh user session'
      }))
    }
  }, [session.user, initializeSession])

  // Get current user ID for API requests
  const getCurrentUserId = useCallback((): string => {
    return session.user?.id || 'anonymous'
  }, [session.user?.id])

  // Check if user needs to register
  const needsRegistration = useCallback((): boolean => {
    return !session.isLoading && !session.user
  }, [session.isLoading, session.user])

  // Initialize session on mount
  useEffect(() => {
    initializeSession()
  }, [initializeSession])

  // Update last_active periodically for active users
  useEffect(() => {
    if (!session.user) return

    const interval = setInterval(() => {
      refreshUser()
    }, 5 * 60 * 1000) // Update every 5 minutes

    return () => clearInterval(interval)
  }, [session.user, refreshUser])

  return {
    // State
    user: session.user,
    isAuthenticated: session.isAuthenticated,
    isLoading: session.isLoading,
    error: session.error,
    
    // Actions
    registerUser,
    clearUser,
    refreshUser,
    
    // Utilities
    getCurrentUserId,
    needsRegistration,
    
    // Debug info
    storageType: UserStorage.getStorageType(),
    isStorageWorking: UserStorage.isStorageWorking()
  }
}