"""
ContextForge Language Tools Configuration.

Provides open source, free test suites and debug tools for all supported programming languages.

Copyright (c) 2025 ContextForge
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class LanguageId(Enum):
    """Supported programming languages."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUBY = "ruby"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    CSHARP = "csharp"
    CPP = "cpp"
    C = "c"
    PHP = "php"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    SCALA = "scala"
    LUA = "lua"
    PERL = "perl"
    R = "r"
    SHELL = "shell"
    HTML = "html"
    CSS = "css"
    JULIA = "julia"


@dataclass
class TestFramework:
    """Configuration for a test framework."""
    name: str
    command: str
    install_command: str
    file_pattern: str
    description: str
    open_source: bool = True
    free: bool = True
    url: str = ""
    config_file: Optional[str] = None


@dataclass
class DebugTool:
    """Configuration for a debug tool."""
    name: str
    command: str
    install_command: str
    description: str
    open_source: bool = True
    free: bool = True
    url: str = ""
    vscode_extension: Optional[str] = None


@dataclass
class Linter:
    """Configuration for a linter."""
    name: str
    command: str
    install_command: str
    description: str
    open_source: bool = True
    free: bool = True
    url: str = ""
    config_file: Optional[str] = None


@dataclass
class LanguageTools:
    """Complete tooling configuration for a programming language."""
    language: LanguageId
    file_extensions: List[str]
    test_frameworks: List[TestFramework] = field(default_factory=list)
    debug_tools: List[DebugTool] = field(default_factory=list)
    linters: List[Linter] = field(default_factory=list)


# Python Tools
PYTHON_TOOLS = LanguageTools(
    language=LanguageId.PYTHON,
    file_extensions=[".py", ".pyw", ".pyi"],
    test_frameworks=[
        TestFramework(
            name="pytest",
            command="python -m pytest",
            install_command="pip install pytest",
            file_pattern="test_*.py",
            description="Full-featured Python testing framework",
            url="https://pytest.org",
            config_file="pytest.ini"
        ),
        TestFramework(
            name="unittest",
            command="python -m unittest discover",
            install_command="",  # Built-in
            file_pattern="test_*.py",
            description="Python standard library test framework",
            url="https://docs.python.org/3/library/unittest.html"
        ),
        TestFramework(
            name="nose2",
            command="nose2",
            install_command="pip install nose2",
            file_pattern="test_*.py",
            description="Successor to nose test runner",
            url="https://docs.nose2.io"
        ),
        TestFramework(
            name="doctest",
            command="python -m doctest",
            install_command="",  # Built-in
            file_pattern="*.py",
            description="Test interactive examples in docstrings",
            url="https://docs.python.org/3/library/doctest.html"
        ),
        TestFramework(
            name="hypothesis",
            command="python -m pytest --hypothesis-show-statistics",
            install_command="pip install hypothesis",
            file_pattern="test_*.py",
            description="Property-based testing for Python",
            url="https://hypothesis.works"
        ),
    ],
    debug_tools=[
        DebugTool(
            name="pdb",
            command="python -m pdb",
            install_command="",  # Built-in
            description="Python debugger (built-in)",
            url="https://docs.python.org/3/library/pdb.html"
        ),
        DebugTool(
            name="ipdb",
            command="python -m ipdb",
            install_command="pip install ipdb",
            description="IPython-enabled pdb with tab completion",
            url="https://github.com/gotcha/ipdb"
        ),
        DebugTool(
            name="pudb",
            command="python -m pudb",
            install_command="pip install pudb",
            description="Full-screen console debugger for Python",
            url="https://github.com/inducer/pudb"
        ),
        DebugTool(
            name="debugpy",
            command="python -m debugpy --listen 5678",
            install_command="pip install debugpy",
            description="Python debugger for VS Code",
            url="https://github.com/microsoft/debugpy",
            vscode_extension="ms-python.python"
        ),
    ],
    linters=[
        Linter(name="pylint", command="pylint", install_command="pip install pylint",
               description="Static code analyzer", url="https://pylint.org", config_file=".pylintrc"),
        Linter(name="flake8", command="flake8", install_command="pip install flake8",
               description="Style guide enforcement", url="https://flake8.pycqa.org", config_file=".flake8"),
        Linter(name="ruff", command="ruff check", install_command="pip install ruff",
               description="Extremely fast Python linter", url="https://github.com/astral-sh/ruff"),
        Linter(name="mypy", command="mypy", install_command="pip install mypy",
               description="Static type checker", url="https://mypy-lang.org", config_file="mypy.ini"),
    ]
)


