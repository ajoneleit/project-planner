'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface UserIdentityFormProps {
  onSubmit: (firstName: string, lastName: string) => Promise<void>
  isLoading?: boolean
  error?: string | null
  showAnonymousOption?: boolean
  onAnonymousSelect?: () => void
}

export function UserIdentityForm({ 
  onSubmit, 
  isLoading = false, 
  error = null,
  showAnonymousOption = false,
  onAnonymousSelect 
}: UserIdentityFormProps) {
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [validationErrors, setValidationErrors] = useState<{
    firstName?: string
    lastName?: string
  }>({})

  const validateForm = (): boolean => {
    const errors: { firstName?: string; lastName?: string } = {}
    
    if (!firstName.trim()) {
      errors.firstName = 'First name is required'
    } else if (firstName.trim().length > 50) {
      errors.firstName = 'First name must be 50 characters or less'
    } else if (!/^[a-zA-Z\s-']+$/.test(firstName.trim())) {
      errors.firstName = 'First name can only contain letters, spaces, hyphens, and apostrophes'
    }
    
    if (!lastName.trim()) {
      errors.lastName = 'Last name is required'
    } else if (lastName.trim().length > 50) {
      errors.lastName = 'Last name must be 50 characters or less'
    } else if (!/^[a-zA-Z\s-']+$/.test(lastName.trim())) {
      errors.lastName = 'Last name can only contain letters, spaces, hyphens, and apostrophes'
    }
    
    setValidationErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!validateForm()) {
      return
    }
    
    try {
      await onSubmit(firstName.trim(), lastName.trim())
      // Clear form on success
      setFirstName('')
      setLastName('')
      setValidationErrors({})
    } catch (error) {
      // Error handling is managed by parent component
      console.error('Form submission failed:', error)
    }
  }

  const handleFirstNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFirstName(e.target.value)
    // Clear validation error when user starts typing
    if (validationErrors.firstName) {
      setValidationErrors(prev => ({ ...prev, firstName: undefined }))
    }
  }

  const handleLastNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setLastName(e.target.value)
    // Clear validation error when user starts typing
    if (validationErrors.lastName) {
      setValidationErrors(prev => ({ ...prev, lastName: undefined }))
    }
  }

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <h2 className="text-2xl font-bold">Welcome to Project Planner</h2>
        <p className="text-gray-600">
          Please enter your name to get started. This helps us track your contributions to projects.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <label htmlFor="firstName" className="text-sm font-medium text-gray-700">
            First Name
          </label>
          <Input
            id="firstName"
            type="text"
            value={firstName}
            onChange={handleFirstNameChange}
            placeholder="Enter your first name"
            disabled={isLoading}
            className={validationErrors.firstName ? 'border-red-500' : ''}
            maxLength={50}
            autoComplete="given-name"
            autoFocus
          />
          {validationErrors.firstName && (
            <p className="text-sm text-red-600">{validationErrors.firstName}</p>
          )}
        </div>

        <div className="space-y-2">
          <label htmlFor="lastName" className="text-sm font-medium text-gray-700">
            Last Name
          </label>
          <Input
            id="lastName"
            type="text"
            value={lastName}
            onChange={handleLastNameChange}
            placeholder="Enter your last name"
            disabled={isLoading}
            className={validationErrors.lastName ? 'border-red-500' : ''}
            maxLength={50}
            autoComplete="family-name"
          />
          {validationErrors.lastName && (
            <p className="text-sm text-red-600">{validationErrors.lastName}</p>
          )}
        </div>

        {error && (
          <div className="p-3 rounded-md bg-red-50 border border-red-200">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        <div className="flex flex-col space-y-3">
          <Button 
            type="submit" 
            disabled={isLoading || !firstName.trim() || !lastName.trim()}
            className="w-full"
          >
            {isLoading ? 'Setting up...' : 'Get Started'}
          </Button>

          {showAnonymousOption && onAnonymousSelect && (
            <Button 
              type="button"
              variant="outline"
              onClick={onAnonymousSelect}
              disabled={isLoading}
              className="w-full"
            >
              Continue as Anonymous
            </Button>
          )}
        </div>
      </form>

      <div className="text-xs text-gray-500 text-center space-y-1">
        <p>Your name will be used to track contributions to projects.</p>
        <p>No account is created - this is stored locally in your browser.</p>
      </div>
    </div>
  )
}