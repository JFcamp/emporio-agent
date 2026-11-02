"""Regras puras sobre dados da loja e horário de funcionamento.

Limitação conhecida: feriados não são considerados por opening_status. O manual
trata domingos e feriados como fechado, mas não há calendário de feriados nos
dados; portanto só a regra semanal é aplicada aqui.
"""

from datetime import datetime, timedelta

from emporio.config import STORE_TZ

# Telefone oficial: o manual cita (67) 3321-4500 uma única vez na seção 7, mas
# (67) 3341-4444 aparece no cabeçalho e na seção 1.2 (Dados da Empresa); por
# consistência com os dados cadastrais, adotamos este último como oficial.
STORE = {
    "nome": "Empório da Música",
    "slogan": "Sua música começa aqui.",
    "endereco": "Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, CEP 79202-333",
    "telefone_whatsapp": "(67) 3341-4444",
    "email": "contato@emporiodamusica.com.br",
    "fundacao": 2008,
}

WEEKDAY_NAMES = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]

HOURS: dict[int, tuple[str, str] | None] = {
    0: ("09:00", "18:00"),
    1: ("09:00", "18:00"),
    2: ("09:00", "18:00"),
    3: ("09:00", "18:00"),
    4: ("09:00", "18:00"),
    5: ("09:00", "13:00"),
    6: None,
}

HOURS_TEXT = (
    "Segunda a sexta, 09:00 às 18:00; sábado, 09:00 às 13:00; "
    "domingo e feriados, fechado."
)


def _to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def _next_opening(now: datetime) -> tuple[str, str]:
    # Procura o próximo dia (incluindo hoje mais tarde) com horário de abertura.
    for offset in range(0, 8):
        day = now + timedelta(days=offset)
        hours = HOURS[day.weekday()]
        if hours is None:
            continue
        opens = hours[0]
        if offset == 0 and _to_minutes(opens) <= now.hour * 60 + now.minute:
            # Já passou do horário de abertura de hoje; segue para o próximo dia.
            continue
        if offset == 0:
            label = "hoje"
        elif offset == 1:
            label = "amanhã"
        else:
            label = WEEKDAY_NAMES[day.weekday()]
        return label, opens
    # Nunca deve ocorrer: sempre há um dia útil em uma semana.
    raise RuntimeError("Não há horário de abertura configurado.")


def opening_status(now: datetime | None = None) -> dict:
    now = (now or datetime.now(STORE_TZ)).astimezone(STORE_TZ)
    hours = HOURS[now.weekday()]
    current = now.hour * 60 + now.minute

    if hours is not None:
        opens, closes = hours
        if _to_minutes(opens) <= current < _to_minutes(closes):
            return {"aberta": True, "fecha_as": closes}

    label, opens = _next_opening(now)
    return {"aberta": False, "reabre": f"{label} às {opens}"}