# JavaScript/TypeScript Tools
JAVASCRIPT_TOOLS = LanguageTools(
    language=LanguageId.JAVASCRIPT,
    file_extensions=[".js", ".mjs", ".cjs", ".jsx"],
    test_frameworks=[
        TestFramework(
            name="jest",
            command="npx jest",
            install_command="npm install --save-dev jest",
            file_pattern="*.test.js",
            description="Delightful JavaScript testing framework",
            url="https://jestjs.io",
            config_file="jest.config.js"
        ),
        TestFramework(
            name="mocha",
            command="npx mocha",
            install_command="npm install --save-dev mocha",
            file_pattern="*.test.js",
            description="Feature-rich JavaScript test framework",
            url="https://mochajs.org"
        ),
        TestFramework(
            name="vitest",
            command="npx vitest",
            install_command="npm install --save-dev vitest",
            file_pattern="*.test.js",
            description="Blazing fast unit test framework",
            url="https://vitest.dev",
            config_file="vitest.config.js"
        ),
        TestFramework(
            name="ava",
            command="npx ava",
            install_command="npm install --save-dev ava",
            file_pattern="*.test.js",
            description="Concurrent test runner for Node.js",
            url="https://github.com/avajs/ava"
        ),
        TestFramework(
            name="tape",
            command="npx tape",
            install_command="npm install --save-dev tape",
            file_pattern="*.test.js",
            description="TAP-producing test harness",
            url="https://github.com/ljharb/tape"
        ),
    ],
    debug_tools=[
        DebugTool(
            name="node-inspect",
            command="node --inspect",
            install_command="",  # Built-in Node.js
            description="Built-in Node.js debugger",
            url="https://nodejs.org/api/debugger.html"
        ),
        DebugTool(
            name="ndb",
            command="npx ndb",
            install_command="npm install -g ndb",
            description="Chrome DevTools-based debugger",
            url="https://github.com/GoogleChromeLabs/ndb"
        ),
    ],
    linters=[
        Linter(name="eslint", command="npx eslint", install_command="npm install --save-dev eslint",
               description="Pluggable JavaScript linter", url="https://eslint.org", config_file=".eslintrc.json"),
        Linter(name="jshint", command="npx jshint", install_command="npm install --save-dev jshint",
               description="JavaScript code quality tool", url="https://jshint.com"),
        Linter(name="standardjs", command="npx standard", install_command="npm install --save-dev standard",
               description="JavaScript Standard Style", url="https://standardjs.com"),
    ]
)

TYPESCRIPT_TOOLS = LanguageTools(
    language=LanguageId.TYPESCRIPT,
    file_extensions=[".ts", ".tsx", ".mts", ".cts"],
    test_frameworks=[
        TestFramework(
            name="jest",
            command="npx jest",
            install_command="npm install --save-dev jest ts-jest @types/jest",
            file_pattern="*.test.ts",
            description="Jest with TypeScript support via ts-jest",
            url="https://jestjs.io",
            config_file="jest.config.ts"
        ),
        TestFramework(
            name="vitest",
            command="npx vitest",
            install_command="npm install --save-dev vitest",
            file_pattern="*.test.ts",
            description="Vite-native unit test framework",
            url="https://vitest.dev",
            config_file="vitest.config.ts"
        ),
        TestFramework(
            name="mocha",
            command="npx mocha --require ts-node/register",
            install_command="npm install --save-dev mocha @types/mocha ts-node",
            file_pattern="*.test.ts",
            description="Mocha with TypeScript support",
            url="https://mochajs.org"
        ),
    ],
    debug_tools=[
        DebugTool(
            name="ts-node",
            command="node --inspect -r ts-node/register",
            install_command="npm install --save-dev ts-node",
            description="TypeScript execution and REPL",
            url="https://typestrong.org/ts-node/"
        ),
    ],
    linters=[
        Linter(name="eslint", command="npx eslint --ext .ts,.tsx",
               install_command="npm install --save-dev eslint @typescript-eslint/parser @typescript-eslint/eslint-plugin",
               description="ESLint with TypeScript support", url="https://typescript-eslint.io"),
        Linter(name="tsc", command="npx tsc --noEmit",
               install_command="npm install --save-dev typescript",
               description="TypeScript compiler for type checking", url="https://www.typescriptlang.org"),
    ]
)

