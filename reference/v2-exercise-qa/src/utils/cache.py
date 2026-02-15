"""Result caching with intelligent invalidation.

Uses JSON for serialization (safer and more portable than pickle).
Uses atomic writes to prevent cache corruption.
"""

import json
import hashlib
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Any, Dict
from dataclasses import asdict, is_dataclass

from ..core.models import ExerciseTestResults, CourseContext, ExerciseContext, ExerciseType, ExercisePattern


def _deserialize_course_context(data: Dict) -> CourseContext:
    """Reconstruct CourseContext from serialized dict."""
    # Reconstruct exercises
    exercises = []
    for ex_data in data.get('exercises', []):
        # Convert type string back to enum
        ex_type = ExerciseType.UNKNOWN
        type_val = ex_data.get('type', 'Unknown')
        for t in ExerciseType:
            if t.value == type_val:
                ex_type = t
                break

        # Convert pattern string back to enum
        pattern = ExercisePattern.UNKNOWN
        pattern_val = ex_data.get('pattern', 'unknown')
        for p in ExercisePattern:
            if p.value == pattern_val:
                pattern = p
                break

        exercise = ExerciseContext(
            id=ex_data.get('id', ''),
            type=ex_type,
            lesson_code=ex_data.get('lesson_code', ''),
            chapter=ex_data.get('chapter', 0),
            chapter_title=ex_data.get('chapter_title', ''),
            title=ex_data.get('title', ''),
            lesson_path=Path(ex_data['lesson_path']) if ex_data.get('lesson_path') else None,
            solution_files=[Path(p) for p in ex_data.get('solution_files', [])],
            grading_script=Path(ex_data['grading_script']) if ex_data.get('grading_script') else None,
            materials_dir=Path(ex_data['materials_dir']) if ex_data.get('materials_dir') else None,
            pattern=pattern
        )
        exercises.append(exercise)

    return CourseContext(
        course_code=data.get('course_code', ''),
        course_title=data.get('course_title', ''),
        epub_path=Path(data['epub_path']) if data.get('epub_path') else None,
        exercises=exercises
    )


def _serialize_dataclass(obj: Any) -> Any:
    """Recursively convert dataclasses and enums to JSON-serializable dicts."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serialize_dataclass(v) for k, v in asdict(obj).items()}
    elif isinstance(obj, dict):
        return {k: _serialize_dataclass(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_dataclass(item) for item in obj]
    elif hasattr(obj, 'value'):  # Enum
        return obj.value
    elif isinstance(obj, Path):
        return str(obj)
    else:
        return obj


def _atomic_write(path: Path, data: str):
    """Write data to file atomically using temp file + rename."""
    # Write to temp file in same directory (ensures same filesystem)
    fd, temp_path = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with open(fd, 'w') as f:
            f.write(data)
        # Atomic rename
        shutil.move(temp_path, path)
    except Exception:
        # Clean up temp file on failure
        try:
            Path(temp_path).unlink()
        except Exception:
            pass
        raise


class ResultCache:
    """
    Test result cache with intelligent invalidation.

    Caches passing test results to skip re-running tests that already passed.
    """

    def __init__(self, cache_dir: Optional[Path] = None, max_age_hours: int = 24):
        """
        Initialize result cache.

        Args:
            cache_dir: Cache directory (defaults to ~/.cache/exercise-qa-2/)
            max_age_hours: Maximum cache age in hours
        """
        if cache_dir is None:
            cache_dir = Path.home() / '.cache' / 'exercise-qa-2' / 'results'

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.max_age = timedelta(hours=max_age_hours)

        # Track cache hits/misses
        self.stats = {
            'hits': 0,
            'misses': 0,
            'invalidations': 0
        }

    def _get_cache_key(self, exercise_id: str, lesson_path: Path) -> str:
        """
        Generate cache key based on exercise and file modification times.

        Args:
            exercise_id: Exercise identifier
            lesson_path: Path to lesson directory

        Returns:
            Cache key (SHA256 hash)
        """
        # Get modification time of key files
        key_files = []

        # Solution files
        solutions_dir = lesson_path / "materials" / "labs" / exercise_id / "solutions"
        if solutions_dir.exists():
            for sol_file in solutions_dir.glob("*.sol"):
                key_files.append((str(sol_file), sol_file.stat().st_mtime))

        # Grading script
        grading_dir = lesson_path / "classroom" / "grading" / "src"
        if grading_dir.exists():
            for grade_file in grading_dir.rglob(f"*{exercise_id}*"):
                if grade_file.is_file():
                    key_files.append((str(grade_file), grade_file.stat().st_mtime))

        # Build key data
        key_data = {
            'exercise_id': exercise_id,
            'lesson_path': str(lesson_path),
            'files': key_files
        }

        # Generate hash
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for key."""
        return self.cache_dir / f"{cache_key}.json"

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
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - mtime

        if age > self.max_age:
            return False

        return True

    def get(self, exercise_id: str, lesson_path: Path) -> Optional[ExerciseTestResults]:
        """
        Get cached test result.

        Args:
            exercise_id: Exercise identifier
            lesson_path: Path to lesson directory

        Returns:
            Cached result or None if not found/invalid
        """
        cache_key = self._get_cache_key(exercise_id, lesson_path)
        cache_path = self._get_cache_path(cache_key)

        if not self._is_cache_valid(cache_path):
            self.stats['misses'] += 1
            return None

        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)

            # Only use cache if test passed
            if data.get('status') == "PASS":
                self.stats['hits'] += 1
                # Reconstruct ExerciseTestResults from dict
                # For now, return the dict - consumers handle both
                return data
            else:
                self.stats['misses'] += 1
                return None

        except Exception:
            self.stats['misses'] += 1
            return None

    def set(self, exercise_id: str, lesson_path: Path, result: ExerciseTestResults):
        """
        Cache test result.

        Args:
            exercise_id: Exercise identifier
            lesson_path: Path to lesson directory
            result: Test result to cache
        """
        # Only cache passing results
        if result.status != "PASS":
            return

        cache_key = self._get_cache_key(exercise_id, lesson_path)
        cache_path = self._get_cache_path(cache_key)

        try:
            # Serialize dataclass to JSON-compatible dict
            data = _serialize_dataclass(result)
            json_str = json.dumps(data, indent=2, default=str)
            # Atomic write to prevent corruption
            _atomic_write(cache_path, json_str)
        except Exception as e:
            print(f"   ⚠️  Failed to cache result: {e}")

    def invalidate(self, exercise_id: str, lesson_path: Path):
        """
        Invalidate cached result.

        Args:
            exercise_id: Exercise identifier
            lesson_path: Path to lesson directory
        """
        cache_key = self._get_cache_key(exercise_id, lesson_path)
        cache_path = self._get_cache_path(cache_key)

        if cache_path.exists():
            cache_path.unlink()
            self.stats['invalidations'] += 1

    def clear_all(self):
        """Clear all cached results."""
        count = 0
        for cache_file in self.cache_dir.glob("*.cache"):
            cache_file.unlink()
            count += 1

        self.stats['invalidations'] += count
        print(f"   ✓ Cleared {count} cached result(s)")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0

        return {
            **self.stats,
            'total_requests': total_requests,
            'hit_rate': hit_rate
        }


