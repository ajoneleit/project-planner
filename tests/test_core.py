import pytest
import tempfile
import shutil
import sys
import json
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.langgraph_runner import (
    MarkdownMemory, 
    ProjectRegistry, 
    make_graph,
    stream_chat_response,
    INDEX_FILE
)
from app.main import app

try:
    from fastapi.testclient import TestClient
except ImportError:
    # Fallback for testing without FastAPI installed
    TestClient = None

# Test fixtures
@pytest.fixture
def temp_memory_dir():
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    
    # Mock the memory directory
    with patch('app.langgraph_runner.MEMORY_DIR', Path(temp_dir)):
        with patch('app.langgraph_runner.INDEX_FILE', Path(temp_dir) / "index.json"):
            yield Path(temp_dir)
    
    # Cleanup
    shutil.rmtree(temp_dir)

@pytest.fixture
def client():
    """FastAPI test client."""
    if TestClient is None:
        pytest.skip("FastAPI not available for testing")
    return TestClient(app)

# Test MarkdownMemory
@pytest.mark.asyncio
async def test_markdown_memory_creation(temp_memory_dir):
    """Test markdown file creation and initial content."""
    _ = temp_memory_dir  # Use the fixture to avoid warning
    memory = MarkdownMemory("test-project")
    
    await memory.ensure_file_exists()
    
    assert memory.file_path.exists()
    content = await memory.read_content()
    assert "# Test Project" in content
    assert "## Conversation History" in content
    assert "Created:" in content

@pytest.mark.asyncio
async def test_markdown_memory_append_qa(temp_memory_dir):
    """Test appending Q&A pairs to markdown."""
    _ = temp_memory_dir  # Use the fixture to avoid warning
    memory = MarkdownMemory("test-project")
    
    await memory.ensure_file_exists()
    await memory.append_qa("What is this project?", "This is a test project.")
    
    content = await memory.read_content()
    assert "### Q: What is this project?" in content
    assert "**A:** This is a test project." in content

@pytest.mark.asyncio
async def test_markdown_memory_conversation_history(temp_memory_dir):
    """Test extracting conversation history."""
    _ = temp_memory_dir  # Use the fixture to avoid warning
    memory = MarkdownMemory("test-project")
    
    await memory.ensure_file_exists()
    await memory.append_qa("Question 1", "Answer 1")
    await memory.append_qa("Question 2", "Answer 2")
    
    history = await memory.get_conversation_history()
    assert "Question 1" in history
    assert "Question 2" in history
    assert history.startswith("## Conversation History")

# Test ProjectRegistry
@pytest.mark.asyncio
async def test_project_registry_operations(temp_memory_dir):
    """Test project registry CRUD operations."""
    _ = temp_memory_dir  # Use the fixture to avoid warning
    # Test empty registry
    index = await ProjectRegistry.load_index()
    assert index == {}
    
    # Test adding project
    await ProjectRegistry.add_project("test-project", {"name": "Test Project"})
    
    # Test loading updated registry
    index = await ProjectRegistry.load_index()
    assert "test-project" in index
    assert index["test-project"]["name"] == "Test Project"
    assert "created" in index["test-project"]
    
    # Test listing projects
    projects = await ProjectRegistry.list_projects()
    assert projects == index

# Test API endpoints
def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "project-planner-bot"}

