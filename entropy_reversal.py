from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

SEED = 42
N_PARTICLES = 2000
N_STEPS = 80
INITIAL_POSITION = 0


def shannon_entropy(positions):
    _, counts = np.unique(positions, return_counts=True)
    p = counts / counts.sum()
    return float(-np.sum(p * np.log2(p)))


def distribution(positions, x_values):
    counts = np.array([(positions == x).sum() for x in x_values], dtype=float)
    return counts / counts.sum()


def kl_divergence_bits(p, q):
    """Calculate D_KL(p || q) in bits.

    Terms with p_i = 0 contribute zero. If q_i = 0 where p_i > 0,
    the divergence is mathematically infinite.
    """
    p = np.asarray(p, dtype=float)
    q = np.asarray(q, dtype=float)
    mask = p > 0

    if np.any(q[mask] == 0):
        return float("inf")

    return float(np.sum(p[mask] * np.log2(p[mask] / q[mask])))


def forward_walk(rng):
    positions = np.full(N_PARTICLES, INITIAL_POSITION, dtype=int)
    history = []
    entropy = [shannon_entropy(positions)]

    for _ in range(N_STEPS):
        moves = rng.choice([-1, 1], size=N_PARTICLES)
        positions += moves
        history.append(moves.copy())
        entropy.append(shannon_entropy(positions))

    return positions, np.array(history), entropy


def exact_reverse(final_positions, history):
    positions = final_positions.copy()
    entropy = [shannon_entropy(positions)]

    for moves in history[::-1]:
        positions -= moves
        entropy.append(shannon_entropy(positions))

    return positions, entropy


def random_backward(final_positions, rng):
    positions = final_positions.copy()
    entropy = [shannon_entropy(positions)]

    for _ in range(N_STEPS):
        positions += rng.choice([-1, 1], size=N_PARTICLES)
        entropy.append(shannon_entropy(positions))

    return positions, entropy


def partial_reverse(final_positions, history, fraction, rng):
    """
    Keep the complete movement histories of only a fraction of the particles.

    Remembered particles use the correct inverse move at every reverse step.
    Particles without a stored history use new random moves.
    """
    positions = final_positions.copy()
    remembered_particles = rng.random(N_PARTICLES) < fraction

    for moves in history[::-1]:
        random_moves = rng.choice([-1, 1], size=N_PARTICLES)
        positions += np.where(remembered_particles, -moves, random_moves)

    return positions


def make_figures():
    output_dir = Path(__file__).parent / "figures"
    output_dir.mkdir(exist_ok=True)

    rng_forward = np.random.default_rng(SEED)
    rng_random = np.random.default_rng(SEED + 1)

    initial = np.full(N_PARTICLES, INITIAL_POSITION, dtype=int)
    final_positions, history, forward_entropy = forward_walk(rng_forward)
    reversed_positions, reverse_entropy = exact_reverse(final_positions, history)
    random_positions, random_entropy = random_backward(final_positions, rng_random)

    x_min = min(initial.min(), final_positions.min(), reversed_positions.min(), random_positions.min())
    x_max = max(initial.max(), final_positions.max(), reversed_positions.max(), random_positions.max())
    x_values = np.arange(x_min, x_max + 1)

    initial_distribution = distribution(initial, x_values)
    forward_distribution = distribution(final_positions, x_values)
    guided_distribution = distribution(reversed_positions, x_values)
    random_distribution = distribution(random_positions, x_values)

    history_kl = kl_divergence_bits(guided_distribution, random_distribution)

    plt.figure(figsize=(10, 5.5))
    plt.plot(x_values, initial_distribution, label="Initial ordered state")
    plt.plot(x_values, forward_distribution, label="After random diffusion")
    plt.plot(x_values, guided_distribution, label="After exact reversal")
    plt.xlabel("Position")
    plt.ylabel("Probability")
    plt.title("Particle distributions before and after entropy reversal")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "particle_distributions.png", dpi=200)
    plt.close()


    plt.figure(figsize=(10, 5.5))
    plt.plot(x_values, random_distribution, label="Random backward result")
    plt.plot(x_values, guided_distribution, label="Guided reversal result")
    plt.xlabel("Position")
    plt.ylabel("Probability")
    plt.title("KL divergence between guided and random final distributions")
    plt.text(
        0.02,
        0.95,
        f"D_KL(P_guided || P_random) = {history_kl:.4f} bits",
        transform=plt.gca().transAxes,
        va="top",
        bbox=dict(boxstyle="round", alpha=0.15),
    )
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "kl_divergence_comparison.png", dpi=200)
    plt.close()

    forward_time = np.arange(len(forward_entropy))
    reverse_time = np.arange(N_STEPS, N_STEPS + len(reverse_entropy))

    plt.figure(figsize=(10, 5.5))
    plt.plot(forward_time, forward_entropy, label="Forward random diffusion")
    plt.plot(reverse_time, reverse_entropy, label="Exact reversal with stored history")
    plt.plot(reverse_time, random_entropy, label="Random backward attempt")
    plt.xlabel("Simulation step")
    plt.ylabel("Shannon entropy (bits)")
    plt.title("Entropy change with and without microscopic history")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "entropy_over_time.png", dpi=200)
    plt.close()

    fractions = np.linspace(0.0, 1.0, 9)
    recovery_values = []
    results = []
    forward_final_entropy = forward_entropy[-1]

    for fraction in fractions:
        recoveries = []
        return_rates = []

        for trial in range(20):
            rng = np.random.default_rng(
                SEED + int(fraction * 1000) + 100 * trial + 10
            )
            positions = partial_reverse(
                final_positions,
                history,
                float(fraction),
                rng,
            )
            final_entropy = shannon_entropy(positions)
            recovery = (
                (forward_final_entropy - final_entropy)
                / forward_final_entropy
            )
            recoveries.append(float(np.clip(recovery, 0.0, 1.0)))
            return_rates.append(
                float(np.mean(positions == INITIAL_POSITION))
            )

        mean_recovery = float(np.mean(recoveries))
        mean_return_rate = float(np.mean(return_rates))
        recovery_values.append(mean_recovery)
        results.append((fraction, mean_recovery, mean_return_rate))

    plt.figure(figsize=(8.5, 5.5))
    plt.plot(fractions, recovery_values, marker="o")
    plt.xlabel("Fraction of microscopic history retained")
    plt.ylabel("Fraction of entropy recovered")
    plt.title("More stored history allows stronger entropy reversal")
    plt.ylim(-0.05, 1.05)
    plt.tight_layout()
    plt.savefig(output_dir / "memory_vs_recovery.png", dpi=200)
    plt.close()

    print("Simulation finished.")
    print(f"Initial entropy: {forward_entropy[0]:.4f} bits")
    print(f"Entropy after diffusion: {forward_entropy[-1]:.4f} bits")
    print(f"Entropy after exact reversal: {reverse_entropy[-1]:.4f} bits")
    print(f"Entropy after random backward attempt: {random_entropy[-1]:.4f} bits")
    print(f"Exact return rate: {np.mean(reversed_positions == INITIAL_POSITION):.4f}")
    print(f"Random return rate: {np.mean(random_positions == INITIAL_POSITION):.4f}")
    print(f"KL divergence D_KL(P_guided || P_random): {history_kl:.4f} bits")
    print()
    print("memory_fraction, recovered_entropy_fraction, return_rate")
    for fraction, recovery, return_rate in results:
        print(f"{fraction:.3f}, {recovery:.3f}, {return_rate:.3f}")


if __name__ == "__main__":
    make_figures()
