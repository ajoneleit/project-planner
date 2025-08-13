'use client'

import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { ExpandableTextarea } from '@/components/expandable-textarea'
import { Send, Loader2, Bot, FileEdit } from 'lucide-react'
import { cn } from '@/lib/utils'
import { apiStreamRequest, apiConfig } from '@/lib/api'
import { useCurrentUserId, useUserDisplay } from '@/contexts/UserContext'
import { UserAvatar } from '@/components/user-avatar'

interface Message {
  id: string
  content: string
  role: 'user' | 'assistant'
  timestamp: Date
  hasDocumentUpdate?: boolean
}

interface ChatWindowProps {
  projectSlug: string
  onMessageComplete?: () => void // Callback when message is complete
}

export function ChatWindow({ projectSlug, onMessageComplete }: ChatWindowProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const userId = useCurrentUserId()
  const { displayName, isAnonymous } = useUserDisplay()

  // Storage key for this project's conversation
  const conversationKey = `conversation_${projectSlug}_${userId}`

  // Load conversation from sessionStorage on mount or project change
  useEffect(() => {
    const loadStoredConversation = () => {
      try {
        const storedConversation = sessionStorage.getItem(conversationKey)
        if (storedConversation) {
          const parsedMessages = JSON.parse(storedConversation)
          // Convert timestamp strings back to Date objects
          const messagesWithDates = parsedMessages.map((msg: Message & { timestamp: string }) => ({
            ...msg,
            timestamp: new Date(msg.timestamp)
          }))
          setMessages(messagesWithDates)
          console.log(`Loaded ${messagesWithDates.length} messages for project ${projectSlug}`)
          return true // Found stored conversation
        }
      } catch (error) {
        console.error('Error loading stored conversation:', error)
        sessionStorage.removeItem(conversationKey) // Clear corrupted data
      }
      return false // No stored conversation
    }
    
    const hasStoredConversation = loadStoredConversation()
    if (!hasStoredConversation) {
      setMessages([]) // Clear messages if no stored conversation
    }
  }, [projectSlug, userId, conversationKey])

  // Save conversation to sessionStorage whenever messages change
  useEffect(() => {
    if (messages.length > 0) {
      try {
        sessionStorage.setItem(conversationKey, JSON.stringify(messages))
        console.log(`Saved ${messages.length} messages for project ${projectSlug}`)
      } catch (error) {
        console.error('Error saving conversation:', error)
      }
    }
  }, [messages, conversationKey, projectSlug])

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]')
      if (scrollContainer) {
        // Smooth scroll to bottom
        scrollContainer.scrollTo({
          top: scrollContainer.scrollHeight,
          behavior: 'smooth'
        })
      }
    }
  }, [messages, isStreaming])

  // Focus input on mount and fetch initial message
  useEffect(() => {
    textareaRef.current?.focus()
    
    // Fetch initial message automatically (but only if no stored conversation)
    const fetchInitialMessage = async () => {
      // Check if we have stored conversation first
      try {
        const storedConversation = sessionStorage.getItem(conversationKey)
        if (storedConversation && JSON.parse(storedConversation).length > 0) {
          return // Don't fetch initial message if we have stored conversation
        }
      } catch {
        // If parsing fails, continue with initial message fetch
      }
      
      if (messages.length > 0) return // Don't fetch if we already have messages
      
      try {
        setIsStreaming(true)
        
        // Use user ID from context
        
        const stream = await apiStreamRequest(`/api/projects/${projectSlug}/initial-message?user_id=${userId}`, {
          method: 'GET',
        })

        if (!stream) {
          return // No initial message needed
        }

        // Create assistant message for initial message
        const assistantMessage: Message = {
          id: Date.now().toString(),
          content: '',
          role: 'assistant',
          timestamp: new Date(),
          hasDocumentUpdate: false
        }

        setMessages([assistantMessage])

        // Stream the initial message
        const reader = stream.getReader()
        const decoder = new TextDecoder()
        let done = false

        while (!done) {
          const { value, done: streamDone } = await reader.read()
          done = streamDone

          if (value) {
            const chunk = decoder.decode(value)
            const lines = chunk.split('\n')
            
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6))
                  
                  if (data.token) {
                    setMessages(prev => prev.map(msg => 
                      msg.id === assistantMessage.id 
                        ? { ...msg, content: msg.content + data.token }
                        : msg
                    ))
                  } else if (data.done) {
                    done = true
                    break
                  }
                } catch {
                  continue
                }
              }
            }
          }
        }
      } catch (error) {
        console.error('Error fetching initial message:', error)
      } finally {
        setIsStreaming(false)
      }
    }
    
    fetchInitialMessage()
  }, [projectSlug, userId, conversationKey, messages.length]) // Re-run when project or user changes

  const handleSendMessage = async () => {
    if (!input.trim() || isStreaming) return

    const userMessage: Message = {
      id: Date.now().toString(),
      content: input.trim(),
      role: 'user',
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsStreaming(true)

    try {
      const stream = await apiStreamRequest(`/api/projects/${projectSlug}/chat`, {
        method: 'POST',
        body: JSON.stringify({
          message: userMessage.content,
          model: 'gpt-4o-mini'
        }),
      })

      if (!stream) {
        throw new Error('No response stream received')
      }

      // Create assistant message
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: '',
        role: 'assistant',
        timestamp: new Date(),
        hasDocumentUpdate: false
      }

      setMessages(prev => [...prev, assistantMessage])

      // Stream the response
      const reader = stream.getReader()
      const decoder = new TextDecoder()
      let done = false

      while (!done) {
        const { value, done: streamDone } = await reader.read()
        done = streamDone

        if (value) {
          const chunk = decoder.decode(value)
          const lines = chunk.split('\n')
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                
                if (data.token) {
                  setMessages(prev => prev.map(msg => 
                    msg.id === assistantMessage.id 
                      ? { ...msg, content: msg.content + data.token }
                      : msg
                  ))
                } else if (data.done) {
                  // Check if response indicates document update
                  const hasUpdate = assistantMessage.content.includes('📝') || 
                                  assistantMessage.content.includes('updated') ||
                                  assistantMessage.content.includes('document')
                  
                  setMessages(prev => prev.map(msg => 
                    msg.id === assistantMessage.id 
                      ? { ...msg, hasDocumentUpdate: hasUpdate }
                      : msg
                  ))
                  
                  done = true
                  break
                } else if (data.error) {
                  throw new Error(data.error)
                }
              } catch {
                // Skip malformed JSON
                continue
              }
            }
          }
        }
      }

      // Notify parent component that message is complete
      if (onMessageComplete) {
        onMessageComplete()
      }

    } catch (error) {
      console.error('Chat error:', error)
      
      // Add error message
      const errorMessage: Message = {
        id: (Date.now() + 2).toString(),
        content: `Sorry, there was an error processing your message: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.`,
        role: 'assistant',
        timestamp: new Date(),
      }
      
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsStreaming(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }


  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className="h-full flex flex-col bg-background">
      {/* Chat Header */}
      <div className="flex-shrink-0 p-4 border-b border-border bg-card">
        <h3 className="font-medium text-card-foreground">Project Chat</h3>
        <p className="text-sm text-muted-foreground">Ask questions or request changes - I&apos;ll update your document automatically</p>
      </div>

      {/* Messages - Scrollable area with proper height constraints */}
      <div className="flex-1 overflow-hidden">
        <ScrollArea ref={scrollAreaRef} className="h-full">
          <div className="p-4">
            <div className="space-y-4 min-h-full">
              {messages.length === 0 ? (
                <div className="text-center py-8">
                  <Bot className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                  <p className="text-muted-foreground mb-2">Start a conversation</p>
                  <p className="text-sm text-muted-foreground/70">
                    I can answer questions and automatically update your project document
                  </p>
                </div>
              ) : (
                messages.map((message) => (
              <div
                key={message.id}
                className={cn(
                  "flex items-start space-x-3",
                  message.role === 'user' ? "justify-end" : "justify-start"
                )}
              >
                {message.role === 'assistant' && (
                  <div className="flex-shrink-0 w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                )}
                
                <div
                  className={cn(
                    "max-w-[80%] rounded-lg p-3",
                    message.role === 'user'
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                  <div className="flex items-center justify-between mt-1">
                    <p
                      className={cn(
                        "text-xs",
                        message.role === 'user' ? "text-primary-foreground/70" : "text-muted-foreground/70"
                      )}
                    >
                      {formatTime(message.timestamp)}
                    </p>
                    {message.hasDocumentUpdate && (
                      <div className="flex items-center text-xs text-green-600 dark:text-green-400">
                        <FileEdit className="h-3 w-3 mr-1" />
                        Doc Updated
                      </div>
                    )}
                  </div>
                </div>

                {message.role === 'user' && (
                  <UserAvatar 
                    userId={userId} 
                    name={isAnonymous ? undefined : displayName}
                    size="md" 
                    isAnonymous={isAnonymous}
                  />
                )}
                  </div>
                ))
              )}
              
              {isStreaming && (
                <div className="flex items-start space-x-3">
                  <div className="flex-shrink-0 w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                  <div className="bg-muted rounded-lg p-3">
                    <div className="flex items-center space-x-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span className="text-sm text-muted-foreground">Thinking and updating document...</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </ScrollArea>
      </div>

      {/* Fixed Input Bar */}
      <div className="flex-shrink-0 p-4 border-t border-border bg-card shadow-lg">
        <div className="flex items-end space-x-2">
          <div className="flex-1">
            <ExpandableTextarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask a question or describe what you want to add to your project..."
              disabled={isStreaming}
              maxRows={5}
              minRows={1}
            />
          </div>
          <Button
            onClick={handleSendMessage}
            disabled={!input.trim() || isStreaming}
            size="sm"
            className="mb-1"
          >
            {isStreaming ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          💡 Try: &quot;Add a task to integrate with Slack&quot; or &quot;What are the main risks for this project?&quot;
        </p>
        
        {/* Connection status */}
        <div className="mt-2 text-xs text-muted-foreground/50">
          Connected to: {apiConfig.baseUrl}
        </div>
      </div>
    </div>
  )
}