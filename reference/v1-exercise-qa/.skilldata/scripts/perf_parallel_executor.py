#!/usr/bin/env python3
"""
Parallel Test Execution

Executes multiple tests concurrently for improved performance:
- Parallel test category execution (when tests are independent)
- Concurrent exercise testing
- Connection pooling for SSH
- Smart scheduling based on dependencies
"""

import sys
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from typing import List, Dict, Any, Callable, Optional
from queue import Queue
import threading

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.ssh_connection import SSHConnection
from lib.test_result import TestResult, ExerciseContext


class ConnectionPool:
    """
    SSH connection pool for concurrent test execution.

    Maintains a pool of SSH connections to avoid overhead of
    creating new connections for each test.
    """

    def __init__(self, workstation: str, pool_size: int = 3):
        """
        Initialize connection pool.

        Args:
            workstation: Workstation hostname
            pool_size: Maximum number of concurrent connections
        """
        self.workstation = workstation
        self.pool_size = pool_size
        self.connections: Queue = Queue(maxsize=pool_size)
        self.lock = threading.Lock()

        # Create initial connections
        for _ in range(pool_size):
            conn = SSHConnection(workstation, username="student")
            self.connections.put(conn)

    def get_connection(self) -> SSHConnection:
        """
        Get a connection from the pool.

        Returns:
            SSH connection (blocks if pool is empty)
        """
        return self.connections.get()

    def release_connection(self, conn: SSHConnection):
        """
        Return connection to pool.

        Args:
            conn: SSH connection to release
        """
        self.connections.put(conn)

    def close_all(self):
        """Close all connections in pool."""
        while not self.connections.empty():
            conn = self.connections.get()
            conn.close()