# Ruby Tools
RUBY_TOOLS = LanguageTools(
    language=LanguageId.RUBY,
    file_extensions=[".rb", ".rake", ".gemspec"],
    test_frameworks=[
        TestFramework(
            name="rspec",
            command="bundle exec rspec",
            install_command="gem install rspec",
            file_pattern="*_spec.rb",
            description="BDD testing framework for Ruby",
            url="https://rspec.info",
            config_file=".rspec"
        ),
        TestFramework(
            name="minitest",
            command="ruby -Ilib:test",
            install_command="gem install minitest",
            file_pattern="test_*.rb",
            description="Complete suite of testing facilities",
            url="https://github.com/minitest/minitest"
        ),
        TestFramework(
            name="test-unit",
            command="ruby -Ilib:test",
            install_command="gem install test-unit",
            file_pattern="test_*.rb",
            description="xUnit family unit testing framework",
            url="https://test-unit.github.io"
        ),
    ],
    debug_tools=[
        DebugTool(
            name="debug",
            command="rdbg",
            install_command="gem install debug",
            description="Ruby's official debugger (Ruby 3.1+)",
            url="https://github.com/ruby/debug"
        ),
        DebugTool(
            name="byebug",
            command="byebug",
            install_command="gem install byebug",
            description="Feature-rich debugger for Ruby 2",
            url="https://github.com/deivid-rodriguez/byebug"
        ),
        DebugTool(
            name="pry",
            command="pry",
            install_command="gem install pry pry-byebug",
            description="Powerful REPL and debugger",
            url="https://pry.github.io"
        ),
    ],
    linters=[
        Linter(name="rubocop", command="rubocop", install_command="gem install rubocop",
               description="Ruby static code analyzer", url="https://rubocop.org", config_file=".rubocop.yml"),
        Linter(name="reek", command="reek", install_command="gem install reek",
               description="Code smell detector for Ruby", url="https://github.com/troessner/reek"),
    ]
)


# Go Tools
GO_TOOLS = LanguageTools(
    language=LanguageId.GO,
    file_extensions=[".go"],
    test_frameworks=[
        TestFramework(
            name="go test",
            command="go test ./...",
            install_command="",  # Built-in
            file_pattern="*_test.go",
            description="Go built-in testing framework",
            url="https://golang.org/pkg/testing/"
        ),
        TestFramework(
            name="testify",
            command="go test ./...",
            install_command="go get github.com/stretchr/testify",
            file_pattern="*_test.go",
            description="Go testing toolkit with assertions",
            url="https://github.com/stretchr/testify"
        ),
        TestFramework(
            name="ginkgo",
            command="ginkgo ./...",
            install_command="go install github.com/onsi/ginkgo/v2/ginkgo@latest",
            file_pattern="*_test.go",
            description="BDD-style testing framework for Go",
            url="https://onsi.github.io/ginkgo/"
        ),
    ],
    debug_tools=[
        DebugTool(
            name="delve",
            command="dlv debug",
            install_command="go install github.com/go-delve/delve/cmd/dlv@latest",
            description="Full featured debugger for Go",
            url="https://github.com/go-delve/delve",
            vscode_extension="golang.go"
        ),
    ],
    linters=[
        Linter(name="golangci-lint", command="golangci-lint run",
               install_command="go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest",
               description="Fast Go linters aggregator", url="https://golangci-lint.run", config_file=".golangci.yml"),
        Linter(name="staticcheck", command="staticcheck ./...",
               install_command="go install honnef.co/go/tools/cmd/staticcheck@latest",
               description="Advanced Go linter", url="https://staticcheck.io"),
        Linter(name="go vet", command="go vet ./...",
               install_command="",  # Built-in
               description="Go built-in code analyzer", url="https://golang.org/cmd/vet/"),
    ]
)

# Rust Tools
RUST_TOOLS = LanguageTools(
    language=LanguageId.RUST,
    file_extensions=[".rs"],
    test_frameworks=[
        TestFramework(
            name="cargo test",
            command="cargo test",
            install_command="",  # Built-in with cargo
            file_pattern="*.rs",
            description="Rust built-in testing framework",
            url="https://doc.rust-lang.org/cargo/commands/cargo-test.html"
        ),
        TestFramework(
            name="nextest",
            command="cargo nextest run",
            install_command="cargo install cargo-nextest",
            file_pattern="*.rs",
            description="Next-generation test runner for Rust",
            url="https://nexte.st"
        ),
    ],
    debug_tools=[
        DebugTool(
            name="rust-gdb",
            command="rust-gdb",
            install_command="",  # Comes with Rust
            description="GDB with Rust pretty-printing",
            url="https://doc.rust-lang.org/book/appendix-06-translation.html"
        ),
        DebugTool(
            name="rust-lldb",
            command="rust-lldb",
            install_command="",  # Comes with Rust
            description="LLDB with Rust support",
            url="https://doc.rust-lang.org/book/appendix-06-translation.html"
        ),
        DebugTool(
            name="CodeLLDB",
            command="",  # VS Code extension
            install_command="",
            description="VS Code native debugger for Rust",
            url="https://marketplace.visualstudio.com/items?itemName=vadimcn.vscode-lldb",
            vscode_extension="vadimcn.vscode-lldb"
        ),
    ],
    linters=[
        Linter(name="clippy", command="cargo clippy",
               install_command="rustup component add clippy",
               description="Rust linter with helpful suggestions", url="https://github.com/rust-lang/rust-clippy"),
        Linter(name="rustfmt", command="cargo fmt --check",
               install_command="rustup component add rustfmt",
               description="Rust code formatter", url="https://github.com/rust-lang/rustfmt"),
    ]
)

