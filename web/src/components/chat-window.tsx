'use client'

import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Send, Loader2, User, Bot, FileEdit } from 'lucide-react'
import { cn } from '@/lib/utils'
import { apiStreamRequest, apiConfig } from '@/lib/api'

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
  const inputRef = useRef<HTMLInputElement>(null)

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

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

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
    <div className="h-full flex flex-col bg-white">
      {/* Chat Header */}
      <div className="flex-shrink-0 p-4 border-b">
        <h3 className="font-medium text-gray-900">Project Chat</h3>
        <p className="text-sm text-gray-500">Ask questions or request changes - I&apos;ll update your document automatically</p>
      </div>

      {/* Messages - Scrollable area with proper height constraints */}
      <div className="flex-1 overflow-hidden">
        <ScrollArea ref={scrollAreaRef} className="h-full">
          <div className="p-4">
            <div className="space-y-4 min-h-full">
              {messages.length === 0 ? (
                <div className="text-center py-8">
                  <Bot className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                  <p className="text-gray-500 mb-2">Start a conversation</p>
                  <p className="text-sm text-gray-400">
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
                  <div className="flex-shrink-0 w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                    <Bot className="h-4 w-4 text-blue-600" />
                  </div>
                )}
                
                <div
                  className={cn(
                    "max-w-[80%] rounded-lg p-3",
                    message.role === 'user'
                      ? "bg-blue-600 text-white"
                      : "bg-gray-100 text-gray-900"
                  )}
                >
                  <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                  <div className="flex items-center justify-between mt-1">
                    <p
                      className={cn(
                        "text-xs",
                        message.role === 'user' ? "text-blue-100" : "text-gray-500"
                      )}
                    >
                      {formatTime(message.timestamp)}
                    </p>
                    {message.hasDocumentUpdate && (
                      <div className="flex items-center text-xs text-green-600">
                        <FileEdit className="h-3 w-3 mr-1" />
                        Doc Updated
                      </div>
                    )}
                  </div>
                </div>

                {message.role === 'user' && (
                  <div className="flex-shrink-0 w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center">
                    <User className="h-4 w-4 text-gray-600" />
                  </div>
                )}
                  </div>
                ))
              )}
              
              {isStreaming && (
                <div className="flex items-start space-x-3">
                  <div className="flex-shrink-0 w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                    <Bot className="h-4 w-4 text-blue-600" />
                  </div>
                  <div className="bg-gray-100 rounded-lg p-3">
                    <div className="flex items-center space-x-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span className="text-sm text-gray-500">Thinking and updating document...</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </ScrollArea>
      </div>

      {/* Fixed Input Bar */}
      <div className="flex-shrink-0 p-4 border-t bg-white shadow-lg">
        <div className="flex space-x-2">
          <Input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask a question or describe what you want to add to your project..."
            disabled={isStreaming}
            className="flex-1"
          />
          <Button
            onClick={handleSendMessage}
            disabled={!input.trim() || isStreaming}
            size="sm"
          >
            {isStreaming ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
        <p className="text-xs text-gray-500 mt-2">
          💡 Try: &quot;Add a task to integrate with Slack&quot; or &quot;What are the main risks for this project?&quot;
        </p>
        
        {/* Connection status */}
        <div className="mt-2 text-xs text-gray-500">
          Connected to: {apiConfig.baseUrl}
        </div>
      </div>
    </div>
  )
}