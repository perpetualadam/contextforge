"""
Test suite for Phase 5: Offline Mode Enhancement.

Tests:
- OfflineManager detection and health checks
- DocCache storage and retrieval
- Setup wizard flow (mocked)
- Integration with existing services

Copyright (c) 2025 ContextForge
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest
from unittest.mock import Mock, patch, MagicMock
from services.core.offline_manager import (
    OfflineManager, OfflineStatus, LocalLLMStatus, get_offline_manager
)
from services.cache.doc_cache import DocCache, DocEntry, get_doc_cache, seed_common_docs
from services.cache import MemoryCache


class TestOfflineManager(unittest.TestCase):
    """Test OfflineManager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = OfflineManager()
    
    @patch('services.core.offline_manager.requests.get')
    def test_internet_check_online(self, mock_get):
        """Test internet connectivity check when online."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = self.manager._check_internet()
        self.assertTrue(result)
    
    @patch('services.core.offline_manager.requests.get')
    def test_internet_check_offline(self, mock_get):
        """Test internet connectivity check when offline."""
        mock_get.side_effect = Exception("No internet")
        
        result = self.manager._check_internet()
        self.assertFalse(result)
    
    @patch('services.core.offline_manager.requests.get')
    def test_backend_health_check_available(self, mock_get):
        """Test local backend health check when available."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama3.2"}, {"name": "codellama"}]
        }
        mock_get.return_value = mock_response
        
        backend_config = {
            'name': 'ollama',
            'url': 'http://localhost:11434',
            'health_endpoint': '/api/tags',
            'models_key': 'models'
        }
        
        status = self.manager._check_backend_health(backend_config)
        
        self.assertTrue(status.available)
        self.assertEqual(status.name, 'ollama')
        self.assertEqual(len(status.models), 2)
        self.assertIn('llama3.2', status.models)
    
    @patch('services.core.offline_manager.requests.get')
    def test_backend_health_check_unavailable(self, mock_get):
        """Test local backend health check when unavailable."""
        mock_get.side_effect = ConnectionError("Connection refused")
        
        backend_config = {
            'name': 'ollama',
            'url': 'http://localhost:11434',
            'health_endpoint': '/api/tags',
            'models_key': 'models'
        }
        
        status = self.manager._check_backend_health(backend_config)
        
        self.assertFalse(status.available)
        self.assertIsNotNone(status.error)
        self.assertIn("Connection refused", status.error)
    
    @patch('services.config.get_config')
    @patch('services.core.offline_manager.requests.get')
    def test_get_status_online(self, mock_get, mock_get_config):
        """Test get_status when online with cloud LLM."""
        # Mock internet check
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}
        mock_get.return_value = mock_response

        # Mock config with API keys
        mock_cfg = Mock()
        mock_cfg.llm.openai_api_key = "sk-test-key"
        mock_cfg.llm.anthropic_api_key = ""
        mock_cfg.llm.gemini_api_key = ""
        mock_cfg.llm.deepseek_api_key = ""
        mock_get_config.return_value = mock_cfg

        status = self.manager.get_status(force_refresh=True)

        self.assertTrue(status.internet_available)
        self.assertTrue(status.cloud_llm_available)
        self.assertEqual(status.status, OfflineStatus.ONLINE)
    
    @patch('services.core.offline_manager.requests.get')
    def test_get_status_offline(self, mock_get):
        """Test get_status when offline."""
        # Mock internet check failure
        mock_get.side_effect = Exception("No internet")
        
        status = self.manager.get_status(force_refresh=True)
        
        self.assertFalse(status.internet_available)
        self.assertEqual(status.status, OfflineStatus.OFFLINE)
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        with patch.object(self.manager, 'get_status') as mock_status:
            mock_status.return_value = Mock(
                status=OfflineStatus.ONLINE,
                internet_available=True,
                cloud_llm_available=True,
                local_llm_backends=[
                    LocalLLMStatus(
                        name='ollama',
                        available=True,
                        url='http://localhost:11434',
                        models=['llama3.2'],
                        latency_ms=50
                    )
                ],
                recommended_action="All systems operational"
            )
            
            result = self.manager.to_dict()
            
            self.assertEqual(result['status'], 'online')
            self.assertTrue(result['internet_available'])
            self.assertEqual(len(result['local_backends']), 1)
            self.assertEqual(result['local_backends'][0]['name'], 'ollama')


