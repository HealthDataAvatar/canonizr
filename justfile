up:
    ./bin/up.sh

down:
    ./bin/down.sh

convert FILE:
    ./cli/canonizr convert {{FILE}}

setup:
    ./bin/setup.sh

test:
    docker compose --profile test --profile captioning up --build --abort-on-container-exit || true

report:
    @echo "\n=== Test Results ==="
    @if grep -q 'failures="[1-9]' reports/gateway/junit.xml 2>/dev/null; then \
        echo "❌ Gateway tests FAILED"; \
        grep -o 'failures="[0-9]*"' reports/gateway/junit.xml | head -1 | sed 's/failures="//;s/"//'; \
        echo "\nView detailed report: open reports/gateway/report.html"; \
        exit 1; \
    else \
        echo "✅ Gateway tests PASSED"; \
        echo "\nView detailed report: open reports/gateway/report.html"; \
    fi

web:
    cd web && npm run dev

lint:
    uv run ruff check