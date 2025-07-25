'use client'

import { useEffect, useState } from 'react'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { UserIdentityForm } from './UserIdentityForm'
import { useUser, useUserRegistrationStatus } from '@/contexts/UserContext'

interface UserIdentityModalProps {
  isOpen?: boolean
  onClose?: () => void
  allowAnonymous?: boolean
  title?: string
  description?: string
}

export function UserIdentityModal({ 
  isOpen,
  onClose,
  allowAnonymous = true,
  title,
  description
}: UserIdentityModalProps) {
  const { registerUser, isLoading, error } = useUser()
  const { needsRegistration, isReady } = useUserRegistrationStatus()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [allowAnonymousMode, setAllowAnonymousMode] = useState(false)

  // Determine if modal should be open
  useEffect(() => {
    if (isOpen !== undefined) {
      // Controlled mode
      setIsModalOpen(isOpen)
    } else {
      // Auto mode - show when user needs registration
      setIsModalOpen(isReady && needsRegistration)
    }
  }, [isOpen, isReady, needsRegistration])

  const handleSubmit = async (firstName: string, lastName: string) => {
    try {
      await registerUser(firstName, lastName)
      
      // Close modal on successful registration
      if (onClose) {
        onClose()
      } else {
        setIsModalOpen(false)
      }
    } catch (error) {
      // Error is handled by the form component through the error prop
      console.error('Registration failed:', error)
    }
  }

  const handleAnonymousSelect = () => {
    setAllowAnonymousMode(true)
    
    if (onClose) {
      onClose()
    } else {
      setIsModalOpen(false)
    }
  }

  const handleCloseAttempt = () => {
    if (allowAnonymous || allowAnonymousMode) {
      handleAnonymousSelect()
    }
    // If anonymous is not allowed, prevent closing
  }

  // Don't render anything if not ready or not needed
  if (!isReady) {
    return null
  }

  // Don't show if user allowed anonymous mode
  if (allowAnonymousMode && !needsRegistration) {
    return null
  }

  return (
    <Dialog 
      open={isModalOpen} 
      onOpenChange={allowAnonymous ? handleCloseAttempt : undefined}
    >
      <DialogContent 
        className="sm:max-w-md"
        showCloseButton={allowAnonymous}
      >
        <DialogTitle className="sr-only">
          {title || 'User Registration'}
        </DialogTitle>
        <DialogDescription className="sr-only">
          {description || 'Enter your name to get started with project tracking'}
        </DialogDescription>
        <UserIdentityForm
          onSubmit={handleSubmit}
          isLoading={isLoading}
          error={error}
          showAnonymousOption={allowAnonymous}
          onAnonymousSelect={allowAnonymous ? handleAnonymousSelect : undefined}
        />
      </DialogContent>
    </Dialog>
  )
}

// Automatic modal that shows when needed
export function AutoUserIdentityModal() {
  return (
    <UserIdentityModal
      allowAnonymous={true}
    />
  )
}

// Non-dismissible modal for required registration
export function RequiredUserIdentityModal() {
  return (
    <UserIdentityModal
      allowAnonymous={false}
      title="Registration Required"
      description="Please enter your name to continue using the application."
    />
  )
}

// Hook for programmatically controlling the modal
export function useUserIdentityModal() {
  const [isOpen, setIsOpen] = useState(false)
  const { needsRegistration } = useUserRegistrationStatus()

  const openModal = () => setIsOpen(true)
  const closeModal = () => setIsOpen(false)

  const openIfNeeded = () => {
    if (needsRegistration) {
      setIsOpen(true)
    }
  }

  return {
    isOpen,
    openModal,
    closeModal,
    openIfNeeded,
    needsRegistration
  }
}