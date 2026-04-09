from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich import box

console = Console()


def welcome(agent_name: str) -> None:
    console.print()
    console.print(Panel(
        f"[bold cyan]{agent_name}[/bold cyan] [dim]— type [bold]exit[/bold] to quit[/dim]",
        box=box.ROUNDED,
        border_style="cyan",
        padding=(0, 2),
    ))
    console.print()


def agent_response(agent_name: str, content: str) -> None:
    console.print(Panel(
        Markdown(content),
        title=f"[bold cyan]{agent_name}[/bold cyan]",
        title_align="left",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(1, 2),
    ))


_NO_ARGS_TOOLS = {"write_file", "edit_file"}


def tool_call(name: str, args: dict) -> None:
    arg_parts = []
    if name not in _NO_ARGS_TOOLS:
        for k, v in args.items():
            v_str = str(v)
            if len(v_str) > 60:
                v_str = v_str[:57] + "..."
            arg_parts.append(f"[dim]{k}[/dim][dim white]=[/dim white][italic]{v_str}[/italic]")

    args_str = "  ".join(arg_parts)
    line = Text.assemble(
        ("  → ", "dim cyan"),
        (name, "italic cyan"),
        ("  ", ""),
    )
    console.print(line, end="")
    if args_str:
        console.print(args_str)
    else:
        console.print()


def tool_result(content: str) -> None:
    lines = content.strip().splitlines()
    preview = "\n".join(lines[:5])
    if len(lines) > 5:
        preview += f"\n[dim]… ({len(lines) - 5} more lines)[/dim]"
    console.print(Panel(
        preview,
        border_style="dim",
        box=box.SIMPLE,
        padding=(0, 2),
    ))


def approval_prompt(command: str) -> bool:
    console.print()
    console.print(Panel(
        f"[bold yellow]$ {command}[/bold yellow]",
        title="[bold red]Command requires approval[/bold red]",
        title_align="left",
        border_style="red",
        box=box.ROUNDED,
        padding=(0, 2),
    ))
    answer = console.input("  [bold]Allow?[/bold] [dim]\\[y/N][/dim] ").strip().lower()
    console.print()
    return answer == "y"


def user_prompt() -> str:
    console.print()
    return console.input("[bold green]You[/bold green] [dim]›[/dim] ").strip()


def divider() -> None:
    console.print(Rule(style="dim"))


def error(msg: str) -> None:
    console.print(f"[bold red]Error:[/bold red] {msg}")
