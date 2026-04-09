# Sosa Bash Command Policy

All of these Bash commands are auto-allowed. All other commands must be allowed by the user using the specified 
`approval_fn` or are automatically denied if no `approval_fn` is provided.

---

## Auto-Allowed

These run without user confirmation.

### File Reading
| Program | Notes |
|---------|-------|
| `cat` | |
| `head` | |
| `tail` | |
| `less` | |
| `more` | |

### Filesystem Navigation
| Program | Notes |
|---------|-------|
| `ls` | |
| `find` | |
| `stat` | |
| `file` | |

### Text Processing
| Program | Notes |
|---------|-------|
| `grep` | |
| `rg` | ripgrep |
| `awk` | |
| `sed` | |
| `cut` | |
| `sort` | |
| `uniq` | |
| `tr` | |
| `wc` | |
| `diff` | |
| `jq` | |
| `yq` | |

### Shell Utilities
| Program | Notes |
|---------|-------|
| `echo` | |
| `pwd` | |
| `which` | |
| `whereis` | |
| `type` | |
| `true` | |
| `false` | |

### System Info
| Program | Notes |
|---------|-------|
| `whoami` | |
| `id` | |
| `uname` | |
| `date` | |
| `uptime` | |
| `hostname` | |
| `env` | |
| `printenv` | |
| `ps` | |
| `pgrep` | |