# Java Tools
JAVA_TOOLS = LanguageTools(
    language=LanguageId.JAVA,
    file_extensions=[".java"],
    test_frameworks=[
        TestFramework(
            name="JUnit 5",
            command="mvn test",
            install_command="",  # Add to pom.xml
            file_pattern="*Test.java",
            description="Standard Java testing framework",
            url="https://junit.org/junit5/",
            config_file="pom.xml"
        ),
        TestFramework(
            name="TestNG",
            command="mvn test",
            install_command="",  # Add to pom.xml
            file_pattern="*Test.java",
            description="Testing framework inspired by JUnit",
            url="https://testng.org"
        ),
        TestFramework(
            name="Spock",
            command="./gradlew test",
            install_command="",  # Add to build.gradle
            file_pattern="*Spec.groovy",
            description="Groovy-based testing framework",
            url="https://spockframework.org"
        ),
    ],
    debug_tools=[
        DebugTool(
            name="jdb",
            command="jdb",
            install_command="",  # JDK built-in
            description="Java Debugger (JDK built-in)",
            url="https://docs.oracle.com/javase/8/docs/technotes/tools/windows/jdb.html"
        ),
        DebugTool(
            name="Debug Adapter",
            command="",
            install_command="",
            description="Java Debug Extension for VS Code",
            url="https://marketplace.visualstudio.com/items?itemName=vscjava.vscode-java-debug",
            vscode_extension="vscjava.vscode-java-debug"
        ),
    ],
    linters=[
        Linter(name="checkstyle", command="mvn checkstyle:check",
               install_command="",
               description="Java code style checker", url="https://checkstyle.org", config_file="checkstyle.xml"),
        Linter(name="spotbugs", command="mvn spotbugs:check",
               install_command="",
               description="Find bugs in Java code", url="https://spotbugs.github.io"),
        Linter(name="pmd", command="mvn pmd:check",
               install_command="",
               description="Source code analyzer", url="https://pmd.github.io"),
    ]
)



# C# Tools
CSHARP_TOOLS = LanguageTools(
    language=LanguageId.CSHARP,
    file_extensions=[".cs", ".csx"],
    test_frameworks=[
        TestFramework(
            name="xUnit",
            command="dotnet test",
            install_command="dotnet add package xunit",
            file_pattern="*Tests.cs",
            description="Free, open source, community-focused unit testing tool",
            url="https://xunit.net"
        ),
        TestFramework(
            name="NUnit",
            command="dotnet test",
            install_command="dotnet add package NUnit",
            file_pattern="*Tests.cs",
            description="Unit-testing framework for all .NET languages",
            url="https://nunit.org"
        ),
        TestFramework(
            name="MSTest",
            command="dotnet test",
            install_command="dotnet add package MSTest.TestFramework",
            file_pattern="*Tests.cs",
            description="Microsoft's unit testing framework",
            url="https://docs.microsoft.com/en-us/dotnet/core/testing/unit-testing-with-mstest"
        ),
    ],
    debug_tools=[
        DebugTool(
            name="dotnet debugger",
            command="dotnet run --configuration Debug",
            install_command="",  # Built-in
            description=".NET Core debugger",
            url="https://docs.microsoft.com/en-us/dotnet/core/diagnostics/"
        ),
        DebugTool(
            name="OmniSharp",
            command="",
            install_command="",
            description="C# debugging in VS Code",
            url="https://marketplace.visualstudio.com/items?itemName=ms-dotnettools.csharp",
            vscode_extension="ms-dotnettools.csharp"
        ),
    ],
    linters=[
        Linter(name="dotnet format", command="dotnet format",
               install_command="",  # Built-in .NET 6+
               description="Code style formatter", url="https://docs.microsoft.com/en-us/dotnet/core/tools/dotnet-format"),
        Linter(name="Roslynator", command="dotnet roslynator analyze",
               install_command="dotnet tool install -g roslynator.dotnet.cli",
               description="Roslyn-based analyzers", url="https://github.com/dotnet/roslynator"),
    ]
)

