import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from core.coordinator import coordinator
from learning.calibrator import calibrator
from screener.apex_screener import ApexPredatorScreener
from execution.journal import journal_db
from learning.journal_learner import JournalLearner

console = Console()

def run_analysis(symbol: str, timeframe: str = "15m", capital: float = 10000.0, risk_pct: float = 0.0025):
    console.print(f"[bold cyan]ElderAlpha AI[/bold cyan] analyzing [bold yellow]{symbol}[/bold yellow] ({timeframe})...")
    res = coordinator.analyze_asset(symbol, timeframe, capital, risk_pct)

    if "error" in res:
        console.print(f"[red]Error: {res['error']}[/red]")
        return

    # Price & Volatility
    console.print(Panel(
        f"[bold]Current Price:[/bold] ${res['current_price']:.5f} | "
        f"[bold]Asset:[/bold] {res['asset_name']} ({res['asset_type'].upper()})\n"
        f"[bold]Learned Continuation Probability:[/bold] {res['movement_ai']['continuation_probability']*100:.1f}%\n"
        f"[bold]Signal Quality:[/bold] {res['movement_ai']['signal_quality']}",
        title="Market State & Movement AI",
        border_style="purple"
    ))

    # Pattern & Signal
    if res.get("trade_signal"):
        sig = res["trade_signal"]
        color = "green" if sig["action"] == "BUY" else "red"
        console.print(Panel(
            f"[{color} bold]{sig['action']} - {sig['pattern']}[/{color} bold]\n"
            f"Entry Price: ${sig['entry_price']:.5f}\n"
            f"Stop Loss:   ${sig['stop_loss']:.5f} (Calibrated ATR buffer)\n"
            f"Target 1:    ${sig['target_1']:.5f} (50% scale-out + move stop to breakeven)\n"
            f"Target 2:    ${sig['target_2']:.5f} (Runner)\n"
            f"Position Size: [bold]{sig['units_label']}[/bold] (Max Risk: ${sig['risk_per_trade_usd']:.2f})\n"
            f"Payout Ratio: {sig['payout_ratio']:.2f}R | Confidence: {sig['confidence']*100:.0f}%\n\n"
            f"[italic]{sig['rationale']}[/italic]",
            title="Active Trade Signal",
            border_style=color
        ))
    else:
        console.print("[yellow]No high-probability Elder pattern active right now. Protecting capital.[/yellow]")

    # Calibrated Settings
    cal = res["calibration"]
    console.print(f"[dim]Active Calibration -> ATR Stop: {cal['atr_stop_multiplier']}x | Fib: {cal['abcd_min_pullback_fib']}-{cal['abcd_max_pullback_fib']} | RVOL: {cal['rvol_threshold']}x[/dim]\n")

def run_screener():
    console.print("[bold cyan]Scanning Apex Predator candidates (Forex & Crypto)...[/bold cyan]")
    items = ApexPredatorScreener.scan_market()
    
    table = Table(title="Apex Predator Screener (Elder Ch 24)")
    table.add_column("Symbol", style="bold white")
    table.add_column("Asset", style="dim")
    table.add_column("Price", justify="right")
    table.add_column("RVOL", justify="right")
    table.add_column("ATR %", justify="right")
    table.add_column("Trend")
    table.add_column("Score", justify="right", style="bold magenta")
    table.add_column("Status", style="green")

    for it in items:
        table.add_row(
            it["symbol"],
            it["name"],
            f"${it['price']}",
            f"{it['rvol']}x",
            f"{it['atr_pct']}%",
            it["trend_bias"],
            str(it["predator_score"]),
            it["status"]
        )
    console.print(table)

def run_journal():
    trades = journal_db.get_all_trades()
    a = JournalLearner.analyze_journal(trades)

    console.print(Panel(
        f"[bold]Total Trades:[/bold] {a['total_trades']} | [bold]Win Rate:[/bold] {a['hit_rate_pct']}%\n"
        f"[bold]Payout Ratio:[/bold] {a['payout_ratio']:.2f} (Elder Minimum: 2.0R)\n"
        f"[bold]Profit Factor:[/bold] {a['profit_factor']:.2f} | [bold]Net Realized P/L:[/bold] ${a['net_pnl']:.2f}",
        title="Elder Trade & Mental Journal Summary",
        border_style="cyan"
    ))

def main():
    parser = argparse.ArgumentParser(description="ElderAlpha AI CLI Assistant")
    subparsers = parser.add_subparsers(dest="command")

    # Analyze
    p_analyze = subparsers.add_parser("analyze", help="Analyze symbol")
    p_analyze.add_argument("symbol", type=str, default="EURUSD=X", nargs="?")
    p_analyze.add_argument("--tf", type=str, default="15m", help="Timeframe (1m, 5m, 15m, 1h, 1d)")

    # Screener
    subparsers.add_parser("scan", help="Run Apex Predator Screener")

    # Journal
    subparsers.add_parser("journal", help="Show Trade Journal metrics")

    args = parser.parse_args()

    if args.command == "scan":
        run_screener()
    elif args.command == "journal":
        run_journal()
    else:
        symbol = getattr(args, "symbol", "EURUSD=X")
        tf = getattr(args, "tf", "15m")
        run_analysis(symbol, tf)

if __name__ == "__main__":
    main()
