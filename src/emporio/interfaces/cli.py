"""Interface de linha de comando da Lia, com rich.

Fachada fina sobre EmporioAgent: cuida de logging em arquivo, comandos do
terminal e renderização. A lógica do atendimento vive no agente.
"""

import argparse

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from emporio.agent.graph import EmporioAgent
from emporio.agent.llm import describe
from emporio.bootstrap import ensure_data
from emporio.interfaces.common import setup_logging

HELP = (
    "Comandos: /novo (nova conversa), /debug (liga/desliga ferramentas), "
    "/ajuda, /sair."
)


def _truncate(value: str, limit: int = 120) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _show_tools(console: Console, reply) -> None:
    for call in reply.tool_calls:
        console.print(f"[dim]↳ {call.name}({_truncate(str(call.args))})[/dim]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Atendimento Lia (Empório da Música)")
    parser.add_argument("-t", "--thread", help="retoma uma conversa salva pelo id")
    parser.add_argument("--debug", action="store_true", help="mostra as ferramentas chamadas")
    args = parser.parse_args()

    setup_logging()
    ensure_data()

    console = Console()

    try:
        agent = EmporioAgent()
    except RuntimeError as exc:
        console.print(f"[bold red]{exc}[/bold red]")
        raise SystemExit(1) from exc

    thread_id = args.thread or agent.new_thread_id()
    debug = args.debug

    console.print(
        Panel(
            "Empório da Música · Sua música começa aqui.\n"
            f"Modelo: {describe()}\n"
            f"Conversa: {thread_id}\n"
            f"{HELP}",
            title="Lia",
            border_style="green",
        )
    )

    if args.thread:
        existing = len(agent.history(thread_id))
        console.print(f"[dim]Conversa retomada com {existing} mensagem(ns).[/dim]")

    while True:
        try:
            message = console.input("[bold cyan]Você:[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not message:
            continue
        if message == "/sair":
            break
        if message == "/ajuda":
            console.print(f"[dim]{HELP}[/dim]")
            continue
        if message == "/novo":
            thread_id = agent.new_thread_id()
            console.print(f"[green]Nova conversa: {thread_id}[/green]")
            continue
        if message == "/debug":
            debug = not debug
            console.print(f"[dim]Debug {'ligado' if debug else 'desligado'}.[/dim]")
            continue

        with console.status("[dim]Lia está digitando...[/dim]"):
            reply = agent.chat(message, thread_id)

        if debug:
            _show_tools(console, reply)
        console.print("[bold green]Lia:[/bold green]")
        console.print(Markdown(reply.text))

    console.print(
        "[dim]Até mais! Para retomar esta conversa: "
        f"python -m emporio.interfaces.cli -t {thread_id}[/dim]"
    )


if __name__ == "__main__":
    main()
