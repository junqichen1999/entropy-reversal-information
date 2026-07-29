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

    x_values = np.arange(-60, 61)
    plt.figure(figsize=(10, 5.5))
    plt.plot(x_values, distribution(initial, x_values), label="Initial ordered state")
    plt.plot(x_values, distribution(final_positions, x_values), label="After random diffusion")
    plt.plot(x_values, distribution(reversed_positions, x_values), label="After exact reversal")
    plt.xlabel("Position")
    plt.ylabel("Probability")
    plt.title("Particle distributions before and after entropy reversal")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "particle_distributions.png", dpi=200)
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
    print()
    print("memory_fraction, recovered_entropy_fraction, return_rate")
    for fraction, recovery, return_rate in results:
        print(f"{fraction:.3f}, {recovery:.3f}, {return_rate:.3f}")


if __name__ == "__main__":
    make_figures()
