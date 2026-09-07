"""
Typer Command Line Interface for Hardware Test Automation Agent.
"""

import sys
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from hw_test_agent.agent.orchestrator import Orchestrator
from hw_test_agent.agent.validator import SafetyValidator
from hw_test_agent.instruments.simulated import SimulatedPSU, SimulatedScope
from hw_test_agent.utils.logging_setup import logger

app = typer.Typer(help="AI Agent for Hardware Test Automation")
console = Console()


@app.command()
def run(
    requirement: str = typer.Argument(..., help="Plain English test requirement string"),
    sim: bool = typer.Option(True, "--sim/--real", help="Run with simulated instruments"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate plan without sending commands"),
    report_dir: str = typer.Option("reports", "--report-dir", help="Directory to store HTML & JSON reports"),
    max_voltage: float = typer.Option(12.0, "--max-voltage", help="Safety validator max voltage limit (V)"),
    max_current: float = typer.Option(2.0, "--max-current", help="Safety validator max current limit (A)"),
):
    """Parses plain English test requirement, plans SCPI steps, executes safely, and generates test report."""
    console.print(Panel(f"[bold cyan]AI Hardware Test Automation Agent[/bold cyan]\nRequirement: [yellow]'{requirement}'[/yellow]", expand=False))

    validator = SafetyValidator(max_voltage=max_voltage, max_current=max_current)

    if sim:
        psu = SimulatedPSU()
        scope = SimulatedScope()
    else:
        # Physical PyVISA driver instantiation
        from hw_test_agent.instruments.visa_driver import VisaInstrument
        console.print("[bold yellow]Connecting to physical VISA instruments...[/bold yellow]")
        psu = VisaInstrument("ASRL1::INSTR")
        scope = VisaInstrument("USB0::0x0957::0x1796::MY59001234::INSTR")

    orchestrator = Orchestrator(psu=psu, scope=scope, validator=validator, report_dir=report_dir)

    try:
        with console.status("[bold green]Executing automated hardware test workflow...[/bold green]"):
            result = orchestrator.run(requirement, dry_run_only=dry_run)

        # Output Summary Table
        table = Table(title="Test Execution Summary", show_header=True, header_style="bold magenta")
        table.add_column("Property", style="cyan")
        table.add_column("Details", style="white")

        table.add_row("Test Name", result.spec.name)
        table.add_row("Measurement Type", str(result.spec.measurement.value if hasattr(result.spec.measurement, "value") else result.spec.measurement))

        status_style = "bold green" if result.status == "PASS" else ("bold red" if result.status == "FAIL" else "bold yellow")
        table.add_row("Status", f"[{status_style}]{result.status}[/{status_style}]")

        if result.primary_measurement:
            val_str = f"{result.primary_measurement.value} {result.primary_measurement.unit}"
            table.add_row("Primary Measurement", val_str)

        table.add_row("Margin / Info", result.margin_str)
        table.add_row("Execution Time", f"{result.execution_time_sec:.3f} s")
        table.add_row("HTML Report", f"{report_dir}/report.html")

        console.print(table)

        if result.diagnosis:
            console.print(Panel(f"[bold red]Failure Root Cause Diagnosis:[/bold red]\n{result.diagnosis}", title="LLM Diagnostics", border_style="red"))

        if result.status == "FAIL":
            sys.exit(1)

    except Exception as e:
        console.print(f"[bold red]Error running test orchestrator: {e}[/bold red]")
        sys.exit(2)


if __name__ == "__main__":
    app()
