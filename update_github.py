#!/usr/bin/env python3
"""
GitHub Repository Update Script for Receipt Automation System

This script helps update the GitHub repository with the current version of the project.
It will:
1. Check if git is installed
2. Check if the repository is already initialized
3. Add all files to git (excluding those in .gitignore)
4. Commit the changes
5. Push to GitHub
"""

import os
import sys
import subprocess
from datetime import datetime

def check_git_installed():
    """Check if git is installed"""
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Git is not installed or not in PATH.")
        print("Please install Git from https://git-scm.com/downloads")
        return False

def check_git_repo():
    """Check if the current directory is a git repository"""
    try:
        subprocess.run(["git", "status"], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False

def init_git_repo():
    """Initialize a new git repository"""
    try:
        subprocess.run(["git", "init"], check=True)
        print("✅ Initialized new Git repository.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to initialize Git repository: {e}")
        return False

def add_files():
    """Add all files to git (excluding those in .gitignore)"""
    try:
        subprocess.run(["git", "add", "."], check=True)
        print("✅ Added files to Git.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to add files: {e}")
        return False

def commit_changes(message=None):
    """Commit the changes"""
    if not message:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"Update Receipt Automation System - {timestamp}"
    
    try:
        subprocess.run(["git", "commit", "-m", message], check=True)
        print(f"✅ Committed changes with message: {message}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to commit changes: {e}")
        return False

def set_remote(repo_url):
    """Set the remote repository URL"""
    try:
        # Check if remote already exists
        result = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True)
        
        if "origin" in result.stdout:
            # Update existing remote
            subprocess.run(["git", "remote", "set-url", "origin", repo_url], check=True)
            print(f"✅ Updated remote repository URL: {repo_url}")
        else:
            # Add new remote
            subprocess.run(["git", "remote", "add", "origin", repo_url], check=True)
            print(f"✅ Added remote repository URL: {repo_url}")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to set remote repository: {e}")
        return False

def push_to_github(branch="main"):
    """Push to GitHub"""
    try:
        subprocess.run(["git", "push", "-u", "origin", branch], check=True)
        print(f"✅ Pushed changes to GitHub ({branch} branch).")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to push to GitHub: {e}")
        print("This could be due to:")
        print("  - No internet connection")
        print("  - Repository URL is incorrect")
        print("  - You don't have permission to push to this repository")
        print("  - The branch doesn't exist on the remote repository")
        return False

if __name__ == "__main__":
    print("Receipt Automation System - GitHub Repository Update")
    print("="*50)
    
    # Check if git is installed
    if not check_git_installed():
        sys.exit(1)
    
    # Check if the repository is already initialized
    if not check_git_repo():
        print("Git repository not initialized.")
        init = input("Do you want to initialize a new Git repository? (y/N): ")
        if init.lower() == 'y':
            if not init_git_repo():
                sys.exit(1)
        else:
            print("Exiting without initializing Git repository.")
            sys.exit(0)
    
    # Ask for GitHub repository URL
    repo_url = input("\nEnter your GitHub repository URL (e.g., https://github.com/username/repo.git): ")
    if not repo_url:
        print("No repository URL provided. Exiting.")
        sys.exit(1)
    
    # Set the remote repository URL
    if not set_remote(repo_url):
        sys.exit(1)
    
    # Add files
    if not add_files():
        sys.exit(1)
    
    # Commit changes
    commit_msg = input("\nEnter commit message (or press Enter for default message): ")
    if not commit_changes(commit_msg if commit_msg else None):
        sys.exit(1)
    
    # Ask for branch name
    branch = input("\nEnter branch name to push to (default: main): ")
    if not branch:
        branch = "main"
    
    # Push to GitHub
    push = input(f"\nDo you want to push to GitHub ({branch} branch)? (y/N): ")
    if push.lower() == 'y':
        if not push_to_github(branch):
            sys.exit(1)
    else:
        print("Changes committed but not pushed to GitHub.")
    
    print("\n✅ GitHub repository update completed!")
    print(f"Repository URL: {repo_url}")
    print(f"Branch: {branch}")
    print("\nYou can manually push your changes later with:")
    print(f"  git push -u origin {branch}") 