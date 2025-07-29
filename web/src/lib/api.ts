// API configuration with environment detection and fallbacks

export interface ApiConfig {
  baseUrl: string
  timeout: number
  retries: number
}

// Function to get current user ID - will be set by user context
let getCurrentUserIdFn: (() => string) | null = null

// Set the user ID getter function (called by UserProvider)
export function setUserIdGetter(getUserId: () => string) {
  getCurrentUserIdFn = getUserId
}

// Get current user ID for API requests
function getCurrentUserId(): string {
  return getCurrentUserIdFn ? getCurrentUserIdFn() : 'anonymous'
}

function detectEnvironment(): 'development' | 'production' | 'static' {
  if (typeof window === 'undefined') {
    return 'development' // SSR fallback
  }
  
  const hostname = window.location.hostname
  const protocol = window.location.protocol
  
  // Production detection
  if (hostname !== 'localhost' && hostname !== '127.0.0.1' && !hostname.startsWith('192.168')) {
    return 'production'
  }
  
  // Static file serving detection
  if (protocol === 'file:' || window.location.port === '') {
    return 'static'
  }
  
  return 'development'
}

function getApiBaseUrl(): string {
  // Check for explicit API URL override first
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL
  }
  
  // Handle SSR - return default URL for server-side rendering
  if (typeof window === 'undefined') {
    return 'http://localhost:8000'
  }
  
  const env = detectEnvironment()
  
  switch (env) {
    case 'production':
      // In production, API is served from same origin
      return window.location.origin
      
    case 'static':
      // Static files served by FastAPI
      return window.location.origin
      
    case 'development':
    default:
      // Development: try to connect to backend on standard port
      const hostname = window.location.hostname
      
      // Try common backend ports in order
      const backendPorts = [8000, 8001, 5000]
      const preferredPort = process.env.NEXT_PUBLIC_API_PORT ? 
        parseInt(process.env.NEXT_PUBLIC_API_PORT) : 8000
      
      // Put preferred port first
      const ports = [preferredPort, ...backendPorts.filter(p => p !== preferredPort)]
      
      // For development, return the first port (will be tested by health check)
      return `http://${hostname}:${ports[0]}`
  }
}

export const apiConfig: ApiConfig = {
  baseUrl: getApiBaseUrl(),
  timeout: 30000, // 30 seconds
  retries: 3
}

// Enhanced fetch with retries and error handling
export async function apiRequest<T>(
  endpoint: string, 
  options: RequestInit = {}
): Promise<T> {
  let lastError: Error | null = null
  
  // Enhance request with user_id for chat endpoints
  const enhancedOptions = { ...options }
  
  // Add user_id to chat requests in the request body
  if (endpoint.includes('/chat') && enhancedOptions.method === 'POST') {
    try {
      const body = enhancedOptions.body ? JSON.parse(enhancedOptions.body as string) : {}
      body.user_id = getCurrentUserId()
      enhancedOptions.body = JSON.stringify(body)
    } catch (error) {
      console.warn('Failed to add user_id to chat request:', error)
    }
  }
  
  // Try AWS URL first, then fallback to local ports in development
  const env = detectEnvironment()
  const hostsToTry = env === 'development' && typeof window !== 'undefined' ? [
    apiConfig.baseUrl, // AWS URL first
    `${window.location.protocol}//${window.location.hostname}:8000`,
    `${window.location.protocol}//${window.location.hostname}:8001`,
    `${window.location.protocol}//${window.location.hostname}:5000`
  ].filter((v, i, a) => a.indexOf(v) === i) : [apiConfig.baseUrl] // Remove duplicates
  
  for (const baseUrl of hostsToTry) {
    const fullUrl = `${baseUrl}${endpoint}`
    
    try {
      console.log(`Attempting API request to: ${fullUrl}`)
      
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), apiConfig.timeout)
      
      const response = await fetch(fullUrl, {
        ...enhancedOptions,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...enhancedOptions.headers,
        }
      })
      
      clearTimeout(timeoutId)
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      console.log(`API request successful: ${fullUrl}`)
      
      // Update config with working base URL for future requests
      if (baseUrl !== apiConfig.baseUrl) {
        console.log(`Updating API base URL from ${apiConfig.baseUrl} to ${baseUrl}`)
        apiConfig.baseUrl = baseUrl
      }
      
      return data
      
    } catch (error) {
      console.warn(`API request failed for ${fullUrl}:`, error)
      lastError = error as Error
      
      // If it's a network error and we're in development, try next host
      if (env === 'development' && baseUrl !== hostsToTry[hostsToTry.length - 1]) {
        continue
      }
      
      // For non-development or last attempt, throw error
      break
    }
  }
  
  // If all attempts failed, throw the last error
  throw new Error(`API request failed after trying ${hostsToTry.length} endpoints. Last error: ${lastError?.message}`)
}

// Streaming API request for chat  
export async function apiStreamRequest(
  endpoint: string,
  options: RequestInit = {}
): Promise<ReadableStream<Uint8Array> | null> {
  const url = `${apiConfig.baseUrl}${endpoint}`
  
  // Enhance request with user_id for chat endpoints
  const enhancedOptions = { ...options }
  
  // Add user_id to chat requests in the request body
  if (endpoint.includes('/chat') && enhancedOptions.method === 'POST') {
    try {
      const body = enhancedOptions.body ? JSON.parse(enhancedOptions.body as string) : {}
      body.user_id = getCurrentUserId()
      enhancedOptions.body = JSON.stringify(body)
    } catch (error) {
      console.warn('Failed to add user_id to stream chat request:', error)
    }
  }
  
  try {
    console.log(`Starting stream request to: ${url}`)
    
    const response = await fetch(url, {
      ...enhancedOptions,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        ...enhancedOptions.headers,
      }
    })
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    
    return response.body
    
  } catch (error) {
    console.error(`Stream request failed for ${url}:`, error)
    throw error
  }
}

// Project management functions
export async function archiveProject(slug: string): Promise<{ message: string }> {
  return apiRequest<{ message: string }>(`/api/projects/${slug}/archive`, {
    method: 'PUT'
  })
}

export async function unarchiveProject(slug: string): Promise<{ message: string }> {
  return apiRequest<{ message: string }>(`/api/projects/${slug}/unarchive`, {
    method: 'PUT'
  })
}

export async function deleteProject(slug: string): Promise<{ message: string }> {
  return apiRequest<{ message: string }>(`/api/projects/${slug}`, {
    method: 'DELETE'
  })
}

export async function fetchArchivedProjects(): Promise<Array<{
  slug: string
  name: string
  created: string
  status: string
}>> {
  return apiRequest<Array<{
    slug: string
    name: string
    created: string
    status: string
  }>>('/api/projects/archived')
}

// Health check to verify API connectivity
export async function healthCheck(): Promise<boolean> {
  try {
    const health = await apiRequest<{status: string}>('/health')
    return health.status === 'healthy'
  } catch {
    return false
  }
}