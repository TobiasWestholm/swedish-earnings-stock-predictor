#!/usr/bin/env python3
"""
Test Gaussian smoothing implementation for earnings analysis.
"""

import numpy as np

# Test data: create a noisy signal
np.random.seed(42)
x = np.linspace(0, 10, 100)
signal = np.sin(x) + 0.3 * np.random.randn(100)

# Apply Gaussian smoothing
window_size = 15
sigma = 3.0

# Create Gaussian kernel
kernel_x = np.arange(window_size) - (window_size - 1) / 2
kernel = np.exp(-0.5 * (kernel_x / sigma) ** 2)
kernel = kernel / kernel.sum()

print("Gaussian Kernel:")
print(f"  Window size: {window_size}")
print(f"  Sigma: {sigma}")
print(f"  Kernel sum: {kernel.sum():.6f} (should be 1.0)")
print(f"  Kernel shape: {kernel.shape}")
print(f"  Kernel values: {kernel}")

# Apply convolution
smoothed = np.convolve(signal, kernel, mode='same')

print(f"\nSignal shape: {signal.shape}")
print(f"Smoothed shape: {smoothed.shape}")
print(f"Signal range: [{signal.min():.2f}, {signal.max():.2f}]")
print(f"Smoothed range: [{smoothed.min():.2f}, {smoothed.max():.2f}]")

# Visual comparison (first 10 points)
print("\nFirst 10 points comparison:")
print("Index | Original | Smoothed | Difference")
print("-" * 50)
for i in range(10):
    diff = smoothed[i] - signal[i]
    print(f"{i:5d} | {signal[i]:8.3f} | {smoothed[i]:8.3f} | {diff:8.3f}")

# Test with earnings-like data (percentage values around 100)
earnings_like = 100 + 2 * np.sin(x) + 0.8 * np.random.randn(100)
earnings_smoothed = np.convolve(earnings_like, kernel, mode='same')

print(f"\nEarnings-like data:")
print(f"  Original range: [{earnings_like.min():.2f}, {earnings_like.max():.2f}]")
print(f"  Smoothed range: [{earnings_smoothed.min():.2f}, {earnings_smoothed.max():.2f}]")

print("\n✓ Gaussian smoothing test complete!")
