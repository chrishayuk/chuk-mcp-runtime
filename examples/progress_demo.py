"""
Automated Progress Demo

Demonstrates progress reporting by running demo tools and displaying
real-time progress notifications with visual progress bars.

This example shows:
1. Step-based progress (N/total)
2. Percentage progress (0.0-1.0)
3. Multi-stage task progress
4. Batch processing progress
5. Detailed progress with custom messages
"""

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock

from chuk_mcp_runtime.common.mcp_tool_decorator import mcp_tool
from chuk_mcp_runtime.server.request_context import (
    MCPRequestContext,
    send_progress,
    set_request_context,
)

# ═══════════════════════════════════════════════════════════════════
# DEMO TOOLS
# ═══════════════════════════════════════════════════════════════════


@mcp_tool(name="process_items", description="Process a list of items with progress reporting")
async def process_items_tool(items: List[str]) -> Dict[str, Any]:
    """
    Process items one by one, reporting progress after each item.

    This demonstrates step-based progress reporting where each step
    represents processing one item.

    Args:
        items: List of items to process

    Returns:
        Dictionary with processed items and count
    """
    total = len(items)
    processed = []

    for i, item in enumerate(items, 1):
        # Report progress for current step
        await send_progress(progress=i, total=total, message=f"Processing: {item}")

        # Simulate some work
        await asyncio.sleep(0.5)

        # Process the item
        processed.append(f"processed_{item}")

    return {
        "processed": processed,
        "count": len(processed),
        "message": f"Successfully processed {len(processed)} items",
    }


