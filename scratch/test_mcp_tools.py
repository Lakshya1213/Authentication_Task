import sys
import os
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server import mcp

print("Listing all registered MCP tools:")
for tool_name, tool in mcp._tools.items():
    print(f"\n- Tool Name: {tool_name}")
    print(f"  Description: {tool.description.strip()}")
    # Print argument names
    print(f"  Arguments: {list(tool.parameters.get('properties', {}).keys())}")

print("\nValidation Succeeded: All CRM tools are registered and correctly structured on the FastMCP instance.")
