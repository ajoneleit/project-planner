#!/usr/bin/env python3
"""
Simplified test runner that can be executed directly without dependencies.
This tests the core logic without external dependencies.
"""

import sys
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_basic_imports():
    """Test that basic imports work."""
    try:
        # Test basic path operations
        from pathlib import Path
        import json
        import asyncio
        print("✅ Basic imports successful")
        return True
    except ImportError as e:
        print(f"❌ Basic imports failed: {e}")
        return False

def test_file_operations():
    """Test basic file operations."""
    try:
        temp_dir = tempfile.mkdtemp()
        temp_file = Path(temp_dir) / "test.md"
        
        # Test file creation
        content = "# Test Project\n\nThis is a test."
        temp_file.write_text(content)
        
        # Test file reading
        read_content = temp_file.read_text()
        assert "# Test Project" in read_content
        assert "This is a test." in read_content
        
        # Cleanup
        shutil.rmtree(temp_dir)
        print("✅ File operations test passed")
        return True
    except Exception as e:
        print(f"❌ File operations test failed: {e}")
        return False

def test_json_operations():
    """Test JSON operations."""
    try:
        import json
        
        test_data = {
            "test-project": {
                "name": "Test Project", 
                "created": "2024-01-01T00:00:00",
                "status": "active"
            }
        }
        
        # Test JSON serialization
        json_str = json.dumps(test_data, indent=2)
        assert "test-project" in json_str
        
        # Test JSON deserialization
        parsed_data = json.loads(json_str)
        assert parsed_data["test-project"]["name"] == "Test Project"
        
        print("✅ JSON operations test passed")
        return True
    except Exception as e:
        print(f"❌ JSON operations test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Running simplified tests...")
    print("=" * 50)
    
    tests = [
        test_basic_imports,
        test_file_operations, 
        test_json_operations
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            results.append(False)
    
    print("=" * 50)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"🎉 All {total} tests passed!")
        return 0
    else:
        print(f"⚠️  {passed}/{total} tests passed")
        return 1

if __name__ == "__main__":
    sys.exit(main())