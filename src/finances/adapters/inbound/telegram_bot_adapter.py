"""Inbound Telegram Bot adapter for personal finance management with interactive keyboards."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, cast

import requests

from src.finances.application.manage_budget_use_case import (
    GetMonthlySummaryUseCase,
    MonthlySummary,
    SetBudgetUseCase,
)
from src.finances.application.register_expense_use_case import RegisterExpenseUseCase
from src.finances.domain.models import ExpenseCategory

logger = logging.getLogger(__name__)

CATEGORY_ICONS: dict[ExpenseCategory, str] = {
    ExpenseCategory.FOOD: "🍔",
    ExpenseCategory.LEISURE: "🎮",
    ExpenseCategory.TRANSPORT: "🚗",
    ExpenseCategory.EDUCATION: "📚",
    ExpenseCategory.ESSENTIALS: "🏠",
    ExpenseCategory.INVESTMENT: "📈",
    ExpenseCategory.HEALTH: "💊",
}


class TelegramFinanceBotAdapter:
    """Handles bidirectional Telegram interactions for expenses and budgets."""

    def __init__(
        self,
        bot_token: str,
        allowed_chat_id: str | int,
        register_expense_use_case: RegisterExpenseUseCase,
        set_budget_use_case: SetBudgetUseCase,
        get_summary_use_case: GetMonthlySummaryUseCase,
        session: requests.Session | None = None,
    ) -> None:
        """Initialize adapter with credentials, use cases, and HTTP session."""
        self._token = str(bot_token).strip()
        self._allowed_chat_id = str(allowed_chat_id).strip()
        self._register_expense_use_case = register_expense_use_case
        self._set_budget_use_case = set_budget_use_case
        self._get_summary_use_case = get_summary_use_case
        self._session = session or requests.Session()
        self._base_url = f"https://api.telegram.org/bot{self._token}"

        self._user_state: dict[str, str] = {}
        self._selected_category: dict[str, ExpenseCategory] = {}

    def send_message(
        self, chat_id: str | int, text: str, reply_markup: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send message via Telegram Bot API."""
        payload: dict[str, Any] = {
            "chat_id": str(chat_id),
            "text": text,
            "parse_mode": "HTML",
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        resp = self._session.post(f"{self._base_url}/sendMessage", json=payload, timeout=10)
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    def answer_callback_query(
        self, callback_query_id: str, text: str | None = None
    ) -> dict[str, Any]:
        """Acknowledge a Telegram button click callback."""
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        resp = self._session.post(f"{self._base_url}/answerCallbackQuery", json=payload, timeout=10)
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    def get_updates(self, offset: int | None = None, timeout: int = 10) -> list[dict[str, Any]]:
        """Fetch incoming updates via long-polling."""
        payload: dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            payload["offset"] = offset
        resp = self._session.post(f"{self._base_url}/getUpdates", json=payload, timeout=timeout + 5)
        resp.raise_for_status()
        data = cast(dict[str, Any], resp.json())
        return cast(list[dict[str, Any]], data.get("result", []))

    def process_update(self, update: dict[str, Any]) -> None:
        """Route an update to button callback or text message handler."""
        if "callback_query" in update:
            self._handle_callback_query(update["callback_query"])
        elif "message" in update:
            self._handle_message(update["message"])

    def _is_authorized(self, sender_id: str | int) -> bool:
        """Validate if sender matches configured allowed chat ID."""
        return str(sender_id).strip() == self._allowed_chat_id

    def _handle_callback_query(self, query: dict[str, Any]) -> None:
        """Process inline keyboard button actions."""
        query_id = query.get("id", "")
        sender_id = str(query.get("from", {}).get("id", ""))
        chat_id = str(query.get("message", {}).get("chat", {}).get("id", ""))
        data = query.get("data", "")

        if not self._is_authorized(sender_id):
            if query_id:
                self.answer_callback_query(query_id, text="Acesso não autorizado.")
            return

        if query_id:
            self.answer_callback_query(query_id)

        if data == "menu:main":
            self._send_main_menu(chat_id)
        elif data == "menu:expense":
            self._send_category_selection(chat_id, action="exp")
        elif data == "menu:budget":
            self._send_category_selection(chat_id, action="bud")
        elif data == "menu:summary":
            self._send_monthly_summary(chat_id)
        elif data.startswith("exp_cat:"):
            cat_name = data.split(":", 1)[1]
            category = ExpenseCategory[cat_name]
            self._user_state[chat_id] = "AWAITING_EXPENSE_INPUT"
            self._selected_category[chat_id] = category
            icon = CATEGORY_ICONS.get(category, "🏷️")
            self.send_message(
                chat_id,
                f"Categoria selecionada: <b>{icon} {category.value}</b>\n\n"
                f"Envie o valor e a descrição (ex: <code>45.50 Almoço</code>).\n\n"
                f"<i>Envie /cancelar para voltar.</i>",
            )
        elif data.startswith("bud_cat:"):
            cat_name = data.split(":", 1)[1]
            category = ExpenseCategory[cat_name]
            self._user_state[chat_id] = "AWAITING_BUDGET_INPUT"
            self._selected_category[chat_id] = category
            icon = CATEGORY_ICONS.get(category, "🏷️")
            self.send_message(
                chat_id,
                f"Categoria selecionada: <b>{icon} {category.value}</b>\n\n"
                f"Envie o teto para este mês (ex: <code>500</code> ou <code>450.00</code>).\n\n"
                f"<i>Envie /cancelar para voltar.</i>",
            )

    def _handle_message(self, message: dict[str, Any]) -> None:
        """Process incoming text messages and commands."""
        sender_id = str(message.get("from", {}).get("id", ""))
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = str(message.get("text", "")).strip()

        if not self._is_authorized(sender_id):
            self.send_message(chat_id, "⛔ <b>Acesso não autorizado.</b>")
            return

        if not text:
            return

        command = text.split()[0].lower()

        if command in ("/start", "/menu", "/ajuda"):
            self._user_state.pop(chat_id, None)
            self._selected_category.pop(chat_id, None)
            self._send_main_menu(chat_id)
            return

        if command in ("/cancelar", "cancelar"):
            self._user_state.pop(chat_id, None)
            self._selected_category.pop(chat_id, None)
            self.send_message(chat_id, "✖️ <b>Operação cancelada.</b>")
            self._send_main_menu(chat_id)
            return

        if command in ("/gasto", "/registrar"):
            self._send_category_selection(chat_id, action="exp")
            return

        if command in ("/resumo", "/balanco"):
            self._send_monthly_summary(chat_id)
            return

        if command in ("/teto", "/orcamento"):
            self._send_category_selection(chat_id, action="bud")
            return

        state = self._user_state.get(chat_id)

        if state == "AWAITING_EXPENSE_INPUT":
            self._process_expense_input(chat_id, text)
        elif state == "AWAITING_BUDGET_INPUT":
            self._process_budget_input(chat_id, text)
        else:
            self.send_message(
                chat_id,
                "Comando não reconhecido. Use os botões abaixo ou digite /menu.",
                reply_markup=self._main_menu_keyboard(),
            )

    def _process_expense_input(self, chat_id: str, text: str) -> None:
        """Parse value and description, then invoke RegisterExpenseUseCase."""
        category = self._selected_category.get(chat_id)
        if category is None:
            self._user_state.pop(chat_id, None)
            self._send_main_menu(chat_id)
            return

        parts = text.split(maxsplit=1)
        raw_amount = parts[0].replace(",", ".")
        description = parts[1].strip() if len(parts) > 1 else category.value

        try:
            amount = float(raw_amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            self.send_message(
                chat_id,
                "⚠️ Valor inválido. Digite um número positivo (ex: <code>45.50 Cinema</code>):",
            )
            return

        month = datetime.now().strftime("%Y-%m")

        try:
            result = self._register_expense_use_case.execute(
                amount=amount,
                category=category,
                description=description,
                month=month,
            )
        except Exception as e:
            logger.exception("Failed to register expense via bot")
            self.send_message(chat_id, f"⚠️ Erro ao registrar gasto: {e}")
            return

        self._user_state.pop(chat_id, None)
        self._selected_category.pop(chat_id, None)

        icon = CATEGORY_ICONS.get(category, "🏷️")
        reply = [
            "✅ <b>Gasto registrado com sucesso!</b>",
            f"💸 <b>Valor:</b> R$ {amount:.2f}",
            f"🏷️ <b>Categoria:</b> {icon} {category.value} ({description})",
            f"📅 <b>Mês:</b> {month}",
            f"📊 <b>Total gasto na categoria:</b> R$ {result.total_spent:.2f}",
        ]

        if result.remaining is not None and result.usage_pct is not None:
            reply.append(
                f"📉 <b>Saldo restante:</b> R$ {result.remaining:.2f} "
                f"({result.usage_pct:.1f}% usado)"
            )

        if result.exceeded:
            reply.append(
                f"\n🚨 <b>ATENÇÃO:</b> Você ultrapassou o teto de {category.value}! "
                f"Estouro: R$ {abs(result.remaining or 0):.2f}"
            )
        elif result.warning:
            reply.append(
                f"\n⚠️ <b>ALERTA:</b> Faixa de alerta (>= 80%) atingida para {category.value}!"
            )

        self.send_message(chat_id, "\n".join(reply), reply_markup=self._main_menu_keyboard())

    def _process_budget_input(self, chat_id: str, text: str) -> None:
        """Parse budget limit, then invoke SetBudgetUseCase."""
        category = self._selected_category.get(chat_id)
        if category is None:
            self._user_state.pop(chat_id, None)
            self._send_main_menu(chat_id)
            return

        raw_amount = text.strip().replace(",", ".")
        try:
            amount = float(raw_amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            self.send_message(
                chat_id,
                "⚠️ Valor inválido. Digite um número positivo para o teto (ex: <code>500</code>):",
            )
            return

        month = datetime.now().strftime("%Y-%m")

        try:
            budget = self._set_budget_use_case.execute(
                category=category,
                amount=amount,
                month=month,
            )
        except Exception as e:
            logger.exception("Failed to set budget via bot")
            self.send_message(chat_id, f"⚠️ Erro ao salvar teto: {e}")
            return

        self._user_state.pop(chat_id, None)
        self._selected_category.pop(chat_id, None)

        icon = CATEGORY_ICONS.get(category, "🏷️")
        reply = (
            f"🎯 <b>Teto configurado com sucesso!</b>\n\n"
            f"🏷️ <b>Categoria:</b> {icon} {category.value}\n"
            f"💰 <b>Limite para {month}:</b> R$ {budget.allocated_amount:.2f}"
        )
        self.send_message(chat_id, reply, reply_markup=self._main_menu_keyboard())

    def _send_monthly_summary(self, chat_id: str) -> None:
        """Fetch and send formatted monthly spending panorama."""
        month = datetime.now().strftime("%Y-%m")
        summary: MonthlySummary = self._get_summary_use_case.execute(month)

        lines = [f"📊 <b>Panorama Financeiro — {month}</b>\n"]

        for item in summary.categories:
            icon = CATEGORY_ICONS.get(item.category, "•")
            status = ""
            if item.is_exceeded:
                status = " 🚨"
            elif item.is_warning:
                status = " ⚠️"

            if (
                item.allocated is not None
                and item.usage_pct is not None
                and item.remaining is not None
            ):
                lines.append(
                    f"{icon} <b>{item.category.value}:</b> R$ {item.spent:.2f} / "
                    f"R$ {item.allocated:.2f} ({item.usage_pct:.1f}%){status}\n"
                    f"   <i>Resta: R$ {item.remaining:.2f}</i>"
                )
            else:
                lines.append(
                    f"{icon} <b>{item.category.value}:</b> R$ {item.spent:.2f} <i>(sem teto)</i>"
                )

        lines.append(f"\n💵 <b>Total Gasto no Mês:</b> R$ {summary.total_spent:.2f}")

        self.send_message(chat_id, "\n".join(lines), reply_markup=self._main_menu_keyboard())

    def _send_main_menu(self, chat_id: str) -> None:
        """Send the top-level menu with interactive buttons."""
        text = "🤖 <b>Surge Finanças</b>\n\nO que você deseja fazer agora?"
        self.send_message(chat_id, text, reply_markup=self._main_menu_keyboard())

    def _send_category_selection(self, chat_id: str, action: str) -> None:
        """Send keyboard containing all expense categories."""
        action_name = "registrar gasto" if action == "exp" else "definir teto"
        text = f"Selecione a categoria para <b>{action_name}</b>:"
        keyboard = self._category_keyboard(prefix=f"{action}_cat")
        self.send_message(chat_id, text, reply_markup=keyboard)

    @staticmethod
    def _main_menu_keyboard() -> dict[str, Any]:
        """Construct inline keyboard for main navigation."""
        return {
            "inline_keyboard": [
                [{"text": "➕ Registrar Gasto", "callback_data": "menu:expense"}],
                [{"text": "📊 Resumo do Mês", "callback_data": "menu:summary"}],
                [{"text": "🎯 Definir Teto", "callback_data": "menu:budget"}],
            ]
        }

    @staticmethod
    def _category_keyboard(prefix: str) -> dict[str, Any]:
        """Construct inline keyboard with category options."""
        buttons: list[list[dict[str, str]]] = []
        row: list[dict[str, str]] = []

        for category in ExpenseCategory:
            icon = CATEGORY_ICONS.get(category, "🏷️")
            btn = {
                "text": f"{icon} {category.value}",
                "callback_data": f"{prefix}:{category.name}",
            }
            row.append(btn)
            if len(row) == 2:
                buttons.append(row)
                row = []

        if row:
            buttons.append(row)

        buttons.append([{"text": "🔙 Voltar ao Menu", "callback_data": "menu:main"}])
        return {"inline_keyboard": buttons}

    def start_polling(self, stop_event: threading.Event | None = None) -> None:
        """Continuously poll Telegram Bot API for updates."""
        logger.info("Starting Telegram bot polling for chat ID: %s", self._allowed_chat_id)
        offset: int | None = None

        while stop_event is None or not stop_event.is_set():
            try:
                updates = self.get_updates(offset=offset, timeout=10)
                for update in updates:
                    offset = update["update_id"] + 1
                    self.process_update(update)
            except Exception:
                logger.exception("Error during Telegram polling loop")
                time.sleep(2)
