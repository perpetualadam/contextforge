"""
ContextForge Offline Setup Wizard.

Interactive CLI wizard to help users set up local LLM backends
(Ollama, LM Studio) for offline mode.

Copyright (c) 2025 ContextForge
"""

import os
import sys
import subprocess
import platform
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SetupWizard:
    """
    Interactive setup wizard for offline mode.
    
    Helps users:
    - Detect if Ollama/LM Studio is installed
    - Guide through installation if needed
    - Download recommended models
    - Test local LLM connectivity
    - Configure .env file
    """
    
    def __init__(self):
        """Initialize setup wizard."""
        self.system = platform.system()
        self.recommended_models = {
            "ollama": ["llama3.2", "codellama:7b", "deepseek-coder:6.7b"],
            "lm_studio": ["TheBloke/CodeLlama-7B-GGUF"]
        }
    
    def run(self):
        """Run the interactive setup wizard."""
        print("\n" + "="*60)
        print("  ContextForge Offline Mode Setup Wizard")
        print("="*60 + "\n")
        
        print("This wizard will help you set up local LLM backends for offline use.\n")
        
        # Check current status
        print("🔍 Checking current setup...\n")
        
        ollama_installed = self._check_ollama_installed()
        lm_studio_installed = self._check_lm_studio_installed()
        
        if ollama_installed:
            print("✅ Ollama is installed")
            ollama_running = self._check_ollama_running()
            if ollama_running:
                print("✅ Ollama is running")
                self._show_ollama_models()
            else:
                print("⚠️  Ollama is not running")
                self._guide_start_ollama()
        else:
            print("❌ Ollama is not installed")
            if self._prompt_yes_no("Would you like to install Ollama?"):
                self._guide_install_ollama()
        
        print()
        
        if lm_studio_installed:
            print("✅ LM Studio is installed")
        else:
            print("❌ LM Studio is not installed")
            if self._prompt_yes_no("Would you like to install LM Studio?"):
                self._guide_install_lm_studio()
        
        print()
        
        # Offer to download models
        if ollama_installed and self._check_ollama_running():
            if self._prompt_yes_no("Would you like to download recommended models?"):
                self._download_ollama_models()
        
        # Test connectivity
        print("\n🧪 Testing local LLM connectivity...\n")
        self._test_connectivity()
        
        # Configure .env
        if self._prompt_yes_no("\nWould you like to configure .env for offline mode?"):
            self._configure_env()
        
        print("\n" + "="*60)
        print("  Setup Complete!")
        print("="*60 + "\n")
        print("You can now use ContextForge in offline mode with local LLMs.\n")
    
    def _check_ollama_installed(self) -> bool:
        """Check if Ollama is installed."""
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def _check_lm_studio_installed(self) -> bool:
        """Check if LM Studio is installed."""
        # LM Studio doesn't have a CLI, so we check common install locations
        if self.system == "Windows":
            paths = [
                os.path.expanduser("~/AppData/Local/LM Studio"),
                "C:\\Program Files\\LM Studio"
            ]
        elif self.system == "Darwin":  # macOS
            paths = ["/Applications/LM Studio.app"]
        else:  # Linux
            paths = [
                os.path.expanduser("~/.local/share/LM Studio"),
                "/opt/lm-studio"
            ]
        
        return any(os.path.exists(p) for p in paths)
    
    def _check_ollama_running(self) -> bool:
        """Check if Ollama service is running."""
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=3)
            return response.status_code == 200
        except Exception:
            return False
    
    def _show_ollama_models(self):
        """Show installed Ollama models."""
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=3)
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                if models:
                    print(f"   Installed models: {', '.join([m['name'] for m in models])}")
                else:
                    print("   No models installed yet")
        except Exception as e:
            logger.debug(f"Failed to get Ollama models: {e}")
    
    def _guide_start_ollama(self):
        """Guide user to start Ollama."""
        print("\n📖 To start Ollama:")
        if self.system == "Windows":
            print("   - Ollama should start automatically")
            print("   - Or run: ollama serve")
        elif self.system == "Darwin":
            print("   - Open the Ollama app from Applications")
            print("   - Or run: ollama serve")
        else:
            print("   - Run: ollama serve")
            print("   - Or: systemctl start ollama")

    def _guide_install_ollama(self):
        """Guide user to install Ollama."""
        print("\n📖 To install Ollama:")
        print("   Visit: https://ollama.ai/download")
        print()

        if self.system == "Windows":
            print("   1. Download OllamaSetup.exe")
            print("   2. Run the installer")
            print("   3. Ollama will start automatically")
        elif self.system == "Darwin":
            print("   1. Download Ollama.dmg")
            print("   2. Drag Ollama to Applications")
            print("   3. Open Ollama from Applications")
        else:  # Linux
            print("   Run: curl https://ollama.ai/install.sh | sh")

        print("\n   After installation, run this wizard again.")

    def _guide_install_lm_studio(self):
        """Guide user to install LM Studio."""
        print("\n📖 To install LM Studio:")
        print("   Visit: https://lmstudio.ai/")
        print()
        print("   1. Download LM Studio for your platform")
        print("   2. Install and open the application")
        print("   3. Download a model from the Discover tab")
        print("   4. Start the local server from the Server tab")
        print("\n   After installation, run this wizard again.")

    def _download_ollama_models(self):
        """Download recommended Ollama models."""
        print("\n📥 Downloading recommended models...\n")

        for model in self.recommended_models["ollama"]:
            if self._prompt_yes_no(f"Download {model}?"):
                print(f"   Downloading {model}... (this may take a while)")
                try:
                    result = subprocess.run(
                        ["ollama", "pull", model],
                        capture_output=True,
                        text=True,
                        timeout=600  # 10 minutes
                    )
                    if result.returncode == 0:
                        print(f"   ✅ {model} downloaded successfully")
                    else:
                        print(f"   ❌ Failed to download {model}")
                        print(f"      {result.stderr}")
                except subprocess.TimeoutExpired:
                    print(f"   ⚠️  Download timed out. Try manually: ollama pull {model}")
                except Exception as e:
                    print(f"   ❌ Error: {e}")

    def _test_connectivity(self):
        """Test local LLM connectivity."""
        from services.core.offline_manager import get_offline_manager

        manager = get_offline_manager()
        status = manager.get_status(force_refresh=True)

        print(f"Status: {status.status.value}")
        print(f"Internet: {'✅' if status.internet_available else '❌'}")
        print(f"Cloud LLM: {'✅' if status.cloud_llm_available else '❌'}")
        print()

        for backend in status.local_llm_backends:
            icon = "✅" if backend.available else "❌"
            print(f"{icon} {backend.name}: {backend.url}")
            if backend.available:
                print(f"   Latency: {backend.latency_ms}ms")
                if backend.models:
                    print(f"   Models: {len(backend.models)}")
            elif backend.error:
                print(f"   Error: {backend.error}")

    def _configure_env(self):
        """Configure .env file for offline mode."""
        env_path = ".env"
        env_example_path = ".env.example"

        # Check if .env exists
        if not os.path.exists(env_path):
            if os.path.exists(env_example_path):
                print(f"\n📝 Creating {env_path} from {env_example_path}...")
                with open(env_example_path, 'r') as f:
                    content = f.read()
                with open(env_path, 'w') as f:
                    f.write(content)
                print(f"   ✅ Created {env_path}")
            else:
                print(f"\n📝 Creating new {env_path}...")
                with open(env_path, 'w') as f:
                    f.write("# ContextForge Configuration\n\n")
                print(f"   ✅ Created {env_path}")

        # Update LLM priority to prefer local
        print("\n📝 Configuring for offline mode...")

        with open(env_path, 'r') as f:
            lines = f.readlines()

        # Update or add LLM_PRIORITY
        updated = False
        for i, line in enumerate(lines):
            if line.startswith("LLM_PRIORITY="):
                lines[i] = "LLM_PRIORITY=local,cloud\n"
                updated = True
                break

        if not updated:
            lines.append("\n# LLM Configuration\n")
            lines.append("LLM_PRIORITY=local,cloud\n")

        with open(env_path, 'w') as f:
            f.writelines(lines)

        print(f"   ✅ Updated {env_path}")
        print("   Set LLM_PRIORITY=local,cloud")

    def _prompt_yes_no(self, question: str) -> bool:
        """Prompt user for yes/no answer."""
        while True:
            response = input(f"{question} (y/n): ").strip().lower()
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            else:
                print("Please enter 'y' or 'n'")


def main():
    """Run the setup wizard."""
    wizard = SetupWizard()
    wizard.run()


if __name__ == "__main__":
    main()


