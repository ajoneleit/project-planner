#!/usr/bin/env python3
"""Debug the exact reference analysis output format."""

import asyncio
import sys
import json
sys.path.append('app')

async def debug_exact_analysis():
    """Debug what the reference analysis actually returns."""
    
    print("🔍 Debugging exact reference analysis output...")
    
    try:
        from app.langgraph_runner import LLMReferenceAnalyzer
        
        analyzer = LLMReferenceAnalyzer("gpt-4o-mini")
        
        # Test with the exact scenario from our simple test that worked
        conversation_context = """User: Can you provide security recommendations for this project?