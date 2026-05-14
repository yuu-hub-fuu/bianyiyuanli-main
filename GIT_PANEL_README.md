# Nexa Studio - Git Panel Integration

## Overview

The IDE now includes a modern, VSCode-style Source Control (Git) panel for graphical Git operations.

## Features

### Activity Bar
- **📁 Explorer**: Browse files in your workspace
- **⚡ Source Control**: Manage Git operations

Switch between panels by clicking the buttons at the top of the left sidebar.

### Source Control Panel

#### Branch Information
- Display current branch name
- Show commits ahead/behind remote
- Pull: Fetch and merge changes from remote
- Push: Send commits to remote
- Sync: Pull then push in one action

#### Changes Section
Shows modified files with status:
- **Modified** (M): Changes in existing files
- **Added** (A): New files
- **Deleted** (D): Removed files
- **Renamed** (R): Moved files
- **Untracked** (?): New files not yet staged

#### Commit Section
- Type commit message
- Click "✓ Commit" to stage all changes and create commit
- Automatic refresh after successful commit

## Git Operations

### Commit
1. Switch to Source Control panel
2. View changes in the "Changes" section
3. Enter commit message
4. Click "✓ Commit"

### Push/Pull
- Click "⬆ Push" to send your commits
- Click "⬇ Pull" to fetch remote changes
- Click "⟳ Sync" for both operations

### Refresh
- Manual refresh via "↻" button in panel header
- Auto-refresh after commit/push/pull

## Requirements

- Git must be installed and available in PATH
- Working Git repository (auto-detects .git folder)

## Limitations

- Currently supports basic Git operations
- Requires command-line git binary
- Error messages shown as dialogs for failed operations

## Keyboard Shortcuts

While in Source Control panel:
- No special shortcuts currently (use mouse)
- Consider adding in future versions

## Troubleshooting

### "Git not found" error
- **Solution**: Install Git from https://git-scm.com/
- Add Git to PATH (automatic on Windows installer)
- Restart IDE after installation

### "Not a git repository" error
- **Solution**: Initialize repository with: `git init`
- Or navigate to an existing Git project
- Repository detection looks up directory tree

### Commit fails with "nothing to commit"
- **Reason**: No changes detected
- **Solution**: Modify a file and try again
- Check git status: `git status`

### Push/Pull hangs
- **Reason**: Network timeout or authentication required
- **Solution**: 
  - Check network connection
  - Setup SSH keys or credentials
  - Use git credential manager

### Cannot see commits count (↑/↓)
- **Reason**: No remote tracking branch
- **Solution**: Push once to setup tracking
- Or run: `git push -u origin main`

## Advanced Usage

### Manual Git Operations
For operations not in the GUI, use terminal:
```bash
# Switch branches
git checkout -b feature-name

# View history
git log --oneline

# Create tags
git tag v1.0.0

# Interactive rebase
git rebase -i HEAD~3
```

### Git Configuration
Edit `.git/config` or use:
```bash
git config user.name "Your Name"
git config user.email "email@example.com"
git config push.default current
```

## Future Enhancements

- Branch switching/creation UI
- Stash operations
- Merge/rebase support
- Conflict resolution UI
- Detailed change diff viewer
- Commit history browser
- .gitignore editor integration

## Performance Tips

1. **Large repositories**: Initial refresh may take a few seconds
2. **Many files**: Scroll smoothly in changes list
3. **Network operations**: Don't close IDE during push/pull
4. **Auto-refresh**: Happens automatically after operations
