# Sosa Bash Command Policy

All of these Bash commands are auto-allowed. All other commands must be allowed by the user using the specified 
`approval_fn` or are automatically denied if no `approval_fn` is provided.

---

## Auto-Allowed

These run without user confirmation.

### File Reading
| Program | Notes |
|---------|-------|
| `cat` | print file contents |
| `head` | first N lines of a file |
| `tail` | last N lines of a file |
| `less` | pager |
| `more` | pager |

### Filesystem Navigation
| Program | Notes |
|---------|-------|
| `ls` | list directory contents |
| `find` | search for files |
| `stat` | file/filesystem status |
| `file` | determine file type |

### Text Processing
| Program | Notes |
|---------|-------|
| `grep` | search with regex |
| `rg` | ripgrep |
| `awk` | text processing language |
| `sed` | stream editor |
| `cut` | extract columns/fields |
| `sort` | sort lines |
| `uniq` | filter duplicate lines |
| `tr` | translate or delete characters |
| `wc` | word/line/character count |
| `diff` | compare files line by line |
| `jq` | JSON processor |
| `yq` | YAML processor |

### Shell Utilities
| Program | Notes |
|---------|-------|
| `echo` | print text |
| `pwd` | print working directory |
| `which` | locate a command |
| `whereis` | locate binary, source, and manual |
| `type` | describe a command |
| `true` | return success |
| `false` | return failure |

### System Info
| Program | Notes |
|---------|-------|
| `whoami` | print current username |
| `id` | print user and group IDs |
| `uname` | print system information |
| `date` | print date and time |
| `uptime` | how long the system has been running |
| `hostname` | print system hostname |
| `ps` | report process status |
| `pgrep` | find processes by name |
