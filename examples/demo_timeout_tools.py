# demo_timeout_tools.py
"""
Simple End-to-End Demo for CHUK MCP Runtime Timeout Testing

This demonstrates per-tool timeout configuration using only decorators.
No config.yaml needed - everything is self-contained.
"""

import asyncio
import time
import random
from typing import Dict, Any
from chuk_mcp_runtime.common.mcp_tool_decorator import mcp_tool

# ---------------------------------------------------------------------------
# Demo Tools with Different Timeout Behaviors
# ---------------------------------------------------------------------------


@mcp_tool(
    name="fast_tool",
    description="A tool that completes quickly (1-2 seconds)",
    timeout=5,  # 5 second timeout - should always succeed
)
async def fast_tool(message: str = "Hello") -> Dict[str, Any]:
    """Fast tool that always completes within timeout."""
    duration = random.uniform(1.0, 2.0)
    await asyncio.sleep(duration)

    return {
        "result": f"Fast tool completed: {message}",
        "duration": f"{duration:.1f}s",
        "status": "success",
    }


@mcp_tool(
    name="medium_tool",
    description="A tool that takes moderate time (3-7 seconds)",
    timeout=10,  # 10 second timeout - should usually succeed
)
async def medium_tool(complexity: int = 5) -> Dict[str, Any]:
    """Medium speed tool with variable duration."""
    duration = complexity * 1.2  # 1.2 to 12 seconds based on complexity
    await asyncio.sleep(duration)

    return {
        "result": f"Medium tool completed with complexity {complexity}",
        "duration": f"{duration:.1f}s",
        "complexity": complexity,
        "status": "success",
    }


@mcp_tool(
    name="slow_tool",
    description="A tool that takes a long time (8-12 seconds)",
    timeout=15,  # 15 second timeout - might succeed if patient
)
async def slow_tool(iterations: int = 8) -> Dict[str, Any]:
    """Slow tool that processes in iterations."""
    progress = []

    for i in range(iterations):
        await asyncio.sleep(1.0)
        progress.append(f"Step {i + 1}")

    return {
        "result": "Slow tool completed all iterations",
        "iterations": iterations,
        "progress": progress,
        "duration": f"{iterations}s",
        "status": "success",
    }


@mcp_tool(
    name="timeout_demo",
    description="A tool designed to demonstrate timeout behavior",
    timeout=6,  # 6 second timeout - will timeout with default params
)
async def timeout_demo(sleep_time: float = 8.0) -> Dict[str, Any]:
    """Tool that will likely timeout to demonstrate timeout handling."""
    print(f"🕐 Starting sleep for {sleep_time} seconds (timeout: 6s)...")
    await asyncio.sleep(sleep_time)

    return {
        "result": "This message should NOT appear if timeout works",
        "sleep_time": sleep_time,
        "status": "completed",
    }


@mcp_tool(
    name="no_timeout_tool",
    description="A tool that uses default timeout (no timeout specified)",
    # No timeout parameter - uses system default (60s)
)
async def no_timeout_tool(work_duration: int = 3) -> Dict[str, Any]:
    """Tool using default timeout from system."""
    await asyncio.sleep(work_duration)

    return {
        "result": "No timeout tool completed",
        "work_duration": work_duration,
        "timeout_source": "system_default",
        "status": "success",
    }


@mcp_tool(
    name="variable_tool",
    description="A tool with variable behavior for testing",
    timeout=12,
)
async def variable_tool(mode: str = "normal") -> Dict[str, Any]:
    """Tool with different behaviors based on mode."""
    durations = {
        "fast": 2.0,
        "normal": 5.0,
        "slow": 10.0,
        "timeout": 15.0,  # Will exceed 12s timeout
    }

    duration = durations.get(mode, 5.0)
    await asyncio.sleep(duration)

    return {
        "result": f"Variable tool completed in {mode} mode",
        "mode": mode,
        "duration": f"{duration}s",
        "status": "success",
    }


# ---------------------------------------------------------------------------
# Demo Runner Functions
# ---------------------------------------------------------------------------


