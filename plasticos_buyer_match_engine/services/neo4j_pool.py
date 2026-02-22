"""Neo4j connection pool manager with health checks and circuit breaker.

Moved from Buyer Matching Using Neo4j/connection_pool.py; used by
plasticos.graph.service for graph traversal and buyer matching.
"""

import logging
import threading
import time
from contextlib import contextmanager

_logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import ServiceUnavailable
except ImportError:
    GraphDatabase = None
    ServiceUnavailable = Exception


class CircuitBreaker:
    """Circuit breaker pattern for Neo4j connection failures.

    States:
    - CLOSED: Normal operation
    - OPEN: Too many failures, reject requests
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "CLOSED"
        self._lock = threading.Lock()

    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        with self._lock:
            if self.state == "OPEN":
                if time.time() - self.last_failure_time >= self.timeout:
                    _logger.info("Circuit breaker entering HALF_OPEN state")
                    self.state = "HALF_OPEN"
                else:
                    raise (ServiceUnavailable or Exception)("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise exc

    def _on_success(self):
        with self._lock:
            self.failures = 0
            self.state = "CLOSED"
            _logger.debug("Circuit breaker reset to CLOSED")

    def _on_failure(self):
        with self._lock:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.failure_threshold:
                self.state = "OPEN"
                _logger.error("Circuit breaker opened after %d failures", self.failures)


class Neo4jConnectionPool:
    """Singleton connection pool manager for Neo4j.

    Single driver instance per (uri, auth) tuple; circuit breaker;
    thread-safe.
    """

    _instances = {}
    _lock = threading.Lock()

    def __new__(cls, uri, username, password, **config):
        key = (uri, username)
        with cls._lock:
            if key not in cls._instances:
                instance = super().__new__(cls)
                cls._instances[key] = instance
                instance._initialized = False
            return cls._instances[key]

    def __init__(self, uri, username, password, **config):
        if getattr(self, "_initialized", False):
            return
        self.uri = uri
        self.username = username
        self.password = password
        self.config = config
        self.driver = None
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config.get("circuit_breaker_threshold", 5),
            timeout=config.get("circuit_breaker_timeout", 60),
        )
        if GraphDatabase is not None:
            try:
                self.driver = GraphDatabase.driver(
                    self.uri,
                    auth=(self.username, self.password),
                    max_connection_pool_size=config.get("pool_size", 25),
                    connection_timeout=config.get("connection_timeout", 30),
                    max_connection_lifetime=config.get("max_lifetime", 3600),
                )
                _logger.info("Neo4j connection pool established: %s", self.uri)
            except Exception as exc:
                _logger.error("Failed to create Neo4j driver: %s", exc)
                raise
        self._initialized = True

    @contextmanager
    def session(self, **kwargs):
        """Get a session from the pool with circuit breaker protection."""
        if not self.driver:
            raise RuntimeError("Neo4j driver not available (neo4j package not installed?)")

        def _get_session():
            return self.driver.session(**kwargs)

        session = self.circuit_breaker.call(_get_session)
        try:
            yield session
        finally:
            session.close()

    def health_check(self):
        """Verify Neo4j connectivity."""
        if not self.driver:
            return False
        try:
            with self.session() as session:
                result = session.run("RETURN 1 AS health")
                record = result.single()
                return record and record["health"] == 1
        except Exception as exc:
            _logger.error("Neo4j health check failed: %s", exc)
            return False

    def close(self):
        """Close the driver and release connections."""
        if self.driver:
            self.driver.close()
            self.driver = None
            _logger.info("Neo4j connection pool closed")