class ParallelExecutor:
    """
    Parallel test executor.

    Executes tests concurrently while respecting dependencies.
    """

    def __init__(self, max_workers: int = 3, use_processes: bool = False):
        """
        Initialize parallel executor.

        Args:
            max_workers: Maximum number of concurrent workers
            use_processes: Use processes instead of threads (for CPU-bound tasks)
        """
        self.max_workers = max_workers
        self.use_processes = use_processes
        self.connection_pool: Optional[ConnectionPool] = None

    def setup_connection_pool(self, workstation: str):
        """
        Setup SSH connection pool.

        Args:
            workstation: Workstation hostname
        """
        self.connection_pool = ConnectionPool(workstation, self.max_workers)

    def execute_tests_parallel(self, test_tasks: List[Dict[str, Any]],
                               progress_callback: Optional[Callable] = None) -> List[TestResult]:
        """
        Execute multiple tests in parallel.

        Args:
            test_tasks: List of test tasks (dict with 'func', 'args', 'kwargs')
            progress_callback: Optional callback for progress updates

        Returns:
            List of test results
        """
        results = []

        # Use thread pool (better for I/O-bound SSH operations)
        ExecutorClass = ProcessPoolExecutor if self.use_processes else ThreadPoolExecutor

        with ExecutorClass(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_task = {}
            for task in test_tasks:
                future = executor.submit(
                    task['func'],
                    *task.get('args', []),
                    **task.get('kwargs', {})
                )
                future_to_task[future] = task

            # Collect results as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)

                    if progress_callback:
                        progress_callback(result, task)

                except Exception as e:
                    print(f"Task failed: {task.get('name', 'Unknown')}")
                    print(f"Error: {e}")

                    # Create error result
                    error_result = TestResult(
                        category=task.get('category', 'Unknown'),
                        exercise_id=task.get('exercise_id', 'Unknown'),
                        passed=False,
                        timestamp=datetime.now().isoformat(),
                        duration_seconds=0,
                        error_message=str(e)
                    )
                    results.append(error_result)

        return results

    def execute_test_categories_parallel(self, exercise: ExerciseContext,
                                        test_categories: List[Any],
                                        ssh: SSHConnection) -> Dict[str, TestResult]:
        """
        Execute multiple test categories in parallel for a single exercise.

        Only executes independent categories in parallel. Sequential dependencies
        are respected (e.g., TC-PREREQ must complete before others).

        Args:
            exercise: Exercise context
            test_categories: List of test category instances
            ssh: SSH connection

        Returns:
            Dict mapping category name to test result
        """
        results = {}

        # Phase 1: Prerequisites (must run first, blocking)
        prereq_categories = [tc for tc in test_categories
                            if getattr(tc, '__class__.__name__', '') == 'TC_PREREQ']

        for tc in prereq_categories:
            result = tc.test(exercise, ssh)
            results[tc.__class__.__name__] = result

            if not result.passed:
                # Prerequisites failed, skip remaining tests
                return results

        # Phase 2: Independent tests (can run in parallel)
        independent_categories = [
            tc for tc in test_categories
            if getattr(tc, '__class__.__name__', '') in [
                'TC_INSTRUCT',  # Analyzes EPUB only
                'TC_SOL',       # Tests solutions
                'TC_EXEC',      # Executes commands
                'TC_WORKFLOW'   # Automated workflow
            ]
        ]

        if independent_categories:
            # Build tasks
            tasks = []
            for tc in independent_categories:
                tasks.append({
                    'func': tc.test,
                    'args': [exercise, ssh],
                    'name': tc.__class__.__name__,
                    'category': tc.__class__.__name__,
                    'exercise_id': exercise.id
                })

            # Execute in parallel
            parallel_results = self.execute_tests_parallel(tasks)

            for result in parallel_results:
                results[result.category] = result

        # Phase 3: Dependent tests (must run sequentially after phase 2)
        dependent_categories = [
            tc for tc in test_categories
            if getattr(tc, '__class__.__name__', '') in [
                'TC_GRADE',  # Depends on solutions being tested
                'TC_IDEM',   # Depends on exercise completion
                'TC_CLEAN'   # Must be last
            ]
        ]

        for tc in dependent_categories:
            # Check if we should pass additional context
            if tc.__class__.__name__ == 'TC_CLEAN':
                # TC_CLEAN needs initial state
                result = tc.test(exercise, ssh, initial_state=None)
            else:
                result = tc.test(exercise, ssh)

            results[tc.__class__.__name__] = result

        return results

    def execute_exercises_parallel(self, exercises: List[ExerciseContext],
                                   test_func: Callable,
                                   progress_callback: Optional[Callable] = None) -> List[Dict]:
        """
        Execute tests for multiple exercises in parallel.

        Args:
            exercises: List of exercises to test
            test_func: Function to test a single exercise
            progress_callback: Optional progress callback

        Returns:
            List of test results (one per exercise)
        """
        # Build tasks
        tasks = []
        for exercise in exercises:
            tasks.append({
                'func': test_func,
                'args': [exercise],
                'name': exercise.id,
                'category': 'FULL',
                'exercise_id': exercise.id
            })

        # Execute in parallel
        return self.execute_tests_parallel(tasks, progress_callback)

    def smart_schedule(self, exercises: List[ExerciseContext],
                      dependency_graph: Optional[Dict] = None) -> List[List[ExerciseContext]]:
        """
        Create smart schedule for parallel execution.

        Groups exercises that can run in parallel while respecting dependencies.

        Args:
            exercises: List of exercises
            dependency_graph: Optional dependency graph

        Returns:
            List of batches (each batch can run in parallel)
        """
        if not dependency_graph:
            # No dependencies - all can run in parallel (in batches of max_workers)
            batches = []
            for i in range(0, len(exercises), self.max_workers):
                batches.append(exercises[i:i + self.max_workers])
            return batches

        # TODO: Implement dependency-aware scheduling
        # For now, use simple batching
        return self.smart_schedule(exercises, None)

    def cleanup(self):
        """Cleanup resources."""
        if self.connection_pool:
            self.connection_pool.close_all()


class PerformanceMetrics:
    """
    Track performance metrics for parallel execution.
    """

    def __init__(self):
        """Initialize metrics tracker."""
        self.start_time = None
        self.end_time = None
        self.total_tests = 0
        self.parallel_tests = 0
        self.sequential_tests = 0
        self.time_saved = 0

    def start(self):
        """Start tracking."""
        self.start_time = time.time()

    def end(self):
        """End tracking."""
        self.end_time = time.time()

    def record_parallel_batch(self, batch_size: int, duration: float):
        """
        Record parallel batch execution.

        Args:
            batch_size: Number of tests in batch
            duration: Time taken
        """
        self.parallel_tests += batch_size
        self.total_tests += batch_size

        # Estimate time saved (assumes each test would take duration/batch_size sequentially)
        estimated_sequential_time = (duration / batch_size) * batch_size
        self.time_saved += (estimated_sequential_time - duration)

    def record_sequential_test(self, duration: float):
        """
        Record sequential test execution.

        Args:
            duration: Time taken
        """
        self.sequential_tests += 1
        self.total_tests += 1

    def get_summary(self) -> Dict[str, Any]:
        """
        Get performance summary.

        Returns:
            Dict with performance metrics
        """
        total_duration = (self.end_time - self.start_time) if self.end_time and self.start_time else 0

        return {
            'total_duration': total_duration,
            'total_tests': self.total_tests,
            'parallel_tests': self.parallel_tests,
            'sequential_tests': self.sequential_tests,
            'time_saved_estimate': self.time_saved,
            'speedup_factor': (total_duration + self.time_saved) / total_duration if total_duration > 0 else 1.0
        }

    def print_summary(self):
        """Print performance summary."""
        summary = self.get_summary()

        print("\n" + "=" * 60)
        print("⚡ Performance Metrics")
        print("=" * 60)
        print(f"  Total Duration: {summary['total_duration']:.2f}s")
        print(f"  Total Tests: {summary['total_tests']}")
        print(f"  Parallel Tests: {summary['parallel_tests']}")
        print(f"  Sequential Tests: {summary['sequential_tests']}")
        print(f"  Estimated Time Saved: {summary['time_saved_estimate']:.2f}s")
        print(f"  Speedup Factor: {summary['speedup_factor']:.2f}x")
        print("=" * 60)


def demo():
    """Demo parallel execution."""
    import random

    def mock_test(exercise_id: str, duration: float) -> TestResult:
        """Mock test function."""
        time.sleep(duration)
        return TestResult(
            category="TC-DEMO",
            exercise_id=exercise_id,
            passed=random.choice([True, True, False]),  # 2/3 pass rate
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration
        )

    # Create exercises
    exercises = [f"exercise-{i}" for i in range(10)]

    # Test sequential execution
    print("Sequential Execution:")
    print("-" * 60)
    start = time.time()
    for ex in exercises:
        result = mock_test(ex, 0.5)
        print(f"  {result.exercise_id}: {'PASS' if result.passed else 'FAIL'}")
    seq_duration = time.time() - start
    print(f"\nTotal time: {seq_duration:.2f}s")

    # Test parallel execution
    print("\n\nParallel Execution (3 workers):")
    print("-" * 60)

    executor = ParallelExecutor(max_workers=3)
    metrics = PerformanceMetrics()
    metrics.start()

    tasks = []
    for ex in exercises:
        tasks.append({
            'func': mock_test,
            'args': [ex, 0.5],
            'name': ex,
            'category': 'TC-DEMO',
            'exercise_id': ex
        })

    results = executor.execute_tests_parallel(tasks)

    for result in results:
        print(f"  {result.exercise_id}: {'PASS' if result.passed else 'FAIL'}")

    metrics.end()
    par_duration = time.time() - start - seq_duration

    print(f"\nTotal time: {par_duration:.2f}s")
    print(f"Speedup: {seq_duration / par_duration:.2f}x")


if __name__ == "__main__":
    demo()
