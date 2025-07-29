// Test CORS in browser console
// Open browser console and paste this code

const API_BASE = 'https://fbm26vyfbw.us-east-1.awsapprunner.com';

console.log('🧪 Testing CORS functionality...');

// Test 1: Simple GET request
async function testHealthEndpoint() {
    console.log('\n1️⃣ Testing Health Endpoint (GET)...');
    try {
        const response = await fetch(`${API_BASE}/health`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log('✅ Health endpoint SUCCESS');
            console.log('📊 CORS origins configured:', data.cors_origins);
            console.log('🌍 Environment:', data.environment);
        } else {
            console.log('❌ Health endpoint failed:', response.status);
        }
    } catch (error) {
        console.log('💥 Health endpoint error:', error.message);
        if (error.message.includes('CORS')) {
            console.log('🚨 CORS ERROR DETECTED');
        }
    }
}

// Test 2: Projects endpoint (preflight request)  
async function testProjectsEndpoint() {
    console.log('\n2️⃣ Testing Projects Endpoint (GET with custom headers)...');
    try {
        const response = await fetch(`${API_BASE}/api/projects`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'  // This triggers preflight
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log('✅ Projects endpoint SUCCESS');
            console.log('📋 Found projects:', data.length);
        } else {
            console.log('❌ Projects endpoint failed:', response.status);
        }
    } catch (error) {
        console.log('💥 Projects endpoint error:', error.message);
        if (error.message.includes('CORS')) {
            console.log('🚨 CORS ERROR DETECTED');
        }
    }
}

// Test 3: POST request (definitely triggers preflight)
async function testCreateProject() {
    console.log('\n3️⃣ Testing Create Project (POST - triggers preflight)...');
    try {
        const response = await fetch(`${API_BASE}/api/projects`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer test-token'  // This triggers preflight
            },
            body: JSON.stringify({
                name: 'CORS Test Project',
                description: 'Testing CORS functionality',
                created_by: 'cors-test'
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log('✅ Create project SUCCESS');
            console.log('🆕 Created project:', data.slug);
        } else if (response.status === 400 || response.status === 422) {
            console.log('✅ Create project triggered preflight (validation error expected)');
        } else {
            console.log('❌ Create project failed:', response.status);
        }
    } catch (error) {
        console.log('💥 Create project error:', error.message);
        if (error.message.includes('CORS')) {
            console.log('🚨 CORS ERROR DETECTED');
        }
    }
}

// Test 4: Check CORS headers in response
async function testCORSHeaders() {
    console.log('\n4️⃣ Testing CORS Headers...');
    try {
        const response = await fetch(`${API_BASE}/health`);
        
        console.log('📋 Response Headers:');
        for (let [key, value] of response.headers.entries()) {
            if (key.toLowerCase().includes('access-control')) {
                console.log(`   ${key}: ${value}`);
            }
        }
    } catch (error) {
        console.log('💥 Headers test error:', error.message);
    }
}

// Run all tests
async function runAllTests() {
    console.log('🚀 Starting CORS test suite...\n');
    
    await testHealthEndpoint();
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    await testProjectsEndpoint();
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    await testCreateProject();
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    await testCORSHeaders();
    
    console.log('\n🏁 CORS tests completed!');
    console.log('💡 Check Network tab in DevTools for detailed CORS headers');
}

// Auto-run if this script is executed
runAllTests();