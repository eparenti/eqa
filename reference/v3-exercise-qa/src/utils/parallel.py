"""Parallel test execution with SSH connection pooling."""

import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty
from typing import List, Optional, Callable, Any
from pathlib import Path

from ..clients.ssh import SSHConnection
from ..core.models import ExerciseContext, ExerciseTestResults


class ConnectionPool:
    """
    SSH connection pool for concurrent test execution.

    Maintains a pool of SSH connections to avoid the overhead of
    creating new connections for each test.
    """

    def __init__(self, host: str, username: str = "student", pool_size: int = 3):
        """
        Initialize connection pool.

        Args:
            host: Hostname (e.g., 'workstation')
            username: SSH username
            pool_size: Maximum number of concurrent connections
        """
        self.host = host
        self.username = username
        self.pool_size = pool_size
        self.connections: Queue = Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        self._initialized = False

    def initialize(self) -> bool:
        """
        Create initial connections.

        Returns:
            True if at least one connection succeeded
        """
        print(f"   🔌 Initializing connection pool ({self.pool_size} connections)...")

        success_count = 0
        for i in range(self.pool_size):
            conn = SSHConnection(self.host, username=self.username)
            if conn.connect():
                self.connections.put(conn)
                success_count += 1
                print(f"      ✓ Connection {i+1}/{self.pool_size} ready")
            else:
                print(f"      ✗ Connection {i+1}/{self.pool_size} failed")

        self._initialized = success_count > 0
        print(f"   {'✓' if self._initialized else '✗'} Pool ready with {success_count} connection(s)")
        return self._initialized

    def get_connection(self, timeout: float = 10.0) -> Optional[SSHConnection]:
        """
        Get a connection from the pool.

        Args:
            timeout: Maximum time to wait for available connection

        Returns:
            SSH connection or None if timeout
        """
        try:
            return self.connections.get(timeout=timeout)
        except Empty:
            return None

    def release_connection(self, conn: SSHConnection):
        """
        Return connection to pool.

        Args:
            conn: SSH connection to release
        """
        if conn and conn.test_connection():
            self.connections.put(conn)
        else:
            # Connection is dead, create a new one
            new_conn = SSHConnection(self.host, username=self.username)
            if new_conn.connect():
                self.connections.put(new_conn)

    def close_all(self):
        """Close all connections in pool."""
        while not self.connections.empty():
            try:
                conn = self.connections.get_nowait()
                conn.close()
            except Empty:
                break


class ParallelExecutor:
    """
    Parallel test executor for multiple exercises.

    Executes tests concurrently while managing SSH connection pool.
    """

    def __init__(self, max_workers: int = 3):
        """
        Initialize parallel executor.

        Args:
            max_workers: Maximum number of concurrent test executions
        """
        self.max_workers = max_workers
        self.connection_pool: Optional[ConnectionPool] = None

    def setup_connection_pool(self, host: str, username: str = "student") -> bool:
        """
        Setup SSH connection pool.

        Args:
            host: Hostname
            username: SSH username

        Returns:
            True if pool was initialized successfully
        """
        self.connection_pool = ConnectionPool(host, username, self.max_workers)
        return self.connection_pool.initialize()

    def execute_tests(
        self,
        exercises: List[ExerciseContext],
        test_function: Callable[[ExerciseContext, SSHConnection], ExerciseTestResults]
    ) -> List[ExerciseTestResults]:
        """
        Execute tests in parallel across multiple exercises.

        Args:
            exercises: List of exercises to test
            test_function: Function that tests a single exercise

        Returns:
            List of test results (in original order)
        """
        if not self.connection_pool or not self.connection_pool._initialized:
            raise RuntimeError("Connection pool not initialized. Call setup_connection_pool() first.")

        results = [None] * len(exercises)  # Pre-allocate to maintain order

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tests
            future_to_index = {}
            for i, exercise in enumerate(exercises):
                future = executor.submit(self._execute_single_test, exercise, test_function)
                future_to_index[future] = i

            # Collect results as they complete
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()
                    results[index] = result
                except Exception as e:
                    print(f"   ✗ Error testing {exercises[index].id}: {e}")
                    # Create a failed result
                    results[index] = self._create_error_result(exercises[index], str(e))

        return results

    def _execute_single_test(
        self,
        exercise: ExerciseContext,
        test_function: Callable[[ExerciseContext, SSHConnection], ExerciseTestResults]
    ) -> ExerciseTestResults:
        """
        Execute test for a single exercise using connection from pool.

        Args:
            exercise: Exercise to test
            test_function: Test function

        Returns:
            Test results
        """
        # Get connection from pool
        conn = self.connection_pool.get_connection(timeout=30.0)
        if not conn:
            raise RuntimeError(f"Failed to get SSH connection for {exercise.id}")

        try:
            # Execute test
            result = test_function(exercise, conn)
            return result
        finally:
            # Return connection to pool
            self.connection_pool.release_connection(conn)

    def _create_error_result(self, exercise: ExerciseContext, error: str) -> ExerciseTestResults:
        """Create an error result for failed test execution."""
        from datetime import datetime
        from ..core.models import Bug, BugSeverity

        bug = Bug(
            id=f"EXEC-ERROR-001-{exercise.id}",
            severity=BugSeverity.P0_BLOCKER,
            category="TC-EXEC",
            exercise_id=exercise.id,
            description=f"Test execution failed: {error}",
            fix_recommendation="Check test framework and SSH connectivity"
        )

        return ExerciseTestResults(
            exercise_id=exercise.id,
            lesson_code=exercise.lesson_code,
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            duration_seconds=0.0,
            status="FAIL",
            test_categories={},
            bugs=[bug],
            summary="Test execution error"
        )

    def cleanup(self):
        """Clean up resources."""
        if self.connection_pool:
            self.connection_pool.close_all()