# C/C++ Tools
CPP_TOOLS = LanguageTools(
    language=LanguageId.CPP,
    file_extensions=[".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".h"],
    test_frameworks=[
        TestFramework(
            name="Google Test",
            command="./build/test",
            install_command="",  # CMake FetchContent or vcpkg
            file_pattern="*_test.cpp",
            description="Google's C++ testing and mocking framework",
            url="https://github.com/google/googletest"
        ),
        TestFramework(
            name="Catch2",
            command="./build/test",
            install_command="",  # CMake FetchContent or vcpkg
            file_pattern="*_test.cpp",
            description="Modern, C++-native test framework",
            url="https://github.com/catchorg/Catch2"
        ),
        TestFramework(
            name="doctest",
            command="./build/test",
            install_command="",  # Header-only
            file_pattern="*_test.cpp",
            description="Fast single-header testing framework",
            url="https://github.com/doctest/doctest"
        ),
    ],
    debug_tools=[
        DebugTool(
            name="GDB",
            command="gdb",
            install_command="",  # System package
            description="GNU Project debugger",
            url="https://www.gnu.org/software/gdb/"
        ),
        DebugTool(
            name="LLDB",
            command="lldb",
            install_command="",  # System package
            description="LLVM debugger",
            url="https://lldb.llvm.org/"
        ),
        DebugTool(
            name="CodeLLDB",
            command="",
            install_command="",
            description="VS Code native debugger for C/C++",
            url="https://marketplace.visualstudio.com/items?itemName=vadimcn.vscode-lldb",
            vscode_extension="vadimcn.vscode-lldb"
        ),
    ],
    linters=[
        Linter(name="clang-tidy", command="clang-tidy",
               install_command="",  # Part of LLVM
               description="C++ linter based on Clang", url="https://clang.llvm.org/extra/clang-tidy/",
               config_file=".clang-tidy"),
        Linter(name="cppcheck", command="cppcheck --enable=all",
               install_command="",  # System package
               description="Static analysis tool for C/C++", url="http://cppcheck.sourceforge.net"),
        Linter(name="cpplint", command="cpplint",
               install_command="pip install cpplint",
               description="Google C++ style checker", url="https://github.com/cpplint/cpplint"),
    ]
)

# C Tools (shares many with C++)
C_TOOLS = LanguageTools(
    language=LanguageId.C,
    file_extensions=[".c", ".h"],
    test_frameworks=[
        TestFramework(
            name="Unity",
            command="./build/test",
            install_command="",
            file_pattern="test_*.c",
            description="Simple unit testing for C",
            url="https://github.com/ThrowTheSwitch/Unity"
        ),
        TestFramework(
            name="Check",
            command="make check",
            install_command="",  # System package
            file_pattern="check_*.c",
            description="Unit testing framework for C",
            url="https://libcheck.github.io/check/"
        ),
        TestFramework(
            name="CMocka",
            command="ctest",
            install_command="",
            file_pattern="test_*.c",
            description="Unit testing framework for C with mock support",
            url="https://cmocka.org/"
        ),
    ],
    debug_tools=[
        DebugTool(
            name="GDB",
            command="gdb",
            install_command="",
            description="GNU Project debugger",
            url="https://www.gnu.org/software/gdb/"
        ),
        DebugTool(
            name="LLDB",
            command="lldb",
            install_command="",
            description="LLVM debugger",
            url="https://lldb.llvm.org/"
        ),
    ],
    linters=[
        Linter(name="clang-tidy", command="clang-tidy",
               install_command="",
               description="C linter based on Clang", url="https://clang.llvm.org/extra/clang-tidy/"),
        Linter(name="cppcheck", command="cppcheck --enable=all",
               install_command="",
               description="Static analysis for C", url="http://cppcheck.sourceforge.net"),
    ]
)


# PHP Tools
PHP_TOOLS = LanguageTools(
    language=LanguageId.PHP,
    file_extensions=[".php", ".phtml"],
    test_frameworks=[
        TestFramework(
            name="PHPUnit",
            command="./vendor/bin/phpunit",
            install_command="composer require --dev phpunit/phpunit",
            file_pattern="*Test.php",
            description="The PHP Testing Framework",
            url="https://phpunit.de",
            config_file="phpunit.xml"
        ),
        TestFramework(
            name="Pest",
            command="./vendor/bin/pest",
            install_command="composer require pestphp/pest --dev --with-all-dependencies",
            file_pattern="*Test.php",
            description="Elegant PHP testing framework",
            url="https://pestphp.com"
        ),
        TestFramework(
            name="Codeception",
            command="./vendor/bin/codecept run",
            install_command="composer require codeception/codeception --dev",
            file_pattern="*Cest.php",
            description="Full stack testing framework",
            url="https://codeception.com"
        ),
    ],
    debug_tools=[
        DebugTool(
            name="Xdebug",
            command="php -dxdebug.mode=debug",
            install_command="pecl install xdebug",
            description="PHP debugging and profiling extension",
            url="https://xdebug.org",
            vscode_extension="xdebug.php-debug"
        ),
    ],
    linters=[
        Linter(name="PHP_CodeSniffer", command="./vendor/bin/phpcs",
               install_command="composer require squizlabs/php_codesniffer --dev",
               description="PHP coding standard checker", url="https://github.com/squizlabs/PHP_CodeSniffer",
               config_file="phpcs.xml"),
        Linter(name="PHPStan", command="./vendor/bin/phpstan analyse",
               install_command="composer require phpstan/phpstan --dev",
               description="PHP static analysis tool", url="https://phpstan.org",
               config_file="phpstan.neon"),
        Linter(name="Psalm", command="./vendor/bin/psalm",
               install_command="composer require vimeo/psalm --dev",
               description="Static analysis tool for PHP", url="https://psalm.dev"),
    ]
)

# Shell Tools
SHELL_TOOLS = LanguageTools(
    language=LanguageId.SHELL,
    file_extensions=[".sh", ".bash", ".zsh"],
    test_frameworks=[
        TestFramework(
            name="Bats",
            command="bats test/",
            install_command="npm install -g bats",
            file_pattern="*.bats",
            description="Bash Automated Testing System",
            url="https://github.com/bats-core/bats-core"
        ),
        TestFramework(
            name="shunit2",
            command="./test.sh",
            install_command="",  # Download from GitHub
            file_pattern="test_*.sh",
            description="xUnit-based unit testing for shell scripts",
            url="https://github.com/kward/shunit2"
        ),
    ],
    debug_tools=[
        DebugTool(
            name="bashdb",
            command="bashdb",
            install_command="",  # System package
            description="Bash debugger following gdb interface",
            url="http://bashdb.sourceforge.net/"
        ),
    ],
    linters=[
        Linter(name="ShellCheck", command="shellcheck",
               install_command="",  # System package
               description="Shell script static analysis", url="https://www.shellcheck.net"),
        Linter(name="shfmt", command="shfmt -d",
               install_command="go install mvdan.cc/sh/v3/cmd/shfmt@latest",
               description="Shell script formatter", url="https://github.com/mvdan/sh"),
    ]
)


# ============================================================================
# HTML Tools
# ============================================================================
HTML_TOOLS = LanguageTools(
    language=LanguageId.HTML,
    file_extensions=[".html", ".htm", ".xhtml"],
    test_frameworks=[
        # HTML doesn't have traditional test frameworks, but can use browser testing
        TestFramework(
            name="HTMLHint Test",
            command="htmlhint",
            install_command="npm install -g htmlhint",
            file_pattern="*.html",
            description="HTML linting as a form of testing",
            url="https://htmlhint.com/"
        ),
    ],
    debug_tools=[
        DebugTool(
            name="Browser DevTools",
            command="",  # Built into browsers
            install_command="",  # No installation needed
            description="Browser developer tools for debugging HTML",
            vscode_extension="msjsdiag.debugger-for-chrome"
        ),
    ],
    linters=[
        Linter(name="HTMLHint", command="htmlhint",
               install_command="npm install -g htmlhint",
               description="Static code analysis for HTML", url="https://htmlhint.com/"),
        Linter(name="html-validate", command="html-validate",
               install_command="npm install -g html-validate",
               description="Offline HTML validator", url="https://html-validate.org/"),
        Linter(name="Prettier", command="prettier --check",
               install_command="npm install -g prettier",
               description="Opinionated code formatter for HTML", url="https://prettier.io/"),
    ]
)


# ============================================================================
# CSS Tools
# ============================================================================
CSS_TOOLS = LanguageTools(
    language=LanguageId.CSS,
    file_extensions=[".css", ".scss", ".sass", ".less"],
    test_frameworks=[
        # CSS doesn't have traditional test frameworks
        TestFramework(
            name="Stylelint Test",
            command="stylelint",
            install_command="npm install -g stylelint",
            file_pattern="*.css",
            description="CSS linting as a form of testing",
            url="https://stylelint.io/"
        ),
    ],
    debug_tools=[
        DebugTool(
            name="Browser DevTools",
            command="",  # Built into browsers
            install_command="",  # No installation needed
            description="Browser developer tools for debugging CSS",
            vscode_extension="msjsdiag.debugger-for-chrome"
        ),
    ],
    linters=[
        Linter(name="Stylelint", command="stylelint",
               install_command="npm install -g stylelint stylelint-config-standard",
               description="Modern CSS linter", url="https://stylelint.io/",
               config_file=".stylelintrc.json"),
        Linter(name="CSSLint", command="csslint",
               install_command="npm install -g csslint",
               description="CSS code quality tool", url="https://github.com/CSSLint/csslint"),
        Linter(name="Prettier", command="prettier --check",
               install_command="npm install -g prettier",
               description="Opinionated code formatter for CSS", url="https://prettier.io/"),
    ]
)


# ============================================================================
# Julia Tools
# ============================================================================
JULIA_TOOLS = LanguageTools(
    language=LanguageId.JULIA,
    file_extensions=[".jl"],
    test_frameworks=[
        TestFramework(
            name="Test.jl",
            command="julia -e 'using Pkg; Pkg.test()'",
            install_command="",  # Built into Julia
            file_pattern="test/*.jl",
            description="Julia's built-in testing framework",
            url="https://docs.julialang.org/en/v1/stdlib/Test/",
            config_file="test/runtests.jl"
        ),
        TestFramework(
            name="ReTest.jl",
            command="julia -e 'using ReTest; retest()'",
            install_command="julia -e 'using Pkg; Pkg.add(\"ReTest\")'",
            file_pattern="test/*.jl",
            description="Pattern-based test selection for Julia",
            url="https://github.com/JuliaTesting/ReTest.jl"
        ),
    ],
    debug_tools=[
        DebugTool(
            name="Debugger.jl",
            command="julia --project -e 'using Debugger'",
            install_command="julia -e 'using Pkg; Pkg.add(\"Debugger\")'",
            description="Julia debugger",
            url="https://github.com/JuliaDebug/Debugger.jl",
            vscode_extension="julialang.language-julia"
        ),
        DebugTool(
            name="Infiltrator.jl",
            command="julia -e 'using Infiltrator'",
            install_command="julia -e 'using Pkg; Pkg.add(\"Infiltrator\")'",
            description="Drop into REPL at breakpoints",
            url="https://github.com/JuliaDebug/Infiltrator.jl"
        ),
    ],
    linters=[
        Linter(name="JuliaFormatter", command="julia -e 'using JuliaFormatter; format(\".\")'",
               install_command="julia -e 'using Pkg; Pkg.add(\"JuliaFormatter\")'",
               description="Julia code formatter", url="https://github.com/domluna/JuliaFormatter.jl",
               config_file=".JuliaFormatter.toml"),
        Linter(name="StaticLint.jl", command="julia -e 'using StaticLint'",
               install_command="julia -e 'using Pkg; Pkg.add(\"StaticLint\")'",
               description="Static analysis for Julia", url="https://github.com/julia-vscode/StaticLint.jl"),
    ]
)


# ============================================================================
# Swift Tools
# ============================================================================
SWIFT_TOOLS = LanguageTools(
    language=LanguageId.SWIFT,
    file_extensions=[".swift"],
    test_frameworks=[
        TestFramework(
            name="XCTest",
            command="swift test",
            install_command="",  # Part of Swift toolchain
            file_pattern="Tests/**/*.swift",
            description="Apple's testing framework for Swift",
            url="https://developer.apple.com/documentation/xctest",
            config_file="Package.swift"
        ),
        TestFramework(
            name="Quick",
            command="swift test",
            install_command="",  # Add via Swift Package Manager
            file_pattern="Tests/**/*Spec.swift",
            description="BDD testing framework for Swift",
            url="https://github.com/Quick/Quick"
        ),
        TestFramework(
            name="Nimble",
            command="swift test",
            install_command="",  # Add via Swift Package Manager
            file_pattern="Tests/**/*.swift",
            description="Matcher framework for Swift (works with Quick)",
            url="https://github.com/Quick/Nimble"
        ),
    ],
    debug_tools=[
        DebugTool(
            name="LLDB",
            command="lldb",
            install_command="",  # Part of Xcode/Swift toolchain
            description="LLVM debugger for Swift",
            url="https://lldb.llvm.org/",
            vscode_extension="vadimcn.vscode-lldb"
        ),
        DebugTool(
            name="Xcode Debugger",
            command="",  # Integrated in Xcode
            install_command="",  # Part of Xcode
            description="Xcode's integrated debugger",
            url="https://developer.apple.com/xcode/"
        ),
    ],
    linters=[
        Linter(name="SwiftLint", command="swiftlint",
               install_command="brew install swiftlint",
               description="Swift style and conventions enforcer",
               url="https://github.com/realm/SwiftLint",
               config_file=".swiftlint.yml"),
        Linter(name="SwiftFormat", command="swiftformat --lint",
               install_command="brew install swiftformat",
               description="Swift code formatter",
               url="https://github.com/nicklockwood/SwiftFormat",
               config_file=".swiftformat"),
        Linter(name="swift-format", command="swift-format lint",
               install_command="brew install swift-format",
               description="Apple's official Swift formatter",
               url="https://github.com/apple/swift-format"),
    ]
)


# ============================================================================
# Kotlin Tools
# ============================================================================
KOTLIN_TOOLS = LanguageTools(
    language=LanguageId.KOTLIN,
    file_extensions=[".kt", ".kts"],
    test_frameworks=[
        TestFramework(
            name="JUnit 5",
            command="./gradlew test",
            install_command="",  # Add via Gradle/Maven
            file_pattern="src/test/**/*Test.kt",
            description="JUnit 5 testing framework for Kotlin",
            url="https://junit.org/junit5/",
            config_file="build.gradle.kts"
        ),
        TestFramework(
            name="Kotest",
            command="./gradlew test",
            install_command="",  # Add via Gradle
            file_pattern="src/test/**/*Test.kt",
            description="Flexible and comprehensive testing framework for Kotlin",
            url="https://kotest.io/"
        ),
        TestFramework(
            name="Spek",
            command="./gradlew test",
            install_command="",  # Add via Gradle
            file_pattern="src/test/**/*Spec.kt",
            description="BDD-style specification framework for Kotlin",
            url="https://www.spekframework.org/"
        ),
        TestFramework(
            name="MockK",
            command="./gradlew test",
            install_command="",  # Add via Gradle
            file_pattern="src/test/**/*.kt",
            description="Mocking library for Kotlin",
            url="https://mockk.io/"
        ),
    ],
    debug_tools=[
        DebugTool(
            name="Kotlin Debugger (IntelliJ)",
            command="",  # Integrated in IDE
            install_command="",  # Part of IntelliJ IDEA
            description="IntelliJ IDEA's integrated debugger for Kotlin",
            url="https://www.jetbrains.com/idea/",
            vscode_extension="fwcd.kotlin"
        ),
        DebugTool(
            name="JDB",
            command="jdb",
            install_command="",  # Part of JDK
            description="Java Debugger - works with Kotlin bytecode",
            url="https://docs.oracle.com/javase/8/docs/technotes/tools/windows/jdb.html"
        ),
        DebugTool(
            name="Kotlin Debug Adapter",
            command="kotlin-debug-adapter",
            install_command="",  # Part of Kotlin extension
            description="Debug Adapter Protocol implementation for Kotlin",
            url="https://github.com/fwcd/kotlin-debug-adapter",
            vscode_extension="fwcd.kotlin"
        ),
    ],
    linters=[
        Linter(
            name="ktlint",
            command="ktlint",
            install_command="brew install ktlint",
            description="Anti-bikeshedding Kotlin linter with built-in formatter",
            url="https://pinterest.github.io/ktlint/",
            config_file=".editorconfig"
        ),
        Linter(
            name="detekt",
            command="./gradlew detekt",
            install_command="",  # Add via Gradle plugin
            description="Static code analysis for Kotlin",
            url="https://detekt.dev/",
            config_file="detekt.yml"
        ),
        Linter(
            name="Diktat",
            command="./gradlew diktatCheck",
            install_command="",  # Add via Gradle plugin
            description="Strict coding standard for Kotlin",
            url="https://diktat.saveourtool.com/",
            config_file="diktat-analysis.yml"
        ),
    ]
)


# ============================================================================
# Language Tools Registry
# ============================================================================

# Registry of all language tools
LANGUAGE_TOOLS_REGISTRY: Dict[LanguageId, LanguageTools] = {
    LanguageId.PYTHON: PYTHON_TOOLS,
    LanguageId.JAVASCRIPT: JAVASCRIPT_TOOLS,
    LanguageId.TYPESCRIPT: TYPESCRIPT_TOOLS,
    LanguageId.RUBY: RUBY_TOOLS,
    LanguageId.GO: GO_TOOLS,
    LanguageId.RUST: RUST_TOOLS,
    LanguageId.JAVA: JAVA_TOOLS,
    LanguageId.CSHARP: CSHARP_TOOLS,
    LanguageId.CPP: CPP_TOOLS,
    LanguageId.C: C_TOOLS,
    LanguageId.PHP: PHP_TOOLS,
    LanguageId.SHELL: SHELL_TOOLS,
    LanguageId.HTML: HTML_TOOLS,
    LanguageId.CSS: CSS_TOOLS,
    LanguageId.JULIA: JULIA_TOOLS,
    LanguageId.SWIFT: SWIFT_TOOLS,
    LanguageId.KOTLIN: KOTLIN_TOOLS,
}

# File extension to language mapping
EXTENSION_TO_LANGUAGE: Dict[str, LanguageId] = {}
for lang_id, tools in LANGUAGE_TOOLS_REGISTRY.items():
    for ext in tools.file_extensions:
        EXTENSION_TO_LANGUAGE[ext] = lang_id


def get_tools_by_language(language: LanguageId) -> Optional[LanguageTools]:
    """Get tooling configuration for a specific language."""
    return LANGUAGE_TOOLS_REGISTRY.get(language)


def get_tools_by_extension(file_extension: str) -> Optional[LanguageTools]:
    """Get tooling configuration based on file extension."""
    if not file_extension.startswith("."):
        file_extension = f".{file_extension}"
    lang = EXTENSION_TO_LANGUAGE.get(file_extension.lower())
    if lang:
        return LANGUAGE_TOOLS_REGISTRY.get(lang)
    return None


def get_all_test_frameworks() -> Dict[LanguageId, List[TestFramework]]:
    """Get all test frameworks grouped by language."""
    return {
        lang_id: tools.test_frameworks
        for lang_id, tools in LANGUAGE_TOOLS_REGISTRY.items()
    }


def get_all_debug_tools() -> Dict[LanguageId, List[DebugTool]]:
    """Get all debug tools grouped by language."""
    return {
        lang_id: tools.debug_tools
        for lang_id, tools in LANGUAGE_TOOLS_REGISTRY.items()
    }


def get_all_linters() -> Dict[LanguageId, List[Linter]]:
    """Get all linters grouped by language."""
    return {
        lang_id: tools.linters
        for lang_id, tools in LANGUAGE_TOOLS_REGISTRY.items()
    }
