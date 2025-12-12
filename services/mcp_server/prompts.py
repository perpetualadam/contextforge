"""
ContextForge MCP Prompts - Prompt templates for the MCP server.

This module defines prompt templates that are exposed through the MCP protocol,
providing pre-configured prompts for common ContextForge use cases.

Copyright (c) 2025 ContextForge
"""

import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_prompts(mcp: FastMCP) -> None:
    """Register all ContextForge prompts with the MCP server."""
    
    @mcp.prompt()
    def code_review(
        code: str,
        language: str = "python",
        focus: str = "general"
    ) -> str:
        """
        Generate a code review prompt for the given code.
        
        Args:
            code: The code to review
            language: Programming language of the code
            focus: Review focus (general, security, performance, style)
            
        Returns:
            A structured code review prompt
        """
        focus_instructions = {
            "general": "Review for correctness, readability, and best practices.",
            "security": "Focus on security vulnerabilities, input validation, and safe coding practices.",
            "performance": "Analyze for performance bottlenecks, memory usage, and optimization opportunities.",
            "style": "Check for code style, naming conventions, and documentation."
        }
        
        instruction = focus_instructions.get(focus, focus_instructions["general"])
        
        return f"""Please review the following {language} code:

```{language}
{code}
```

**Review Focus:** {focus.title()}
{instruction}

Please provide:
1. A summary of what the code does
2. Issues found (if any)
3. Suggestions for improvement
4. Overall assessment
"""
    
    @mcp.prompt()
    def explain_code(
        code: str,
        language: str = "python",
        detail_level: str = "medium"
    ) -> str:
        """
        Generate a prompt to explain the given code.
        
        Args:
            code: The code to explain
            language: Programming language of the code
            detail_level: Level of detail (brief, medium, detailed)
            
        Returns:
            A prompt for code explanation
        """
        detail_instructions = {
            "brief": "Provide a brief, high-level explanation.",
            "medium": "Explain the code with moderate detail, covering main concepts.",
            "detailed": "Provide a detailed line-by-line explanation with examples."
        }
        
        instruction = detail_instructions.get(detail_level, detail_instructions["medium"])
        
        return f"""Please explain the following {language} code:

```{language}
{code}
```

**Detail Level:** {detail_level.title()}
{instruction}

Include:
- What the code does
- Key concepts used
- How it works step by step
"""
    
    @mcp.prompt()
    def debug_error(
        error_message: str,
        code: Optional[str] = None,
        context: Optional[str] = None
    ) -> str:
        """
        Generate a debugging prompt for an error.
        
        Args:
            error_message: The error message or stack trace
            code: Optional code that caused the error
            context: Optional additional context
            
        Returns:
            A structured debugging prompt
        """
        prompt = f"""I'm encountering the following error:

```
{error_message}
```
"""
        
        if code:
            prompt += f"""
**Code that caused the error:**
```
{code}
```
"""
        
        if context:
            prompt += f"""
**Additional context:**
{context}
"""
        
        prompt += """
Please help me:
1. Understand what this error means
2. Identify the root cause
3. Suggest how to fix it
4. Provide any preventive measures
"""
        return prompt
    
    @mcp.prompt()
    def search_codebase_query(
        task: str,
        language: Optional[str] = None
    ) -> str:
        """
        Generate a search query for finding relevant code.
        
        Args:
            task: Description of what you're trying to accomplish
            language: Optional programming language filter
            
        Returns:
            A search query prompt
        """
        lang_filter = f" in {language}" if language else ""
        
        return f"""I need to find code{lang_filter} that helps with: {task}

Please search the codebase and:
1. Find relevant functions, classes, or modules
2. Explain how they relate to my task
3. Suggest how to use or adapt them
4. Note any dependencies or requirements
"""
    
    @mcp.prompt()
    def generate_tests(
        code: str,
        language: str = "python",
        framework: str = "pytest"
    ) -> str:
        """
        Generate a prompt for creating tests.
        
        Args:
            code: The code to test
            language: Programming language
            framework: Testing framework to use
            
        Returns:
            A test generation prompt
        """
        return f"""Please generate comprehensive tests for the following {language} code using {framework}:

```{language}
{code}
```

Include:
1. Unit tests for each function/method
2. Edge cases and boundary conditions
3. Error handling tests
4. Mock/stub setup if needed
5. Test documentation
"""
