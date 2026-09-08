import asyncio
import json
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from backend.experiments.models import BudgetConfig, ObjectiveConfig, StrategyType
from backend.experiments.orchestrator import ExperimentOrchestrator
from backend.experiments.scientist.retrospective import RetrospectiveGenerator
from backend.experiments.store import JSONExperimentStore

app = typer.Typer(help="Autonomous Experiment Scientist (AES) CLI for Self-Healing RAG")
console = Console()


def load_dataset(dataset_path: Path, include_candidates: bool = False):
    if not dataset_path.exists():
        raise typer.BadParameter(f"Dataset file not found at {dataset_path}")
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not include_candidates:
        # Filter out unverified candidate samples
        data = [d for d in data if d.get("status") != "candidate" or d.get("human_reviewed") is True]

    return data


@app.command()
def run(
    name: str = typer.Option("aes_optimization_campaign", help="Name of the experiment campaign"),
    strategy: str = typer.Option("scientist", help="Strategy: default, random, grid, bayesian, scientist"),
    max_trials: int = typer.Option(5, help="Maximum number of experiment trials"),
    p95_sla: float = typer.Option(2000.0, help="Max p95 latency SLA threshold in milliseconds"),
    dataset_file: Path = typer.Option(Path("data/eval/dataset_v1.json"), help="Path to evaluation dataset"),
    include_candidates: bool = typer.Option(False, help="Include unverified synthetic candidate queries"),
):
    """Run an autonomous optimization campaign."""
    console.print(Panel.fit(f"[bold cyan]AES Campaign Runner[/bold cyan]\nStrategy: [green]{strategy}[/green] | Max Trials: [yellow]{max_trials}[/yellow]"))

    try:
        strat_enum = StrategyType(strategy.lower())
    except ValueError:
        console.print(f"[red]Invalid strategy '{strategy}'. Choose from: default, random, grid, bayesian, scientist[/red]")
        raise typer.Exit(1)

    dataset = load_dataset(dataset_file, include_candidates=include_candidates)
    console.print(f"Loaded [bold]{len(dataset)}[/bold] evaluation items from [cyan]{dataset_file}[/cyan]")

    store = JSONExperimentStore()
    orchestrator = ExperimentOrchestrator(store=store)

    objective = ObjectiveConfig(max_p95_latency_ms=p95_sla)
    budget = BudgetConfig(max_experiments=max_trials)

    with console.status("[bold green]Executing experimentation campaign..."):
        campaign = asyncio.run(
            orchestrator.run_campaign(
                name=name,
                dataset=dataset,
                strategy=strat_enum,
                objective=objective,
                budget=budget,
            )
        )

    console.print(f"\n[bold green]Campaign {campaign.campaign_id} Completed![/bold green] Status: {campaign.status.value}")

    # Display Leaderboard
    table = Table(title="Experiment Leaderboard")
    table.add_column("Rank", style="cyan", no_wrap=True)
    table.add_column("Trial ID", style="magenta")
    table.add_column("Strategy", style="green")
    table.add_column("Objective Score", style="bold yellow")
    table.add_column("Quality", style="white")
    table.add_column("p95 Latency", style="white")
    table.add_column("Healing Retries", style="white")
    table.add_column("Significant?", style="bold")

    sorted_trials = sorted(campaign.trials, key=lambda t: t.objective_score, reverse=True)
    for rank, t in enumerate(sorted_trials, start=1):
        sig = "[bold green]YES[/bold green]" if (t.statistical_summary and t.statistical_summary.is_statistically_significant) else "[dim]NO[/dim]"
        table.add_row(
            f"#{rank}",
            t.trial_id[:8],
            t.strategy.value,
            f"{t.objective_score:.4f}",
            f"{t.mean_quality:.4f}",
            f"{t.p95_latency_ms:.0f}ms",
            f"{t.mean_healing_count:.1f}",
            sig,
        )

    console.print(table)


@app.command()
def baselines(
    dataset_file: Path = typer.Option(Path("data/eval/dataset_v1.json"), help="Evaluation dataset"),
    trials_per_baseline: int = typer.Option(3, help="Number of trials per baseline strategy"),
):
    """Benchmark all baseline strategies (Default, Random, Grid, Bayesian, Scientist) on identical dataset."""
    console.print(Panel.fit("[bold magenta]Benchmarking Baselines against Scientist[/bold magenta]"))

    dataset = load_dataset(dataset_file)
    store = JSONExperimentStore()
    orchestrator = ExperimentOrchestrator(store=store)

    strategies = [
        StrategyType.DEFAULT,
        StrategyType.RANDOM,
        StrategyType.GRID,
        StrategyType.BAYESIAN,
        StrategyType.SCIENTIST,
    ]

    results_table = Table(title="Baseline Strategy Comparison Matrix")
    results_table.add_column("Strategy", style="cyan bold")
    results_table.add_column("Trials", style="white")
    results_table.add_column("Best Score", style="bold yellow")
    results_table.add_column("Best Quality", style="green")
    results_table.add_column("p95 Latency", style="magenta")

    for strat in strategies:
        console.print(f"Running strategy benchmark: [cyan]{strat.value}[/cyan]...")
        budget = BudgetConfig(max_experiments=trials_per_baseline)
        campaign = asyncio.run(
            orchestrator.run_campaign(
                name=f"benchmark_{strat.value}",
                dataset=dataset,
                strategy=strat,
                budget=budget,
            )
        )
        best_trial = next((t for t in campaign.trials if t.trial_id == campaign.best_trial_id), None)
        if best_trial:
            results_table.add_row(
                strat.value,
                str(len(campaign.trials)),
                f"{best_trial.objective_score:.4f}",
                f"{best_trial.mean_quality:.4f}",
                f"{best_trial.p95_latency_ms:.0f}ms",
            )

    console.print("\n")
    console.print(results_table)


@app.command()
def report(campaign_id: str = typer.Argument(..., help="Campaign ID")):
    """Display scientific retrospective report for a campaign."""
    store = JSONExperimentStore()
    campaign = store.get_campaign(campaign_id)
    if not campaign:
        console.print(f"[red]Campaign '{campaign_id}' not found.[/red]")
        raise typer.Exit(1)

    md = RetrospectiveGenerator.generate_markdown_report(campaign)
    console.print(md)


@app.command()
def status(campaign_id: Optional[str] = typer.Option(None, help="Optional campaign ID")):
    """List recent campaigns or view status of a specific campaign."""
    store = JSONExperimentStore()
    if campaign_id:
        campaign = store.get_campaign(campaign_id)
        if not campaign:
            console.print(f"[red]Campaign '{campaign_id}' not found.[/red]")
            raise typer.Exit(1)
        console.print(Panel.fit(f"Campaign: [bold]{campaign.name}[/bold] ({campaign.campaign_id})\nStatus: [green]{campaign.status.value}[/green]\nTrials: {len(campaign.trials)}"))
    else:
        campaigns = store.list_campaigns()
        table = Table(title="Recent Campaigns")
        table.add_column("Campaign ID", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Strategy", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Trials", style="magenta")
        table.add_column("Created At", style="dim")

        for c in campaigns[:10]:
            table.add_row(
                c.campaign_id,
                c.name,
                c.baseline_strategy.value,
                c.status.value,
                str(len(c.trials)),
                c.created_at.strftime("%Y-%m-%d %H:%M"),
            )
        console.print(table)


if __name__ == "__main__":
    app()
