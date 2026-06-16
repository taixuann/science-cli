"""Pulse-specific plotting utilities."""
import io


def generate_endurance_plot(cycles, r_on, r_off):
    """Generate SVG of endurance cycling data."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    
    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(cycles, r_on, "o-", color="#E74C3C", markersize=3, label="R_ON")
    ax1.plot(cycles, r_off, "s-", color="#3498DB", markersize=3, label="R_OFF")
    ax1.set_xlabel("Cycle #")
    ax1.set_ylabel("Resistance (Ohm)")
    ax1.set_yscale("log")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue().decode("utf-8")


def generate_retention_plot(time, resistance):
    """Generate SVG of retention decay data."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.semilogx(time, resistance, "o-", color="#2ECC71", markersize=4)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Resistance (Ohm)")
    ax.grid(True, alpha=0.3)
    
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue().decode("utf-8")


def generate_stp_plot(time, current):
    """Generate SVG of STP decay trace."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(time, current * 1e6, "o-", color="#9B59B6", markersize=4)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Current (uA)")
    ax.grid(True, alpha=0.3)
    
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue().decode("utf-8")