class TestDocCache(unittest.TestCase):
    """Test DocCache functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.backend = MemoryCache()
        self.cache = DocCache(backend=self.backend)

    def test_add_and_get_doc(self):
        """Test adding and retrieving documentation."""
        entry = DocEntry(
            key="list.append",
            category="stdlib",
            language="python",
            title="list.append",
            content="Add an item to the end of the list.",
            tags=["list", "stdlib", "python"],
            url="https://docs.python.org/3/tutorial/datastructures.html"
        )

        # Add entry
        result = self.cache.add(entry)
        self.assertTrue(result)

        # Retrieve entry
        retrieved = self.cache.get("stdlib", "python", "list.append")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.key, "list.append")
        self.assertEqual(retrieved.content, "Add an item to the end of the list.")

    def test_get_nonexistent_doc(self):
        """Test retrieving non-existent documentation."""
        result = self.cache.get("api", "python", "nonexistent")
        self.assertIsNone(result)

    def test_add_python_stdlib(self):
        """Test adding Python stdlib documentation."""
        result = self.cache.add_python_stdlib(
            module="os",
            function="path.join",
            doc="Join one or more path components intelligently.",
            url="https://docs.python.org/3/library/os.path.html"
        )
        self.assertTrue(result)

        # Retrieve it
        retrieved = self.cache.get("stdlib", "python", "os.path.join")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.title, "os.path.join")

    def test_add_language_reference(self):
        """Test adding language reference."""
        result = self.cache.add_language_reference(
            language="python",
            topic="async-await",
            content="Async/await syntax for asynchronous programming.",
            tags=["async", "concurrency"]
        )
        self.assertTrue(result)

        retrieved = self.cache.get("language", "python", "async-await")
        self.assertIsNotNone(retrieved)
        self.assertIn("async", retrieved.tags)

    def test_add_code_pattern(self):
        """Test adding code pattern."""
        result = self.cache.add_code_pattern(
            language="python",
            pattern_name="singleton",
            code="class Singleton:\n    _instance = None",
            description="Singleton pattern",
            tags=["design-pattern"]
        )
        self.assertTrue(result)

        retrieved = self.cache.get("pattern", "python", "singleton")
        self.assertIsNotNone(retrieved)
        self.assertIn("```python", retrieved.content)

    def test_add_api_doc(self):
        """Test adding API documentation."""
        result = self.cache.add_api_doc(
            language="python",
            package="requests",
            api_name="get",
            doc="Send a GET request.",
            url="https://requests.readthedocs.io/"
        )
        self.assertTrue(result)

        retrieved = self.cache.get("api", "python", "requests.get")
        self.assertIsNotNone(retrieved)

    def test_bulk_add(self):
        """Test bulk adding documentation."""
        entries = [
            DocEntry(
                key="dict.get",
                category="stdlib",
                language="python",
                title="dict.get",
                content="Return the value for key if key is in the dictionary.",
                tags=["dict", "stdlib"]
            ),
            DocEntry(
                key="str.split",
                category="stdlib",
                language="python",
                title="str.split",
                content="Return a list of the words in the string.",
                tags=["str", "stdlib"]
            )
        ]

        count = self.cache.bulk_add(entries)
        self.assertEqual(count, 2)

        # Verify both were added
        self.assertIsNotNone(self.cache.get("stdlib", "python", "dict.get"))
        self.assertIsNotNone(self.cache.get("stdlib", "python", "str.split"))

    def test_get_stats(self):
        """Test cache statistics."""
        # Add some entries
        self.cache.add_python_stdlib("os", "getcwd", "Get current working directory")

        # Get (hit)
        self.cache.get("stdlib", "python", "os.getcwd")

        # Get (miss)
        self.cache.get("stdlib", "python", "nonexistent")

        stats = self.cache.get_stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["entries"], 1)

    def test_clear(self):
        """Test clearing cache."""
        # Add entries
        self.cache.add_python_stdlib("os", "path.join", "Join paths")
        self.cache.add_language_reference("python", "decorators", "Decorator syntax")

        # Clear all
        count = self.cache.clear()
        self.assertGreater(count, 0)

        # Verify cleared
        self.assertIsNone(self.cache.get("stdlib", "python", "os.path.join"))

    def test_seed_common_docs(self):
        """Test seeding common documentation."""
        seed_common_docs()

        # Verify some entries were added
        cache = get_doc_cache()
        result = cache.get("stdlib", "python", "os.path.join")
        self.assertIsNotNone(result)


class TestIntegration(unittest.TestCase):
    """Test Phase 5 integration with existing services."""

    @patch('services.core.offline_manager.requests.get')
    def test_llm_router_with_offline_manager(self, mock_get):
        """Test LLMRouter integration with OfflineManager."""
        from services.core import LLMRouter
        from services.core.offline_manager import get_offline_manager

        # Mock online status
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}
        mock_get.return_value = mock_response

        # Create offline manager
        manager = get_offline_manager()

        # Create LLMRouter with offline manager
        router = LLMRouter(mode="auto", offline_manager=manager)

        # Verify it uses offline manager
        self.assertIsNotNone(router._offline_manager)

    def test_api_gateway_offline_endpoint(self):
        """Test API Gateway offline status endpoint."""
        # This would require running the FastAPI app
        # For now, just verify the offline manager can be imported
        from services.core.offline_manager import get_offline_manager

        manager = get_offline_manager()
        self.assertIsNotNone(manager)

        # Verify to_dict works
        result = manager.to_dict()
        self.assertIn('status', result)
        self.assertIn('internet_available', result)
        self.assertIn('local_backends', result)


def run_tests():
    """Run all Phase 5 tests."""
    print("="*60)
    print("  Phase 5: Offline Mode Enhancement - Test Suite")
    print("="*60 + "\n")

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestOfflineManager))
    suite.addTests(loader.loadTestsFromTestCase(TestDocCache))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*60)
    print("  Test Summary")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*60 + "\n")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)