async def run_timeout_demo():
    """Run the complete timeout demonstration."""
    print("🚀 CHUK MCP Runtime - Timeout Demo")
    print("=" * 50)

    # Initialize tools
    from chuk_mcp_runtime.common.mcp_tool_decorator import (
        initialize_tool_registry,
        TOOLS_REGISTRY,
        get_tool_timeout,
    )

    await initialize_tool_registry()

    # Show registered tools and their timeouts
    print("\n📋 Registered Tools:")
    for tool_name, func in TOOLS_REGISTRY.items():
        if hasattr(func, "_mcp_tool"):
            timeout = getattr(func, "_tool_timeout", None)
            effective_timeout = get_tool_timeout(tool_name, 60.0)
            source = "decorator" if timeout else "default"
            print(f"  🔧 {tool_name:<20} | {effective_timeout:>2}s | {source}")

    print("\n🧪 Running Test Scenarios:")
    print("-" * 50)

    # Test scenarios
    scenarios = [
        {
            "name": "Fast Tool Success",
            "tool": "fast_tool",
            "args": {"message": "Speed test"},
            "should_succeed": True,
        },
        {
            "name": "Medium Tool Normal",
            "tool": "medium_tool",
            "args": {"complexity": 4},
            "should_succeed": True,
        },
        {
            "name": "Medium Tool Heavy",
            "tool": "medium_tool",
            "args": {"complexity": 8},
            "should_succeed": True,
        },
        {
            "name": "Timeout Demo (Will Timeout)",
            "tool": "timeout_demo",
            "args": {"sleep_time": 8.0},
            "should_succeed": False,
        },
        {
            "name": "Variable Tool Fast",
            "tool": "variable_tool",
            "args": {"mode": "fast"},
            "should_succeed": True,
        },
        {
            "name": "Variable Tool Timeout",
            "tool": "variable_tool",
            "args": {"mode": "timeout"},
            "should_succeed": False,
        },
        {
            "name": "No Timeout Tool",
            "tool": "no_timeout_tool",
            "args": {"work_duration": 2},
            "should_succeed": True,
        },
    ]

    results = []

    for scenario in scenarios:
        print(f"\n🎯 {scenario['name']}:")
        result = await run_single_test(
            scenario["tool"], scenario["args"], scenario["should_succeed"]
        )
        results.append({**scenario, **result})

    # Summary
    print("\n📊 Test Results Summary:")
    print("-" * 50)
    successes = sum(1 for r in results if r["actual_success"])
    timeouts = sum(1 for r in results if r["timed_out"])
    errors = sum(1 for r in results if r["had_error"] and not r["timed_out"])

    print(f"✅ Successful completions: {successes}")
    print(f"⏰ Timeouts (expected): {timeouts}")
    print(f"❌ Unexpected errors: {errors}")
    print(f"🎯 Total scenarios: {len(results)}")

    # Detailed results
    print("\n📝 Detailed Results:")
    for result in results:
        status_icon = (
            "✅"
            if result["actual_success"]
            else ("⏰" if result["timed_out"] else "❌")
        )
        expected = "✓" if result["should_succeed"] == result["actual_success"] else "✗"
        print(
            f"  {status_icon} {result['name']:<25} | {result['duration']:<8} | Expected: {expected}"
        )


async def run_single_test(
    tool_name: str, args: Dict[str, Any], should_succeed: bool
) -> Dict[str, Any]:
    """Run a single test scenario."""
    from chuk_mcp_runtime.common.mcp_tool_decorator import (
        execute_tool,
        get_tool_timeout,
    )

    timeout = get_tool_timeout(tool_name, 60.0)
    start_time = time.time()

    try:
        print(f"  🔄 Executing {tool_name} (timeout: {timeout}s)...", end=" ")

        # Execute with timeout
        result = await asyncio.wait_for(
            execute_tool(tool_name, **args), timeout=timeout
        )

        duration = time.time() - start_time
        print(f"✅ Success ({duration:.1f}s)")

        return {
            "actual_success": True,
            "timed_out": False,
            "had_error": False,
            "duration": f"{duration:.1f}s",
            "result": result,
        }

    except asyncio.TimeoutError:
        duration = time.time() - start_time
        print(f"⏰ Timeout ({duration:.1f}s)")

        return {
            "actual_success": False,
            "timed_out": True,
            "had_error": False,
            "duration": f"{duration:.1f}s",
            "result": None,
        }

    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ Error ({duration:.1f}s): {e}")

        return {
            "actual_success": False,
            "timed_out": False,
            "had_error": True,
            "duration": f"{duration:.1f}s",
            "error": str(e),
        }


if __name__ == "__main__":
    print("🎯 CHUK MCP Runtime Timeout Demo")
    print("This demo shows per-tool timeout configuration using decorators only.")
    print("No config.yaml needed - everything is self-contained!\n")

    # Run the complete demo
    asyncio.run(run_timeout_demo())

    print("\n🎉 Demo completed! This demonstrates:")
    print("  • Per-tool timeout configuration via @mcp_tool decorator")
    print("  • Automatic timeout enforcement")
    print("  • Graceful timeout handling")
    print("  • Default timeout fallback for tools without explicit timeouts")
    print("\n👋 End of demo.")
