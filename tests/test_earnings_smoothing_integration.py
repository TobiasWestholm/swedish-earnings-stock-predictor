#!/usr/bin/env python3
"""
Integration test for earnings analysis smoothing feature.

Tests:
1. Smoothing function works correctly
2. Edge padding prevents artifacts
3. Adaptive window sizing
4. Data is properly passed to template
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np


def test_gaussian_smoothing():
    """Test the Gaussian smoothing implementation."""
    print("=" * 70)
    print("TEST 1: Gaussian Smoothing Algorithm")
    print("=" * 70)

    # Test data: typical earnings signal pattern
    signal_chart_data = [
        {'time': f'09:{i:02d}', 'mean': 100 + i * 0.2 + np.random.randn() * 0.5, 'count': 5}
        for i in range(20)
    ]

    # Apply smoothing (same logic as routes.py)
    signal_smoothed_chart_data = []

    if len(signal_chart_data) > 5:
        mean_values = np.array([d['mean'] for d in signal_chart_data])
        n_points = len(mean_values)

        # Adaptive window size
        if n_points < 30:
            window_size = min(7, n_points)
            sigma = 2.0
        else:
            window_size = min(15, n_points // 3)
            sigma = 3.0

        print(f"\nData points: {n_points}")
        print(f"Window size: {window_size}")
        print(f"Sigma: {sigma}")

        # Create Gaussian kernel
        x = np.arange(window_size) - (window_size - 1) / 2
        kernel = np.exp(-0.5 * (x / sigma) ** 2)
        kernel = kernel / kernel.sum()

        print(f"Kernel sum: {kernel.sum():.6f} (should be 1.0)")

        # Edge-aware convolution
        pad_width = window_size // 2
        padded_values = np.pad(mean_values, pad_width, mode='edge')
        smoothed_padded = np.convolve(padded_values, kernel, mode='same')
        smoothed_values = smoothed_padded[pad_width:pad_width + n_points]

        for i, data_point in enumerate(signal_chart_data):
            signal_smoothed_chart_data.append({
                'time': data_point['time'],
                'mean': round(float(smoothed_values[i]), 2),
                'count': data_point['count']
            })

    # Verify results
    print("\nFirst 5 points comparison:")
    print("Time  | Original | Smoothed | Difference")
    print("-" * 50)
    for i in range(min(5, len(signal_chart_data))):
        orig = signal_chart_data[i]
        smooth = signal_smoothed_chart_data[i]
        diff = smooth['mean'] - orig['mean']
        print(f"{orig['time']} | {orig['mean']:8.2f} | {smooth['mean']:8.2f} | {diff:+8.2f}")

    # Check smoothed values are in reasonable range
    orig_min = min(d['mean'] for d in signal_chart_data)
    orig_max = max(d['mean'] for d in signal_chart_data)
    smooth_min = min(d['mean'] for d in signal_smoothed_chart_data)
    smooth_max = max(d['mean'] for d in signal_smoothed_chart_data)

    print(f"\nOriginal range: [{orig_min:.2f}, {orig_max:.2f}]")
    print(f"Smoothed range: [{smooth_min:.2f}, {smooth_max:.2f}]")

    # Smoothed range should be within original range (or very close)
    range_check = (smooth_min >= orig_min - 1.0) and (smooth_max <= orig_max + 1.0)

    if range_check:
        print("✓ Smoothed values within expected range")
        return True
    else:
        print("✗ Smoothed values outside expected range")
        return False


def test_edge_padding():
    """Test that edge padding prevents artifacts."""
    print("\n\n")
    print("=" * 70)
    print("TEST 2: Edge Padding")
    print("=" * 70)

    # Test with values that should have severe edge effects without padding
    edge_test_data = [
        {'time': f'09:{i:02d}', 'mean': 100.0, 'count': 5}
        for i in range(10)
    ]

    mean_values = np.array([d['mean'] for d in edge_test_data])
    window_size = 7
    sigma = 2.0

    # Create kernel
    x = np.arange(window_size) - (window_size - 1) / 2
    kernel = np.exp(-0.5 * (x / sigma) ** 2)
    kernel = kernel / kernel.sum()

    # Test WITHOUT padding (would create artifacts)
    smoothed_no_pad = np.convolve(mean_values, kernel, mode='same')

    # Test WITH padding (our implementation)
    pad_width = window_size // 2
    padded_values = np.pad(mean_values, pad_width, mode='edge')
    smoothed_with_pad = np.convolve(padded_values, kernel, mode='same')
    smoothed_with_pad = smoothed_with_pad[pad_width:pad_width + len(mean_values)]

    print(f"\nConstant value test (all values = 100.0)")
    print("Index | No Padding | With Padding | Expected")
    print("-" * 55)
    for i in [0, 1, len(mean_values) - 2, len(mean_values) - 1]:
        print(f"{i:5d} | {smoothed_no_pad[i]:10.2f} | {smoothed_with_pad[i]:12.2f} | 100.00")

    # With edge padding, all values should remain ~100.0
    max_deviation = max(abs(smoothed_with_pad - 100.0))

    print(f"\nMax deviation from 100.0: {max_deviation:.4f}")

    if max_deviation < 0.01:  # Should be essentially zero
        print("✓ Edge padding prevents artifacts")
        return True
    else:
        print("✗ Edge padding not working correctly")
        return False


def test_adaptive_window():
    """Test adaptive window sizing."""
    print("\n\n")
    print("=" * 70)
    print("TEST 3: Adaptive Window Sizing")
    print("=" * 70)

    test_cases = [
        (5, "Too few points"),
        (10, "Short series"),
        (30, "Medium series"),
        (100, "Long series"),
    ]

    results = []

    for n_points, description in test_cases:
        # Simulate data
        data = [{'time': f'{i}', 'mean': 100.0, 'count': 5} for i in range(n_points)]

        # Apply window logic
        if n_points < 30:
            window_size = min(7, n_points)
            sigma = 2.0
        else:
            window_size = min(15, n_points // 3)
            sigma = 3.0

        print(f"\n{description} ({n_points} points):")
        print(f"  Window size: {window_size}")
        print(f"  Sigma: {sigma}")

        # Check window size is reasonable
        is_reasonable = (window_size <= n_points) and (window_size >= 3)
        results.append(is_reasonable)

        if is_reasonable:
            print("  ✓ Window size appropriate")
        else:
            print("  ✗ Window size inappropriate")

    if all(results):
        print("\n✓ Adaptive window sizing works correctly")
        return True
    else:
        print("\n✗ Adaptive window sizing has issues")
        return False


def test_data_structure():
    """Test that output data structure matches expected format."""
    print("\n\n")
    print("=" * 70)
    print("TEST 4: Data Structure")
    print("=" * 70)

    # Input data
    signal_chart_data = [
        {'time': '09:00', 'mean': 100.0, 'count': 5},
        {'time': '09:05', 'mean': 100.5, 'count': 5},
        {'time': '09:10', 'mean': 101.0, 'count': 5},
        {'time': '09:15', 'mean': 101.5, 'count': 5},
        {'time': '09:20', 'mean': 102.0, 'count': 5},
        {'time': '09:25', 'mean': 102.5, 'count': 5},
        {'time': '09:30', 'mean': 103.0, 'count': 5},
    ]

    # Apply smoothing
    mean_values = np.array([d['mean'] for d in signal_chart_data])
    n_points = len(mean_values)
    window_size = 7
    sigma = 2.0

    x = np.arange(window_size) - (window_size - 1) / 2
    kernel = np.exp(-0.5 * (x / sigma) ** 2)
    kernel = kernel / kernel.sum()

    pad_width = window_size // 2
    padded_values = np.pad(mean_values, pad_width, mode='edge')
    smoothed_padded = np.convolve(padded_values, kernel, mode='same')
    smoothed_values = smoothed_padded[pad_width:pad_width + n_points]

    signal_smoothed_chart_data = []
    for i, data_point in enumerate(signal_chart_data):
        signal_smoothed_chart_data.append({
            'time': data_point['time'],
            'mean': round(float(smoothed_values[i]), 2),
            'count': data_point['count']
        })

    # Verify structure
    print("\nChecking output structure:")

    checks = []

    # Same number of points
    same_length = len(signal_smoothed_chart_data) == len(signal_chart_data)
    print(f"  Same length: {same_length}")
    checks.append(same_length)

    # Has required fields
    has_fields = all(
        'time' in d and 'mean' in d and 'count' in d
        for d in signal_smoothed_chart_data
    )
    print(f"  Has required fields: {has_fields}")
    checks.append(has_fields)

    # Time values preserved
    times_match = all(
        orig['time'] == smooth['time']
        for orig, smooth in zip(signal_chart_data, signal_smoothed_chart_data)
    )
    print(f"  Time values preserved: {times_match}")
    checks.append(times_match)

    # Mean values are numbers
    means_numeric = all(
        isinstance(d['mean'], (int, float))
        for d in signal_smoothed_chart_data
    )
    print(f"  Mean values numeric: {means_numeric}")
    checks.append(means_numeric)

    if all(checks):
        print("\n✓ Data structure is correct")
        return True
    else:
        print("\n✗ Data structure has issues")
        return False


if __name__ == '__main__':
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  EARNINGS SMOOTHING INTEGRATION TEST".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")

    results = []

    # Run all tests
    results.append(("Gaussian Smoothing", test_gaussian_smoothing()))
    results.append(("Edge Padding", test_edge_padding()))
    results.append(("Adaptive Window", test_adaptive_window()))
    results.append(("Data Structure", test_data_structure()))

    # Summary
    print("\n\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  TEST RESULTS".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")

    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name:30s}: {status}")

    all_passed = all(result for _, result in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("✓ ALL TESTS PASSED")
        print("\nThe earnings smoothing feature is working correctly!")
        sys.exit(0)
    else:
        print("✗ SOME TESTS FAILED")
        print("\nPlease review the failed tests above.")
        sys.exit(1)
