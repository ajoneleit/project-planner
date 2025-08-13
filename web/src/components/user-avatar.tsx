'use client'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { User } from 'lucide-react'

interface UserAvatarProps {
  userId: string
  name?: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
  isAnonymous?: boolean
}

export function UserAvatar({ userId, name, size = 'md', className, isAnonymous = false }: UserAvatarProps) {
  // Generate consistent color based on userId
  const getAvatarColor = (id: string) => {
    const colors = [
      'bg-red-500',
      'bg-blue-500', 
      'bg-green-500',
      'bg-yellow-500',
      'bg-purple-500',
      'bg-pink-500',
      'bg-indigo-500',
      'bg-teal-500',
      'bg-orange-500',
      'bg-cyan-500'
    ]
    
    // Simple hash function to get consistent color
    let hash = 0
    for (let i = 0; i < id.length; i++) {
      hash = ((hash << 5) - hash + id.charCodeAt(i)) & 0xffffffff
    }
    return colors[Math.abs(hash) % colors.length]
  }

  // Get initials from name 
  const getInitials = () => {
    if (name && name.trim()) {
      const words = name.trim().split(' ').filter(word => word.length > 0)
      if (words.length === 1) {
        // Single word - use first two characters
        return words[0].slice(0, 2).toUpperCase()
      } else {
        // Multiple words - use first letter of first two words
        return words
          .slice(0, 2)
          .map(word => word[0])
          .join('')
          .toUpperCase()
      }
    }
    
    // Fallback to generic initials if no proper name
    return '??'
  }

  const sizeClasses = {
    sm: 'h-6 w-6 text-xs',
    md: 'h-8 w-8 text-sm', 
    lg: 'h-10 w-10 text-base'
  }

  const iconSizeClasses = {
    sm: 'h-3 w-3',
    md: 'h-4 w-4',
    lg: 'h-5 w-5'
  }

  // For anonymous users, show person icon with gray background
  if (isAnonymous) {
    return (
      <Avatar className={`${sizeClasses[size]} ${className || ''}`}>
        <AvatarFallback className="bg-muted text-muted-foreground">
          <User className={iconSizeClasses[size]} />
        </AvatarFallback>
      </Avatar>
    )
  }

  const bgColor = getAvatarColor(userId)
  const initials = getInitials()

  return (
    <Avatar className={`${sizeClasses[size]} ${className || ''}`}>
      <AvatarFallback className={`${bgColor} text-white font-medium`}>
        {initials}
      </AvatarFallback>
    </Avatar>
  )
}