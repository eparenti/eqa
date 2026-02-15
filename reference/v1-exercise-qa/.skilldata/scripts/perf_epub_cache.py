#!/usr/bin/env python3
"""
EPUB Parsing Cache

Caches parsed EPUB content to avoid re-parsing:
- Caches extracted chapter content
- Caches workflow extractions
- Caches course analysis
- Intelligent cache invalidation based on file modification time
"""

import sys
import json
import hashlib
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Any, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class EPUBCache:
    """
    EPUB parsing cache with intelligent invalidation.
    """

    def __init__(self, cache_dir: Optional[Path] = None, max_age_hours: int = 24):
        """
        Initialize EPUB cache.

        Args:
            cache_dir: Cache directory (defaults to ~/.cache/exercise-qa/)
            max_age_hours: Maximum cache age in hours
        """
        if cache_dir is None:
            cache_dir = Path.home() / '.cache' / 'exercise-qa'

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.max_age = timedelta(hours=max_age_hours)

        # Track cache hits/misses
        self.stats = {
            'hits': 0,
            'misses': 0,
            'invalidations': 0
        }

    def _get_cache_key(self, epub_path: Path, operation: str, **kwargs) -> str:
        """
        Generate cache key.

        Args:
            epub_path: Path to EPUB file
            operation: Operation type (e.g., 'chapter', 'workflow', 'analysis')
            **kwargs: Additional parameters that affect cache key

        Returns:
            Cache key (SHA256 hash)
        """
        # Include file modification time in key
        mtime = epub_path.stat().st_mtime if epub_path.exists() else 0

        # Build key components
        key_data = {
            'epub_path': str(epub_path.absolute()),
            'mtime': mtime,
            'operation': operation,
            **kwargs
        }

        # Generate hash
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """
        Get cache file path for key.

        Args:
            cache_key: Cache key

        Returns:
            Path to cache file
        """
        return self.cache_dir / f"{cache_key}.cache"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """
        Check if cache file is still valid.

        Args:
            cache_path: Path to cache file

        Returns:
            True if valid, False otherwise
        """
        if not cache_path.exists():
            return False

        # Check age
        cache_mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - cache_mtime

        if age > self.max_age:
            return False

        return True

    def get(self, epub_path: Path, operation: str, **kwargs) -> Optional[Any]:
        """
        Get cached data.

        Args:
            epub_path: Path to EPUB file
            operation: Operation type
            **kwargs: Additional parameters

        Returns:
            Cached data or None if not found/invalid
        """
        cache_key = self._get_cache_key(epub_path, operation, **kwargs)
        cache_path = self._get_cache_path(cache_key)

        if not self._is_cache_valid(cache_path):
            self.stats['misses'] += 1
            return None

        try:
            with open(cache_path, 'rb') as f:
                data = pickle.load(f)

            self.stats['hits'] += 1
            return data

        except Exception as e:
            print(f"Cache read error: {e}")
            self.stats['misses'] += 1
            return None

    def set(self, epub_path: Path, operation: str, data: Any, **kwargs):
        """
        Store data in cache.

        Args:
            epub_path: Path to EPUB file
            operation: Operation type
            data: Data to cache
            **kwargs: Additional parameters
        """
        cache_key = self._get_cache_key(epub_path, operation, **kwargs)
        cache_path = self._get_cache_path(cache_key)

        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)

        except Exception as e:
            print(f"Cache write error: {e}")

    def invalidate(self, epub_path: Path, operation: Optional[str] = None):
        """
        Invalidate cache entries.

        Args:
            epub_path: Path to EPUB file
            operation: Optional specific operation to invalidate (None = all)
        """
        if operation:
            # Invalidate specific operation
            cache_key = self._get_cache_key(epub_path, operation)
            cache_path = self._get_cache_path(cache_key)

            if cache_path.exists():
                cache_path.unlink()
                self.stats['invalidations'] += 1
        else:
            # Invalidate all entries for this EPUB
            epub_str = str(epub_path.absolute())

            for cache_file in self.cache_dir.glob('*.cache'):
                try:
                    with open(cache_file, 'rb') as f:
                        data = pickle.load(f)

                    # Check if this cache entry is for the EPUB
                    if hasattr(data, '__dict__') and 'epub_path' in data.__dict__:
                        if str(data.epub_path) == epub_str:
                            cache_file.unlink()
                            self.stats['invalidations'] += 1

                except Exception:
                    pass  # Skip problematic cache files

    def clear_all(self):
        """Clear entire cache."""
        for cache_file in self.cache_dir.glob('*.cache'):
            cache_file.unlink()
            self.stats['invalidations'] += 1

    def clear_old(self):
        """Clear old cache entries."""
        for cache_file in self.cache_dir.glob('*.cache'):
            if not self._is_cache_valid(cache_file):
                cache_file.unlink()
                self.stats['invalidations'] += 1

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats
        """
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0

        cache_files = list(self.cache_dir.glob('*.cache'))
        total_size = sum(f.stat().st_size for f in cache_files)

        return {
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'invalidations': self.stats['invalidations'],
            'hit_rate': hit_rate,
            'cache_files': len(cache_files),
            'total_size_mb': total_size / (1024 * 1024),
            'cache_dir': str(self.cache_dir)
        }

    def print_stats(self):
        """Print cache statistics."""
        stats = self.get_stats()

        print("\n" + "=" * 60)
        print("📊 Cache Statistics")
        print("=" * 60)
        print(f"  Cache Directory: {stats['cache_dir']}")
        print(f"  Cache Files: {stats['cache_files']}")
        print(f"  Total Size: {stats['total_size_mb']:.2f} MB")
        print()
        print(f"  Hits: {stats['hits']}")
        print(f"  Misses: {stats['misses']}")
        print(f"  Hit Rate: {stats['hit_rate']:.1f}%")
        print(f"  Invalidations: {stats['invalidations']}")
        print("=" * 60)


class CachedEPUBParser:
    """
    EPUB parser with automatic caching.

    Wraps EPUB parsing operations with transparent caching.
    """

    def __init__(self, cache: Optional[EPUBCache] = None):
        """
        Initialize cached parser.

        Args:
            cache: Optional EPUBCache instance (creates default if None)
        """
        self.cache = cache or EPUBCache()

    def extract_chapter(self, epub_path: Path, chapter_name: str,
                       parser_func: callable) -> Any:
        """
        Extract chapter with caching.

        Args:
            epub_path: Path to EPUB file
            chapter_name: Chapter name
            parser_func: Function to parse chapter (called only on cache miss)

        Returns:
            Parsed chapter content
        """
        # Try cache first
        cached = self.cache.get(epub_path, 'chapter', chapter=chapter_name)

        if cached is not None:
            return cached

        # Cache miss - parse and store
        result = parser_func(epub_path, chapter_name)
        self.cache.set(epub_path, 'chapter', result, chapter=chapter_name)

        return result

    def extract_workflow(self, epub_path: Path, exercise_id: str,
                        extractor_func: callable) -> Any:
        """
        Extract workflow with caching.

        Args:
            epub_path: Path to EPUB file
            exercise_id: Exercise ID
            extractor_func: Function to extract workflow (called only on cache miss)

        Returns:
            Extracted workflow
        """
        # Try cache first
        cached = self.cache.get(epub_path, 'workflow', exercise=exercise_id)

        if cached is not None:
            return cached

        # Cache miss - extract and store
        result = extractor_func(epub_path, exercise_id)
        self.cache.set(epub_path, 'workflow', result, exercise=exercise_id)

        return result

    def analyze_course(self, epub_path: Path, analyzer_func: callable) -> Any:
        """
        Analyze course with caching.

        Args:
            epub_path: Path to EPUB file
            analyzer_func: Function to analyze course (called only on cache miss)

        Returns:
            Course analysis
        """
        # Try cache first
        cached = self.cache.get(epub_path, 'analysis')

        if cached is not None:
            return cached

        # Cache miss - analyze and store
        result = analyzer_func(epub_path)
        self.cache.set(epub_path, 'analysis', result)

        return result


def demo():
    """Demo EPUB caching."""
    import time

    # Create cache
    cache = EPUBCache()

    # Clear old entries
    print("Clearing old cache entries...")
    cache.clear_old()

    # Simulate EPUB parsing
    epub_path = Path("/tmp/test-course.epub")
    epub_path.touch()  # Create dummy file

    # First access (cache miss)
    print("\nFirst access (cache miss expected):")
    data1 = cache.get(epub_path, 'chapter', chapter='chapter1')
    print(f"  Result: {data1}")

    # Store data
    test_data = {
        'chapter': 'chapter1',
        'content': 'This is chapter 1 content',
        'timestamp': datetime.now().isoformat()
    }
    cache.set(epub_path, 'chapter', test_data, chapter='chapter1')
    print(f"  Stored: {test_data}")

    # Second access (cache hit)
    print("\nSecond access (cache hit expected):")
    data2 = cache.get(epub_path, 'chapter', chapter='chapter1')
    print(f"  Result: {data2}")

    # Print stats
    cache.print_stats()

    # Cleanup
    epub_path.unlink()


if __name__ == "__main__":
    demo()
