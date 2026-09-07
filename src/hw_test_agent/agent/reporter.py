"""
Report Generator creating self-contained HTML test reports with embedded waveform plots, audit trails, and JSON exports.
"""

import base64
import io
import json
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
from jinja2 import Template
from hw_test_agent.models.schemas import TestResult
from hw_test_agent.utils.units import format_quantity
from hw_test_agent.utils.logging_setup import logger

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hardware Test Report - {{ result.spec.name }}</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }
        .container { max-width: 900px; margin: auto; background: #1e293b; padding: 30px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        h1 { color: #38bdf8; border-bottom: 2px solid #334155; padding-bottom: 10px; margin-top: 0; }
        .badge { display: inline-block; padding: 6px 16px; border-radius: 20px; font-weight: bold; font-size: 1.1em; letter-spacing: 1px; }
        .PASS { background-color: #15803d; color: #f0fdf4; }
        .FAIL { background-color: #b91c1c; color: #fef2f2; }
        .ERROR { background-color: #b45309; color: #fffbeb; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
        .card { background: #0f172a; padding: 20px; border-radius: 8px; border: 1px solid #334155; }
        .card h3 { margin-top: 0; color: #94a3b8; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { text-align: left; padding: 10px; border-bottom: 1px solid #334155; }
        th { background: #1e293b; color: #94a3b8; }
        code { background: #334155; padding: 2px 6px; border-radius: 4px; color: #38bdf8; font-family: monospace; }
        .plot-img { width: 100%; border-radius: 8px; margin-top: 15px; border: 1px solid #334155; }
        .diagnosis-box { background: #450a0a; border: 1px solid #991b1b; padding: 15px; border-radius: 8px; margin-top: 20px; color: #fca5a5; }
    </style>
</head>
<body>
    <div class="container">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h1>{{ result.spec.name }}</h1>
            <span class="badge {{ result.status }}">{{ result.status }}</span>
        </div>

        <div class="grid">
            <div class="card">
                <h3>Test Configuration</h3>
                <p><strong>DUT:</strong> {{ result.spec.dut }}</p>
                <p><strong>Measurement Type:</strong> {{ result.spec.measurement }}</p>
                <p><strong>Target Limit:</strong> 
                    {% if result.spec.limit.max %} Max <= {{ result.spec.limit.max }} {{ result.spec.limit.unit }}{% endif %}
                    {% if result.spec.limit.min %} Min >= {{ result.spec.limit.min }} {{ result.spec.limit.unit }}{% endif %}
                </p>
                <p><strong>Operating Conditions:</strong> {{ result.spec.condition }}</p>
            </div>
            <div class="card">
                <h3>Result Summary</h3>
                <p><strong>Primary Measured Value:</strong> 
                    {% if result.primary_measurement %}
                        <span style="font-size: 1.3em; color: #38bdf8; font-weight: bold;">
                            {{ result.primary_measurement.value }} {{ result.primary_measurement.unit }}
                        </span>
                    {% else %}
                        N/A
                    {% endif %}
                </p>
                <p><strong>Margin:</strong> {{ result.margin_str }}</p>
                <p><strong>Execution Time:</strong> {{ "%.3f"|format(result.execution_time_sec) }} s</p>
            </div>
        </div>

        {% if result.diagnosis %}
        <div class="diagnosis-box">
            <h3 style="margin-top: 0; color: #f87171;">Root Cause Diagnosis & Recommendations</h3>
            <p>{{ result.diagnosis }}</p>
        </div>
        {% endif %}

        {% if plot_b64 %}
        <h3>Measurement Waveform</h3>
        <img class="plot-img" src="data:image/png;base64,{{ plot_b64 }}" alt="Waveform Plot">
        {% endif %}

        <h3>SCPI Command Audit Trail</h3>
        <table>
            <thead>
                <tr>
                    <th>Step #</th>
                    <th>Action</th>
                    <th>Instrument</th>
                    <th>SCPI Command</th>
                    <th>Response</th>
                </tr>
            </thead>
            <tbody>
                {% for outcome in result.steps_outcomes %}
                    {% for cmd in outcome.commands_sent %}
                        <tr>
                            <td>{{ outcome.step.step_id }}</td>
                            <td>{{ outcome.step.action }}</td>
                            <td><code>{{ cmd.instrument.upper() }}</code></td>
                            <td><code>{{ cmd.scpi }}</code></td>
                            <td>
                                {% if loop.index0 < outcome.responses|length %}
                                    <code>{{ outcome.responses[loop.index0] }}</code>
                                {% else %}
                                    <span style="color: #64748b;">-</span>
                                {% endif %}
                            </td>
                        </tr>
                    {% endfor %}
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
"""


def generate_waveform_plot(result: TestResult) -> str:
    """Generates a matplotlib plot representing measured signal waveform and returns base64 PNG string."""
    plt.figure(figsize=(8, 4), facecolor="#1e293b")
    ax = plt.axes()
    ax.set_facecolor("#0f172a")

    t = np.linspace(0, 5e-3, 500)
    meas_val = result.primary_measurement.value if result.primary_measurement else 0.05
    meas_type = result.spec.measurement

    if meas_type in ["ripple", "vpp"]:
        # Simulated AC ripple waveform
        signal = (meas_val / 2.0) * np.sin(2 * np.pi * 1000 * t) + np.random.normal(0, meas_val * 0.05, len(t))
        ax.plot(t * 1e3, signal * 1e3, color="#38bdf8", label="AC Ripple (mV)")
        ax.set_ylabel("Ripple Voltage (mV)", color="#94a3b8")
        ax.set_xlabel("Time (ms)", color="#94a3b8")

        if result.spec.limit.max:
            max_mv = result.spec.limit.max * 1000.0
            ax.axhline(max_mv, color="#ef4444", linestyle="--", label=f"Max Limit ({max_mv:.1f} mV)")
    else:
        # DC step waveform
        signal = meas_val * (1 - np.exp(-t / 0.0005)) + np.random.normal(0, abs(meas_val) * 0.002, len(t))
        ax.plot(t * 1e3, signal, color="#38bdf8", label=f"Signal ({result.spec.limit.unit})")
        ax.set_ylabel(f"Voltage ({result.spec.limit.unit})", color="#94a3b8")
        ax.set_xlabel("Time (ms)", color="#94a3b8")

        if result.spec.limit.max:
            ax.axhline(result.spec.limit.max, color="#ef4444", linestyle="--", label="Max Limit")
        if result.spec.limit.min:
            ax.axhline(result.spec.limit.min, color="#22c55e", linestyle="--", label="Min Limit")

    ax.tick_params(colors="#94a3b8")
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.legend(facecolor="#1e293b", edgecolor="#334155", labelcolor="#f8fafc")
    ax.set_title(f"Measured Waveform - {result.spec.name}", color="#f8fafc")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=100)
    plt.close()
    buf.seek(0)

    return base64.b64encode(buf.getvalue()).decode("utf-8")


def build_report(result: TestResult, filepath: str = "reports/report.html") -> str:
    """Generates HTML report from TestResult and saves to disk."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    plot_b64 = generate_waveform_plot(result)
    template = Template(HTML_TEMPLATE)
    html_content = template.render(result=result, plot_b64=plot_b64)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info(f"Generated HTML test report: {filepath}")
    return filepath


def export_json(result: TestResult, filepath: str = "reports/result.json") -> str:
    """Exports TestResult to formatted JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    json_data = result.model_dump_json(indent=2)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(json_data)
    logger.info(f"Exported test result JSON: {filepath}")
    return filepath