class EPUBCache:
    """
    EPUB parsing cache with intelligent invalidation.

    Caches parsed EPUB content to avoid re-parsing.
    """

    def __init__(self, cache_dir: Optional[Path] = None, max_age_hours: int = 24):
        """
        Initialize EPUB cache.

        Args:
            cache_dir: Cache directory (defaults to ~/.cache/exercise-qa-2/)
            max_age_hours: Maximum cache age in hours
        """
        if cache_dir is None:
            cache_dir = Path.home() / '.cache' / 'exercise-qa-2' / 'epub'

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.max_age = timedelta(hours=max_age_hours)

        # Track cache hits/misses
        self.stats = {
            'hits': 0,
            'misses': 0
        }

    def _get_cache_key(self, epub_path: Path) -> str:
        """Generate cache key from EPUB path and modification time."""
        mtime = epub_path.stat().st_mtime if epub_path.exists() else 0

        key_data = {
            'epub_path': str(epub_path.absolute()),
            'mtime': mtime
        }

        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()

    def get(self, epub_path: Path) -> Optional[CourseContext]:
        """
        Get cached course context.

        Args:
            epub_path: Path to EPUB file

        Returns:
            Cached course context or None
        """
        cache_key = self._get_cache_key(epub_path)
        cache_path = self.cache_dir / f"{cache_key}.json"

        if not cache_path.exists():
            self.stats['misses'] += 1
            return None

        # Check age
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - mtime

        if age > self.max_age:
            self.stats['misses'] += 1
            return None

        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)
            self.stats['hits'] += 1
            # Reconstruct CourseContext from dict
            return _deserialize_course_context(data)
        except Exception as e:
            self.stats['misses'] += 1
            # If deserialization fails, return None (will re-parse EPUB)
            return None

    def set(self, epub_path: Path, context: CourseContext):
        """Cache course context."""
        cache_key = self._get_cache_key(epub_path)
        cache_path = self.cache_dir / f"{cache_key}.json"

        try:
            data = _serialize_dataclass(context)
            json_str = json.dumps(data, indent=2, default=str)
            _atomic_write(cache_path, json_str)
        except Exception as e:
            print(f"   ⚠️  Failed to cache EPUB: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0

        return {
            **self.stats,
            'total_requests': total_requests,
            'hit_rate': hit_rate
        }
