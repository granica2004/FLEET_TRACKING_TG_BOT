"""Вебхук остаётся на боте, когда контейнер останавливается."""

import ast
import importlib.util
from pathlib import Path

# Грузим модуль напрямую: пакет src.services при импорте читает настройки,
# и ранний импорт кэширует их до того, как соседние тесты зададут окружение.
_spec = importlib.util.spec_from_file_location(
    "webhook_bind",
    Path("src/services/webhook_bind.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
bind_webhook = _mod.bind_webhook
reassert_webhook = _mod.reassert_webhook
webhook_url_for = _mod.webhook_url_for


class _Info:
    def __init__(self, url):
        self.url = url
        self.pending_update_count = 0
        self.last_error_message = None


class _Bot:
    def __init__(self):
        self.set_calls = []
        self.deleted = 0

    async def set_webhook(self, url):
        self.set_calls.append(url)

    async def get_webhook_info(self):
        return _Info(self.set_calls[-1] if self.set_calls else "")

    async def delete_webhook(self, **kwargs):
        self.deleted += 1


def test_webhook_url_strips_slash():
    assert webhook_url_for("https://bot.example/") == "https://bot.example/webhook/telegram"


async def test_bind_sets_webhook_and_does_not_delete():
    bot = _Bot()
    info = await bind_webhook(bot, "https://bot.example")
    assert bot.set_calls == ["https://bot.example/webhook/telegram"]
    assert bot.deleted == 0
    assert info.url == "https://bot.example/webhook/telegram"


async def test_reassert_binds_again_after_delay():
    bot = _Bot()
    await reassert_webhook(bot, "https://bot.example", delays=(0,))
    assert bot.set_calls == ["https://bot.example/webhook/telegram"]


def test_production_shutdown_does_not_drop_webhook():
    source = Path("src/main.py").read_text()
    tree = ast.parse(source)
    lifespan = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "lifespan"
    )
    # Код после yield — остановка. Там не должно быть delete_webhook.
    after = False
    for stmt in lifespan.body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Yield):
            after = True
            continue
        if not after:
            continue
        chunk = ast.get_source_segment(source, stmt) or ""
        assert "delete_webhook" not in chunk