@mcp_tool(
    name="long_computation",
    description="Perform a long computation with percentage progress",
)
async def long_computation_tool(iterations: int = 100) -> Dict[str, Any]:
    """
    Perform a computation with percentage-based progress reporting.

    This demonstrates percentage-based progress (0.0 to 1.0) which is
    useful for operations where you can calculate percent complete.

    Args:
        iterations: Number of computation iterations

    Returns:
        Dictionary with computation result
    """
    result = 0

    for i in range(iterations):
        # Calculate percentage complete (0.0 to 1.0)
        progress = (i + 1) / iterations

        # Report progress every 10%
        if (i + 1) % max(1, iterations // 10) == 0 or i == iterations - 1:
            percent = int(progress * 100)
            await send_progress(
                progress=progress,
                total=1.0,
                message=f"Computing... {percent}% complete",
            )

        # Simulate computation
        await asyncio.sleep(0.05)
        result += i

    return {
        "result": result,
        "iterations": iterations,
        "message": "Computation complete",
    }


@mcp_tool(
    name="download_files",
    description="Simulate downloading multiple files with progress",
)
async def download_files_tool(file_urls: List[str]) -> Dict[str, Any]:
    """
    Simulate downloading files with detailed progress reporting.

    This demonstrates more granular progress reporting with custom
    messages for different stages of processing.

    Args:
        file_urls: List of file URLs to download

    Returns:
        Dictionary with download results
    """
    downloaded = []
    total_files = len(file_urls)

    for i, url in enumerate(file_urls, 1):
        # Report starting download
        await send_progress(
            progress=i - 0.5,  # Halfway through this file
            total=total_files,
            message=f"Downloading {url}...",
        )

        # Simulate download
        await asyncio.sleep(0.7)

        # Report completed download
        await send_progress(progress=i, total=total_files, message=f"Downloaded {url}")

        downloaded.append(
            {
                "url": url,
                "status": "success",
                "size": len(url) * 1024,  # Fake size
            }
        )

    return {
        "downloaded": downloaded,
        "total": len(downloaded),
        "message": f"Successfully downloaded {len(downloaded)} files",
    }


@mcp_tool(
    name="multi_stage_task",
    description="Execute a multi-stage task with progress for each stage",
)
async def multi_stage_task_tool(data: str) -> Dict[str, Any]:
    """
    Execute a task with multiple stages, reporting progress at each stage.

    This demonstrates progress reporting for tasks with distinct stages
    where each stage takes different amounts of time.

    Args:
        data: Input data to process

    Returns:
        Dictionary with results from all stages
    """
    stages = [
        ("Validating input", 0.2),
        ("Processing data", 0.5),
        ("Generating output", 0.8),
        ("Finalizing", 1.0),
    ]

    results = {}

    for stage_name, progress in stages:
        await send_progress(progress=progress, total=1.0, message=stage_name)

        # Simulate stage work
        await asyncio.sleep(0.8)

        results[stage_name] = "complete"

    return {
        "input": data,
        "stages": results,
        "message": "All stages completed successfully",
    }


@mcp_tool(name="batch_process", description="Process items in batches with batch progress")
async def batch_process_tool(items: List[str], batch_size: int = 5) -> Dict[str, Any]:
    """
    Process items in batches, reporting progress after each batch.

    This demonstrates progress reporting for batch operations where
    items are processed in groups.

    Args:
        items: List of items to process
        batch_size: Number of items per batch

    Returns:
        Dictionary with batch processing results
    """
    total_items = len(items)
    processed_count = 0
    batches = []

    # Process in batches
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        batch_num = (i // batch_size) + 1

        await send_progress(
            progress=processed_count,
            total=total_items,
            message=f"Processing batch {batch_num}...",
        )

        # Simulate batch processing
        await asyncio.sleep(0.6)

        processed_count += len(batch)
        batches.append({"batch": batch_num, "items": batch, "count": len(batch)})

        # Report batch complete
        await send_progress(
            progress=processed_count,
            total=total_items,
            message=f"Batch {batch_num} complete ({processed_count}/{total_items} items)",
        )

    return {
        "batches": batches,
        "total_items": total_items,
        "batch_size": batch_size,
        "message": f"Processed {total_items} items in {len(batches)} batches",
    }


# ═══════════════════════════════════════════════════════════════════
# DEMO RUNNER
# ═══════════════════════════════════════════════════════════════════


class ProgressCapture:
    """Captures and displays progress notifications."""

    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        self.notifications = []

    async def send_progress_notification(
        self,
        progress_token: str | int,
        progress: float,
        total: float | None = None,
        message: str | None = None,
    ):
        """Capture and display a progress notification."""
        self.notifications.append(
            {
                "progress": progress,
                "total": total,
                "message": message,
            }
        )

        # Display the progress
        if total:
            percent = (progress / total) * 100
            bar_length = 40
            filled = int(bar_length * progress / total)
            bar = "█" * filled + "░" * (bar_length - filled)
            print(f"  [{bar}] {percent:.1f}% | {message or ''}")
        else:
            print(f"  Progress: {progress} | {message or ''}")


async def run_demo():
    """Run all demo tools with progress tracking."""

    print("=" * 70)
    print("PROGRESS REPORTING DEMO - AUTOMATED RUN")
    print("=" * 70)
    print()

    # Demo 1: Process Items
    print("1️⃣  STEP-BASED PROGRESS: Processing Items")
    print("-" * 70)
    capture = ProgressCapture("process_items")
    session = AsyncMock()
    session.send_progress_notification = capture.send_progress_notification

    ctx = MCPRequestContext(session=session, progress_token="demo-1")
    set_request_context(ctx)

    result = await process_items_tool(["apple", "banana", "cherry", "date"])
    print(f"  ✓ Result: {result['message']}")
    print(f"  ✓ Processed: {result['count']} items")
    print()

    # Demo 2: Long Computation
    print("2️⃣  PERCENTAGE PROGRESS: Long Computation")
    print("-" * 70)
    capture = ProgressCapture("long_computation")
    session.send_progress_notification = capture.send_progress_notification

    ctx = MCPRequestContext(session=session, progress_token="demo-2")
    set_request_context(ctx)

    result = await long_computation_tool(50)
    print(f"  ✓ Result: {result['message']}")
    print(f"  ✓ Iterations: {result['iterations']}, Sum: {result['result']}")
    print()

    # Demo 3: Download Files
    print("3️⃣  DETAILED PROGRESS: Downloading Files")
    print("-" * 70)
    capture = ProgressCapture("download_files")
    session.send_progress_notification = capture.send_progress_notification

    ctx = MCPRequestContext(session=session, progress_token="demo-3")
    set_request_context(ctx)

    result = await download_files_tool(
        [
            "https://example.com/file1.zip",
            "https://example.com/file2.zip",
            "https://example.com/file3.zip",
        ]
    )
    print(f"  ✓ Result: {result['message']}")
    print(f"  ✓ Downloaded: {result['total']} files")
    print()

    # Demo 4: Multi-stage Task
    print("4️⃣  STAGE PROGRESS: Multi-stage Task")
    print("-" * 70)
    capture = ProgressCapture("multi_stage_task")
    session.send_progress_notification = capture.send_progress_notification

    ctx = MCPRequestContext(session=session, progress_token="demo-4")
    set_request_context(ctx)

    result = await multi_stage_task_tool("sample data")
    print(f"  ✓ Result: {result['message']}")
    print(f"  ✓ Stages: {list(result['stages'].keys())}")
    print()

    # Demo 5: Batch Processing
    print("5️⃣  BATCH PROGRESS: Batch Processing")
    print("-" * 70)
    capture = ProgressCapture("batch_process")
    session.send_progress_notification = capture.send_progress_notification

    ctx = MCPRequestContext(session=session, progress_token="demo-5")
    set_request_context(ctx)

    items = [f"item_{i}" for i in range(1, 13)]
    result = await batch_process_tool(items, batch_size=3)
    print(f"  ✓ Result: {result['message']}")
    print(f"  ✓ Batches: {len(result['batches'])}, Items: {result['total_items']}")
    print()

    # Summary
    print("=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    print()
    print("Key Takeaways:")
    print("  • Progress notifications provide real-time feedback to clients")
    print("  • Support for step-based (N/total) and percentage (0.0-1.0) progress")
    print("  • Custom messages help users understand what's happening")
    print("  • Works automatically when client provides a progressToken")
    print()


if __name__ == "__main__":
    asyncio.run(run_demo())
