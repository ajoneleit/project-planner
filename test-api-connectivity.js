#!/usr/bin/env node

const https = require('https');
const http = require('http');

const TEST_SCENARIOS = [
  {
    name: 'Local Development',
    urls: [
      'http://localhost:8000',
      'http://127.0.0.1:8000',
    ]
  },
  {
    name: 'Docker Container',
    urls: [
      'http://localhost:8001',
    ]
  }
];

const ENDPOINTS_TO_TEST = [
  { path: '/health', method: 'GET' },
  { path: '/api/projects', method: 'GET' },
  { path: '/api/projects', method: 'OPTIONS' },
];

const CORS_ORIGINS = [
  'http://localhost:3000',
  'http://localhost:3001',
  'http://127.0.0.1:3000',
];

async function makeRequest(url, options = {}) {
  return new Promise((resolve, reject) => {
    const isHttps = url.startsWith('https:');
    const client = isHttps ? https : http;
    
    const req = client.request(url, options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        resolve({
          statusCode: res.statusCode,
          headers: res.headers,
          data: data,
          success: res.statusCode < 400
        });
      });
    });
    
    req.on('error', reject);
    req.setTimeout(5000, () => reject(new Error('Timeout')));
    
    if (options.body) {
      req.write(options.body);
    }
    
    req.end();
  });
}

async function testEndpoint(baseUrl, endpoint, origin = null) {
  const url = `${baseUrl}${endpoint.path}`;
  const options = {
    method: endpoint.method,
    headers: {
      'Content-Type': 'application/json',
    }
  };
  
  if (origin) {
    options.headers['Origin'] = origin;
  }
  
  try {
    console.log(`  Testing ${endpoint.method} ${url}${origin ? ` (Origin: ${origin})` : ''}`);
    const result = await makeRequest(url, options);
    
    if (result.success) {
      console.log(`    ✅ ${result.statusCode} - OK`);
      
      // Check CORS headers if origin was provided
      if (origin) {
        const corsHeader = result.headers['access-control-allow-origin'];
        if (corsHeader && (corsHeader === origin || corsHeader === '*')) {
          console.log(`    ✅ CORS header present: ${corsHeader}`);
        } else {
          console.log(`    ❌ CORS header missing or incorrect: ${corsHeader}`);
        }
      }
      
      return true;
    } else {
      console.log(`    ❌ ${result.statusCode} - Failed`);
      return false;
    }
  } catch (error) {
    console.log(`    ❌ Error: ${error.message}`);
    return false;
  }
}

async function runTests() {
  console.log('🚀 Starting API Connectivity Tests\n');
  
  let totalTests = 0;
  let passedTests = 0;
  
  for (const scenario of TEST_SCENARIOS) {
    console.log(`📋 Testing ${scenario.name}:`);
    
    for (const baseUrl of scenario.urls) {
      console.log(`\n  Base URL: ${baseUrl}`);
      
      // Test basic endpoints
      for (const endpoint of ENDPOINTS_TO_TEST) {
        totalTests++;
        const success = await testEndpoint(baseUrl, endpoint);
        if (success) passedTests++;
      }
      
      // Test CORS for GET requests
      for (const origin of CORS_ORIGINS) {
        totalTests++;
        const success = await testEndpoint(baseUrl, { path: '/api/projects', method: 'GET' }, origin);
        if (success) passedTests++;
      }
    }
    
    console.log('');
  }
  
  console.log(`\n📊 Test Results: ${passedTests}/${totalTests} passed`);
  
  if (passedTests === totalTests) {
    console.log('🎉 All tests passed!');
    process.exit(0);
  } else {
    console.log('❌ Some tests failed');
    process.exit(1);
  }
}

// Run tests
runTests().catch(console.error);