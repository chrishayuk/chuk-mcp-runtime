#!/usr/bin/env python3
"""
Script to check for outdated packages and update pyproject.toml dependencies.
Compatible with UV package manager and PEP 621 project configuration.
"""

import subprocess
import sys
import json
import re
from pathlib import Path
import toml
import tomli_w
from packaging import version


def run_command(cmd, capture_output=True, text=True, check=True):
    """Run a shell command and return the result."""
    try:
        # Split command string into list for security
        if isinstance(cmd, str):
            import shlex

            cmd_list = shlex.split(cmd)
        else:
            cmd_list = cmd

        result = subprocess.run(
            cmd_list,  # Use list instead of string
            shell=False,  # SECURITY: Never use shell=True with user input
            capture_output=capture_output,
            text=text,
            check=check,
        )
        return result
    except subprocess.CalledProcessError as e:
        print(
            f"❌ Command failed: {' '.join(cmd_list) if isinstance(cmd_list, list) else cmd}"
        )
        print(f"Error: {e}")
        return None


def get_outdated_packages():
    """Get list of outdated packages using uv."""
    print("🔍 Checking for outdated packages...")

    # First, try to get the current lock information
    try:
        # Check if uv.lock exists
        lock_file = Path("uv.lock")
        if not lock_file.exists():
            print("📦 No uv.lock found, running uv lock to generate it...")
            run_command("uv lock")

        # Get outdated packages using uv tree --outdated (if available)
        # Note: uv doesn't have a direct equivalent to poetry show --outdated
        # So we'll use a different approach

        # Get currently installed packages
        result = run_command("uv pip list --format=json")
        if not result or result.returncode != 0:
            print("❌ Failed to get package list from uv")
            return []

        installed_packages = json.loads(result.stdout)

        # For each package, check if there's a newer version available
        outdated = []
        for pkg in installed_packages:
            name = pkg["name"]
            current_version = pkg["version"]

            # Skip local/editable packages
            if "editable" in pkg and pkg["editable"]:
                continue

            # Check for newer version using pip index (uv uses pip under the hood)
            check_cmd = f"uv pip index versions {name}"
            result = run_command(check_cmd, check=False)

            if result and result.returncode == 0:
                # Parse available versions (this is simplified)
                # In practice, you might want to use the PyPI API or a more robust method
                pass

        return outdated

    except Exception as e:
        print(f"❌ Error checking for outdated packages: {e}")
        return []


def get_current_dependencies():
    """Get current dependencies from pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("❌ pyproject.toml not found")
        return {}, {}

    with open(pyproject_path, "r", encoding="utf-8") as f:
        pyproject_data = toml.load(f)

    # Get main dependencies
    main_deps = pyproject_data.get("project", {}).get("dependencies", [])

    # Get dev dependencies
    dev_deps = pyproject_data.get("dependency-groups", {}).get("dev", [])

    return main_deps, dev_deps


def parse_dependency_string(dep_string):
    """Parse a dependency string like 'package>=1.0.0' into name and version constraint."""
    # Simple regex to extract package name and version constraint
    match = re.match(r"^([a-zA-Z0-9\-_\.]+)([><=!]+.+)?$", dep_string.strip())
    if match:
        name = match.group(1)
        constraint = match.group(2) if match.group(2) else ""
        return name, constraint
    return dep_string, ""


def check_package_updates_with_uv():
    """Use uv to check for package updates by trying to resolve with latest versions."""
    print("🔍 Checking for available updates...")

    try:
        # Create a temporary requirements file with relaxed constraints
        main_deps, dev_deps = get_current_dependencies()

        temp_reqs = []
        for dep in main_deps:
            name, _ = parse_dependency_string(dep)
            temp_reqs.append(name)  # Remove version constraints to see latest

        # Write temporary requirements
        with open("temp_requirements.txt", "w") as f:
            f.write("\n".join(temp_reqs))

        # Use uv to resolve latest versions
        result = run_command("uv pip compile temp_requirements.txt --dry-run")

        # Clean up
        Path("temp_requirements.txt").unlink(missing_ok=True)

        if result and result.returncode == 0:
            print("✅ Dependency resolution completed")
            return True
        else:
            print("❌ Failed to resolve dependencies")
            return False

    except Exception as e:
        print(f"❌ Error checking updates: {e}")
        return False


def interactive_update():
    """Interactively update dependencies."""
    main_deps, dev_deps = get_current_dependencies()

    if not main_deps and not dev_deps:
        print("❌ No dependencies found in pyproject.toml")
        return

    print(
        f"📦 Found {len(main_deps)} main dependencies and {len(dev_deps)} dev dependencies"
    )

    # For now, suggest manual update process since uv doesn't have direct equivalent
    print("\n💡 To update dependencies with uv:")
    print("1. Check specific package updates: uv pip show <package-name>")
    print("2. Update individual packages: uv add <package-name>@latest")
    print("3. Update dev dependencies: uv add <package-name>@latest --dev")
    print("4. Update all at once: uv sync --upgrade")

    response = input(
        "\n🤔 Would you like to run 'uv sync --upgrade' to update all dependencies? (y/N): "
    )

    if response.lower() in ["y", "yes"]:
        print("🚀 Running uv sync --upgrade...")
        result = run_command("uv sync --upgrade", capture_output=False)
        if result and result.returncode == 0:
            print("✅ Dependencies updated successfully!")
        else:
            print("❌ Failed to update dependencies")
    else:
        print(
            "ℹ️  No updates performed. You can manually update specific packages as needed."
        )


def main():
    """Main function."""
    print("🚀 UV-compatible dependency updater")
    print("=" * 50)

    # Check if we're in a project with pyproject.toml
    if not Path("pyproject.toml").exists():
        print("❌ No pyproject.toml found in current directory")
        sys.exit(1)

    # Check if uv is available
    result = run_command("uv --version", check=False)
    if not result or result.returncode != 0:
        print("❌ UV package manager not found. Please install uv first.")
        sys.exit(1)

    print(f"✅ Using UV version: {result.stdout.strip()}")

    # Check current project setup
    main_deps, dev_deps = get_current_dependencies()

    if not main_deps and not dev_deps:
        print("❌ No dependencies found in pyproject.toml")
        sys.exit(1)

    print(
        f"📦 Project has {len(main_deps)} main dependencies and {len(dev_deps)} dev dependencies"
    )

    # Check for updates
    if check_package_updates_with_uv():
        print("🎉 Dependency check completed!")

    # Ask if user wants to update
    interactive_update()


if __name__ == "__main__":
    main()
