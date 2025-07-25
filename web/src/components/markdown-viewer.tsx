'use client'

import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useCallback } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { RefreshCw, Download, Loader2, FileText, Clock, Wifi } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { apiRequest } from '@/lib/api'

interface ProjectFile {
  content: string
}

async function fetchProjectFile(slug: string): Promise<ProjectFile> {
  return apiRequest<ProjectFile>(`/api/projects/${slug}/file`)
}

interface MarkdownViewerProps {
  projectSlug: string
  lastChatUpdate?: number // Timestamp of last chat message for auto-refresh
}

export function MarkdownViewer({ projectSlug, lastChatUpdate }: MarkdownViewerProps) {
  const autoRefreshInterval = useRef<NodeJS.Timeout | null>(null)
  const broadcastChannel = useRef<BroadcastChannel | null>(null)
  
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['project-file', projectSlug],
    queryFn: () => fetchProjectFile(projectSlug),
    refetchInterval: false, // Disable built-in auto-refresh, we'll handle it manually
    retry: 3,
    retryDelay: 1000,
    staleTime: 0, // Always consider data stale to ensure fresh fetches
    gcTime: 0, // Don't cache to ensure we always get fresh data
  })

  // Manual refresh function that ensures fresh data fetch
  const handleManualRefresh = useCallback(async () => {
    try {
      await refetch()
    } catch (error) {
      console.error('Manual refresh failed:', error)
    }
  }, [refetch])

  // Auto-refresh setup (30 seconds)
  useEffect(() => {
    const startAutoRefresh = () => {
      if (autoRefreshInterval.current) {
        clearInterval(autoRefreshInterval.current)
      }
      
      autoRefreshInterval.current = setInterval(() => {
        refetch()
      }, 30000) // 30 seconds
    }

    startAutoRefresh()

    return () => {
      if (autoRefreshInterval.current) {
        clearInterval(autoRefreshInterval.current)
        autoRefreshInterval.current = null
      }
    }
  }, [refetch])

  // Multi-tab sync with BroadcastChannel
  useEffect(() => {
    if (typeof window !== 'undefined' && 'BroadcastChannel' in window) {
      broadcastChannel.current = new BroadcastChannel(`project-sync-${projectSlug}`)
      
      broadcastChannel.current.addEventListener('message', (event) => {
        if (event.data.type === 'document-updated') {
          // Another tab detected a document update, refresh immediately
          refetch()
        }
      })

      return () => {
        if (broadcastChannel.current) {
          broadcastChannel.current.close()
          broadcastChannel.current = null
        }
      }
    }
  }, [projectSlug, refetch])

  // Notify other tabs when we detect a document update
  useEffect(() => {
    if (data && broadcastChannel.current) {
      broadcastChannel.current.postMessage({
        type: 'document-updated',
        timestamp: Date.now(),
        projectSlug
      })
    }
  }, [data, projectSlug])

  // Auto-refresh when chat updates occur (existing functionality)
  useEffect(() => {
    if (lastChatUpdate) {
      // Refresh document 2 seconds after chat update to allow processing
      const timer = setTimeout(() => {
        refetch()
      }, 2000)
      
      return () => clearTimeout(timer)
    }
  }, [lastChatUpdate, refetch])

  const handleDownload = () => {
    if (data?.content) {
      const blob = new Blob([data.content], { type: 'text/markdown' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${projectSlug}.md`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    }
  }

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Header */}
      <div className="flex-shrink-0 p-4 border-b flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <FileText className="h-5 w-5 text-gray-600" />
          <h3 className="font-medium text-gray-900">Project Document</h3>
          <div className="flex items-center text-xs text-green-600">
            <Wifi className="h-3 w-3 mr-1" />
            Auto-sync (30s)
          </div>
          {lastChatUpdate && (
            <div className="flex items-center text-xs text-blue-600">
              <Clock className="h-3 w-3 mr-1" />
              Chat-triggered
            </div>
          )}
        </div>
        
        <div className="flex items-center space-x-2">
          <Button 
            variant="outline" 
            size="sm" 
            onClick={handleManualRefresh}
            disabled={isFetching}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
            {isFetching ? 'Refreshing...' : 'Refresh'}
          </Button>
          <Button variant="outline" size="sm" onClick={handleDownload} disabled={!data}>
            <Download className="h-4 w-4 mr-2" />
            Download
          </Button>
        </div>
      </div>

      {/* Content - Scrollable area with proper height constraints */}
      <div className="flex-1 overflow-hidden">
        <ScrollArea className="h-full">
          <div className="p-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="flex items-center space-x-2">
                <Loader2 className="h-6 w-6 animate-spin" />
                <span className="text-gray-500">Loading document...</span>
              </div>
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <div className="text-red-600 mb-4">
                <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p className="font-medium">Error loading document</p>
                <p className="text-sm text-gray-500 mt-2">
                  {error instanceof Error ? error.message : 'Unknown error'}
                </p>
              </div>
              <Button onClick={() => refetch()} variant="outline">
                Try Again
              </Button>
            </div>
          ) : data?.content ? (
            <div className="prose prose-gray max-w-none prose-headings:scroll-mt-4">
              <ReactMarkdown
                components={{
                  h1: ({ children }) => (
                    <h1 className="text-3xl font-bold text-gray-900 mb-6 pb-3 border-b">
                      {children}
                    </h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className="text-2xl font-semibold text-gray-800 mt-8 mb-4">
                      {children}
                    </h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="text-xl font-medium text-gray-800 mt-6 mb-3">
                      {children}
                    </h3>
                  ),
                  p: ({ children }) => (
                    <p className="text-gray-700 leading-relaxed mb-4">
                      {children}
                    </p>
                  ),
                  strong: ({ children }) => (
                    <strong className="font-semibold text-gray-900">
                      {children}
                    </strong>
                  ),
                  ul: ({ children }) => (
                    <ul className="list-disc list-inside mb-4 space-y-1">
                      {children}
                    </ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal list-inside mb-4 space-y-1">
                      {children}
                    </ol>
                  ),
                  li: ({ children }) => (
                    <li className="text-gray-700">{children}</li>
                  ),
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-4 border-blue-200 pl-4 py-2 mb-4 bg-blue-50 text-gray-700 italic">
                      {children}
                    </blockquote>
                  ),
                  code: ({ children }) => (
                    <code className="bg-gray-100 px-1 py-0.5 rounded text-sm font-mono">
                      {children}
                    </code>
                  ),
                  pre: ({ children }) => (
                    <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto mb-4">
                      {children}
                    </pre>
                  ),
                }}
              >
                {data.content}
              </ReactMarkdown>
            </div>
          ) : (
            <div className="text-center py-12">
              <FileText className="h-12 w-12 mx-auto mb-4 text-gray-400" />
              <p className="text-gray-500">No content available</p>
            </div>
          )}
          </div>
        </ScrollArea>
      </div>
    </div>
  )
}