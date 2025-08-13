'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { useUser, useUserDisplay } from '@/contexts/UserContext'
import { useUserIdentityModal, UserIdentityModal } from './UserIdentityModal'
import { UserAvatar } from '@/components/user-avatar'
import { useCurrentUserId } from '@/contexts/UserContext'

interface UserIndicatorProps {
  onUserChange?: () => void
  className?: string
}

export function UserIndicator({ onUserChange, className = '' }: UserIndicatorProps) {
  const { clearUser, isLoading } = useUser()
  const { displayName, isAnonymous } = useUserDisplay()
  const [showDropdown, setShowDropdown] = useState(false)
  const { isOpen, openModal, closeModal } = useUserIdentityModal()
  const userId = useCurrentUserId()

  const handleUserChange = () => {
    setShowDropdown(false)
    if (onUserChange) {
      onUserChange()
    } else if (isAnonymous) {
      openModal() // For anonymous users, open registration modal
    } else {
      clearUser() // For registered users, clear to switch to a different user
    }
  }

  const toggleDropdown = () => {
    setShowDropdown(!showDropdown)
  }

  if (isLoading) {
    return (
      <div className={`flex items-center space-x-2 ${className}`}>
        <div className="w-8 h-8 bg-muted rounded-full animate-pulse" />
        <div className="w-20 h-4 bg-muted rounded animate-pulse" />
      </div>
    )
  }

  return (
    <div className={`relative ${className}`}>
      <Button
        variant="ghost"
        onClick={toggleDropdown}
        className="flex items-center space-x-2 h-auto p-2 hover:bg-accent"
        disabled={isLoading}
      >
        {/* User Avatar */}
        <UserAvatar 
          userId={userId} 
          name={isAnonymous ? undefined : displayName} 
          size="md" 
          isAnonymous={isAnonymous}
        />
        
        {/* User Name */}
        <span className={`
          text-sm font-medium
          ${isAnonymous ? 'text-muted-foreground' : 'text-foreground'}
        `}>
          {displayName}
        </span>
        
        {/* Dropdown Arrow */}
        <svg
          className={`w-4 h-4 text-muted-foreground transition-transform ${
            showDropdown ? 'rotate-180' : ''
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </Button>

      {/* Dropdown Menu */}
      {showDropdown && (
        <>
          {/* Backdrop to close dropdown */}
          <div 
            className="fixed inset-0 z-10" 
            onClick={() => setShowDropdown(false)}
          />
          
          {/* Dropdown Content */}
          <div className="absolute right-0 mt-2 w-72 bg-card rounded-lg shadow-lg border border-border z-20">
            <div className="p-4 border-b border-border">
              <div className="flex items-center space-x-3">
                <UserAvatar 
                  userId={userId} 
                  name={isAnonymous ? undefined : displayName} 
                  size="lg" 
                  isAnonymous={isAnonymous}
                />
                <div>
                  <p className="font-medium text-card-foreground">{displayName}</p>
                  <p className="text-sm text-muted-foreground">
                    {isAnonymous ? 'Anonymous User' : 'Registered User'}
                  </p>
                </div>
              </div>
            </div>
            
            <div className="p-2">
              <Button
                variant="ghost"
                onClick={handleUserChange}
                className="w-full justify-start text-left p-3 h-auto"
              >
                <div>
                  <p className="font-medium">
                    {isAnonymous ? 'Register Name' : 'Switch User'}
                  </p>
                  <p className="text-sm text-muted-foreground leading-tight">
                    {isAnonymous 
                      ? 'Add your name for better attribution' 
                      : 'Change to a different user'
                    }
                  </p>
                </div>
              </Button>
              
              {!isAnonymous && (
                <Button
                  variant="ghost"
                  onClick={() => {
                    clearUser()
                    setShowDropdown(false)
                  }}
                  className="w-full justify-start text-left p-3 h-auto text-destructive hover:text-destructive hover:bg-destructive/10"
                >
                  <div>
                    <p className="font-medium">Continue as Anonymous</p>
                  </div>
                </Button>
              )}
            </div>
          </div>
        </>
      )}

      {/* User Identity Modal for registration */}
      <UserIdentityModal
        isOpen={isOpen}
        onClose={closeModal}
        allowAnonymous={true}
      />
    </div>
  )
}

// Compact version for smaller spaces
export function UserIndicatorCompact({ onUserChange, className = '' }: UserIndicatorProps) {
  const { isLoading } = useUser()
  const { displayName, isAnonymous } = useUserDisplay()
  const userId = useCurrentUserId()

  if (isLoading) {
    return <div className={`w-8 h-8 bg-muted rounded-full animate-pulse ${className}`} />
  }

  return (
    <Button
      variant="ghost"
      onClick={onUserChange}
      className={`p-1 h-auto ${className}`}
      title={`Current user: ${displayName} (click to change)`}
    >
      <UserAvatar 
        userId={userId} 
        name={isAnonymous ? undefined : displayName} 
        size="md" 
        isAnonymous={isAnonymous}
      />
    </Button>
  )
}