@pytest.mark.asyncio
async def test_create_project_endpoint(client, temp_memory_dir):
    """Test project creation endpoint."""
    _ = temp_memory_dir  # Use the fixture to avoid warning
    
    # Patch the correct import paths
    with patch('app.langgraph_runner.ProjectRegistry') as mock_registry:
        mock_registry.list_projects = AsyncMock(return_value={})
        mock_registry.add_project = AsyncMock()
        
        with patch('app.langgraph_runner.MarkdownMemory') as mock_memory:
            mock_memory_instance = AsyncMock()
            mock_memory.return_value = mock_memory_instance
            
            response = client.post("/api/projects", json={
                "name": "Test Project",
                "description": "A test project"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["slug"] == "test-project"
            assert "created successfully" in data["message"]
            
            # Verify the mocks were called
            mock_registry.list_projects.assert_called_once()
            mock_registry.add_project.assert_called_once()
            mock_memory_instance.ensure_file_exists.assert_called_once()

@pytest.mark.asyncio
async def test_list_projects_endpoint(client):
    """Test project listing endpoint."""
    mock_projects = {
        "test-project": {
            "name": "Test Project",
            "created": "2024-01-01T00:00:00",
            "status": "active"
        }
    }
    
    # Patch the correct import path
    with patch('app.langgraph_runner.ProjectRegistry') as mock_registry:
        mock_registry.list_projects = AsyncMock(return_value=mock_projects)
        
        response = client.get("/api/projects")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["slug"] == "test-project"
        assert data[0]["name"] == "Test Project"
        assert data[0]["status"] == "active"
        
        # Verify the mock was called
        mock_registry.list_projects.assert_called_once()

# Test LangGraph integration
@pytest.mark.asyncio
async def test_make_graph_creation(temp_memory_dir):
    """Test LangGraph workflow creation."""
    _ = temp_memory_dir  # Use the fixture to avoid warning
    with patch('app.langgraph_runner.ChatOpenAI') as mock_llm:
        mock_llm.return_value = AsyncMock()
        
        graph = make_graph("test-project", "gpt-4o-mini")
        
        assert graph is not None
        mock_llm.assert_called_once_with(
            model="gpt-4o-mini",
            temperature=0.1,
            streaming=True
        )

@pytest.mark.asyncio 
async def test_stream_chat_response(temp_memory_dir):
    """Test streaming chat response."""
    _ = temp_memory_dir  # Use the fixture to avoid warning
    
    with patch('app.langgraph_runner.make_graph') as mock_make_graph:
        # Mock the graph and its streaming response
        mock_graph = AsyncMock()
        mock_response = AsyncMock()
        mock_response.content = "Test response from AI"
        
        async def mock_astream(*_args, **_kwargs):
            yield [mock_response]
        
        mock_graph.astream = mock_astream
        mock_make_graph.return_value = mock_graph
        
        # Test streaming
        chunks = []
        async for chunk in stream_chat_response("test-project", "Hello", "gpt-4o-mini"):
            chunks.append(chunk)
        
        assert len(chunks) > 0
        
        # Parse the SSE formatted chunks to extract content
        collected_tokens = []
        for chunk in chunks:
            if chunk.startswith("data: "):
                try:
                    # Extract JSON from SSE format
                    json_str = chunk[6:]  # Remove "data: " prefix
                    if json_str.strip():  # Skip empty lines
                        data = json.loads(json_str.strip())
                        if 'token' in data:
                            collected_tokens.append(data['token'])
                        elif 'done' in data and data['done']:
                            break
                except json.JSONDecodeError:
                    continue  # Skip malformed JSON
        
        # Verify we collected tokens from the mocked response
        full_response = ''.join(collected_tokens)
        assert "Test response from AI" in full_response, f"Expected 'Test response from AI' in '{full_response}'"

# Integration test
@pytest.mark.asyncio
async def test_full_project_workflow(temp_memory_dir):
    """Test complete project creation and chat workflow."""
    _ = temp_memory_dir  # Use the fixture to avoid warning
    # Create project
    await ProjectRegistry.add_project("integration-test", {"name": "Integration Test"})
    
    # Initialize memory
    memory = MarkdownMemory("integration-test")
    await memory.ensure_file_exists()
    
    # Simulate Q&A
    await memory.append_qa("What should I do first?", "Start by defining your project goals.")
    
    # Verify content
    content = await memory.read_content()
    assert "Integration Test" in content
    assert "What should I do first?" in content
    assert "Start by defining your project goals." in content
    
    # Verify project in registry
    projects = await ProjectRegistry.list_projects()
    assert "integration-test" in projects
    assert projects["integration-test"]["name"] == "Integration Test"

# Test file operations endpoint
@pytest.mark.asyncio
async def test_get_project_file_endpoint(client, temp_memory_dir):
    """Test getting project markdown file content."""
    _ = temp_memory_dir  # Use the fixture to avoid warning
    
    mock_projects = {"test-project": {"name": "Test Project"}}
    mock_content = "# Test Project\n\nThis is test content."
    
    with patch('app.langgraph_runner.ProjectRegistry') as mock_registry:
        mock_registry.list_projects = AsyncMock(return_value=mock_projects)
        
        with patch('app.langgraph_runner.MarkdownMemory') as mock_memory:
            mock_memory_instance = AsyncMock()
            mock_memory_instance.read_content = AsyncMock(return_value=mock_content)
            mock_memory.return_value = mock_memory_instance
            
            response = client.get("/api/projects/test-project/file")
            
            assert response.status_code == 200
            data = response.json()
            assert data["content"] == mock_content
            
            # Verify mocks were called
            mock_registry.list_projects.assert_called_once()
            mock_memory_instance.read_content.assert_called_once()

# Test error handling
@pytest.mark.asyncio
async def test_create_project_endpoint_duplicate_handling(client, temp_memory_dir):
    """Test project creation with duplicate name handling."""
    _ = temp_memory_dir  # Use the fixture to avoid warning
    
    # Mock existing project with same slug
    existing_projects = {"test-project": {"name": "Existing Project"}}
    
    with patch('app.langgraph_runner.ProjectRegistry') as mock_registry:
        mock_registry.list_projects = AsyncMock(return_value=existing_projects)
        mock_registry.add_project = AsyncMock()
        
        with patch('app.langgraph_runner.MarkdownMemory') as mock_memory:
            mock_memory_instance = AsyncMock()
            mock_memory.return_value = mock_memory_instance
            
            response = client.post("/api/projects", json={
                "name": "Test Project",  # Will create slug "test-project"
                "description": "A duplicate test project"
            })
            
            assert response.status_code == 200
            data = response.json()
            # Should get a unique slug due to conflict resolution
            assert data["slug"] == "test-project-1"
            assert "created successfully" in data["message"]

@pytest.mark.asyncio
async def test_chat_endpoint_project_not_found(client):
    """Test chat endpoint with non-existent project."""
    with patch('app.langgraph_runner.ProjectRegistry') as mock_registry:
        mock_registry.list_projects = AsyncMock(return_value={})
        
        response = client.post("/api/projects/nonexistent/chat", json={
            "message": "Hello",
            "model": "gpt-4o-mini"
        })
        
        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

@pytest.mark.asyncio  
async def test_get_file_endpoint_project_not_found(client):
    """Test file endpoint with non-existent project."""
    with patch('app.langgraph_runner.ProjectRegistry') as mock_registry:
        mock_registry.list_projects = AsyncMock(return_value={})
        
        response = client.get("/api/projects/nonexistent/file")
        
        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_chat_endpoint_streaming_error_handling(client, temp_memory_dir):
    """Test chat endpoint error handling during streaming."""
    _ = temp_memory_dir  # Use the fixture to avoid warning
    
    mock_projects = {"test-project": {"name": "Test Project"}}
    
    with patch('app.langgraph_runner.ProjectRegistry') as mock_registry:
        mock_registry.list_projects = AsyncMock(return_value=mock_projects)
        
        with patch('app.langgraph_runner.stream_chat_response') as mock_stream:
            # Mock streaming function that raises an error
            async def error_stream(*args, **kwargs):
                yield f"data: {json.dumps({'error': 'Simulated streaming error'})}\n\n"
            
            mock_stream.return_value = error_stream()
            
            response = client.post("/api/projects/test-project/chat", json={
                "message": "Hello",
                "model": "gpt-4o-mini"
            })
            
            # Should still return 200 for streaming responses
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream"

@pytest.mark.asyncio
async def test_project_registry_empty_file_handling(temp_memory_dir):
    """Test ProjectRegistry handling of empty index file."""
    _ = temp_memory_dir  # Use the fixture to avoid warning
    
    # Test with non-existent file
    index = await ProjectRegistry.load_index()
    assert index == {}
    
    # Test with empty file
    INDEX_FILE.parent.mkdir(exist_ok=True)
    INDEX_FILE.write_text("")
    
    index = await ProjectRegistry.load_index()
    assert index == {}
    
    # Test saving and loading
    test_data = {"test": {"name": "Test"}}
    await ProjectRegistry.save_index(test_data)
    
    loaded_data = await ProjectRegistry.load_index()
    assert loaded_data == test_data

@pytest.mark.asyncio
async def test_markdown_memory_concurrent_access(temp_memory_dir):
    """Test MarkdownMemory with concurrent access (locking behavior)."""
    _ = temp_memory_dir  # Use the fixture to avoid warning
    
    memory = MarkdownMemory("concurrent-test")
    
    # Test concurrent file creation
    async def create_and_append(suffix):
        await memory.ensure_file_exists()
        await memory.append_qa(f"Question {suffix}", f"Answer {suffix}")
    
    # Run concurrent operations
    await asyncio.gather(
        create_and_append("1"),
        create_and_append("2"),
        create_and_append("3")
    )
    
    # Verify all content was written
    content = await memory.read_content()
    assert "Question 1" in content
    assert "Question 2" in content
    assert "Question 3" in content
    assert "Answer 1" in content
    assert "Answer 2" in content
    assert "Answer 3" in content

if __name__ == "__main__":
    pytest.main([__file__, "-v"])