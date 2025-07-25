// Utilities for safe localStorage operations with fallbacks

import { User, UserSession, USER_STORAGE_KEYS, UserOperationResult } from '@/types/user'

// Check if localStorage is available and working
function isLocalStorageAvailable(): boolean {
  try {
    if (typeof window === 'undefined') return false
    
    const test = '__localStorage_test__'
    window.localStorage.setItem(test, test)
    window.localStorage.removeItem(test)
    return true
  } catch {
    return false
  }
}

// Check if sessionStorage is available as fallback
function isSessionStorageAvailable(): boolean {
  try {
    if (typeof window === 'undefined') return false
    
    const test = '__sessionStorage_test__'
    window.sessionStorage.setItem(test, test)
    window.sessionStorage.removeItem(test)
    return true
  } catch {
    return false
  }
}

// Get appropriate storage mechanism
function getStorage(): Storage | null {
  if (isLocalStorageAvailable()) {
    return window.localStorage
  } else if (isSessionStorageAvailable()) {
    console.warn('localStorage unavailable, using sessionStorage as fallback')
    return window.sessionStorage
  }
  return null
}

// Safe storage operations with error handling
export class UserStorage {
  private static storage: Storage | null = null
  private static memoryFallback: Map<string, string> = new Map()

  private static getStorageProvider(): Storage | Map<string, string> {
    if (this.storage === null) {
      this.storage = getStorage()
    }
    return this.storage || this.memoryFallback
  }

  // Store user data safely
  static setUser(user: User): UserOperationResult {
    try {
      const storage = this.getStorageProvider()
      const userData = JSON.stringify(user)
      
      if (storage instanceof Map) {
        storage.set(USER_STORAGE_KEYS.CURRENT_USER, userData)
        console.warn('Using memory storage fallback for user data')
      } else {
        storage.setItem(USER_STORAGE_KEYS.CURRENT_USER, userData)
      }
      
      return { success: true }
    } catch (error) {
      console.error('Failed to store user data:', error)
      return { 
        success: false, 
        error: 'STORAGE_UNAVAILABLE',
        message: 'Unable to save user data' 
      }
    }
  }

  // Retrieve user data safely
  static getUser(): UserOperationResult<User | null> {
    try {
      const storage = this.getStorageProvider()
      let userData: string | null = null
      
      if (storage instanceof Map) {
        userData = storage.get(USER_STORAGE_KEYS.CURRENT_USER) || null
      } else {
        userData = storage.getItem(USER_STORAGE_KEYS.CURRENT_USER)
      }
      
      if (!userData) {
        return { success: true, data: null }
      }
      
      const user: User = JSON.parse(userData)
      return { success: true, data: user }
    } catch (error) {
      console.error('Failed to retrieve user data:', error)
      return { 
        success: false, 
        error: 'STORAGE_UNAVAILABLE',
        message: 'Unable to load user data' 
      }
    }
  }

  // Clear user data
  static clearUser(): UserOperationResult {
    try {
      const storage = this.getStorageProvider()
      
      if (storage instanceof Map) {
        storage.delete(USER_STORAGE_KEYS.CURRENT_USER)
        storage.delete(USER_STORAGE_KEYS.USER_SESSION)
      } else {
        storage.removeItem(USER_STORAGE_KEYS.CURRENT_USER)
        storage.removeItem(USER_STORAGE_KEYS.USER_SESSION)
      }
      
      return { success: true }
    } catch (error) {
      console.error('Failed to clear user data:', error)
      return { 
        success: false, 
        error: 'STORAGE_UNAVAILABLE',
        message: 'Unable to clear user data' 
      }
    }
  }

  // Store user session metadata
  static setUserSession(session: Partial<UserSession>): UserOperationResult {
    try {
      const storage = this.getStorageProvider()
      const sessionData = JSON.stringify({
        timestamp: new Date().toISOString(),
        ...session
      })
      
      if (storage instanceof Map) {
        storage.set(USER_STORAGE_KEYS.USER_SESSION, sessionData)
      } else {
        storage.setItem(USER_STORAGE_KEYS.USER_SESSION, sessionData)
      }
      
      return { success: true }
    } catch (error) {
      console.error('Failed to store session data:', error)
      return { 
        success: false, 
        error: 'STORAGE_UNAVAILABLE',
        message: 'Unable to save session data' 
      }
    }
  }

  // Get user session metadata
  static getUserSession(): UserOperationResult<Record<string, unknown>> {
    try {
      const storage = this.getStorageProvider()
      let sessionData: string | null = null
      
      if (storage instanceof Map) {
        sessionData = storage.get(USER_STORAGE_KEYS.USER_SESSION) || null
      } else {
        sessionData = storage.getItem(USER_STORAGE_KEYS.USER_SESSION)
      }
      
      if (!sessionData) {
        return { success: true, data: undefined }
      }
      
      const session = JSON.parse(sessionData)
      return { success: true, data: session }
    } catch (error) {
      console.error('Failed to retrieve session data:', error)
      return { 
        success: false, 
        error: 'STORAGE_UNAVAILABLE',
        message: 'Unable to load session data' 
      }
    }
  }

  // Check if storage is working
  static isStorageWorking(): boolean {
    return this.getStorageProvider() !== this.memoryFallback
  }

  // Get storage type for debugging
  static getStorageType(): 'localStorage' | 'sessionStorage' | 'memory' {
    const storage = this.getStorageProvider()
    if (storage === this.memoryFallback) return 'memory'
    if (storage === window.sessionStorage) return 'sessionStorage'
    return 'localStorage'
  }
}

// Utility functions for common operations
export const userStorageUtils = {
  // Initialize storage check on app start
  initialize: (): UserOperationResult => {
    try {
      const storageType = UserStorage.getStorageType()
      console.log(`User storage initialized using: ${storageType}`)
      return { success: true }
    } catch (error) {
      console.error('Failed to initialize user storage:', error)
      return { 
        success: false, 
        error: 'STORAGE_UNAVAILABLE',
        message: 'Storage system unavailable' 
      }
    }
  },

  // Check if user data exists
  hasUserData: (): boolean => {
    const result = UserStorage.getUser()
    return result.success && result.data !== null
  },

  // Validate stored user data
  validateStoredUser: (): UserOperationResult<User | null> => {
    const result = UserStorage.getUser()
    if (!result.success) return result
    
    const user = result.data
    if (!user) return { success: true, data: null }
    
    // Basic validation of user structure
    if (!user.id || !user.first_name || !user.last_name || !user.display_name) {
      console.warn('Invalid user data found in storage, clearing...')
      UserStorage.clearUser()
      return { 
        success: false, 
        error: 'INVALID_INPUT',
        message: 'Invalid user data found' 
      }
    }
    
    return { success: true, data: user }
  }
}