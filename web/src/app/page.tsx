'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, AlertCircle, RefreshCw, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { apiRequest, healthCheck } from '@/lib/api'

interface Project {
  slug: string
  name: string
  created: string
  status: string
}

async function fetchProjects(): Promise<Project[]> {
  return apiRequest<Project[]>('/api/projects')
}

interface CreateProjectData {
  name: string
  description: string
}

async function createProject(data: CreateProjectData): Promise<{ slug: string; message: string }> {
  return apiRequest<{ slug: string; message: string }>('/api/projects', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export default function HomePage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null)
  
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [newProjectDescription, setNewProjectDescription] = useState('')
  
  const { data: projects, isLoading, error, refetch } = useQuery({
    queryKey: ['projects'],
    queryFn: fetchProjects,
    retry: 3,
    retryDelay: 1000,
  })

  // Check API health on mount
  useEffect(() => {
    const checkHealth = async () => {
      const healthy = await healthCheck()
      setApiHealthy(healthy)
      
      if (!healthy) {
        console.warn('API health check failed')
      }
    }
    
    checkHealth()
  }, [])

  const createProjectMutation = useMutation({
    mutationFn: createProject,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setCreateDialogOpen(false)
      setNewProjectName('')
      setNewProjectDescription('')
      router.push(`/p/${data.slug}`)
    },
    onError: (error) => {
      console.error('Failed to create project:', error)
    }
  })

  const handleCreateProject = () => {
    if (newProjectName.trim()) {
      createProjectMutation.mutate({
        name: newProjectName.trim(),
        description: newProjectDescription.trim(),
      })
    }
  }

  const handleRetry = () => {
    setApiHealthy(null)
    refetch()
  }

  useEffect(() => {
    if (projects && projects.length > 0) {
      // Redirect to the first project
      router.push(`/p/${projects[0].slug}`)
    }
  }, [projects, router])

  if (isLoading || apiHealthy === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="flex items-center justify-center space-x-2 mb-4">
            <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
            <span className="text-lg font-medium">Loading Project Planner...</span>
          </div>
          <p className="text-gray-600">
            {apiHealthy === null ? 'Checking system health...' : 'Loading projects...'}
          </p>
        </div>
      </div>
    )
  }

  if (error || apiHealthy === false) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-md">
          <div className="flex items-center justify-center mb-4">
            <AlertCircle className="h-12 w-12 text-red-500" />
          </div>
          
          <h1 className="text-2xl font-bold text-gray-900 mb-4">
            Connection Error
          </h1>
          
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-red-800 text-sm font-medium mb-2">
              Unable to connect to the backend service
            </p>
            <p className="text-red-600 text-sm">
              {error instanceof Error ? error.message : 'Service unavailable'}
            </p>
          </div>
          
          <div className="space-y-3">
            <Button onClick={handleRetry} className="w-full">
              <RefreshCw className="h-4 w-4 mr-2" />
              Try Again
            </Button>
            
            <details className="text-left">
              <summary className="text-sm text-gray-500 cursor-pointer hover:text-gray-700">
                Troubleshooting Steps
              </summary>
              <div className="mt-2 text-xs text-gray-600 space-y-1">
                <p>• Ensure the backend server is running (port 8000)</p>
                <p>• Check network connectivity</p>
                <p>• Verify CORS configuration</p>
                <p>• Check browser console for detailed errors</p>
              </div>
            </details>
          </div>
        </div>
      </div>
    )
  }

  if (!projects || projects.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">No Projects Found</h1>
          <p className="text-gray-600 mb-6">Create your first project to get started</p>
          
          <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button size="lg">
                <Plus className="h-5 w-5 mr-2" />
                Create Your First Project
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New Project</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium">Project Name</label>
                  <Input
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    placeholder="Enter project name..."
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Description (Optional)</label>
                  <Textarea
                    value={newProjectDescription}
                    onChange={(e) => setNewProjectDescription(e.target.value)}
                    placeholder="Describe your project..."
                    className="mt-1"
                    rows={3}
                  />
                </div>
                <div className="flex justify-end space-x-2">
                  <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button 
                    onClick={handleCreateProject}
                    disabled={!newProjectName.trim() || createProjectMutation.isPending}
                  >
                    {createProjectMutation.isPending && (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    )}
                    Create Project
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="flex items-center space-x-2">
        <Loader2 className="h-6 w-6 animate-spin" />
        <span>Redirecting to project...</span>
      </div>
    </div>
  )
}
